import httpx

from app.config import settings
from .base import EmbeddingProvider


class OpenRouterProvider(EmbeddingProvider):
    def __init__(self):
        self.model = settings.openrouter_embedding_model
        self.client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
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
