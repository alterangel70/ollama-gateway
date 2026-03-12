"""
Domain exceptions — business-level error types for LLM operations.
"""


class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass


class LLMConnectionError(LLMError):
    """Raised when unable to connect to LLM service"""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out"""
    pass


class LLMBusyError(LLMError):
    """Raised when LLM is already processing another request"""
    pass


class InvalidModelError(LLMError):
    """Raised when requested model is not available"""
    pass
