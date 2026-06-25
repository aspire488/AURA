from __future__ import annotations

from datetime import datetime, timezone

from app.services.chroma_service import ChromaService


def _recency_score(timestamp: str) -> float:
    """1.0 for now, decays with age. ponytail: simple inverse age."""
    if not timestamp:
        return 0.0
    try:
        dt = datetime.fromisoformat(timestamp)
        days = max((datetime.now(tz=timezone.utc) - dt).total_seconds() / 86400, 0)
        return 1.0 / (1.0 + days * 0.01)
    except (ValueError, TypeError):
        return 0.0


def _dedup_key(item: dict) -> str:
    """Chunk ID is the dedup key across search modes."""
    return item.get("chunk_id", item.get("text", ""))


def hybrid_search(
    chroma: ChromaService,
    query: str,
    embedding: list[float],
    top_k: int = 10,
) -> list[dict]:
    """Semantic + keyword merge with dedup and rerank.

    ponytail: keyword search uses Chroma $contains (native FTS substring).
    No external index, no BM25 lib, no extra infra.
    """
    semantic_results = chroma.query(embedding, top_k=top_k * 2)
    keyword_results = chroma.keyword_search(query, top_k=top_k * 2)

    keyword_ids = {r["chunk_id"] for r in keyword_results}

    seen: dict[str, dict] = {}
    for item in semantic_results + keyword_results:
        key = item["chunk_id"]
        if key in seen:
            # Boost: item appears in both semantic and keyword
            seen[key]["_in_both"] = True
            continue
        seen[key] = {**item, "_in_both": key in keyword_ids}

    scored = []
    for item in seen.values():
        sem = item.get("score", 0.0)
        kw = 1.0 if item.get("_in_both", False) or item["chunk_id"] in keyword_ids else 0.0
        rec = _recency_score(item.get("timestamp", ""))
        final = sem * 0.6 + kw * 0.25 + rec * 0.15
        scored.append({**item, "final_score": round(final, 4)})

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored[:top_k]
