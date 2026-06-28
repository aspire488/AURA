"""Planning Agent – creates plans from goals.
"""

from __future__ import annotations

from .base import BaseAgent

class PlanningAgent(BaseAgent):
    def capabilities(self):
        return ["create_plan", "update_plan"]

    async def execute(self, task):
        await self.accept(task)
        return {"plan": task}
