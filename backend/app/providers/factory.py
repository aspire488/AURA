from app.config import settings

from app.providers import (
    DefaultEmbeddingProvider,
    OpenAIProvider,
    OpenRouterProvider,
)


_cached_provider = None

def get_provider():
    """Return cached embedding provider, instantiate once on first call."""
    global _cached_provider
    if _cached_provider is None:
        match settings.embedding_provider:
            case "openrouter":
                _cached_provider = OpenRouterProvider()
            case "openai":
                _cached_provider = OpenAIProvider()
            case _:
                _cached_provider = DefaultEmbeddingProvider()
    return _cached_provider
