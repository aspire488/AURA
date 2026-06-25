from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.config import settings

# ponytail: stdlib subprocess, no Docker, no eval/exec.
ALLOWED_COMMANDS = frozenset({"python", "ls", "cat", "pwd"})
TIMEOUT_SECONDS = 10


async def execute_code(code: str) -> dict:
    """Execute Python code in a sandboxed subprocess.

    Returns dict with stdout, stderr, exit_code, timed_out.
    ponytail: subprocess with timeout, no shell=True.
    """
    root = Path(settings.filesystem_root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=str(root), delete=False) as f:
        f.write(code)
        tmp_path = Path(f.name)

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", str(tmp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(root),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {TIMEOUT_SECONDS}s",
                "exit_code": -1,
                "timed_out": True,
            }

        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exit_code": proc.returncode or 0,
            "timed_out": False,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


async def execute_command(command: str) -> dict:
    """Execute an allowed filesystem command.

    ponytail: whitelist only python, ls, cat, pwd. No shell=True.
    """
    parts = command.split()
    if not parts:
        return {"stdout": "", "stderr": "Empty command", "exit_code": 1, "timed_out": False}

    cmd = parts[0]
    if cmd not in ALLOWED_COMMANDS:
        return {"stdout": "", "stderr": f"Blocked: '{cmd}' not in allowed commands", "exit_code": 1, "timed_out": False}

    root = Path(settings.filesystem_root).resolve()

    # Resolve paths against filesystem_root for safety
    resolved_args = []
    for arg in parts[1:]:
        target = (root / arg).resolve()
        if not str(target).startswith(str(root)):
            return {"stdout": "", "stderr": f"Blocked: path outside workspace", "exit_code": 1, "timed_out": False}
        resolved_args.append(str(target))

    proc = await asyncio.create_subprocess_exec(
        cmd, *resolved_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(root),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"stdout": "", "stderr": f"Command timed out after {TIMEOUT_SECONDS}s", "exit_code": -1, "timed_out": True}

    return {
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "exit_code": proc.returncode or 0,
        "timed_out": False,
    }
