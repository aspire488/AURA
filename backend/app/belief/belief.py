from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Belief(BaseModel):
    """What AURA currently accepts as true. ponytail: references WorldEntity IDs, no data duplication."""
    belief_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    statement: str = ""  # human-readable claim, e.g. "Alice is a software engineer"
    entity_ids: list[str] = Field(default_factory=list)  # referenced WorldEntity IDs
    evidence_knowledge_ids: list[str] = Field(default_factory=list)  # supporting Knowledge IDs
    evidence_entity_ids: list[str] = Field(default_factory=list)  # supporting WorldEntity IDs
    state: str = "active"  # active | inactive
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
