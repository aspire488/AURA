from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Opinion(BaseModel):
    """Deterministic evaluation derived from beliefs + confidence. ponytail: references belief IDs, no duplication."""
    opinion_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    belief_ids: list[str] = Field(default_factory=list)  # references Belief.belief_id
    value: float = Field(default=0.0, ge=0.0, le=1.0)  # derived score 0..1
    state: str = "active"  # active | inactive
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
