"""Chromium browser history importer.

Exports each visited URL as a record with:
- external_id (generated from URL and visit_time)
- url, title, visit_time (Unix epoch), visit_count

Uses SQLite via the stdlib; no external deps.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Callable, List, Dict, Any

from app.import.manager import register_importer, import_records

logger = logging.getLogger(__name__)

_CHROME_EPOCH_OFFSET = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def _unix_timestamp(chrome_ts: int) -> float:
    """Convert Chrome's microsecond timestamp to Unix seconds."""
    return chrome_ts / 1_000_000 - _CHROME_EPOCH_OFFSET


def _load_history(db_path: str) -> List[Dict[str, Any]]:
    p = Path(db_path).expanduser().resolve()
    if not p.is_file():
        logger.error("History DB not found: %s", db_path)
        return []
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    # The "urls" table holds url, title, visit_count, last_visit_time (microseconds)
    cur.execute("SELECT url, title, visit_count, last_visit_time FROM urls")
    rows = cur.fetchall()
    conn.close()
    records: List[Dict[str, Any]] = []
    for url, title, count, last_visit in rows:
        visit_ts = _unix_timestamp(last_visit)
        external_id = f"url:{url}:{int(visit_ts)}"
        records.append({
            "external_id": external_id,
            "url": url,
            "title": title,
            "visit_count": count,
            "visit_time": visit_ts,
        })
    return records


async def import_browser_history(db_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Import Chromium history from *db_path*.
    Returns number of newly created events.
    """
    records = _load_history(db_path)
    if not records:
        return 0
    if progress_callback:
        progress_callback(len(records))
    created = await import_records("browser_history_import", records)
    logger.info("Imported %d new browser history observations from %s", created, db_path)
    return created

# Register – identity handler
register_importer("browser_history_import", "1.0", lambda rec: rec)  # ponytail: identity