"""Emergence layer – read‑only synthesis of subsystem data.

Provides lightweight, deterministic insight functions without mutating any
state. All operations are async and pull directly from existing stores.
"""

import logging
from collections import Counter
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Helper to lazily import stores – avoids circular imports.
async def _load_stores() -> Dict[str, Any]:
    from app.world.store import world_store
    from app.belief.store import belief_store
    from app.memory.store import memory_store
    from app.knowledge.store import knowledge_store
    from app.opinion.store import opinion_store
    from app.goal.store import goal_store
    from app.learning.store import learning_store
    from app.continuity.store import continuity_store
    return {
        "world": world_store,
        "belief": belief_store,
        "memory": memory_store,
        "knowledge": knowledge_store,
        "opinion": opinion_store,
        "goal": goal_store,
        "learning": learning_store,
        "continuity": continuity_store,
    }


# ---------------------------------------------------------------------------
# Core aggregation – returns a simple snapshot of counts from each subsystem.
# ---------------------------------------------------------------------------
async def aggregate_subsystem_outputs(limit: int = 100) -> Dict[str, Any]:
    """Collect basic stats from all subsystems.

    Returns a dict with entity/relation counts, belief count, etc.
    """
    stores = await _load_stores()
    world = stores["world"]
    belief = stores["belief"]
    memory = stores["memory"]
    knowledge = stores["knowledge"]
    opinion = stores["opinion"]
    goal = stores["goal"]
    learning = stores["learning"]
    continuity = stores["continuity"]

    # Minimal DB round‑trips – each store already provides async count methods.
    return {
        "entities": await world.count_entities(),
        "relations": await world.count_relations(),
        "beliefs": await belief.count(),
        "memories": await memory.count(),
        "knowledge_items": await knowledge.count(),
        "opinions": await opinion.count(),
        "goals": await goal.count(),
        "learning_events": await learning.count(),
        "continuity_entries": await continuity.count(),
    }


# ---------------------------------------------------------------------------
# Insight helpers – each builds on the aggregated data.
# ---------------------------------------------------------------------------
async def identify_recurring_patterns(limit: int = 50) -> List[Dict[str, Any]]:
    """Return relations that appear repeatedly (evidence_count > 1).

    Simple heuristic: use the world relation's evidence_count field.
    """
    from app.world.store import world_store
    # Pull a sample; the store does not expose a direct list, so we query by type.
    # Get a few common types first.
    types = await world_store.find_relations_by_type("", limit=limit)  # returns all limited
    # Filter for evidence >1 and aggregate by (source, target, type).
    patterns = []
    for rel in types:
        if getattr(rel, "evidence_count", 1) > 1:
            patterns.append({
                "source": rel.source_entity,
                "target": rel.target_entity,
                "type": rel.relation_type,
                "evidence": rel.evidence_count,
            })
    return patterns[:limit]


async def identify_persistent_interests(limit: int = 20) -> List[Dict[str, Any]]:
    """Return beliefs that reference frequently‑seen entities.

    Heuristic: entities appearing in many beliefs.
    """
    from app.belief.store import belief_store
    from app.world.store import world_store
    beliefs = await belief_store.list_all(limit=limit * 5)  # oversample
    entity_counter = Counter()
    for b in beliefs:
        for eid in getattr(b, "entity_ids", []):
            entity_counter[eid] += 1
    top = entity_counter.most_common(limit)
    result = []
    for eid, cnt in top:
        entity = await world_store.get_entity(eid)
        result.append({"entity_id": eid, "name": getattr(entity, "name", ""), "belief_refs": cnt})
    return result


async def identify_long_term_trends(limit: int = 10) -> List[Dict[str, Any]]:
    """Simple trend: count of relations per type.
    """
    from app.world.store import world_store
    # Grab a sample of relation types.
    sample = await world_store.find_relations_by_type("", limit=limit * 10)
    counter = Counter(rel.relation_type for rel in sample)
    return [{"type": t, "count": c} for t, c in counter.most_common(limit)]


async def identify_strategic_opportunities(limit: int = 10) -> List[Dict[str, Any]]:
    """Entities with high outgoing relation count – potential hubs.
    """
    from app.world.store import world_store
    # We lack a direct degree query; approximate by scanning recent relations.
    relations = await world_store.find_relations_by_type("", limit=limit * 20)
    out_counter = Counter(rel.source_entity for rel in relations)
    top = out_counter.most_common(limit)
    result = []
    for eid, cnt in top:
        entity = await world_store.get_entity(eid)
        result.append({"entity_id": eid, "name": getattr(entity, "name", ""), "out_degree": cnt})
    return result


async def identify_behavioral_drift(limit: int = 10) -> List[Dict[str, Any]]:
    """Placeholder – drift detection not implemented.
    """
    # ponytail: drift analysis requires time‑series; return empty.
    return []


async def expose_compound_insights(limit: int = 5) -> List[Dict[str, Any]]:
    """Combine several basic insights into a single report.
    """
    patterns = await identify_recurring_patterns(limit)
    interests = await identify_persistent_interests(limit)
    trends = await identify_long_term_trends(limit)
    opportunities = await identify_strategic_opportunities(limit)
    return [{
        "recurring_patterns": patterns,
        "persistent_interests": interests,
        "long_term_trends": trends,
        "strategic_opportunities": opportunities,
    }]

# End of emergence manager – deterministic, read‑only, no new dependencies.
