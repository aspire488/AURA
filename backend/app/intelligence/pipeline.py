from __future__ import annotations

import time
import logging
from dataclasses import dataclass

from app.core.dependencies import get_chroma
from app.intelligence.context_builder import ContextBundle, build_context
from app.intelligence.intent import detect_intent
from app.intelligence.metrics import metrics
from app.intelligence.provider_gateway import gateway, LLMResponse
from app.intelligence.prompt_builder import PromptBundle, build_prompt
from app.intelligence.query_planner import classify_query
from app.intelligence.retriever import hybrid_search
from app.intelligence.validator import ValidationResult, validate_response
from app.providers.factory import get_provider

logger = logging.getLogger(__name__)


@dataclass
class ReasonResult:
    intent: str
    query_type: str
    answer: str
    citations: list[str]
    warnings: list[str]
    latency_ms: float


async def reason(query: str) -> ReasonResult:
    """Single deterministic pipeline. No loops, no agents."""
    pipeline_start = time.perf_counter()

    # 1. Intent detection
    intent = detect_intent(query)

    # 2. Query planning
    query_type = classify_query(query)

    # 3. Embed query
    provider = get_provider()
    embeddings = await provider.embed([query])
    embedding = embeddings[0]

    # 4. Memory retrieval
    chroma = get_chroma()
    results = hybrid_search(chroma, query, embedding, top_k=10)

    # 5. Context building
    context = build_context(query=query, query_type=query_type, results=results, max_tokens=2000)
    metrics.record_retrieval(
        score=sum(c.score for c in context.chunks) / max(len(context.chunks), 1),
        latency_ms=0,
        hit=len(context.chunks) > 0,
    )

    # 6. Prompt building
    prompt = build_prompt(query, context, intent)

    # 7. Provider call
    try:
        llm_response = await gateway.complete(
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
        )
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        pipeline_latency = round((time.perf_counter() - pipeline_start) * 1000, 2)
        metrics.record_reasoning(
            pipeline_latency_ms=pipeline_latency,
            provider_latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            validation_valid=False,
        )
        return ReasonResult(
            intent=intent,
            query_type=query_type,
            answer=f"[LLM unavailable] Retrieved {len(context.chunks)} relevant chunks. Error: {e}",
            citations=prompt.citations,
            warnings=[f"Provider error: {e}"],
            latency_ms=pipeline_latency,
        )

    # 8. Response validation
    validation = validate_response(llm_response.text, context.context, query)

    pipeline_latency = round((time.perf_counter() - pipeline_start) * 1000, 2)

    metrics.record_reasoning(
        pipeline_latency_ms=pipeline_latency,
        provider_latency_ms=llm_response.latency_ms,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        validation_valid=validation.valid,
    )

    return ReasonResult(
        intent=intent,
        query_type=query_type,
        answer=validation.corrected_text or llm_response.text,
        citations=prompt.citations,
        warnings=validation.warnings,
        latency_ms=pipeline_latency,
    )
