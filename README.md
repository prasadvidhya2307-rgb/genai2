# RAG Source Chat API

A beginner-friendly FastAPI backend that supports three source types:

- PDF uploads
- Public website URLs
- Public YouTube URLs with available transcripts

The application follows this flow:

```text
source -> extract text -> split into chunks -> Google embeddings -> local ChromaDB
       -> retrieve relevant chunks -> Gemini -> grounded answer
```

## Project structure

```text
app/
  api/routes.py              HTTP endpoints
  config.py                  .env configuration
  dependencies.py            service dependency wiring
  errors.py                  safe application errors
  main.py                    FastAPI app and CORS
  schemas.py                 request/response models
  services/
    extractors.py            PDF, website, and YouTube extraction
    ingestion.py             chunking and source metadata
    vector_store.py          Google embeddings + ChromaDB
    chat.py                  retrieval and Gemini prompting
frontend/                    dependency-free HTML/CSS/JavaScript UI
frontend/assets/             Lottie loading animation
chroma_data/                 created automatically and persisted locally
```

## 1. Create the environment

This project targets Python 3.10+ (Python 3.12 is recommended).

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Configure Google

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Open `.env` and set `GOOGLE_API_KEY`.
3. Keep `.env` on the server. Never send the key to a frontend or include it in a chat request.

The key is read only by the backend when it creates the LangChain Google clients. The `/health` response reports only whether a key is configured; it never returns the key.

The defaults in `.env.example` are:

- Chat model: `gemini-3.5-flash`
- Embedding model: `gemini-embedding-001`

Both model names are configurable. If your Google project does not have access to the default chat model, set `GEMINI_CHAT_MODEL` to another available Gemini Flash model. If you change the embedding model, clear `chroma_data/` and ingest sources again because different embedding models use different vector spaces.

## 3. Run the server

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API is available at:

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

ChromaDB is persisted in `chroma_data/` by default. Do not delete that directory unless you want to remove all ingested sources.

## Frontend

The frontend is a small, dependency-free HTML/CSS/JavaScript app in `frontend/`. FastAPI serves it from the same process, so the UI and all API endpoints use the same port and origin. You only need one terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). The frontend uses same-origin requests to `/health`, `/sources/pdf`, `/sources/website`, `/sources/youtube`, and `/chat`, so there is no separate frontend port or CORS requirement. It supports PDF upload, website and YouTube ingestion, a local source library, source-scoped chat, and grounded source metadata. It never receives or stores `GOOGLE_API_KEY`.

The API documentation remains available at [http://localhost:8000/docs](http://localhost:8000/docs).

If the frontend is hosted elsewhere in the future, define `window.RAG_API_URL` before loading `app.js`.

## API endpoints

### Health

```http
GET /health
```

### Ingest a PDF

Use `multipart/form-data` with a field named `file`:

```powershell
curl.exe -X POST http://localhost:8000/sources/pdf `
  -F "file=@C:\path\to\document.pdf"
```

Example response:

```json
{
  "message": "pdf source ingested successfully.",
  "source": {
    "source_id": "generated-uuid",
    "source_type": "pdf",
    "title": "document.pdf",
    "source_url": null,
    "created_at": "2026-01-01T00:00:00Z",
    "page_count": 12,
    "language_code": null,
    "video_id": null
  },
  "chunks_created": 28
}
```

PDF text must be selectable text. This implementation does not add OCR, so scanned/image-only PDFs are rejected with a clear error.

### Ingest a website

```powershell
curl.exe -X POST http://localhost:8000/sources/website `
  -H "Content-Type: application/json" `
  -d '{"url":"https://example.com/article"}'
```

Only the readable text of the requested page is indexed. JavaScript that is not present in the downloaded HTML is not indexed.

### Ingest a YouTube video

```powershell
curl.exe -X POST http://localhost:8000/sources/youtube `
  -H "Content-Type: application/json" `
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}'
```

The backend requests an English transcript when available and otherwise uses another available transcript. Videos without transcripts, private videos, and videos whose transcripts are blocked return an ingestion error.

### Delete a source

Delete a source and all of its chunks from ChromaDB:

```http
DELETE /sources/{source_id}
```

The frontend adds a delete button to every source card and asks for confirmation before removing it.

### Ask a question

Search all ingested sources:

```powershell
curl.exe -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"What are the main topics?","top_k":5}'
```

Search only selected sources:

```json
{
  "question": "What does this document say about setup?",
  "source_ids": ["source-id-returned-by-an-ingestion-endpoint"],
  "top_k": 5
}
```

The response contains the Gemini answer and grouped source metadata:

```json
{
  "answer": "...",
  "sources": [
    {
      "source_id": "source-id-returned-by-an-ingestion-endpoint",
      "source_type": "pdf",
      "title": "document.pdf",
      "source_url": null,
      "relevant_chunks": 2,
      "chunk_indices": [3, 4],
      "page_numbers": [2, 3]
    }
  ]
}
```

Gemini is instructed to answer only from the retrieved context. When the context does not contain an answer, the API returns:

```text
I couldn't find that in the ingested sources.
```

## Configuration

All settings are optional except `GOOGLE_API_KEY`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | none | Server-side Google AI Studio key |
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash` | Gemini chat model |
| `GOOGLE_EMBEDDING_MODEL` | `gemini-embedding-001` | Google embedding model |
| `CHROMA_PERSIST_DIRECTORY` | `./chroma_data` | Local ChromaDB directory |
| `CHROMA_COLLECTION_NAME` | `rag_sources` | Chroma collection |
| `CHUNK_SIZE` | `1000` | Maximum characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between chunks |
| `DEFAULT_TOP_K` | `5` | Default retrieved chunk count |
| `MAX_PDF_SIZE_MB` | `20` | Maximum PDF upload size |
| `MAX_WEBSITE_SIZE_MB` | `5` | Maximum downloaded HTML size |
| `WEBSITE_TIMEOUT_SECONDS` | `20` | Website download timeout |
| `CORS_ORIGINS` | local frontend origins | JSON list of allowed origins |

## Error handling

Expected problems such as unsupported files, empty transcripts, oversized sources, missing API configuration, provider failures, and unavailable vector storage return JSON responses with an appropriate HTTP status and a safe `detail` message. Internal exceptions and credentials are not returned to clients.

## Notes

- There is no authentication, payment system, agent framework, or extra database.
- ChromaDB metadata is the source of truth for source IDs, titles, URLs, page numbers, and chunk indexes.
- Website extraction is intentionally a single-page HTML extractor. JavaScript-heavy sites may need a headless browser, which is outside this simple implementation.
- YouTube's transcript endpoint can be rate-limited or blocked for some server IP addresses.

---

Created by Divya Sharma.
