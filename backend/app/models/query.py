from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryResult(BaseModel):
    text: str
    score: float
    conversation_id: str
    role: str


class QueryResponse(BaseModel):
    results: list[QueryResult]
