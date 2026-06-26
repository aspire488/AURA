from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Identity(BaseModel):
    """Persistent cognitive identity. ponytail: flat model, no inheritance."""
    identity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    display_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
