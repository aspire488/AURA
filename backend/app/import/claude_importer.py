import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Callable

from .manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _load_export(json_path: str) -> List[Dict[str, Any]]:
    """Load a Claude export JSON file.
    Expected format: list of message dicts with keys `id`, `timestamp`, `role`, `content`.
    ponytail: tolerant – skips entries missing required fields.
    """
    try:
        data = json.loads(Path(json_path).read_text())
    except Exception:
        logger.error("Failed to read Claude export %s", json_path)
        return []
    if not isinstance(data, list):
        logger.error("Claude export %s not a list", json_path)
        return []
    return data


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
            "timestamp": msg.get("timestamp"),
            "author_role": msg.get("role"),
            "content": msg.get("content"),
        }
        # external_id combines source file and message id for deduplication
        payload["external_id"] = f"claude:{msg_id}"
        records.append(payload)
    if malformed:
        logger.warning("Skipped %d malformed Claude messages", malformed)  # ponytail: report issue
    return records


async def import_claude_export(json_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Public entry point – load a Claude export JSON and import messages.
    Returns number of newly created observation events.
    """
    messages = _load_export(json_path)
    if not messages:
        return 0
    records = _flatten_messages(messages)
    if progress_callback:
        progress_callback(len(records))
    if not records:
        return 0
    created = await import_records("claude_export", records)
    logger.info("Imported %d new Claude messages from %s", created, json_path)
    return created

# Register the importer – version can be bumped when the format changes.
register_importer("claude_export", "1.0", lambda rec: rec)  # ponytail: identity handler
