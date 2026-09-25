"""FastAPI application entry point."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.errors import AppError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
frontend_directory = Path(__file__).resolve().parents[1] / "frontend"

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "A small RAG backend for PDF files, websites, and YouTube transcripts. "
        "Gemini answers only from retrieved ChromaDB chunks."
    ),
)

allow_all_origins = settings.cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve the frontend from the same FastAPI process when it is available.
# API routes are registered first, so /health, /sources/*, /chat, and /docs
# continue to resolve to the backend rather than the static file mount.
if frontend_directory.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=frontend_directory, html=True),
        name="frontend",
    )


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Turn expected errors into safe JSON responses."""

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Do not return stack traces or provider details to clients."""

    logger.exception("Unhandled request error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )
