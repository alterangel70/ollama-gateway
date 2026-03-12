"""
Domain ports — abstract interfaces that infrastructure adapters must implement.
"""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional, List
from .entities import LLMRequest, LLMResponse


class ILLMProvider(ABC):
    """Port for any LLM backend (Ollama, OpenAI, Anthropic, etc.)."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text for the given request."""
        pass

    @abstractmethod
    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Generate text token-by-token; yields each text chunk as it arrives."""
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Return the names of all available models."""
        pass


class ILogger(ABC):
    """Port for structured logging."""

    @abstractmethod
    def info(self, message: str, **context: Any) -> None:
        """Log an informational message with optional structured properties."""
        pass

    @abstractmethod
    def error(self, message: str, error: Optional[Exception] = None, **context: Any) -> None:
        """Log an error, optionally including exception details."""
        pass

    @abstractmethod
    def warning(self, message: str, **context: Any) -> None:
        """Log a warning with optional structured properties."""
        pass


class IMetrics(ABC):
    """Port for application metrics collection."""

    @abstractmethod
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a named counter."""
        pass

    @abstractmethod
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a value into a named histogram."""
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a named gauge to an absolute value."""
        pass
