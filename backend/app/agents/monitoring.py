"""Monitoring Agent – reports health metrics.
"""

from __future__ import annotations

from .base import BaseAgent

class MonitoringAgent(BaseAgent):
    def capabilities(self):
        return ["report_metrics", "health_check"]

    async def execute(self, task):
        await self.accept(task)
        # For demo, simply return the task.
        return {"monitoring": task}
