"""Browser Agent – interacts with the browser via the existing tool.
"""

from __future__ import annotations

from .base import BaseAgent

class BrowserAgent(BaseAgent):
    def capabilities(self):
        return ["open_url", "click", "type"]

    async def execute(self, task):
        await self.accept(task)
        return {"browser": task}
