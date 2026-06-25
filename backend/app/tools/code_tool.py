from __future__ import annotations

import time

from app.intelligence.metrics import metrics
from app.runtime.code_executor import execute_code, execute_command
from app.runtime.tool_registry import registry


async def run_python(code: str) -> str:
    """Execute Python code in sandbox. ponytail: subprocess, no eval."""
    start = time.perf_counter()
    result = await execute_code(code)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_code(latency_ms, result["exit_code"] == 0)

    parts = []
    if result["stdout"]:
        parts.append(result["stdout"].rstrip())
    if result["stderr"]:
        parts.append(f"STDERR:\n{result['stderr'].rstrip()}")
    if result["exit_code"] != 0:
        parts.append(f"Exit code: {result['exit_code']}")
    if result["timed_out"]:
        parts.append("Timed out")
    return "\n".join(parts) or "(no output)"


async def working_directory() -> str:
    """Show current working directory."""
    result = await execute_command("pwd")
    return result["stdout"].strip() or result["stderr"].strip()


def register() -> None:
    registry.register(
        "run_python",
        "Execute Python code in a sandboxed environment",
        run_python,
        {"code": "Python code to execute"},
    )
    registry.register(
        "working_directory",
        "Show the current working directory",
        working_directory,
        {},
    )
