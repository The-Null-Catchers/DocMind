from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_local_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
