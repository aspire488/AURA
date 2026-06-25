from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.runtime.tool_registry import registry


async def read_file(path: str) -> str:
    """Read file contents, restricted to filesystem_root."""
    root = Path(settings.filesystem_root).resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        return f"Error: path {path} is outside workspace root"
    if not target.is_file():
        return f"Error: {path} is not a file"
    # ponytail: read text only, no binary handling needed yet
    return target.read_text(encoding="utf-8")


async def list_directory(path: str = ".") -> str:
    """List directory contents, restricted to filesystem_root."""
    root = Path(settings.filesystem_root).resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        return f"Error: path {path} is outside workspace root"
    if not target.is_dir():
        return f"Error: {path} is not a directory"
    entries = sorted(
        (e.name + ("/" if e.is_dir() else "")) for e in target.iterdir()
    )
    return "\n".join(entries) if entries else "(empty)"


def register() -> None:
    registry.register(
        "filesystem",
        "Read a file or list a directory within the workspace",
        read_file,
        {"path": "relative path within workspace"},
    )
    registry.register(
        "list_directory",
        "List directory contents within the workspace",
        list_directory,
        {"path": "relative directory path (default: .)"},
    )
