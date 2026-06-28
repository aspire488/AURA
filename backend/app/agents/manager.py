"""Agent Layer – registration, lifecycle, scheduling, capability & permission handling.

All agents conform to the minimal contract:
    initialize()
    health()
    capabilities()
    accept(task)
    execute(task)
    cancel(task)
    resume(task)
    shutdown()

The manager wires agents into the existing ``agent_harness``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.agent_harness.manager import (
    register_agent,
    register_agent_capability,
    dispatch_agent,
    agent_health,
    _metrics as agent_metrics,
)

# Simple permission map – agent name -> allowed capability prefixes
_PERMISSION_MAP: Dict[str, List[str]] = {
    # Example: "research": ["search", "summarize"],
    # Populate as needed; default deny.
}

logger = logging.getLogger(__name__)

class AgentLifecycleManager:
    """Manage start‑up and shutdown of all registered agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}

    def register(self, name: str, agent: Any, capabilities: List[str] | None = None) -> None:
        """Register an agent instance and its capabilities.
        The handler passed to the harness simply forwards the payload to
        ``agent.execute``.
        """
        async def handler(payload: Any) -> Any:
            return await agent.execute(payload)

        register_agent(name, handler)
        if capabilities:
            register_agent_capability(name, capabilities)
        self._agents[name] = agent
        logger.debug("Agent %s registered with capabilities %s", name, capabilities)

    async def initialize_all(self) -> None:
        for name, agent in self._agents.items():
            if hasattr(agent, "initialize"):
                await maybe_await(agent.initialize())
                logger.debug("Agent %s initialized", name)

    async def shutdown_all(self) -> None:
        for name, agent in self._agents.items():
            if hasattr(agent, "shutdown"):
                await maybe_await(agent.shutdown())
                logger.debug("Agent %s shut down", name)


async def maybe_await(result: Any) -> Any:
    """Utility to await coroutines or return plain values."""
    if asyncio.iscoroutine(result):
        return await result
    return result

# Scheduler – event‑driven, delayed, or immediate dispatch
class AgentScheduler:
    """Very lightweight scheduler using ``asyncio``.
    Supports:
        * immediate (default)
        * delay in seconds
        * periodic (simple repeat with interval)
    """

    def __init__(self) -> None:
        self._tasks: List[asyncio.Task] = []

    def schedule(
        self,
        name: str,
        payload: Any,
        *,
        delay: float | None = None,
        interval: float | None = None,
        retries: int = 0,
        timeout: float | None = None,
    ) -> None:
        async def _job() -> None:
            if delay:
                await asyncio.sleep(delay)
            while True:
                try:
                    await dispatch_agent(name, payload, timeout=timeout, retries=retries)
                except Exception as exc:
                    logger.exception("Agent %s failed: %s", name, exc)
                if interval is None:
                    break
                await asyncio.sleep(interval)
        task = asyncio.create_task(_job())
        self._tasks.append(task)

    async def cancel_all(self) -> None:
        for t in self._tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

# Permission manager – simple prefix check
class AgentPermissionManager:
    @staticmethod
    def is_allowed(agent_name: str, capability: str) -> bool:
        allowed = _PERMISSION_MAP.get(agent_name, [])
        return any(capability.startswith(pfx) for pfx in allowed)

# Capability resolver – reads from harness registry
class AgentCapabilityResolver:
    @staticmethod
    def get_capabilities(agent_name: str) -> List[str]:
        # Direct import of internal dict – acceptable for internal use
        from app.agent_harness.manager import _capability_registry
        return _capability_registry.get(agent_name, [])

# Health monitor – aggregates harness health and agent health
def aggregate_health() -> Dict[str, Any]:
    health = agent_health()
    # Extend with per‑agent health if needed
    return health

# Metrics – expose harness counters
def get_metrics() -> Dict[str, int]:
    return agent_metrics.copy()
