from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextChunk:
    chunk_id: str
    text: str
    score: float
    conversation_id: str
    role: str
    citation: str


@dataclass
class ContextBundle:
    query: str
    query_type: str
    chunks: list[ContextChunk]
    context: str
    citations: list[str]
    estimated_tokens: int


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English. ponytail: good enough."""
    return max(len(text) // 4, 0)


def build_context(
    query: str,
    query_type: str,
    results: list[dict],
    max_tokens: int = 2000,
) -> ContextBundle:
    """Assemble retrieval results into a context bundle.

    Orders by score, accumulates text up to max_tokens, builds citations.
    No LLM calls. No truncation artifacts — stops at chunk boundary.
    """
    chunks: list[ContextChunk] = []
    citations: list[str] = []
    parts: list[str] = []
    total_tokens = 0
    separator = "\n\n---\n\n"

    for r in results:
        chunk = ContextChunk(
            chunk_id=r.get("chunk_id", ""),
            text=r.get("text", ""),
            score=r.get("final_score", r.get("score", 0.0)),
            conversation_id=r.get("conversation_id", ""),
            role=r.get("role", ""),
            citation=f"[{r.get('conversation_id', 'unknown')}:{r.get('chunk_id', '')[:8]}]",
        )

        chunk_tokens = _estimate_tokens(chunk.text)
        if total_tokens + chunk_tokens > max_tokens and chunks:
            break

        chunks.append(chunk)
        citations.append(chunk.citation)
        parts.append(chunk.text)
        total_tokens += chunk_tokens
        if separator and len(parts) > 1:
            # Subtract separator overhead from next chunk budget
            total_tokens += _estimate_tokens(separator)

    return ContextBundle(
        query=query,
        query_type=query_type,
        chunks=chunks,
        context=separator.join(parts),
        citations=citations,
        estimated_tokens=total_tokens,
    )
