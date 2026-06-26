"""Continuity model – captures long‑term session state.

Only minimal fields are kept to allow deterministic resume of a cognitive session.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from pydantic import BaseModel, Field


class Continuity(BaseModel):
    """Persisted continuity record.
    ponytail: keep fields minimal; ID is short hex.
    """

    continuity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str  # external session identifier
    state: Dict[str, Any] = Field(default_factory=dict)  # arbitrary JSON‑serialisable state
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
