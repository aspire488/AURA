from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Reasoning(BaseModel):
    """Deterministic conclusions derived from goals, opinions, and beliefs. ponytail: references IDs, no data duplication."""
    reasoning_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal_id: str
    belief_ids: list[str] = Field(default_factory=list)  # references Belief.belief_id
    opinion_ids: list[str] = Field(default_factory=list)  # references Opinion.opinion_id
    conclusion: str = ""  # simple derived text
    state: str = "active"  # active | inactive
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
