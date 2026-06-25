from pydantic import BaseModel


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    updated_at: str


class ConversationListResponse(BaseModel):
    total: int
    items: list[ConversationSummary]


class ConversationChunk(BaseModel):
    chunk_id: str
    text: str
    role: str
    timestamp: str


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    title: str
    source: str
    created_at: str
    updated_at: str
    message_count: int
    summary: str | None = None
    messages: list[ConversationChunk]
    chunk_count: int
