from __future__ import annotations

from app.intelligence.provider_gateway import gateway, LLMResponse
from app.providers.factory import get_provider


class ProviderAdapter:
    """Clean interface over embedding + LLM providers.

    ponytail: delegates to existing gateway and provider factory.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        return await gateway.complete(system_prompt, user_prompt, model, temperature, max_tokens)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        provider = get_provider()
        return await provider.embed(texts)

    async def health(self) -> dict:
        try:
            provider = get_provider()
            await provider.embed(["health check"])
            return {"status": "up"}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    async def close(self):
        await gateway.close()
