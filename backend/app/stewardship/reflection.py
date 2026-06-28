import datetime
import json
from typing import List

from app.world.store import world_store
import logging
from app.belief.belief import Belief
from app.belief.store import belief_store
from app.substrate.postgres.client import get_session
logger = logging.getLogger(__name__)
from sqlalchemy import text

# ponytail: simple reflection that flags low‑confidence or stale relations

LOW_CONFIDENCE_THRESHOLD = 0.5  # confidence below this is considered drift
RECENT_SECONDS = 3600  # consider relations updated in the last hour for review

async def _fetch_problematic_relations() -> List[dict]:
    """Return rows (as dict) for relations needing reflection.
    ponytail: single query with OR conditions, returns mapping rows.
    """
    async with get_session() as session:
        now_ts = datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
        cutoff = now_ts - RECENT_SECONDS
        result = await session.execute(
            text(
                "SELECT * FROM world_relations "
                "WHERE confidence < :conf OR updated_at > :recent"
            ),
            {"conf": LOW_CONFIDENCE_THRESHOLD, "recent": cutoff},
        )
        return [row for row in result.mappings()]

async def execute_system_reflection() -> None:
    """Analyze world model for drift and upsert reflective beliefs.
    ponytail: minimal logic, creates a Belief per problematic relation.
    """
    rows = await _fetch_problematic_relations()
    if not rows:
        return
    for row in rows:
        stmt = (
            f"Low confidence or recent change in relation {row['relation_id']}: "
            f"{row['source_entity']} {row['relation_type']} {row['target_entity']} (conf={row.get('confidence')})"
        )
        belief = Belief(
            statement=stmt,
            entity_ids=[row['source_entity'], row['target_entity']],
            evidence_entity_ids=[row['source_entity'], row['target_entity']],
            confidence_value=row.get('confidence', 1.0),
            opinion_value=0.0,
            metadata={"origin": "system_reflection", "relation_id": row['relation_id']},
        )
        try:
            await belief_store.save(belief)
        except Exception:
            logger.exception("Failed to save belief")

# ponytail: expose for daemon import
__all__ = ["execute_system_reflection"]
