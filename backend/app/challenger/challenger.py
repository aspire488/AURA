from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Challenge(BaseModel):
    """Minimal challenge record linking reasoning, belief, opinion IDs.
    ponytail: stores IDs, no duplication of full objects.
    """

    challenge_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: str  # e.g., "conflict_belief", "contradiction_opinion", "unsupported_reasoning"
    target_ids: list[str] = Field(default_factory=list)  # IDs referenced (reasoning, belief, opinion)
    description: str = ""
    state: str = "active"  # active | resolved | invalid
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
