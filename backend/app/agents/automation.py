"""Automation Agent – runs automated workflows.
"""

from __future__ import annotations

from .base import BaseAgent

class AutomationAgent(BaseAgent):
    def capabilities(self):
        return ["run_workflow", "trigger"]

    async def execute(self, task):
        await self.accept(task)
        return {"automation": task}
