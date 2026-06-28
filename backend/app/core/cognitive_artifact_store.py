"""Persistence for :class:`CognitiveArtifact`.

Uses the same raw‑SQL pattern as other stores.  Only the minimal CRUD
required by the current integration (save, get, list) is provided.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from sqlalchemy import text

from app.core.cognitive_artifact import CognitiveArtifact
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cognitive_artifacts (
    id VARCHAR(12) PRIMARY KEY,
    artifact_type VARCHAR(64) NOT NULL,
    producer VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    provenance JSONB DEFAULT '{}',
    parent_id VARCHAR(12),
    timestamp DOUBLE PRECISION NOT NULL,
    version INTEGER NOT NULL
);
"""


class CognitiveArtifactStore:
    """Raw‑SQL store for :class:`CognitiveArtifact`."""



    async def initialize(self) -> None:
        async with get_session() as session:
            await session.execute(text(CREATE_TABLE))
            await session.commit()
        logger.info("CognitiveArtifact table ready")

    async def save(self, artifact: CognitiveArtifact) -> None:
        """Persist the artifact if the policy allows it.

        ponytail: early‑exit on policy reject to avoid DB round‑trip.
        """

        async with get_session() as session:
            await session.execute(
                text(
                    "INSERT INTO cognitive_artifacts (id, artifact_type, producer, payload, confidence, provenance, parent_id, timestamp, version) "
                    "VALUES (:id, :type, :producer, :payload, :conf, :prov, :parent, :ts, :ver) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "artifact_type=EXCLUDED.artifact_type, producer=EXCLUDED.producer, payload=EXCLUDED.payload, "
                    "confidence=EXCLUDED.confidence, provenance=EXCLUDED.provenance, parent_id=EXCLUDED.parent_id, "
                    "timestamp=EXCLUDED.timestamp, version=EXCLUDED.version"
                ),
                {
                    "id": artifact.id,
                    "type": artifact.artifact_type,
                    "producer": artifact.producer,
                    "payload": json.dumps(artifact.payload),
                    "conf": artifact.confidence,
                    "prov": json.dumps(artifact.provenance),
                    "parent": artifact.parent_id,
                    "ts": artifact.timestamp,
                    "ver": artifact.version,
                },
            )
            await session.commit()

    async def get(self, artifact_id: str) -> Optional[CognitiveArtifact]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM cognitive_artifacts WHERE id = :id"), {"id": artifact_id}
            )
            row = result.mappings().first()
            return self._row_to_artifact(row) if row else None

    async def list_recent(self, limit: int = 100) -> List[CognitiveArtifact]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM cognitive_artifacts ORDER BY timestamp DESC LIMIT :limit"),
                {"limit": limit},
            )
            return [self._row_to_artifact(row) for row in result.mappings()]

    def _row_to_artifact(self, row: dict) -> CognitiveArtifact:
        return CognitiveArtifact(
            id=row["id"],
            artifact_type=row["artifact_type"],
            producer=row["producer"],
            payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
            confidence=row["confidence"],
            provenance=json.loads(row["provenance"]) if isinstance(row["provenance"], str) else row["provenance"],
            parent_id=row["parent_id"],
            timestamp=row["timestamp"],
            version=row["version"],
        )


cognitive_artifact_store = CognitiveArtifactStore()
