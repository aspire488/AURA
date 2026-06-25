from uuid import uuid4


def parse_conversation(raw: dict) -> list[dict]:
    conversation_id = raw.get("id") or raw.get("conversation_id", "")
    if not conversation_id:
        return []

    mapping: dict = raw.get("mapping", {})
    if not mapping:
        return []

    messages: list[dict] = []

    for node_id, node in mapping.items():
        msg = node.get("message")
        if msg is None:
            continue

        role = msg.get("author", {}).get("role")
        if role not in ("user", "assistant", "system"):
            continue

        content_parts: list = msg.get("content", {}).get("parts", [])
        text = " ".join(p for p in content_parts if isinstance(p, str)).strip()
        if not text:
            continue

        create_time = msg.get("create_time")
        timestamp = None
        if isinstance(create_time, (int, float)):
            from datetime import datetime, timezone
            timestamp = datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()

        messages.append({
            "message_id": msg.get("id") or node_id or str(uuid4()),
            "conversation_id": conversation_id,
            "role": role,
            "content": text,
            "timestamp": timestamp or "",
        })

    messages.sort(key=lambda m: m.get("timestamp", ""))
    return messages
