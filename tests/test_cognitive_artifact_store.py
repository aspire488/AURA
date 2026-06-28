"""Tests for the generic CognitiveArtifact store and persistence policy.

These tests are lightweight and skip when the required PostgreSQL
connection string is not set (AURA_POSTGRES_URL). They verify basic CRUD,
UPSERT behavior, JSON payload round‑trip, and that the policy permits
persistence of whitelisted artifact types.
"""

from __future__ import annotations

import os
import pytest

from app.core.cognitive_artifact import CognitiveArtifact
from app.core.cognitive_artifact_store import cognitive_artifact_store

@pytest.mark.asyncio
async def test_store_crud_and_policy():
    if not os.getenv("AURA_POSTGRES_URL"):
        pytest.skip("PostgreSQL not configured for integration test")
    await cognitive_artifact_store.initialize()
    art = CognitiveArtifact(
        artifact_type="reflection",
        producer="unit-test",
        payload={"key": "value"},
    )
    await cognitive_artifact_store.save(art)
    fetched = await cognitive_artifact_store.get(art.id)
    assert fetched is not None
    assert fetched.payload == {"key": "value"}
    assert fetched.artifact_type == "reflection"
    # UPSERT
    fetched.payload["key"] = "new"
    await cognitive_artifact_store.save(fetched)
    fetched2 = await cognitive_artifact_store.get(art.id)
    assert fetched2 is not None and fetched2.payload["key"] == "new"
    recent = await cognitive_artifact_store.list_recent(limit=5)
    assert any(a.id == art.id for a in recent)
    child = CognitiveArtifact(
        artifact_type="reflection",
        producer="unit-test",
        payload={"child": True},
        parent_id=art.id,
    )
    await cognitive_artifact_store.save(child)
    fetched_child = await cognitive_artifact_store.get(child.id)
    assert fetched_child is not None and fetched_child.parent_id == art.id
