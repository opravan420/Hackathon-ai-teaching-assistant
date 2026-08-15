class LLMError(Exception):
    """Base exception for all LLM errors."""
    pass

class LLMConnectionError(LLMError):
    """Raised when the application cannot reach the Ollama service."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when the Ollama request times out."""
    pass

class LLMInvalidModelError(LLMError):
    """Raised when the configured model is missing or invalid."""
    pass

class LLMResponseError(LLMError):
    """Raised when Ollama returns an empty or malformed response."""
    pass
