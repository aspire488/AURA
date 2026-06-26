'''Gmail Takeout JSON importer.

Expects a path to a JSON file containing a list of Gmail messages as exported
by Google Takeout (the ``messages`` array). Extracts a minimal canonical
observation payload:

- ``type``: ``gmail_message``
- ``external_id``: Gmail message ``id`` (used for duplicate detection)
- ``sender``
- ``recipients`` (list)
- ``subject``
- ``body`` (plain‑text snippet)
- ``labels``
- ``timestamp`` (``internalDate`` ms since epoch converted to seconds)
- ``thread_id``

Missing fields are tolerated; the record is still emitted with whatever data
is present.
'''\n\nimport base64\nimport json\nimport logging\nfrom typing import Callable, List, Dict, Any\n\nfrom app.import.manager import register_importer, import_records\n\nlogger = logging.getLogger(__name__)\n\ndef _decode_body(data: str) -> str:\n    """Decode base64url body data to UTF‑8 text. ponytail: ignore errors."""\n    try:\n        # Gmail uses URL‑safe base64 without padding\n        padded = data + "=" * (-len(data) % 4)\n        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")\n    except Exception:\n        return ""\n\ndef _extract_headers(headers: List[Dict[str, str]]) -> Dict[str, str]:\n    """Return a dict of header name → value (case‑insensitive)."""\n    out: Dict[str, str] = {}\n    for h in headers:\n        name = h.get("name", "").lower()\n        if name:\n            out[name] = h.get("value", "")\n    return out\n\ndef _load_records(path: str) -> List[Dict[str, Any]]:\n    """Load Gmail JSON and transform each message to a canonical payload.\n\n    ponytail: simple identity handling – no pagination, no attachment support.\n    """\n    with open(path, "r", encoding="utf-8") as f:\n        data = json.load(f)\n    messages = data.get("messages", data)\n    records: List[Dict[str, Any]] = []\n    for msg in messages:\n        try:\n            payload = msg.get("payload", {})\n            headers = _extract_headers(payload.get("headers", []))\n            body_data = payload.get("body", {}).get("data", "")\n            body = _decode_body(body_data) or msg.get("snippet", "")\n            rec: Dict[str, Any] = {\n                "type": "gmail_message",\n                "external_id": msg.get("id"),\n                "sender": headers.get("from", ""),\n                "recipients": [r.strip() for r in headers.get("to", "").split(",") if r.strip()],\n                "subject": headers.get("subject", ""),\n                "body": body,\n                "labels": msg.get("labelIds", []),\n                "timestamp": int(int(msg.get("internalDate", "0")) / 1000),\n                "thread_id": msg.get("threadId"),\n            }\n            records.append(rec)\n        except Exception:\n            logger.exception("Failed to parse Gmail message %s", msg.get("id"))\n    return records\n\nasync def import_gmail(path: str, progress_callback: Callable[[int], None] | None = None) -> int:\n    """Import Gmail messages from a Takeout JSON file.\n\n    Returns the number of newly created observation events.\n    """\n    records = _load_records(path)\n    if progress_callback:\n        progress_callback(len(records))\n    created = await import_records("gmail_import", records)\n    logger.info("Imported %d new Gmail observations from %s", created, path)\n    return created\n\n# Register the importer – identity handler (records already in final shape)\nregister_importer("gmail_import", "1.0", lambda rec: rec)  # ponytail: identity