"""Orchestrator Agent – coordinates high‑level tasks.

In this minimalist implementation it simply forwards the payload unchanged.
"""

from __future__ import annotations

from .base import BaseAgent

class OrchestratorAgent(BaseAgent):
    def capabilities(self):
        return ["orchestrate"]

    async def execute(self, task):
        # In a full system this would spawn sub‑agents; here we echo.
        await self.accept(task)
        return {"orchestrated": task}
