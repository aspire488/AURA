"""Oracle core model and helpers.

Provides the Decision record linking reasoning and challenger outcomes.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, List

from pydantic import BaseModel, Field

class Decision(BaseModel):
    """Minimal deterministic decision record.
    ponytail: stores IDs, final conclusion, and simple status.
    """

    decision_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    reasoning_ids: List[str] = Field(default_factory=list)
    challenger_ids: List[str] = Field(default_factory=list)
    status: str = "active"  # active | finalized | invalid
    final_conclusion: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
