"""Canonical reflection record.

A reflection links a completed Plan (or its constituent Decisions/Reasoning) to
self‑assessment data.  Minimal deterministic fields are stored; richer analysis
can be added later.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, List

from pydantic import BaseModel, Field


class Reflection(BaseModel):
    """Self‑review of a plan or decision.
    ponytail: keep fields minimal, deterministic IDs, JSON‑compatible lists.
    """

    reflection_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    plan_id: str | None = None  # associated Plan, if any
    decision_ids: List[str] = Field(default_factory=list)
    reasoning_ids: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    status: str = "active"  # active | invalid
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
