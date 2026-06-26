"""Skill system – register and execute deterministic skill functions.

Each skill has a version string and a callable. Minimal implementation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

_skill_registry: Dict[str, Tuple[str, Callable[[Any], Any]]] = {}


def register_skill(name: str, version: str, handler: Callable[[Any], Any]) -> None:
    """Register a skill with *name*, *version*, and callable *handler*.
    ponytail: overwrite on conflict – deterministic last registration wins.
    """
    _skill_registry[name] = (version, handler)


async def execute_skill(name: str, payload: Any) -> Any:
    """Execute registered skill *name* with *payload*.
    ponytail: raise KeyError if not found.
    """
    if name not in _skill_registry:
        raise KeyError(f"Skill {name} not registered")
    version, handler = _skill_registry[name]
    result = handler(payload)
    if hasattr(result, "__await__"):
        return await result
    return result


def list_skills() -> Dict[str, str]:
    """Return mapping of skill name to version."""
    return {name: ver for name, (ver, _) in _skill_registry.items()}
