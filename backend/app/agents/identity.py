"""Identity Agent – resolves user/project identities.
"""

from __future__ import annotations

from .base import BaseAgent

class IdentityAgent(BaseAgent):
    def capabilities(self):
        return ["resolve_identity", "list_identities"]

    async def execute(self, task):
        await self.accept(task)
        return {"identity": task}
