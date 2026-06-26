from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class WorldEntity(BaseModel):
    """Canonical entity in the world model. ponytail: flat model, no class hierarchy."""
    entity_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    entity_type: str = "concept"  # ponytail: concept, person, tool, place, etc.
    aliases: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldRelation(BaseModel):
    """Directed relation between two entities. ponytail: simple edge, no graph DB."""
    relation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_entity: str = ""
    target_entity: str = ""
    relation_type: str = ""
    confidence: float = 1.0
    evidence_count: int = 1
    source_knowledge_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorldAttribute(BaseModel):
    """Key-value attribute on an entity. ponytail: separate table, not JSONB blob."""
    attribute_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    entity_id: str = ""
    attr_key: str = ""
    attr_value: str = ""
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
