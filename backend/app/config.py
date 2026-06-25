from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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

    # Added for substrate lifecycle
    postgres_url: str = ""
    filesystem_root: str = "/var/aura"

    def validate_settings(self):
        errors = []
        if self.chroma_port < 1 or self.chroma_port > 65535:
            errors.append(f"Invalid AURA_CHROMA_PORT: {self.chroma_port}")
        if self.redis_port < 1 or self.redis_port > 65535:
            errors.append(f"Invalid AURA_REDIS_PORT: {self.redis_port}")
        if errors:
            raise ValueError("Configuration error: " + "; ".join(errors))

settings = Settings()
