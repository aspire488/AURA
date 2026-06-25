from __future__ import annotations

import re


def detect_intent(query: str) -> str:
    """Deterministic intent classification.

    ponytail: regex + keyword matching, no ML.
    Order matters — most specific first.
    """
    q = query.strip()
    lower = q.lower()

    # Command: starts with / or imperative verb
    if q.startswith("/"):
        return "command"
    command_verbs = (
        "run", "execute", "deploy", "start", "stop", "restart", "install",
        "create", "delete", "remove", "update", "set", "config", "show",
    )
    first_word = lower.split()[0] if lower.split() else ""
    if first_word in command_verbs:
        return "command"

    # Summarize: explicit request for summary
    summarize_patterns = (
        r"\bsummar(?:ize|ise|y|ies)\b", r"\boverview\b", r"\brecap\b",
        r"\btldr?\b", r"\btoo long\b", r"\bbrief(?:ly)?\b",
    )
    if any(re.search(p, lower) for p in summarize_patterns):
        return "summarize"

    # Recall: asking about past conversations/memories
    recall_patterns = (
        r"\bremember\b", r"\bdid i (?:say|tell|mention|ask)\b",
        r"\bwhat did (?:i|we|you)\b", r"\bprevious(?:ly)?\b",
        r"\bbefore\b", r"\blast time\b", r"\brecall\b",
    )
    if any(re.search(p, lower) for p in recall_patterns):
        return "recall"

    # Search: explicit search request
    search_patterns = (
        r"\bsearch\b", r"\bfind\b", r"\blook(?:ing)? (?:for|up)\b",
        r"\bwhere (?:is|are|did)\b", r"\bquery\b",
    )
    if any(re.search(p, lower) for p in search_patterns):
        return "search"

    # Question: ends with ? or starts with question words
    if q.endswith("?"):
        return "question"
    question_starters = (
        "what", "how", "why", "when", "where", "who", "which",
        "can", "could", "would", "should", "is", "are", "do", "does",
        "did", "will", "have", "has",
    )
    if first_word in question_starters:
        return "question"

    # Conversation: greeting or chitchat
    conv_patterns = (
        r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bthanks\b",
        r"\bhow are you\b", r"\bgood morning\b", r"\bbye\b",
    )
    if any(re.search(p, lower) for p in conv_patterns):
        return "conversation"

    return "unknown"
