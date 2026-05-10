from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    LITELLM_API_KEY: str = ""
    LITELLM_BASE_URL: str = "https://litellm.cyhkbl.qzz.io"
    LITELLM_MODEL: str = "mimo-v2.5-pro"
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8100
    FRONTEND_URL: str = "http://localhost:8200"
    DATA_DIR: str = "./data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings singleton."""

    return Settings()
