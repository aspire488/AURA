from app.config import settings

from app.providers import (
    DefaultEmbeddingProvider,
    OpenAIProvider,
    OpenRouterProvider,
)


def get_provider():
    """Return the configured embedding provider.

    The provider is chosen based on ``settings.embedding_provider``.
    Closed set of allowed values: ``default``, ``openai``, ``openrouter``.
    """
    match settings.embedding_provider:
        case "openrouter":
            return OpenRouterProvider()
        case "openai":
            return OpenAIProvider()
        case _:
            return DefaultEmbeddingProvider()
