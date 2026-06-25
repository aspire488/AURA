from __future__ import annotations

import re
import time


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


def extract_tool_args(tool_name: str, query: str) -> dict:
    """Extract arguments for a tool from the query text.

    ponytail: regex extraction, no arg parser.
    """
    if tool_name == "filesystem":
        m = re.search(r"\bread (?:file |the )?(.+)", query.lower())
        return {"path": m.group(1).strip() if m else "."}
    if tool_name == "list_directory":
        m = re.search(r"\b(?:in |to |at )(.+)", query.lower())
        return {"path": m.group(1).strip() if m else "."}
    if tool_name == "http":
        m = re.search(r"(https?://\S+)", query)
        return {"url": m.group(1) if m else ""}
    return {}


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


def create_plan(query: str) -> "ExecutionPlan":
    """Build an ExecutionPlan from a query.

    Splits on 'then', routes each step to tool or LLM.
    ponytail: deterministic, regex-only, no LLM planning.
    """
    from app.runtime.execution_engine import ExecutionPlan, ExecutionStep

    step_texts = plan_steps(query)
    steps: list[ExecutionStep] = []

    for i, text in enumerate(step_texts):
        tool_name = plan_tool(text)
        tool_args = extract_tool_args(tool_name, text) if tool_name else {}
        steps.append(ExecutionStep(
            index=i,
            query=text,
            tool_name=tool_name,
            tool_args=tool_args,
        ))

    return ExecutionPlan(
        query=query,
        steps=steps,
        created_at=time.time(),
    )
