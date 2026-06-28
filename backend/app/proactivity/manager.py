"""Proactivity manager – deterministic triggers for opportunities and stalled goals.

Implemented as pure functions; no DB persistence needed for this minimal runtime.
"""

from __future__ import annotations
from typing import List

async def detect_opportunities() -> List[str]:
    """Return a list of simple opportunity strings.
    ponytail: placeholder – returns empty list; extend when needed.
    """
    return []
