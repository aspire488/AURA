"""In‑memory dead‑letter queue for failed event processing.

Used by EventBus.publish when a subscriber raises an exception.
Provides simple CRUD via API for operational workflows.
"""

from typing import List, Dict
import uuid

_dlq: List[Dict] = []

def add(entry: Dict) -> str:
    """Add a failed event entry and return its ID."""
    entry_id = str(uuid.uuid4())
    _dlq.append({"id": entry_id, "retries": 0, **entry})
    return entry_id

def list_entries() -> List[Dict]:
    """Return a copy of all DLQ entries."""
    return list(_dlq)

def remove(entry_id: str) -> bool:
    """Remove entry by ID. Returns True if removed."""
    global _dlq
    for i, e in enumerate(_dlq):
        if e["id"] == entry_id:
            del _dlq[i]
            return True
    return False
