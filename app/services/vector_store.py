"""Google embeddings and persistent Chroma vector-store access."""

from __future__ import annotations

import logging
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import Settings
from app.errors import ConfigurationError, VectorStoreError


logger = logging.getLogger(__name__)


def _storage_error_message(exc: Exception) -> str:
    """Turn common provider/store failures into actionable, safe messages."""

    detail = str(exc).lower()
    if "dimension" in detail:
        return (
            "The local Chroma collection uses a different embedding size. "
            "Back up chroma_data/, remove it, and ingest the sources again."
        )
    if any(term in detail for term in ("429", "quota", "rate limit", "resource_exhausted")):
        return "The embedding provider hit a rate limit or quota. Wait a moment and try again."
    if any(term in detail for term in ("database is locked", "sqlite", "locked")):
        return (
            "The local ChromaDB is busy. Make sure only one backend process is using "
            "chroma_data/ and try again."
        )
    if any(term in detail for term in ("api key", "permission", "unauthenticated", "model")):
        return "Google embeddings could not create vectors. Check GOOGLE_API_KEY and the embedding model."
    return "Google embeddings or ChromaDB could not store the document chunks. Check the backend log."


class ChromaVectorStore:
    """Small wrapper around the LangChain Chroma integration."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.google_api_key_value
        if not api_key:
            raise ConfigurationError(
                "GOOGLE_API_KEY is missing. Add it to .env before ingesting or chatting."
            )

        try:
            embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.google_embedding_model,
                api_key=api_key,
            )
            # Supplying persist_directory makes Chroma persist locally automatically.
            self._store = Chroma(
                collection_name=settings.chroma_collection_name,
                embedding_function=embeddings,
                persist_directory=str(settings.chroma_persist_directory),
                collection_metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            logger.exception("Could not initialize the Chroma vector store")
            raise VectorStoreError("The local vector store could not be initialized.") from exc

    def add_documents(self, documents: list[Document], ids: list[str]) -> None:
        if not documents:
            raise VectorStoreError("There are no document chunks to store.")
        try:
            self._store.add_documents(documents=documents, ids=ids)
        except Exception as exc:
            logger.exception("Could not add documents to Chroma")
            raise VectorStoreError(_storage_error_message(exc)) from exc

    def delete_source(self, source_id: str) -> int:
        """Delete every Chroma chunk belonging to one source."""

        try:
            result = self._store.get(
                where={"source_id": source_id},
                include=[],
            )
            ids = result.get("ids", [])
            if not ids:
                return 0
            self._store.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            logger.exception("Could not delete source %s from Chroma", source_id)
            raise VectorStoreError("The source could not be deleted from the vector store.") from exc

    def search(
        self,
        query: str,
        *,
        k: int,
        source_ids: list[str] | None = None,
    ) -> list[Document]:
        query_filter: dict[str, Any] | None = None
        if source_ids:
            query_filter = {"source_id": {"$in": source_ids}}

        try:
            return self._store.similarity_search(query, k=k, filter=query_filter)
        except Exception as exc:
            logger.exception("Could not search Chroma")
            raise VectorStoreError("Relevant document chunks could not be retrieved.") from exc
