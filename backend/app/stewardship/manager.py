'''Stewardship manager – health audits and deterministic diagnostics.

Provides functions that scan the database for common integrity issues.
All functions are side‑effect‑free; they only return data structures
describing any problems found.
''' 

from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import text

from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)


# Helper – fetch all rows for a given query
async def _fetch_all(query: str, **params: Any) -> List[Dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(text(query), params)
        rows = result.mappings().all()
        return [dict(row) for row in rows]


# ---- Audits ---------------------------------------------------------------

async def detect_orphan_relationships() -> List[Dict[str, Any]]:
    """Return relationships whose source or target identity does not exist.
    ponytail: simple SQL joins – no additional tables.
    """
    # Load all identities for quick lookup
    identity_rows = await _fetch_all("SELECT identity_id FROM identities")
    valid_ids = {row["identity_id"] for row in identity_rows}
    rels = await _fetch_all("SELECT relationship_id, source_identity, target_identity FROM relationships")
    orphans = []
    for r in rels:
        if r["source_identity"] not in valid_ids or r["target_identity"] not in valid_ids:
            orphans.append(r)
    return orphans

# ---- Repair actions -------------------------------------------------------

async def repair_orphan_relationships() -> None:
    """Delete relationships referencing missing identities."""
    async with get_session() as session:
        await session.execute(
            text(
                "DELETE FROM relationships WHERE source_identity NOT IN (SELECT identity_id FROM identities) OR target_identity NOT IN (SELECT identity_id FROM identities)"
            )
        )
        await session.commit()

async def repair_duplicate_identities() -> None:
    """Keep one identity per display_name, delete extras."""
    # Find duplicates
    dup_rows = await _fetch_all(
        "SELECT display_name, array_agg(identity_id) AS ids FROM identities GROUP BY display_name HAVING count(*) > 1"
    )
    async with get_session() as session:
        for row in dup_rows:
            ids = json.loads(row["ids"]) if isinstance(row["ids"], str) else row["ids"]
            # keep first, delete rest
            to_delete = ids[1:]
            for did in to_delete:
                await session.execute(text("DELETE FROM identities WHERE identity_id = :did"), {"did": did})
        await session.commit()

async def cleanup_stalled_imports(days_threshold: int = 30) -> None:
    """Delete import records older than threshold days."""
    cutoff = time.time() - days_threshold * 86400
    async with get_session() as session:
        await session.execute(text("DELETE FROM imports WHERE timestamp < :cutoff"), {"cutoff": cutoff})
        await session.commit()


async def detect_duplicate_identities() -> List[Dict[str, Any]]:
    """Return groups of identities sharing the same display_name.
    ponytail: one‑line GROUP BY query.
    """
    dup_rows = await _fetch_all(
        """
        SELECT display_name, array_agg(identity_id) AS ids, count(*) AS cnt
        FROM identities
        GROUP BY display_name
        HAVING count(*) > 1
        """
    )
    return dup_rows


async def detect_stalled_imports(days_threshold: int = 7) -> List[Dict[str, Any]]:
    """Return import records older than *days_threshold* that may be stalled.
    ponytail: no import status tracking, so we flag old entries.
    """
    import_time_cutoff = __import__('time').time() - days_threshold * 86400
    rows = await _fetch_all(
        "SELECT import_id, importer_name, timestamp FROM imports WHERE timestamp < :cutoff",
        cutoff=import_time_cutoff,
    )
    return rows


async def audit_subsystem_health() -> Dict[str, Any]:
    """Run a collection of audits and return a summary dict.
    ponytail: deterministic, no side effects.
    """
    orphan_rels = await detect_orphan_relationships()
    dup_idents = await detect_duplicate_identities()
    stalled = await detect_stalled_imports()
    return {
        "orphan_relationships": orphan_rels,
        "duplicate_identities": dup_idents,
        "stalled_imports": stalled,
    }


# Singleton pattern for external callers
_manager: Any | None = None


def get_stewardship_manager() -> Any:
    global _manager
    if _manager is None:
        _manager = type("StewardshipManager", (), {
            "detect_orphan_relationships": staticmethod(detect_orphan_relationships),
            "detect_duplicate_identities": staticmethod(detect_duplicate_identities),
            "detect_stalled_imports": staticmethod(detect_stalled_imports),
            "audit_subsystem_health": staticmethod(audit_subsystem_health),
        })()
    return _manager
