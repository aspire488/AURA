from __future__ import annotations

import re
from datetime import datetime, timezone


def score_importance(role: str, content: str, timestamp: str = "", retrieval_count: int = 0) -> int:
    """Deterministic importance score 0–100.

    ponytail: pure heuristics, no ML, no embeddings.
    Weights sum to ~100 for typical important content.
    """
    score = 0
    text = content.strip()
    lower = text.lower()

    # Base score by role
    if role == "user":
        score += 15
    elif role == "assistant":
        score += 10

    # Length signal — longer = more substantive
    length = len(text)
    if length > 500:
        score += 20
    elif length > 200:
        score += 15
    elif length > 50:
        score += 10
    elif length > 10:
        score += 5

    # Question = someone needs an answer
    if "?" in text or lower.startswith(("what", "how", "why", "when", "where", "who", "can", "is", "do", "does")):
        score += 15

    # Code block = technical knowledge
    if "```" in text or re.search(r"\b(def |class |import |from |function |const |let |var )\b", text):
        score += 15

    # URL = reference material
    if re.search(r"https?://\S+", text):
        score += 10

    # Recency boost — newer is better
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            days = max((datetime.now(tz=timezone.utc) - dt).total_seconds() / 86400, 0)
            if days < 1:
                score += 10
            elif days < 7:
                score += 7
            elif days < 30:
                score += 4
        except (ValueError, TypeError):
            pass

    # Retrieval frequency = useful memory
    if retrieval_count > 10:
        score += 10
    elif retrieval_count > 5:
        score += 7
    elif retrieval_count > 2:
        score += 4

    return min(score, 100)
