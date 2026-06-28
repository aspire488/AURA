from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field
from typing import List, Any


class Belief(BaseModel):
    """Unified belief state with embedded confidence and opinion metrics. ponytail: consolidates three tables into one."""
    belief_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    statement: str = ""
    entity_ids: List[str] = Field(default_factory=list)
    evidence_knowledge_ids: List[str] = Field(default_factory=list)
    evidence_entity_ids: List[str] = Field(default_factory=list)
    evidence_observation_ids: List[str] = Field(default_factory=list)
    confidence_value: float = Field(default=1.0, ge=0.0, le=1.0)
    opinion_value: float = Field(default=0.0, ge=0.0, le=1.0)
    state: str = "active"  # active | consolidated | historical
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
