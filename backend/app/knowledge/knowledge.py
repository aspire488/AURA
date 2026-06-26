from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Knowledge(BaseModel):
    """Deterministic fact extracted from memory. ponytail: flat model, no class hierarchy."""
    knowledge_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    identity_id: str = ""
    source_memory_ids: list[str] = Field(default_factory=list)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
