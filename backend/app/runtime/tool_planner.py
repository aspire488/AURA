from __future__ import annotations

import re


def plan_tool(query: str) -> str | None:
    """Determine which tool, if any, matches the query.

    ponytail: regex patterns, no LLM. Returns tool name or None.
    """
    lower = query.lower().strip()

    # Time/date
    if re.search(r"\b(?:what time|current time|time is it|clock)\b", lower):
        return "time"
    if re.search(r"\b(?:what date|current date|today(?:'s)? date|day is it)\b", lower):
        return "date"

    # Filesystem
    if re.search(r"\bread (?:file |the )?(.+)", lower):
        return "filesystem"
    if re.search(r"\blist (?:dir|directory|files?|folder)", lower):
        return "list_directory"

    # HTTP
    if re.search(r"\bfetch (?:https?://\S+)", lower):
        return "http"
    if re.search(r"\bhttps?://\S+", lower):
        return "http"

    return None


# ponytail: new functions below — multi-step and deferred planning.


def plan_steps(query: str) -> list[str]:
    """Split a query into sequential steps on 'then'.

    ponytail: split on 'then', strip, drop empty.
    'Read config.py then summarize' -> ['Read config.py', 'summarize']
    'Read config.py' -> ['Read config.py']
    """
    parts = re.split(r"\bthen\b", query, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def is_deferred(query: str) -> bool:
    """Check if the query is a deferred/remember task.

    ponytail: regex on 'remember to' / 'remember that' / 'don't forget'.
    """
    return bool(re.search(
        r"\b(?:remember to|remember that|don'?t forget|schedule|later)\b",
        query.lower(),
    ))


def classify_plan(query: str) -> str:
    """Return 'deferred', 'multi', or 'single'.

    ponytail: three checks, return first match.
    """
    if is_deferred(query):
        return "deferred"
    if len(plan_steps(query)) > 1:
        return "multi"
    return "single"
