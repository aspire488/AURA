from __future__ import annotations

import re


def classify_memory(role: str, content: str) -> str:
    """Deterministic memory classification.

    ponytail: simple rules, no ML.
    LONG_TERM: factual, personal, technical — worth remembering.
    EPHEMERAL: greetings, filler, too short to matter.
    SHORT_TERM: everything in between.
    """
    text = content.strip()
    lower = text.lower()
    word_count = len(text.split())

    # Very short or greeting-like = ephemeral
    if word_count <= 2:
        return "EPHEMERAL"
    ephemeral_patterns = (
        "hello", "hi", "hey", "ok", "okay", "thanks", "thank you",
        "bye", "goodbye", "sure", "yes", "no", "got it", "understood",
        "continue", "go on", "next", "cool", "great", "nice", "awesome",
        "right", "correct", "perfect", "exactly", "absolutely",
    )
    if lower in ephemeral_patterns or (word_count <= 3 and lower.rstrip("!.?") in ephemeral_patterns):
        return "EPHEMERAL"

    # Factual / personal / technical = long term
    long_term_signals = [
        r"\b(my|i have|i am|i'm|our|we have|we are)\b",        # personal facts
        r"\b(laptop|desktop|server|machine|computer|phone)\b",  # hardware
        r"\b(password|username|api.?key|token|secret)\b",       # credentials/config
        r"\b(project|repo|codebase|codebase|code)\b",           # project knowledge
        r"\b(lesson|learned|realized|discovered|found out)\b",  # lessons
        r"\b(never|always|must|must not|should|should not)\b",  # rules/preferences
        r"\b(version|release|deploy|production|staging)\b",     # technical state
        r"\d+gb|\d+tb|\d+mb|\bcpu\b|\bram\b|\bssd\b",         # specs
    ]
    long_term_hits = sum(1 for p in long_term_signals if re.search(p, lower))
    if long_term_hits >= 2 or (long_term_hits >= 1 and word_count > 15):
        return "LONG_TERM"
    if "```" in text or re.search(r"\b(def |class |import |function )\b", text):
        return "LONG_TERM"

    return "SHORT_TERM"
