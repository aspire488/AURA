from __future__ import annotations

import time
import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    model: str


class ProviderGateway:
    """Single interface for all LLM calls.

    ponytail: httpx direct call, no SDK dependency.
    Handles OpenAI and OpenRouter (same API shape).
    """

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=60.0)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        provider = settings.embedding_provider
        if provider == "openai":
            return await self._call_openai(system_prompt, user_prompt, model or "gpt-4o-mini", temperature, max_tokens)
        elif provider == "openrouter":
            return await self._call_openrouter(system_prompt, user_prompt, model or "openai/gpt-4o-mini", temperature, max_tokens)
        else:
            # Default: try OpenAI-compatible endpoint
            return await self._call_openai(system_prompt, user_prompt, model or "gpt-4o-mini", temperature, max_tokens)

    async def _call_openai(self, system: str, user: str, model: str, temp: float, max_tokens: int) -> LLMResponse:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set — cannot call LLM")
        start = time.perf_counter()
        resp = await self._client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": temp,
                "max_tokens": max_tokens,
            },
        )
        latency = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            latency_ms=round(latency, 2),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
        )

    async def _call_openrouter(self, system: str, user: str, model: str, temp: float, max_tokens: int) -> LLMResponse:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set — cannot call LLM")
        start = time.perf_counter()
        resp = await self._client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": temp,
                "max_tokens": max_tokens,
            },
        )
        latency = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            latency_ms=round(latency, 2),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", model),
        )

    async def close(self):
        await self._client.aclose()


# ponytail: module-level singleton
gateway = ProviderGateway()
