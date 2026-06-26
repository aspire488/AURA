"""Base definitions for historical importers.

Each importer is a callable that receives a raw record (dict) and returns a
payload dict suitable for emitting as a ``historical_import`` event.

The payload must be JSON‑serialisable.  If the importer can produce a stable
identifier for the record, include it under the key ``external_id`` – this is
used for duplicate detection.
"""

from __future__ import annotations

from typing import Callable, Dict, Any

# Importer callable signature
Importer = Callable[[Dict[str, Any]], Dict[str, Any]]
