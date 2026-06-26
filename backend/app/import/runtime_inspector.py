from __future__ import annotations

from app.intelligence.metrics import metrics
from .inspector import _import_stats

def get_runtime_counters() -> dict:
    """Return current in‑process counters relevant to cognition pipeline."""
    # The metrics snapshot already contains the required fields.
    snap = metrics.snapshot()
    # Filter to the requested keys.
    keys = [
        "observations_created",
        "memories_created",
        "knowledge_created",
        "world_model_updates",
        "beliefs_created",
        "beliefs_updated",
        "identities_created",
    ]
    # Some keys may not exist; default to 0.
    # Add total imported events from inspector (sum of created across importers)
    total_imported = sum(stat.created for stat in _import_stats.values())
    result = {k: snap.get(k, 0) for k in keys if k in snap}
    result["imports_created"] = total_imported
    return result
