from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    app_secret: str = "dev-only-secret-change-me"
    database_url: str = "sqlite:///./docmind.db"
    redis_url: str = "redis://localhost:6379/0"
    public_api_url: str = "http://localhost:8000"
    web_origin: str = "http://localhost:3000"

    storage_backend: str = "local"
    storage_local_dir: str = "./storage"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "docmind"
    s3_region: str = "us-east-1"

    ai_mode: str = "mock"
    llm_provider: str = "mock"
    llm_model: str = "mock-grounded-v1"
    embedding_provider: str = "hash"
    embedding_model: str = "hash-384-v1"
    embedding_dimension: int = 384
    ocr_provider: str = "tesseract"
    ocr_languages: str = "ara+eng"
    reranker_provider: str = "none"

    malware_scanner: str = "noop"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None

    access_token_minutes: int = 20
    refresh_token_days: int = 30
    max_upload_mb: int = 100
    default_chunk_tokens: int = 650
    default_chunk_overlap: int = 100

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.app_env.lower() not in {"production", "staging"}:
            return self

        weak_secret = (
            len(self.app_secret) < 32
            or "change-me" in self.app_secret.lower()
            or "dev-only" in self.app_secret.lower()
        )
        if weak_secret:
            raise ValueError("APP_SECRET must be a strong production secret")
        if self.database_url.lower().startswith("sqlite"):
            raise ValueError("Production DATABASE_URL must use PostgreSQL")
        if self.storage_backend.lower() == "s3" and (
            not self.s3_access_key or not self.s3_secret_key
        ):
            raise ValueError("S3 credentials are required when STORAGE_BACKEND=s3")

        required_llm_keys = {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "groq": self.groq_api_key,
        }
        llm_key = required_llm_keys.get(self.llm_provider.lower())
        if self.llm_provider.lower() in required_llm_keys and not llm_key:
            raise ValueError(f"Credentials are required for LLM_PROVIDER={self.llm_provider}")

        required_embedding_keys = {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
        }
        embedding_key = required_embedding_keys.get(self.embedding_provider.lower())
        if self.embedding_provider.lower() in required_embedding_keys and not embedding_key:
            raise ValueError(
                f"Credentials are required for EMBEDDING_PROVIDER={self.embedding_provider}"
            )
        return self

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_local_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
