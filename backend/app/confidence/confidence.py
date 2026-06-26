from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Confidence(BaseModel):
    """Confidence score for a belief. ponytail: simple numeric confidence linked to a belief_id."""
    confidence_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    belief_id: str = ""  # reference to Belief.belief_id, no duplication
    value: float = Field(default=1.0, ge=0.0, le=1.0)  # 0..1
    evidence_knowledge_ids: list[str] = Field(default_factory=list)
    evidence_observation_ids: list[str] = Field(default_factory=list)
    state: str = "active"  # active | inactive
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
