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



