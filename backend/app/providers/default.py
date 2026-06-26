import logging

import chromadb.utils.embedding_functions as ef

from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


class DefaultEmbeddingProvider(EmbeddingProvider):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        logger.info("EMBED: __init__ start")
        self._ef = ef.DefaultEmbeddingFunction()
        logger.info("EMBED: __init__ end")


    async def embed(self, texts: list[str]) -> list[list[float]]:
        logger.info("EMBED: start")
        result = self._ef(texts)
        if result is None:
            raise RuntimeError("Default embedding function returned None")
        logger.info("EMBED: end")
        return result
