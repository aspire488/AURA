from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ponytail: load Docker secret if env var missing
    def _load_secret(self, name: str) -> str:
        val = getattr(self, name, None)
        if val:
            return val
        # try Docker secret file
        secret_path = f"/run/secrets/{name}"  # secrets are named same as env var without prefix
        try:
            with open(secret_path) as f:
                return f.read().strip()
        except Exception:
            return ""

    model_config = SettingsConfigDict(env_prefix="AURA_", env_file=".env")

    version: str = "0.1.0"

    chroma_host: str = "localhost"
    chroma_port: int = 8000

    redis_host: str = "localhost"
    redis_port: int = 6379

    embedding_provider: str = "default"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"

    openrouter_api_key: str = ""
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    postgres_url: str = "sqlite+aiosqlite:///./data/aura.db"
    filesystem_root: str = "./data"  # ponytail: use local writable dir

    n8n_webhook_url: str = "http://localhost:5678/webhook"

    # Provider resilience. ponytail: comma-separated priority list.
    provider_priority: str = "openai,openrouter,gemini,groq,cerebras,github,gmail,google_calendar,google_drive,discord,telegram,whatsapp,notion,slack,dropbox"
    provider_timeout_seconds: float = 30.0

    # Rate limiting
    rate_limit_rpm: int = 60
    encryption_key: str = ""

    def validate_settings(self):
        errors = []
        if self.chroma_port < 1 or self.chroma_port > 65535:
            errors.append(f"Invalid AURA_CHROMA_PORT: {self.chroma_port}")
        if self.redis_port < 1 or self.redis_port > 65535:
            errors.append(f"Invalid AURA_REDIS_PORT: {self.redis_port}")
        if errors:
            raise ValueError("Configuration error: " + "; ".join(errors))

    async def validate_runtime(self) -> list[str]:
        """Async startup checks. ponytail: fail-fast on bad config."""
        errors = []

        # filesystem_root
        root = Path(self.filesystem_root)
        if not root.exists():
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"filesystem_root {self.filesystem_root} not accessible: {e}")

        # Provider URLs
        for name, url in [("openai", self.openai_base_url), ("openrouter", self.openrouter_base_url)]:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                errors.append(f"{name} URL invalid: {url}")

        # Redis
        try:
            import redis.asyncio as aioredis
            client = aioredis.Redis(host=self.redis_host, port=self.redis_port, socket_timeout=3)
            await client.ping()
            await client.aclose()
        except Exception as e:
            errors.append(f"Redis unreachable at {self.redis_host}:{self.redis_port}: {e}")

        # Chroma
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://{self.chroma_host}:{self.chroma_port}/api/v1/heartbeat")
                if resp.status_code >= 500:
                    errors.append(f"Chroma unhealthy at {self.chroma_host}:{self.chroma_port}")
        except Exception as e:
            errors.append(f"Chroma unreachable at {self.chroma_host}:{self.chroma_port}: {e}")

        return errors

settings = Settings()
