'''Validation endpoints for pipeline and integrity checks.
Provides lightweight checks using existing services without extra dependencies.
'''

from fastapi import APIRouter, Depends
# ponytail: removed unused request model imports
from pydantic import BaseModel

# ponytail: removed direct API import
from app.core.dependencies import get_chroma, get_redis
from app.world.store import world_store
from app.belief.store import belief_store

router = APIRouter(tags=['validation'])

class StageResult(BaseModel):
    stage: str
    ok: bool
    detail: str | None = None

@router.get('/validate/pipeline', response_model=list[StageResult])
async def validate_pipeline(
    chroma: Depends = Depends(get_chroma),  # ponytail: keep typing simple, service injected via Depends
    redis: Depends = Depends(get_redis),
):
    results: list[StageResult] = []
    # health
    try:
        chroma_status, _ = await chroma.check_health()
        redis_status, _ = await redis.check_health()
        ok = chroma_status == "up" and redis_status == "up"
        detail = "healthy" if ok else f"chroma:{chroma_status},redis:{redis_status}"
        results.append(StageResult(stage='health', ok=ok, detail=detail))
    except Exception as e:
        results.append(StageResult(stage='health', ok=False, detail=str(e)))
    # retrieval (lightweight check using keyword search)
    try:
        # Use keyword search which does not require embeddings
        _ = chroma.keyword_search("validation")
        results.append(StageResult(stage='retrieval', ok=True))
    except Exception as e:
        results.append(StageResult(stage='retrieval', ok=False, detail=str(e)))
    # reasoning (basic task manager check)
    try:
        from app.runtime.task_manager import get_task_manager
        _ = get_task_manager()
        results.append(StageResult(stage='reasoning', ok=True))
    except Exception as e:
        results.append(StageResult(stage='reasoning', ok=False, detail=str(e)))
    # store (lightweight validation via delete operation)
    try:
        # Attempt a delete of a non‑existent validation record; success indicates store is reachable
        _ = chroma.delete_by_conversation_id("validation_temp")
        results.append(StageResult(stage='store', ok=True))
    except Exception as e:
        results.append(StageResult(stage='store', ok=False, detail=str(e)))
    return results

@router.get('/validate/integrity', response_model=dict)
async def validate_integrity():
    # Orphan entities: entities not referenced by any belief
    entities = await world_store.list_entities()
    entity_ids = {e.entity_id for e in entities}
    referenced = set()
    all_beliefs = await belief_store.list_all()
    for b in all_beliefs:
        referenced.update(b.entity_ids)
    orphan = entity_ids - referenced
    dup_entities = len(entities) - len({e.name for e in entities})
    dup_beliefs = len(all_beliefs) - len({b.statement for b in all_beliefs})
    rel_count = await world_store.count_relations()
    return {
        'orphan_entities': len(orphan),
        'duplicate_entities': dup_entities,
        'duplicate_beliefs': dup_beliefs,
        'total_entities': len(entities),
        'total_beliefs': len(all_beliefs),
        'total_relations': rel_count,
    }
