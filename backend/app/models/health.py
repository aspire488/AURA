from pydantic import BaseModel


class ServiceStatus(BaseModel):
    status: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, ServiceStatus]
    uptime_seconds: float | None = None
    process_id: int | None = None
    python_version: str | None = None
    memory_usage_mb: float | None = None
