from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryResult(BaseModel):
    chunk_id: str = ""
    text: str
    score: float
    conversation_id: str
    role: str
    timestamp: str = ""


class QueryResponse(BaseModel):
    results: list[QueryResult]


class ContextRequest(BaseModel):
    query: str
    top_k: int = 10
    max_tokens: int = 2000


class ContextChunkResponse(BaseModel):
    chunk_id: str
    text: str
    score: float
    conversation_id: str
    role: str
    citation: str


class ContextResponse(BaseModel):
    query_type: str
    context: str
    citations: list[str]
    chunks: list[ContextChunkResponse]
    estimated_tokens: int
