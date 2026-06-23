class YontAIException(Exception):
    """Base exception for expected YontAI domain failures."""


class OllamaConnectionError(YontAIException):
    """Raised when the local Ollama service cannot be reached."""


class OllamaModelError(YontAIException):
    """Raised when Ollama rejects a model operation or returns invalid data."""
