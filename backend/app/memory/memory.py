from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Canonical memory types. ponytail: flat enum, four types."""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    HISTORICAL = "historical"


class Memory(BaseModel):
    """Structured long-term memory derived from an Observation.

    ponytail: flat model, no class hierarchy per type. Type field differentiates.
    """
    memory_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    observation_id: str
    identity_id: str = ""
    memory_type: MemoryType
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    summary: str = ""
    content: str = ""
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    access_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
