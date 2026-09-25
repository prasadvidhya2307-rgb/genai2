"""Pydantic request and response models for the HTTP API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


SourceType = Literal["pdf", "website", "youtube"]


class SourceMetadata(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    source_url: str | None = None
    created_at: datetime
    page_count: int | None = None
    language_code: str | None = None
    video_id: str | None = None


class SourceResponse(BaseModel):
    message: str
    source: SourceMetadata
    chunks_created: int


class SourceDeleteResponse(BaseModel):
    message: str
    source_id: str
    deleted_chunks: int


class WebsiteSourceRequest(BaseModel):
    url: HttpUrl


class YouTubeSourceRequest(BaseModel):
    url: HttpUrl


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] | None = Field(default=None, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value

    @field_validator("source_ids")
    @classmethod
    def clean_source_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not cleaned:
            raise ValueError("source_ids must contain at least one non-empty ID")
        return cleaned


class ChatSource(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    source_url: str | None = None
    relevant_chunks: int
    chunk_indices: list[int] = Field(default_factory=list)
    page_numbers: list[int] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    google_api_key_configured: bool
