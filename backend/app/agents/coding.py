"""Coding Agent – placeholder for code generation/execution.
"""

from __future__ import annotations

from .base import BaseAgent

class CodingAgent(BaseAgent):
    def capabilities(self):
        return ["generate_code", "run_code"]

    async def execute(self, task):
        await self.accept(task)
        return {"coding": task}
