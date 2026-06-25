from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    parameters: dict = field(default_factory=dict)


class ToolRegistry:
    """Register and lookup tools by name.

    ponytail: dict lookup. No execution logic, no validation.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, handler: Callable, parameters: dict | None = None) -> None:
        self._tools[name] = Tool(name=name, description=description, handler=handler, parameters=parameters or {})

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.handler(**kwargs)


# ponytail: module-level singleton
registry = ToolRegistry()
