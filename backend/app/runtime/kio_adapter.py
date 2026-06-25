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

logger = logging.getLogger(__name__)


@dataclass
class KIORequest:
    query: str
    session_id: str = ""
    max_tokens: int = 2000


@dataclass
class KIOResponse:
    intent: str
    query_type: str
    answer: str
    citations: list[str]
    warnings: list[str]
    session_id: str
    latency_ms: float


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
            await sessions.append_message(session_id, "user", request.query)
        elif not session_id and sessions:
            session = await sessions.get_or_create()
            session_id = session.session_id
            await sessions.append_message(session_id, "user", request.query)

        # 1. Intent
        intent = detect_intent(request.query)

        # 2. Query type
        query_type = classify_query(request.query)

        # 3. Embed
        embeddings = await provider.embed([request.query])
        embedding = embeddings[0]

        # 4. Retrieve
        results = hybrid_search(memory._chroma, request.query, embedding, top_k=10)

        # 5. Context
        context = build_context(query=request.query, query_type=query_type, results=results, max_tokens=request.max_tokens)
        metrics.record_retrieval(
            score=sum(c.score for c in context.chunks) / max(len(context.chunks), 1),
            latency_ms=0,
            hit=len(context.chunks) > 0,
        )

        # 6. Build prompt with session history
        prompt = build_prompt(request.query, context, intent)
        if history:
            history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-10:])
            prompt.user_prompt = f"Conversation history:\n{history_text}\n\n{prompt.user_prompt}"

        # 7. Generate
        try:
            llm_response = await provider.generate(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
            )
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            latency = round((time.perf_counter() - start) * 1000, 2)
            metrics.record_reasoning(latency, 0, 0, 0, False)
            return KIOResponse(
                intent=intent, query_type=query_type,
                answer=f"[LLM unavailable] {len(context.chunks)} chunks retrieved. Error: {e}",
                citations=prompt.citations, warnings=[f"Provider error: {e}"],
                session_id=session_id, latency_ms=latency,
            )

        # 8. Validate
        validation = validate_response(llm_response.text, context.context, request.query)
        latency = round((time.perf_counter() - start) * 1000, 2)

        metrics.record_reasoning(latency, llm_response.latency_ms, llm_response.prompt_tokens, llm_response.completion_tokens, validation.valid)

        answer = validation.corrected_text or llm_response.text

        # Store assistant response in session
        if sessions and session_id:
            await sessions.append_message(session_id, "assistant", answer)

        return KIOResponse(
            intent=intent, query_type=query_type, answer=answer,
            citations=prompt.citations, warnings=validation.warnings,
            session_id=session_id, latency_ms=latency,
        )


# ponytail: module-level, lazy init services on first use.
kio = KIOAdapter()
