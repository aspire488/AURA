"""Agent harness – lightweight registration and dispatch.

Only in‑memory registry; deterministic routing based on agent name.

Extended with minimal capability lookup, health monitoring, execution history,
 timeout, cancellation, simple retry, and dispatch metrics.
"""

from __future__ import annotations

from typing import Callable, Dict, Any

# Global registry – simple dict; ponytail encourages minimal shared state.
_agent_registry: Dict[str, Callable[[Any], Any]] = {}

# Capability registry – name -> list of capability strings
_capability_registry: Dict[str, list[str]] = {}

# Execution history – simple list of dicts
_execution_history: list[dict] = []

# Metrics counters
_metrics = {
    "dispatch_total": 0,
    "dispatch_success": 0,
    "dispatch_failure": 0,
}

# Cancellation support – map name to asyncio.Task
import asyncio
_active_tasks: Dict[str, asyncio.Task] = {}



def register_agent(name: str, handler: Callable[[Any], Any]) -> None:
    """Register *handler* under *name*.
    ponytail: overwrite if exists – deterministic last‑write wins.
    """
    _agent_registry[name] = handler

def register_agent_capability(name: str, capabilities: list[str]) -> None:
    """Associate *capabilities* with an agent name.
    ponytail: overwrite existing list.
    """
    _capability_registry[name] = capabilities


async def dispatch_agent(name: str, payload: Any, *, timeout: float | None = None, retries: int = 0) -> Any:
    """Dispatch *payload* to the registered agent *name*.
    Supports optional *timeout* (seconds) and simple *retries*.
    ponytail: raise KeyError if missing – caller must ensure registration.
    """
    if name not in _agent_registry:
        raise KeyError(f"Agent {name} not registered")
    _metrics["dispatch_total"] += 1
    handler = _agent_registry[name]
    async def _run() -> Any:
        result = handler(payload)
        if hasattr(result, "__await__"):
            return await result
        return result
    attempt = 0
    while True:
        try:
            if timeout is not None:
                task = asyncio.create_task(_run())
                _active_tasks[name] = task
                res = await asyncio.wait_for(task, timeout)
            else:
                res = await _run()
            _metrics["dispatch_success"] += 1
            # Record success
            record_execution(name, payload, res, True)
            return res
        except Exception as e:
            _metrics["dispatch_failure"] += 1
            # Record failure
            record_execution(name, payload, str(e), False)
            attempt += 1
            if attempt > retries:
                raise e
            # simple back‑off not implemented – immediate retry
        finally:
            _active_tasks.pop(name, None)
    
    # unreachable

# Health monitoring
def agent_health() -> dict:
    """Return basic health snapshot.
    ponytail: deterministic reporting.
    """
    return {
        "registered_agents": len(_agent_registry),
        "capability_entries": len(_capability_registry),
        "active_tasks": len(_active_tasks),
    }

# Execution history utilities
def record_execution(name: str, payload: Any, result: Any, success: bool) -> None:
    _execution_history.append({
        "name": name,
        "payload": payload,
        "result": result,
        "success": success,
        "timestamp": asyncio.get_event_loop().time(),
    })
