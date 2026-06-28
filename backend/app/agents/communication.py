"""Communication Agent – sends messages via configured channels.
"""

from __future__ import annotations

from .base import BaseAgent

class CommunicationAgent(BaseAgent):
    def capabilities(self):
        return ["send_message", "receive"]

    async def execute(self, task):
        await self.accept(task)
        return {"communication": task}
