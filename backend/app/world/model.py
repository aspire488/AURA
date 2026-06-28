import time
import uuid
from typing import Any, Dict

from pydantic import BaseModel, Field

# ponytail: flat Pydantic models for world graph entities/relations

class WorldEntity(BaseModel):
    """Represents a discrete node in AURA's world model (e.g., person, project, tool, device)."""
    entity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    category: str  # e.g., "user", "project", "application", "preference"
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class WorldRelation(BaseModel):
    """Represents a directed semantic edge connecting two WorldEntities."""
    relation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    subject_id: str  # Source Entity ID
    predicate: str   # The relationship type (e.g., "owns", "prefers", "contains", "excludes")
    object_id: str   # Target Entity ID
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_id: str | None = None  # Links back to the source Observation or Belief ID
    updated_at: float = Field(default_factory=time.time)

# ponytail: expose via __all__
__all__ = ["WorldEntity", "WorldRelation"]
