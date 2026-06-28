"""Canonical CognitiveArtifact envelope.

All layers produce opaque, JSON‑serialisable payloads wrapped in this
structure.  The model is deliberately minimal – only metadata needed for
provenance, versioning and optional persistence.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from pydantic import BaseModel, Field


class CognitiveArtifact(BaseModel):
    """Generic envelope for any cognitive output.

    ponytail: keep fields flat, JSON‑compatible, deterministic IDs.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    artifact_type: str
    producer: str
    payload: Dict[str, Any]
    confidence: float = 1.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    version: int = 1
