from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    """Link between two identities. ponytail: simple edge, no graph DB."""
    relationship_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_identity: str = ""
    target_identity: str = ""
    relationship_type: str = ""
    confidence: float = 1.0
    evidence_count: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
