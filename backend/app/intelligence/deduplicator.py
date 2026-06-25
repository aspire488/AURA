from __future__ import annotations

import hashlib
import re
import unicodedata


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove punctuation."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    """SHA-256 of normalized content. Used for exact dedup."""
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


def is_duplicate(
    new_text: str,
    existing_hashes: set[str],
    existing_embeddings: list[tuple[str, list[float]]] | None = None,
    new_embedding: list[float] | None = None,
    similarity_threshold: float = 0.99,
) -> tuple[bool, str]:
    """Check if content is a duplicate.

    Returns (is_dup, reason).
    Checks: exact hash match, then embedding cosine similarity.
    ponytail: no FAISS, no vector DB — brute-force cosine for small sets is fine.
    """
    norm_hash = content_hash(new_text)

    # Exact / normalized duplicate
    if norm_hash in existing_hashes:
        return True, "duplicate"

    # Embedding similarity check
    if existing_embeddings and new_embedding:
        best_sim = 0.0
        for _, emb in existing_embeddings:
            sim = _cosine_similarity(new_embedding, emb)
            best_sim = max(best_sim, sim)
            if best_sim >= similarity_threshold:
                return True, "duplicate"

    return False, ""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure Python cosine similarity. ponytail: no numpy."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
