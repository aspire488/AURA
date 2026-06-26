"""Skill system – register and execute deterministic skill functions.

Each skill has a version string and a callable. Minimal implementation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple, List

_skill_registry: Dict[str, Tuple[str, Callable[[Any], Any]]] = {}
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
    result = handler(payload)
    if hasattr(result, "__await__"):
        res = await result
    else:
        res = result
    # Record usage metric
    _skill_usage[name] = _skill_usage.get(name, 0) + 1
    return res


def list_skills() -> Dict[str, str]:
    """Return mapping of skill name to version."""
    return {name: ver for name, (ver, _) in _skill_registry.items()}

def get_skill_info(name: str) -> dict:
    """Return full info for a skill, including metadata and usage."""
    if name not in _skill_registry:
        raise KeyError(f"Skill {name} not registered")
    version, _ = _skill_registry[name]
    meta = _skill_metadata.get(name, {})
    usage = _skill_usage.get(name, 0)
    return {"name": name, "version": version, "metadata": meta, "usage": usage}

def list_skills_by_category(category: str) -> List[str]:
    """Return skill names belonging to *category* (case‑sensitive)."""
    return [n for n, meta in _skill_metadata.items() if category in meta.get("categories", [])]
