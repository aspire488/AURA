"""Persistence policy for CognitiveArtifact.

Current implementation is a minimal deterministic policy that evaluates
artifact properties (e.g., confidence).  It is deliberately simple and
extensible – future versions can add accepted flags, significance
scoring, etc.
"""

from __future__ import annotations

from app.core.cognitive_artifact import CognitiveArtifact


class SimplePersistencePolicy:
    """Deterministic policy based on artifact confidence.

    For now we persist only artifacts with confidence >= 1.0 – the default
    for all current producers.  This placeholder can be expanded to
    include accepted state or long‑term significance without changing the
    interface.
    """

    def should_persist(self, artifact: CognitiveArtifact) -> bool:
        # ponytail: deterministic one‑liner; adjust threshold as needed
        return artifact.confidence >= 1.0
