from pydantic import BaseModel


class ReasonRequest(BaseModel):
    query: str


class ReasonResponse(BaseModel):
    intent: str
    query_type: str
    answer: str
    citations: list[str]
    warnings: list[str]
    latency_ms: float
