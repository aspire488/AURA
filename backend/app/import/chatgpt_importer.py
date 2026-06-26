import json
import logging
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Callable

from .manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _load_conversations(zip_path: str) -> List[Dict[str, Any]]:
    """Extract ``conversations.json`` from the ChatGPT export zip.
    Returns a list of conversation objects as parsed from JSON.
    """
    with zipfile.ZipFile(zip_path, "r") as z:
        # The export always contains a top‑level ``conversations.json`` file.
        try:
            with z.open("conversations.json") as f:
                data = json.load(f)
        except KeyError:
            logger.error("conversations.json not found in %s", zip_path)
            return []
    return data  # type: ignore[arg-type]


def _flatten_messages(conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert nested conversation structure into flat message records.
    Adds ``parent_message_id`` for ordering and skips malformed entries.
    """
    records: List[Dict[str, Any]] = []
    malformed = 0
    for conv in conversations:
        conv_id = conv.get("id") or conv.get("uuid") or conv.get("conversation_id")
        if not conv_id:
            malformed += 1
            continue
        prev_msg_id: Optional[str] = None
        for msg in conv.get("messages", []):
            msg_id = msg.get("id")
            if not msg_id:
                malformed += 1
                continue
            payload: Dict[str, Any] = {
                "conversation_id": conv_id,
                "message_id": msg_id,
                "timestamp": msg.get("timestamp") or msg.get("create_time"),
                "author_role": msg.get("author", {}).get("role", msg.get("role")),
                "content": msg.get("content") or msg.get("text"),
                "parent_message_id": prev_msg_id,  # ponytail: simple parent link
            }
            payload["external_id"] = f"{conv_id}:{msg_id}"
            records.append(payload)
            prev_msg_id = msg_id
    if malformed:
        logger.warning("Skipped %d malformed messages in ChatGPT import", malformed)  # ponytail: report issue
    return records


async def import_chatgpt_export(zip_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Public entry point – load a ChatGPT ``export.zip`` and import all messages.
    Returns the number of newly created observation events.
    """
    conversations = _load_conversations(zip_path)
    if not conversations:
        logger.warning("No conversations loaded from %s", zip_path)
        return 0
    records = _flatten_messages(conversations)
    if progress_callback:
        progress_callback(len(records))
    if not records:
        logger.warning("No messages found in %s", zip_path)
        return 0
    created = await import_records("chatgpt_export", records)
    logger.info("Imported %d new messages from %s", created, zip_path)
    return created


# Register the importer – version can be bumped when the format changes.
register_importer("chatgpt_export", "1.0", lambda rec: rec)  # ponytail: identity handler, payload already prepared
