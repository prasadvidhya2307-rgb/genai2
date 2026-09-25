"""Version 1 HTTP routes."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.config import Settings, get_settings
from app.dependencies import get_chat_service, get_ingestion_service
from app.errors import SourceNotFoundError, SourceValidationError
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SourceDeleteResponse,
    SourceResponse,
    WebsiteSourceRequest,
    YouTubeSourceRequest,
)
from app.services.chat import ChatService
from app.services.extractors import extract_pdf, extract_website, extract_youtube
from app.services.ingestion import IngestionService


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Report process health without calling Google or exposing credentials."""

    return HealthResponse(
        service=settings.app_name,
        google_api_key_configured=bool(settings.google_api_key_value),
    )


@router.post(
    "/sources/pdf",
    response_model=SourceResponse,
    status_code=201,
    tags=["sources"],
)
def ingest_pdf(
    file: UploadFile = File(...),
    service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings),
) -> SourceResponse:
    """Extract, chunk, embed, and persist a PDF upload."""

    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise SourceValidationError("The uploaded file must have a .pdf extension.")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        raise SourceValidationError("The uploaded file must be a PDF.")

    content = file.file.read(settings.max_pdf_bytes + 1)
    if len(content) > settings.max_pdf_bytes:
        raise SourceValidationError(
            f"The PDF is larger than the {settings.max_pdf_size_mb} MB limit."
        )
    extracted = extract_pdf(content, filename)
    return service.ingest(extracted, "pdf")


@router.post(
    "/sources/website",
    response_model=SourceResponse,
    status_code=201,
    tags=["sources"],
)
def ingest_website(
    payload: WebsiteSourceRequest,
    service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings),
) -> SourceResponse:
    """Extract readable text from one website and persist its chunks."""

    extracted = extract_website(
        str(payload.url),
        max_bytes=settings.max_website_bytes,
        timeout_seconds=settings.website_timeout_seconds,
    )
    return service.ingest(extracted, "website")


@router.post(
    "/sources/youtube",
    response_model=SourceResponse,
    status_code=201,
    tags=["sources"],
)
def ingest_youtube(
    payload: YouTubeSourceRequest,
    service: IngestionService = Depends(get_ingestion_service),
) -> SourceResponse:
    """Fetch the available transcript and persist its chunks."""

    extracted = extract_youtube(str(payload.url))
    return service.ingest(extracted, "youtube")


@router.delete(
    "/sources/{source_id}",
    response_model=SourceDeleteResponse,
    tags=["sources"],
)
def delete_source(
    source_id: str,
    service: IngestionService = Depends(get_ingestion_service),
) -> SourceDeleteResponse:
    """Delete a source and all of its chunks from ChromaDB."""

    deleted_chunks = service.delete(source_id)
    if deleted_chunks == 0:
        raise SourceNotFoundError("The requested source was not found.")
    return SourceDeleteResponse(
        message="Source deleted successfully.",
        source_id=source_id,
        deleted_chunks=deleted_chunks,
    )


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """Answer a question using the most relevant stored chunks."""

    return service.answer(
        payload.question,
        top_k=payload.top_k,
        source_ids=payload.source_ids,
    )
