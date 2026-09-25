# Source Atlas frontend

This is a small, dependency-free frontend for the FastAPI RAG backend. It uses plain HTML, CSS, and JavaScript, so there is no Node.js build step.

## Run it

FastAPI serves both this frontend and the API from the same port. You only need one terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

The frontend uses relative requests such as `/health`, `/sources/website`, and `/chat`, so the UI and API are fully attached to the same origin. No separate frontend server or CORS configuration is required.

## Backend URL

The normal setup does not need a frontend URL configuration. If the frontend is hosted somewhere else in the future, define `window.RAG_API_URL` before `app.js` loads. The frontend never asks for or stores the Google API key; that key remains in the backend `.env` file.

## Included UI flows

- Drag-and-drop PDF ingestion
- Website URL ingestion
- YouTube URL ingestion
- Local source library persisted in browser storage
- Source-scoped chat
- Delete sources from the library
- Grounded answers with source metadata
- Full-screen Lottie loading overlay using `assets/wait-loading.json`
- Loading, empty, and error states
