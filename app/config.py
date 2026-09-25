"""Application configuration loaded from environment variables and .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Settings for the application.

    The Google API key is deliberately represented as a SecretStr so it is
    masked if a settings object is logged or printed.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "RAG source chat API"
    google_api_key: SecretStr = Field(default=SecretStr(""))

    # These can be changed in .env without changing application code.
    gemini_chat_model: str = "gemini-3.5-flash"
    google_embedding_model: str = "gemini-embedding-001"

    chroma_persist_directory: Path = PROJECT_ROOT / "chroma_data"
    chroma_collection_name: str = "rag_sources"

    chunk_size: int = Field(default=1000, ge=200, le=8000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)
    default_top_k: int = Field(default=5, ge=1, le=20)

    max_pdf_size_mb: int = Field(default=20, ge=1, le=200)
    max_website_size_mb: int = Field(default=5, ge=1, le=50)
    website_timeout_seconds: float = Field(default=20.0, ge=1, le=120)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
    )

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, value: int, info) -> int:
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and value >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return value

    @field_validator("chroma_persist_directory", mode="after")
    @classmethod
    def resolve_chroma_directory(cls, value: Path) -> Path:
        if not value.is_absolute():
            return (PROJECT_ROOT / value).resolve()
        return value

    @property
    def google_api_key_value(self) -> str | None:
        """Return the key only for server-side SDK construction."""

        value = self.google_api_key.get_secret_value().strip()
        return value or None

    @property
    def max_pdf_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def max_website_bytes(self) -> int:
        return self.max_website_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the process."""

    return Settings()
