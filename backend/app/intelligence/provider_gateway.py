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
    """Single interface for all LLM calls with automatic fallback.

    ponytail: httpx direct call, no SDK dependency.
    Tries providers in priority order on failure.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=settings.provider_timeout_seconds)
        self._provider_failures: dict[str, int] = {}
        self._provider_fallbacks: int = 0

    def _get_priority_list(self) -> list[str]:
        """Return provider names in priority order. ponytail: comma-separated config."""
        return [p.strip() for p in settings.provider_priority.split(",") if p.strip()]

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Try providers in priority order. ponytail: fallback on failure."""
        errors = []
        for provider_name in self._get_priority_list():
            try:
                result = await self._call_provider(
                    provider_name, system_prompt, user_prompt, model, temperature, max_tokens
                )
                return result
            except Exception as e:
                self._provider_failures[provider_name] = self._provider_failures.get(provider_name, 0) + 1
                self._provider_fallbacks += 1
                logger.warning("Provider %s failed: %s, trying next", provider_name, e)
                errors.append(f"{provider_name}: {e}")
        raise RuntimeError(f"All providers failed: {'; '.join(errors)}")

    async def _call_provider(
        self,
        provider_name: str,
        system: str,
        user: str,
        model: str,
        temp: float,
        max_tokens: int,
    ) -> LLMResponse:
        if provider_name == "openai":
            return await self._call_openai(system, user, model or "gpt-4o-mini", temp, max_tokens)
        elif provider_name == "openrouter":
            return await self._call_openrouter(system, user, model or "openai/gpt-4o-mini", temp, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    async def _call_openai(self, system: str, user: str, model: str, temp: float, max_tokens: int) -> LLMResponse:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
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
            raise ValueError("OPENROUTER_API_KEY not set")
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

    def health(self) -> dict:
        return {
            "provider_failures": dict(self._provider_failures),
            "provider_fallbacks": self._provider_fallbacks,
        }

    async def close(self):
        await self._client.aclose()


# ponytail: module-level singleton
gateway = ProviderGateway()
