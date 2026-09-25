"""Chunking and source-ingestion orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Settings
from app.errors import SourceExtractionError
from app.schemas import SourceMetadata, SourceResponse, SourceType
from app.services.extractors import ExtractedSource
from app.services.vector_store import ChromaVectorStore


class IngestionService:
    """Turn extracted source documents into Chroma records."""

    def __init__(self, vector_store: ChromaVectorStore, settings: Settings) -> None:
        self._vector_store = vector_store
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def ingest(
        self,
        extracted: ExtractedSource,
        source_type: SourceType,
    ) -> SourceResponse:
        source_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        chunks = self._splitter.split_documents(extracted.documents)

        if not chunks:
            raise SourceExtractionError("The extracted source did not produce any chunks.")

        indexed_chunks = []
        chunk_ids = []
        for chunk_index, chunk in enumerate(chunks):
            metadata = {
                key: value
                for key, value in chunk.metadata.items()
                if value is not None
            }
            metadata.update(extracted.metadata)
            metadata.update(
                {
                    "source_id": source_id,
                    "source_type": source_type,
                    "source_title": extracted.title,
                    "source_url": extracted.source_url or "",
                    "chunk_index": chunk_index,
                    "created_at": created_at.isoformat(),
                }
            )
            indexed_chunks.append(
                Document(
                    page_content=chunk.page_content,
                    metadata=metadata,
                )
            )
            chunk_ids.append(f"{source_id}:{chunk_index}")

        self._vector_store.add_documents(indexed_chunks, chunk_ids)

        page_count = extracted.metadata.get("page_count")
        language_code = extracted.metadata.get("language_code")
        video_id = extracted.metadata.get("video_id")
        source = SourceMetadata(
            source_id=source_id,
            source_type=source_type,
            title=extracted.title,
            source_url=extracted.source_url,
            created_at=created_at,
            page_count=page_count if isinstance(page_count, int) else None,
            language_code=language_code if isinstance(language_code, str) else None,
            video_id=video_id if isinstance(video_id, str) else None,
        )
        return SourceResponse(
            message=f"{source_type} source ingested successfully.",
            source=source,
            chunks_created=len(indexed_chunks),
        )

    def delete(self, source_id: str) -> int:
        """Remove all stored chunks for a source and return the count."""

        return self._vector_store.delete_source(source_id)
