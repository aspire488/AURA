from __future__ import annotations

import re
from collections import Counter


def _extract_keywords(text: str) -> list[str]:
    """Extract top keywords by frequency, skipping stop words."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "because", "but", "and",
        "or", "if", "while", "this", "that", "these", "those", "i", "me",
        "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
        "it", "its", "they", "them", "their", "what", "which", "who", "whom",
        "it's", "don't", "doesn't", "didn't", "won't", "wouldn't", "couldn't",
        "shouldn't", "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't",
        "hadn't", "yes", "no", "ok", "okay", "also", "like", "much", "many",
    }
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    filtered = [w for w in words if w not in stop_words]
    counts = Counter(filtered)
    return [w for w, _ in counts.most_common(5)]


def summarize_conversation(chunks: list[dict]) -> dict:
    """Deterministic conversation summary from chunks.

    ponytail: no LLM. Title = first user message (truncated).
    Summary = first assistant message (truncated).
    Keywords = top frequency words.
    """
    if not chunks:
        return {"title": "", "summary": "", "keywords": [], "message_count": 0}

    user_msgs = [c for c in chunks if c.get("role") == "user"]
    all_msgs = chunks

    # Title: first user message, truncated
    title = ""
    if user_msgs:
        title = user_msgs[0].get("text", "")[:80]

    # Summary: first assistant message or first message, truncated
    summary = ""
    assistant_msgs = [c for c in chunks if c.get("role") == "assistant"]
    if assistant_msgs:
        summary = assistant_msgs[0].get("text", "")[:200]
    elif all_msgs:
        summary = all_msgs[0].get("text", "")[:200]

    # Keywords from all text
    all_text = " ".join(c.get("text", "") for c in all_msgs)
    keywords = _extract_keywords(all_text)

    return {
        "title": title,
        "summary": summary,
        "keywords": keywords,
        "message_count": len(all_msgs),
    }
