def chunk_messages(messages: list[dict]) -> list[dict]:
    result: list[dict] = []
    for msg in messages:
        result.append({
            "chunk_id": msg["message_id"],
            "message_id": msg["message_id"],
            "conversation_id": msg["conversation_id"],
            "role": msg["role"],
            "text": msg["content"],
            "timestamp": msg["timestamp"],
            "chunk_index": 0,
        })
    return result
