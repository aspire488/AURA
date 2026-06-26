"""Agent harness – lightweight registration and dispatch.

Only in‑memory registry; deterministic routing based on agent name.
"""

from __future__ import annotations

from typing import Callable, Dict, Any

# Global registry – simple dict; ponytail encourages minimal shared state.
_agent_registry: Dict[str, Callable[[Any], Any]] = {}


def register_agent(name: str, handler: Callable[[Any], Any]) -> None:
    """Register *handler* under *name*.
    ponytail: overwrite if exists – deterministic last‑write wins.
    """
    _agent_registry[name] = handler


async def dispatch_agent(name: str, payload: Any) -> Any:
    """Dispatch *payload* to the registered agent *name*.
    ponytail: raise KeyError if missing – caller must ensure registration.
    """
    if name not in _agent_registry:
        raise KeyError(f"Agent {name} not registered")
    handler = _agent_registry[name]
    # Handler may be sync or async; support both.
    result = handler(payload)
    if hasattr(result, "__await__"):
        return await result
    return result
