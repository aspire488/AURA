"""Skill system – register and execute deterministic skill functions.

Each skill has a version string and a callable. Minimal implementation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple, List

_skill_registry: Dict[str, Tuple[str, Callable[[Any], Any]]] = {}
# Stats for each skill – execution count, success/failure, latency, timestamps
_skill_stats: Dict[str, dict] = {}
# Metadata registry: name -> dict with optional fields
_skill_metadata: Dict[str, dict] = {}
# Usage counters
_skill_usage: Dict[str, int] = {}



def register_skill(
    name: str,
    version: str,
    handler: Callable[[Any], Any],
    *,
    metadata: dict | None = None,
    categories: list[str] | None = None,
    aliases: list[str] | None = None,
    dependencies: list[str] | None = None,
) -> None:
    """Register a skill with *name*, *version*, and callable *handler*.
    ponytail: overwrite on conflict – deterministic last registration wins.
    """
    if not callable(handler):
        raise TypeError("handler must be callable")
    _skill_registry[name] = (version, handler)
    _skill_metadata[name] = {
        "metadata": metadata or {},
        "categories": categories or [],
        "aliases": aliases or [],
        "dependencies": dependencies or [],
    }
    _skill_usage[name] = 0


async def execute_skill(name: str, payload: Any) -> Any:
    """Execute registered skill *name* with *payload*.
    ponytail: raise KeyError if not found.
    """
    if name not in _skill_registry:
        raise KeyError(f"Skill {name} not registered")
    version, handler = _skill_registry[name]
    # Simple dependency check – ensure dependent skills are registered
    deps = _skill_metadata.get(name, {}).get("dependencies", [])
    missing = [d for d in deps if d not in _skill_registry]
    if missing:
        raise KeyError(f"Skill {name} missing dependencies: {missing}")
    # Timing start
    import time
    start = time.perf_counter()
    success = True
    try:
        result = handler(payload)
        if hasattr(result, "__await__"):
            res = await result
        else:
            res = result
    except Exception as e:
        success = False
        res = None
        raise e
    finally:
        elapsed = round((time.perf_counter() - start) * 1000, 2)  # ms
        # Initialize stats dict if missing
        if name not in _skill_stats:
            _skill_stats[name] = {
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "total_latency_ms": 0.0,
                "last_success": 0.0,
                "last_failure": 0.0,
            }
        stats = _skill_stats[name]
        stats["execution_count"] += 1
        stats["total_latency_ms"] += elapsed
        if success:
            stats["success_count"] += 1
            stats["last_success"] = time.time()
        else:
            stats["failure_count"] += 1
            stats["last_failure"] = time.time()
    # Record usage metric (kept for backward compatibility)
    _skill_usage[name] = _skill_usage.get(name, 0) + 1
    return res


def list_skills() -> Dict[str, str]:
    """Return mapping of skill name to version."""
    return {name: ver for name, (ver, _) in _skill_registry.items()}

def get_skill_info(name: str) -> dict:
    """Return full info for a skill, including execution stats.
    ponytail: expose only required fields.
    """
    if name not in _skill_registry:
        raise KeyError(f"Skill {name} not registered")
    version, handler = _skill_registry[name]
    # Gather stats, ensure entry exists
    stats = _skill_stats.get(name, {
        "execution_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "total_latency_ms": 0.0,
        "last_success": 0.0,
        "last_failure": 0.0,
    })
    avg_latency = (stats["total_latency_ms"] / stats["execution_count"]) if stats["execution_count"] else 0.0
    return {
        "id": name,
        "name": name,
        "version": version,
        "handler": handler,
        "supported_capabilities": _skill_metadata.get(name, {}).get("categories", []),
        "execution_count": stats["execution_count"],
        "success_count": stats["success_count"],
        "failure_count": stats["failure_count"],
        "average_latency_ms": avg_latency,
        "last_success": stats["last_success"],
        "last_failure": stats["last_failure"],
    }

def list_skills_by_category(category: str) -> List[str]:
    """Return skill names belonging to *category* (case‑sensitive)."""
    return [n for n, meta in _skill_metadata.items() if category in meta.get("categories", [])]
