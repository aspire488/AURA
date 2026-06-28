from fastapi import APIRouter, HTTPException
from typing import List, Dict

from app.events.dlq_store import list_entries, remove

router = APIRouter(prefix="/dlq", tags=["dlq"])

@router.get("/", response_model=List[Dict])
async def get_dlq():
    return list_entries()

@router.post("/ack")
async def ack_dlq(entry_id: str):
    if not remove(entry_id):
        raise HTTPException(status_code=404, detail="DLQ entry not found")
    return {"status": "removed", "id": entry_id}
