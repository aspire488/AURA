from __future__ import annotations


def classify_query(query: str) -> str:
    """Deterministic query classification.

    ponytail: simple heuristics, no ML, no embeddings.
    - Quoted phrases or explicit exact-match markers → keyword
    - Very short or generic → semantic
    - Everything else → hybrid
    """
    q = query.strip()

    # Explicit keyword signals
    if '"' in q or "'" in q:
        return "keyword"
    if q.startswith("exact:") or q.startswith('""'):
        return "keyword"

    words = q.split()
    if len(words) <= 2:
        return "semantic"

    return "hybrid"
