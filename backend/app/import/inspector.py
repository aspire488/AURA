from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

# Simple stats collector per importer
@dataclass
class ImportStats:
    total: int = 0
    processed: int = 0
    duplicates: int = 0
    failures: int = 0
    created: int = 0  # number of new events emitted
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def throughput(self) -> float:
        return self.created / self.elapsed if self.elapsed else 0.0

    def snapshot(self) -> dict:
        return {
            "total": self.total,
            "processed": self.processed,
            "skipped": self.duplicates,
            "failures": self.failures,
            "created": self.created,
            "elapsed": self.elapsed,
            "throughput": self.throughput,
        }

# Global registry for import progress
_import_stats: Dict[str, ImportStats] = {}

def start_import(importer_name: str, total: int) -> None:
    """Initialize progress tracking for an import run."""
    _import_stats[importer_name] = ImportStats(total=total)

def record_processed(importer_name: str, duplicate: bool = False, failure: bool = False, created: bool = False) -> None:
    stats = _import_stats.get(importer_name)
    if not stats:
        # fallback – create with unknown total
        stats = ImportStats()
        _import_stats[importer_name] = stats
    stats.processed += 1
    if duplicate:
        stats.duplicates += 1
    if failure:
        stats.failures += 1
    if created:
        stats.created += 1

def get_import_progress(importer_name: str) -> Optional[dict]:
    """Return a snapshot of import progress, or None if not tracked."""
    stats = _import_stats.get(importer_name)
    return stats.snapshot() if stats else None

# Very lightweight pipeline trace – store the last payload processed per importer
_last_trace: Dict[str, dict] = {}

def set_last_trace(importer_name: str, payload: dict) -> None:
    _last_trace[importer_name] = payload

def get_last_trace(importer_name: str) -> Optional[dict]:
    return _last_trace.get(importer_name)
