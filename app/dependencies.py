"""FastAPI dependency factories for the application services."""

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.chat import ChatService
from app.services.ingestion import IngestionService
from app.services.vector_store import ChromaVectorStore


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    """Create one persistent Chroma wrapper per application process."""

    return ChromaVectorStore(get_settings())


def get_ingestion_service() -> IngestionService:
    return IngestionService(get_vector_store(), get_settings())


def get_chat_service() -> ChatService:
    return ChatService(get_vector_store(), get_settings())
