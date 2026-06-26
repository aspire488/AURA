from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Goal(BaseModel):
    """Desired future state derived from Opinions. ponytail: minimal fields, no duplication."""
    goal_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "active"  # active | paused | completed | abandoned | invalid
    priority: int = 0
    supporting_opinion_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
