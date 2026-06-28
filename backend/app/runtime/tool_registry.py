from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Dict
import inspect


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

    async def execute(self, name: str, identity_id: str | None = None, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Unknown tool: {name}")
        # Validate required parameters based on registration and handler signature
        # 1. Ensure all declared parameters are provided
        missing_params = [p for p in tool.parameters.keys() if p not in kwargs]
        if missing_params:
            raise ValueError(f"Missing required arguments {missing_params} for tool '{name}'")
        # 2. Type checking using handler annotations (if any)
        sig = inspect.signature(tool.handler)
        for param_name, param in sig.parameters.items():
            if param_name == "identity_id":
                continue  # handled separately
            if param_name in kwargs and param.annotation is not param.empty:
                expected = param.annotation
                # Allow None for optional args
                if kwargs[param_name] is not None and not isinstance(kwargs[param_name], expected):
                    raise ValueError(
                        f"Argument '{param_name}' for tool '{name}' expected type {expected.__name__}, "
                        f"got {type(kwargs[param_name]).__name__}"
                    )
        # Inject identity_id if the handler accepts it
        if identity_id is not None and "identity_id" in sig.parameters:
            kwargs["identity_id"] = identity_id
        # Timing and stats collection
        import time
        start = time.perf_counter()
        success = True
        try:
            result = await tool.handler(**kwargs)
        except Exception as e:
            success = False
            raise e
        finally:
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            if name not in _tool_stats:
                _tool_stats[name] = {
                    "execution_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "total_latency_ms": 0.0,
                    "last_success": 0.0,
                    "last_failure": 0.0,
                }
            stats = _tool_stats[name]
            stats["execution_count"] += 1
            stats["total_latency_ms"] += elapsed
            if success:
                stats["success_count"] += 1
                stats["last_success"] = time.time()
            else:
                stats["failure_count"] += 1
                stats["last_failure"] = time.time()
        return result


# ponytail: module-level singleton
registry = ToolRegistry()
# Simple stats tracking per tool
_tool_stats: Dict[str, dict] = {}
