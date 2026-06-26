import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable

from .manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _load_export(json_path: str) -> List[Dict[str, Any]]:
    """Load a Gemini export JSON file.
    Expected format: list of conversation dicts each containing `messages` list.
    Each message dict should have `id`, `createTime`, `author`, `content`.
    ponytail: tolerant, skips malformed entries.
    """
    try:
        data = json.loads(Path(json_path).read_text())
    except Exception:
        logger.error("Failed to read Gemini export %s", json_path)
        return []
    # Support both top‑level list of messages or dict with `conversations`
    if isinstance(data, dict) and "conversations" in data:
        convs = data["conversations"]
        msgs = []
        for conv in convs:
            msgs.extend(conv.get("messages", []))
        return msgs
    if isinstance(data, list):
        return data
    logger.error("Unexpected Gemini export format %s", json_path)
    return []


def _flatten_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    malformed = 0
    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            malformed += 1
            continue
        payload = {
            "message_id": msg_id,
            "timestamp": msg.get("createTime"),
            "author_role": msg.get("author", {}).get("role"),
            "content": msg.get("content"),
        }
        payload["external_id"] = f"gemini:{msg_id}"
        records.append(payload)
    if malformed:
        logger.warning("Skipped %d malformed Gemini messages", malformed)  # ponytail: report issue
    return records


async def import_gemini_export(json_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Import Gemini export JSON into observations.
    Returns number of newly created events.
    """
    messages = _load_export(json_path)
    if not messages:
        return 0
    records = _flatten_messages(messages)
    if progress_callback:
        progress_callback(len(records))
    if not records:
        return 0
    created = await import_records("gemini_export", records)
    logger.info("Imported %d new Gemini messages from %s", created, json_path)
    return created

# Register importer
register_importer("gemini_export", "1.0", lambda rec: rec)  # ponytail: identity handler
