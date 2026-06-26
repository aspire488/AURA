'''Validation endpoints for pipeline and integrity checks.
Provides lightweight checks using existing services without extra dependencies.
'''

from fastapi import APIRouter, Depends
from app.models.query import QueryRequest
from app.models.reason import ReasonRequest
from app.models.store import StoreRequest
from pydantic import BaseModel

from app.api.health import health
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
        hr = await health(chroma=chroma, redis=redis)
        ok = hr.status == 'healthy'
        results.append(StageResult(stage='health', ok=ok, detail=hr.status))
    except Exception as e:
        results.append(StageResult(stage='health', ok=False, detail=str(e)))
    # retrieval (direct provider embed and chroma query)
    try:
        from app.providers.factory import get_provider
        provider = get_provider()
        embeddings = await provider.embed(["test"])
        # Perform a simple chroma query to ensure it works
        _ = chroma.query(embeddings[0], top_k=1)
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
    # store (direct chroma upsert using provider embed)
    try:
        from app.providers.factory import get_provider
        provider = get_provider()
        embeddings = await provider.embed(["validation entry"])
        doc_id = "validation_doc"
        chroma.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=["validation entry"],
            metadatas=[{"source": "validation"}],
        )
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
