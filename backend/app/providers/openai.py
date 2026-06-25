import httpx

from app.config import settings
from .base import EmbeddingProvider


class OpenAIProvider(EmbeddingProvider):
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self.model = settings.openai_embedding_model
        self.client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.post(
            "/embeddings",
            json={"input": texts, "model": self.model},
        )
        response.raise_for_status()
        data = response.json()
        sorted_results = sorted(data["data"], key=lambda x: x["index"])
        return [r["embedding"] for r in sorted_results]
