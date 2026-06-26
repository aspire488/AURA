"""Historical import framework.

Provides:
- ``register_importer`` to add deterministic importers.
- ``import_records`` to process raw records through the chosen importer,
  deduplicate using a PostgreSQL table, and emit a ``historical_import``
  event which will flow through the normal observation → memory → … pipeline.

The implementation follows the same minimal patterns used elsewhere in the
codebase (e.g. ``skill_system.manager``).  No extra dependencies are added.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Tuple

from app.main import emit
from app.substrate.postgres.client import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Registry: name -> (version, handler)
_importer_registry: Dict[str, Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {}


def register_importer(name: str, version: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
    """Register an importer.
    ponytail: last registration wins – deterministic overwrite.
    """
    _importer_registry[name] = (version, handler)
    logger.debug("Importer %s registered (v%s)", name, version)


# Simple table for import deduplication
_CREATE_IMPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS imports (
    import_id VARCHAR(12) PRIMARY KEY,
    importer_name VARCHAR(64) NOT NULL,
    external_hash VARCHAR(64) NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    UNIQUE (importer_name, external_hash)
);
"""


async def _ensure_table() -> None:
    async with get_session() as session:
        for stmt in _CREATE_IMPORTS_TABLE.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await session.execute(text(stmt))
        await session.commit()


def _hash_payload(payload: Dict[str, Any]) -> str:
    # Stable hash for duplicate detection
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload_bytes).hexdigest()


async def import_records(importer_name: str, records: list[Dict[str, Any]]) -> int:
    # Initialize progress tracking for this run (pony-tail: simple stats)
    from .inspector import start_import, record_processed, set_last_trace
    start_import(importer_name, total=len(records))
    """Process *records* with the registered importer.

    Returns the number of newly created events.
    Duplicate records (same payload hash for the same importer) are skipped.
    """
    if importer_name not in _importer_registry:
        raise KeyError(f"Importer {importer_name} not registered")
    version, handler = _importer_registry[importer_name]
    await _ensure_table()
    created = 0
    for rec in records:
        # Process each raw record
        try:
            payload = handler(rec)
        except Exception:
            logger.exception("Importer %s failed on record %s", importer_name, rec)
            # Record failure
            record_processed(importer_name, failure=True)
            continue
        # Determine external identifier hash – use explicit key if present
        external_id = payload.get("external_id")
        if external_id is not None:
            hash_key = hashlib.sha256(str(external_id).encode()).hexdigest()
        else:
            hash_key = _hash_payload(payload)
        # Check duplicate
        async with get_session() as session:
            result = await session.execute(
                text("SELECT 1 FROM imports WHERE importer_name = :name AND external_hash = :h"),
                {"name": importer_name, "h": hash_key},
            )
            if result.first():
                logger.debug("Duplicate import skipped for %s", hash_key)
                # Record duplicate as skipped
                record_processed(importer_name, duplicate=True)
                continue
            # Emit event – goes through observation pipeline
            await emit(
                "historical_import",
                source=importer_name,
                payload=payload,
                version=version,
            )
            # Record import in DB
            await session.execute(
                text(
                    "INSERT INTO imports (import_id, importer_name, external_hash, timestamp) "
                    "VALUES (:iid, :name, :h, :ts)"
                ),
                {
                    "iid": hashlib.sha256((importer_name + hash_key).encode()).hexdigest()[:12],
                    "name": importer_name,
                    "h": hash_key,
                    "ts": time.time(),
                },
            )
            await session.commit()
            created += 1
            # Record successful creation and progress
            record_processed(importer_name, created=True)
            # Store last trace payload for simple pipeline view (pony-tail: minimal)
            set_last_trace(importer_name, payload)
    logger.info("Import %s processed %d records, %d new events", importer_name, len(records), created)
    return created
