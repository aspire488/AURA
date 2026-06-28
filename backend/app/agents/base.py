"""Base class for all AURA agents.

Each agent must implement the minimal contract. The base provides default
no‑op implementations so concrete agents only override what they need.
"""

from __future__ import annotations

import asyncio
from typing import Any, List

class BaseAgent:
    def __init__(self) -> None:
        self._current_task: Any = None
        self._cancel_event = asyncio.Event()

    async def initialize(self) -> None:
        """Prepare resources – default does nothing."""
        pass

    def health(self) -> dict:
        """Return simple health snapshot."""
        return {"status": "ok"}

    def capabilities(self) -> List[str]:
        """List capability strings – override in subclass."""
        return []

    async def accept(self, task: Any) -> None:
        self._current_task = task
        self._cancel_event.clear()

    async def execute(self, task: Any) -> Any:
        """Execute the given *task* and return a result.
        Sub‑classes should implement real work; the base simply returns the
        payload unchanged.
        """
        await self.accept(task)
        return task

    async def cancel(self, task: Any) -> None:
        self._cancel_event.set()
        self._current_task = None

    async def resume(self, task: Any) -> Any:
        # Simple resume – re‑execute if not cancelled
        if self._cancel_event.is_set():
            raise RuntimeError("Task was cancelled")
        return await self.execute(task)

    async def shutdown(self) -> None:
        await self.cancel(self._current_task)
