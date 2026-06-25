from pydantic import BaseModel


class StoreRequest(BaseModel):
    role: str
    content: str
    source: str


class StoreResponse(BaseModel):
    status: str
    memory_type: str = ""
    importance: int = 0


class MemoryStatsResponse(BaseModel):
    total_chunks: int
    total_conversations: int
    duplicates_skipped: int
    short_term: int
    long_term: int
    ephemeral: int
    average_chunk_length: float
    oldest_memory: str
    newest_memory: str
