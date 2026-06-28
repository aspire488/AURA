"""Cognitive exchange layer.

Producers create :class:`CognitiveArtifact` instances and hand them to the
exchange via :func:`emit`.  The exchange applies a persistence policy and
delegates to the generic store.  This decouples producers (e.g., the
Reflection subsystem) from storage concerns.
"""

from __future__ import annotations

import logging

from app.core.cognitive_artifact import CognitiveArtifact
from app.core.cognitive_artifact_store import cognitive_artifact_store
from app.core.cognitive_artifact_policy import SimplePersistencePolicy

logger = logging.getLogger(__name__)


class CognitiveExchange:
    """Orchestrates artifact emission, applying the persistence policy.

    ponytail: minimal indirection – policy check then store.save.
    """

    def __init__(self) -> None:
        self._policy = SimplePersistencePolicy()
        self._store = cognitive_artifact_store

    async def emit(self, artifact: CognitiveArtifact) -> None:
        """Emit an artifact.

        If the policy says to persist, the store is invoked.  Future routing
        (e.g., publishing, indexing) can be added here without touching the
        producer.
        """
        if self._policy.should_persist(artifact):
            await self._store.save(artifact)
        else:
            logger.debug("CognitiveArtifact %s not persisted by policy", artifact.id)


cognitive_exchange = CognitiveExchange()
