"""Knowledge Agent – stores/retrieves deterministic facts.

Very thin stub: echoes payload under ``knowledge`` key.
"""

from __future__ import annotations

from .base import BaseAgent

class KnowledgeAgent(BaseAgent):
    def capabilities(self):
        return ["store_fact", "retrieve_fact"]

    async def execute(self, task):
        await self.accept(task)
        return {"knowledge": task}
