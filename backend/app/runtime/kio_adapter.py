from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

from app.intelligence.context_builder import build_context
from app.intelligence.intent import detect_intent
from app.intelligence.metrics import metrics
from app.intelligence.prompt_builder import build_prompt
from app.intelligence.query_planner import classify_query
from app.intelligence.retriever import hybrid_search
from app.intelligence.validator import validate_response
from app.runtime.memory_adapter import MemoryAdapter
from app.runtime.provider_adapter import ProviderAdapter
from app.runtime.session_manager import SessionManager
from app.runtime.tool_planner import plan_tool, extract_tool_args, classify_plan, create_plan
from app.runtime.tool_registry import registry
from app.runtime.agent_state import get_agent_state
from app.runtime.execution_engine import engine as execution_engine

logger = logging.getLogger(__name__)


@dataclass
class KIORequest:
    query: str
    session_id: str = ""
    max_tokens: int = 2000
    task_id: str = ""  # for resume
    start_from: int = 0  # step index to resume from


@dataclass
class KIOResponse:
    intent: str
    query_type: str
    answer: str
    citations: list[str]
    warnings: list[str]
    session_id: str
    latency_ms: float
    execution_trace: list[dict] = field(default_factory=list)


class KIOAdapter:
    """Orchestration layer. No HTTP knowledge.

    ponytail: delegates to existing modules, adds session context.
    """

    def __init__(
        self,
        memory: MemoryAdapter | None = None,
        provider: ProviderAdapter | None = None,
        sessions: SessionManager | None = None,
    ):
        self._memory = memory
        self._provider = provider
        self._sessions = sessions

    def _get_memory(self) -> MemoryAdapter:
        return self._memory or MemoryAdapter()

    def _get_provider(self) -> ProviderAdapter:
        return self._provider or ProviderAdapter()

    def _get_sessions(self) -> SessionManager | None:
        return self._sessions

    async def _llm_step(
        self,
        query: str,
        intent: str,
        execution_context: str = "",
        history_text: str = "",
        max_tokens: int = 2000,
    ) -> tuple[str, list[str], list[str]]:
        """Run the full LLM pipeline for a single step. Returns (answer, citations, warnings)."""
        provider = self._get_provider()
        memory = self._get_memory()

        embeddings = await provider.embed([query])
        embedding = embeddings[0]
        results = hybrid_search(memory._chroma, query, embedding, top_k=10)
        query_type = classify_query(query)
        context = build_context(query=query, query_type=query_type, results=results, max_tokens=max_tokens)
        metrics.record_retrieval(
            score=sum(c.score for c in context.chunks) / max(len(context.chunks), 1),
            latency_ms=0,
            hit=len(context.chunks) > 0,
        )

        prompt = build_prompt(
            query, context, intent,
            execution_context=execution_context,
            history_text=history_text,
        )

        try:
            llm_response = await provider.generate(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return f"[LLM unavailable] {len(context.chunks)} chunks retrieved. Error: {e}", prompt.citations, [f"Provider error: {e}"]

        validation = validate_response(llm_response.text, context.context, query)
        metrics.record_reasoning(0, llm_response.latency_ms, llm_response.prompt_tokens, llm_response.completion_tokens, validation.valid)
        answer = validation.corrected_text or llm_response.text
        return answer, prompt.citations, validation.warnings

    async def process_request(self, request: KIORequest) -> KIOResponse:
        start = time.perf_counter()
        memory = self._get_memory()
        provider = self._get_provider()

        # Session context
        session_id = request.session_id
        sessions = self._get_sessions()
        history: list[dict] = []
        if sessions and session_id:
            session = await sessions.get_or_create(session_id)
            session_id = session.session_id
            history = session.history
            if not request.task_id:  # don't re-append on resume
                await sessions.append_message(session_id, "user", request.query)
        elif not session_id and sessions:
            session = await sessions.get_or_create()
            session_id = session.session_id
            await sessions.append_message(session_id, "user", request.query)

        # 1. Intent
        intent = detect_intent(request.query)

        # 2. Query type
        query_type = classify_query(request.query)

        # 3. Plan type
        plan_type = classify_plan(request.query)

        # 4. Multi-step: route through execution engine
        if plan_type == "multi":
            return await self._execute_multi_step(request, session_id, intent, query_type, history, start)

        # 5. Single-step: tool check — if a tool matches, execute and return early
        tool_name = plan_tool(request.query)
        if tool_name:
            try:
                if session_id:
                    try:
                        agent = get_agent_state()
                        await agent.set_active_tools(session_id, [tool_name])
                    except Exception:
                        pass
                kwargs = extract_tool_args(tool_name, request.query)
                result = await registry.execute(tool_name, **kwargs)
                if session_id:
                    try:
                        await agent.set_active_tools(session_id, [])
                    except Exception:
                        pass
                latency = round((time.perf_counter() - start) * 1000, 2)
                if sessions and session_id:
                    await sessions.append_message(session_id, "assistant", str(result))
                return KIOResponse(
                    intent=intent, query_type=query_type, answer=str(result),
                    citations=[], warnings=[], session_id=session_id, latency_ms=latency,
                )
            except Exception as e:
                logger.warning("Tool %s failed: %s, falling through to LLM", tool_name, e)

        # 6. Full LLM pipeline
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:]) if history else ""
        answer, citations, warnings = await self._llm_step(request.query, intent, history_text=history_text, max_tokens=request.max_tokens)

        latency = round((time.perf_counter() - start) * 1000, 2)
        if sessions and session_id:
            await sessions.append_message(session_id, "assistant", answer)

        return KIOResponse(
            intent=intent, query_type=query_type, answer=answer,
            citations=citations, warnings=warnings,
            session_id=session_id, latency_ms=latency,
        )

    async def _execute_multi_step(
        self,
        request: KIORequest,
        session_id: str,
        intent: str,
        query_type: str,
        history: list[dict],
        start: float,
    ) -> KIOResponse:
        """Execute multi-step plan through the execution engine."""
        plan = create_plan(request.query)

        # Build history context for the first LLM step
        history_text = ""
        if history:
            history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])

        # LLM callback for non-tool steps
        async def llm_callback(step_query: str, context_text: str) -> str:
            answer, _, _ = await self._llm_step(step_query, intent, execution_context=context_text, history_text=history_text)
            return answer

        result = await execution_engine.execute(
            plan,
            start_from=request.start_from,
            llm_callback=llm_callback,
        )

        latency = round((time.perf_counter() - start) * 1000, 2)
        metrics.record_execution(len(plan.steps), latency, result.success)

        if sessions and session_id:
            await sessions.append_message(session_id, "assistant", result.answer)

        # Collect citations from tool steps
        citations = [s.query for s in result.steps if s.tool_name and s.status == "completed"]

        return KIOResponse(
            intent=intent, query_type=query_type, answer=result.answer,
            citations=citations, warnings=[],
            session_id=session_id, latency_ms=latency,
            execution_trace=result.trace,
        )


# ponytail: module-level, lazy init services on first use.
kio = KIOAdapter()
