from pydantic import BaseModel


class StoreRequest(BaseModel):
    role: str
    content: str
    source: str


class StoreResponse(BaseModel):
    status: str
