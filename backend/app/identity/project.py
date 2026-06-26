from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Project(BaseModel):
    """Named project container. ponytail: flat, no hierarchy."""
    project_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
