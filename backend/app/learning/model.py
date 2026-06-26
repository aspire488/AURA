"""Learning record model.

Each learning record derives deterministic lessons from a :class:`app.reflection.reflection.Reflection`
and persists minimal metadata. The design mirrors other models (e.g., ``Belief``)
but is intentionally tiny – only the fields required for the runtime are stored.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, List

from pydantic import BaseModel, Field


class Learning(BaseModel):
    """Deterministic learning record.
    ponytail: keep fields minimal; ID is deterministic short hex.
    """

    learning_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    reflection_id: str  # source reflection
    lessons: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
