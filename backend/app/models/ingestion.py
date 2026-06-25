from pydantic import BaseModel


class IngestionStartRequest(BaseModel):
    limit: int | None = None


class IngestionStartResponse(BaseModel):
    job_id: str
    status: str


class IngestionStatusResponse(BaseModel):
    job_id: str | None = None
    status: str
    total: int = 0
    processed: int = 0
    errors: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
