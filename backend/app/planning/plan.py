from __future__ import annotations

import time
import uuid
from typing import Any, List

from pydantic import BaseModel, Field


class Plan(BaseModel):
    """Canonical planning record linking goals and oracle decisions.
    ponytail: minimal fields, deterministic action list generated on demand.
    """

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "active"  # active | executing | completed | invalid
    priority: int = 0
    goal_ids: List[str] = Field(default_factory=list)
    decision_ids: List[str] = Field(default_factory=list)
    action_sequence: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
