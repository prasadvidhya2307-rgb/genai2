"""Content extractors for the three supported source types."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.errors import SourceExtractionError, SourceValidationError


@dataclass(slots=True)
class ExtractedSource:
    """Normalized content returned by a source extractor."""

    title: str
    source_url: str | None
    documents: list[Document]
    metadata: dict[str, str | int | bool]


def _clean_text(text: str) -> str:
    """Normalize extracted text without changing its meaning."""

    lines = []
    for line in text.replace("\x00", "").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def _safe_filename(filename: str) -> str:
    # Uploaded filenames are display metadata, never a filesystem path.
    name = filename.replace("\\", "/").split("/")[-1].strip()
    return name or "document.pdf"


def extract_pdf(content: bytes, filename: str) -> ExtractedSource:
    """Extract text page by page from a PDF upload."""

    if not content:
        raise SourceExtractionError("The uploaded PDF is empty.")

    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise SourceExtractionError("The PDF is password protected.")
            except SourceExtractionError:
                raise
            except Exception as exc:
                raise SourceExtractionError("The PDF is password protected.") from exc

        documents: list[Document] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                # A malformed page should not prevent other pages from being used.
                page_text = ""
            page_text = _clean_text(page_text)
            if page_text:
                documents.append(
                    Document(
                        page_content=page_text,
                        metadata={"page": page_number},
                    )
                )

        if not documents:
            raise SourceExtractionError(
                "No selectable text was found in the PDF. Scanned PDFs require OCR first."
            )

        return ExtractedSource(
            title=_safe_filename(filename),
            source_url=None,
            documents=documents,
            metadata={"page_count": len(reader.pages)},
        )
    except SourceExtractionError:
        raise
    except Exception as exc:
        raise SourceExtractionError("The uploaded file is not a readable PDF.") from exc


def extract_website(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
) -> ExtractedSource:
    """Download one HTML page and extract its readable text."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceValidationError("The website URL must use http or https.")

    try:
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "RAGSourceChat/1.0 (+https://developers.google.com/search)",
            },
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if content_type and not any(
                allowed in content_type for allowed in ("text/html", "application/xhtml")
            ):
                raise SourceValidationError(
                    "The URL must point to an HTML web page, not another file type."
                )

            body = bytearray()
            for part in response.iter_bytes():
                body.extend(part)
                if len(body) > max_bytes:
                    raise SourceExtractionError(
                        f"The web page is larger than the {max_bytes // (1024 * 1024)} MB limit."
                    )

            final_url = str(response.url)
            encoding = response.encoding or "utf-8"
    except SourceValidationError:
        raise
    except SourceExtractionError:
        raise
    except httpx.TimeoutException as exc:
        raise SourceExtractionError("The website took too long to respond.") from exc
    except httpx.HTTPStatusError as exc:
        raise SourceExtractionError(
            f"The website returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise SourceExtractionError("The website could not be reached.") from exc
    except UnicodeError as exc:
        raise SourceExtractionError("The website text could not be decoded.") from exc

    html = bytes(body).decode(encoding, errors="replace")
    try:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript", "svg", "canvas"]):
            element.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        root = soup.find("main") or soup.find("article") or soup.body or soup
        for element in root(["nav", "footer"]):
            element.decompose()

        text = _clean_text(root.get_text("\n", strip=True))
    except Exception as exc:
        raise SourceExtractionError("The web page HTML could not be parsed.") from exc

    if not text:
        raise SourceExtractionError("No readable text was found on the web page.")

    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = urlparse(final_url).hostname or final_url

    return ExtractedSource(
        title=title[:300],
        source_url=final_url,
        documents=[Document(page_content=text, metadata={})],
        metadata={"website_host": urlparse(final_url).hostname or ""},
    )


def _youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SourceValidationError("The YouTube URL is invalid.")

    host = parsed.hostname.lower().rstrip(".")
    youtube_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
    short_hosts = {"youtu.be", "www.youtu.be"}
    if host not in youtube_hosts | short_hosts:
        raise SourceValidationError("Enter a valid YouTube video URL.")

    if host in short_hosts:
        candidate = parsed.path.strip("/").split("/")[0]
    else:
        query_value = parse_qs(parsed.query).get("v", [None])[0]
        path_match = re.search(
            r"/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})(?:/|$)", parsed.path
        )
        candidate = query_value or (path_match.group(1) if path_match else None)

    if not candidate or not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise SourceValidationError("The YouTube URL does not contain a valid video ID.")
    return candidate


def extract_youtube(url: str) -> ExtractedSource:
    """Fetch the available YouTube transcript and return it as one document."""

    video_id = _youtube_video_id(url)
    transcript_api = YouTubeTranscriptApi()

    try:
        try:
            fetched = transcript_api.fetch(
                video_id,
                languages=["en", "en-US", "en-GB"],
            )
        except NoTranscriptFound:
            # English is preferred, but another available language is still useful.
            transcript_list = list(transcript_api.list(video_id))
            if not transcript_list:
                raise SourceExtractionError("No transcript is available for this video.")
            fetched = transcript_list[0].fetch()

        snippets = []
        for snippet in fetched:
            text = snippet.text if hasattr(snippet, "text") else snippet["text"]
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                snippets.append(text)

        transcript_text = _clean_text(" ".join(snippets))
        if not transcript_text:
            raise SourceExtractionError("The YouTube transcript is empty.")

        language_code = getattr(fetched, "language_code", None) or "unknown"
        is_generated = bool(getattr(fetched, "is_generated", False))
        return ExtractedSource(
            title=f"YouTube video {video_id}",
            source_url=url,
            documents=[
                Document(
                    page_content=transcript_text,
                    metadata={"video_id": video_id},
                )
            ],
            metadata={
                "video_id": video_id,
                "language_code": language_code,
                "is_generated": is_generated,
            },
        )
    except SourceExtractionError:
        raise
    except TranscriptsDisabled as exc:
        raise SourceExtractionError("Subtitles are disabled for this video.") from exc
    except AgeRestricted as exc:
        raise SourceExtractionError("This video is age-restricted.") from exc
    except VideoUnavailable as exc:
        raise SourceExtractionError("This video is unavailable.") from exc
    except RequestBlocked as exc:
        raise SourceExtractionError(
            "YouTube blocked the transcript request from this server."
        ) from exc
    except NoTranscriptFound as exc:
        raise SourceExtractionError("No transcript is available for this video.") from exc
    except CouldNotRetrieveTranscript as exc:
        raise SourceExtractionError("The YouTube transcript could not be retrieved.") from exc
    except Exception as exc:
        # The transcript library can raise provider-specific request errors.
        raise SourceExtractionError("The YouTube transcript could not be retrieved.") from exc
