import json
from pathlib import Path


IMPORT_DIR = Path("/imports/chatgpt/extracted")


def scan_source_files() -> list[Path]:
    if not IMPORT_DIR.exists():
        return []
    return sorted(IMPORT_DIR.glob("conversations-*.json"))


def load_conversation_batch(path: Path, limit: int | None = None) -> list[dict]:
    with open(path) as f:
        conversations: list[dict] = json.load(f)
    if limit is not None:
        return conversations[:limit]
    return conversations
