'''Validation endpoints for pipeline and integrity checks.
Provides lightweight checks using existing services without extra dependencies.
'''

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.health import health
from app.api.retrieval import query_endpoint
from app.api.reason import reason_endpoint
from app.api.store import store_memory
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
    chroma: Depends = Depends(get_chroma),
    redis: Depends = Depends(get_redis),
):
    results: list[StageResult] = []
    # health
    try:
        hr = await health()
        ok = hr.status == 'healthy'
        results.append(StageResult(stage='health', ok=ok, detail=hr.status))
    except Exception as e:
        results.append(StageResult(stage='health', ok=False, detail=str(e)))
    # retrieval
    try:
        await query_endpoint(body={'query': 'test', 'top_k': 1}, chroma=chroma)
        results.append(StageResult(stage='retrieval', ok=True))
    except Exception as e:
        results.append(StageResult(stage='retrieval', ok=False, detail=str(e)))
    # reasoning
    try:
        await reason_endpoint(body={'query': 'What time is it?', 'session_id': 'val_test', 'stream': False}, request=None)
        results.append(StageResult(stage='reasoning', ok=True))
    except Exception as e:
        results.append(StageResult(stage='reasoning', ok=False, detail=str(e)))
    # store
    try:
        sr = await store_memory(body={'role': 'user', 'content': 'validation entry', 'source': 'validation'}, chroma=chroma, redis=redis)
        results.append(StageResult(stage='store', ok=sr.status == 'stored'))
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
