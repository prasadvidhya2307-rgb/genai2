"""Application errors with safe client-facing messages."""


class AppError(Exception):
    """Base class for expected application errors."""

    status_code = 500
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class ConfigurationError(AppError):
    status_code = 503
    default_message = "The service is not configured correctly."


class SourceValidationError(AppError):
    status_code = 400
    default_message = "The supplied source is invalid."


class SourceExtractionError(AppError):
    status_code = 422
    default_message = "The source content could not be extracted."


class SourceNotFoundError(AppError):
    status_code = 404
    default_message = "The requested source was not found."


class VectorStoreError(AppError):
    status_code = 503
    default_message = "The vector store is currently unavailable."


class LLMError(AppError):
    status_code = 502
    default_message = "The language model could not answer the question."
