"""
Domain entities — core business objects with no external dependencies.
"""
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4

from ..config import settings


@dataclass
class LLMRequest:
    """Represents a single LLM generation request."""
    id: UUID
    prompt: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt: Optional[str]
    created_at: datetime

    @classmethod
    def create(
        cls,
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        system_prompt: Optional[str] = None
    ) -> "LLMRequest":
        """Factory method — applies default values from settings when fields are omitted."""
        return cls(
            id=uuid4(),
            prompt=prompt,
            model=model or settings.DEFAULT_MODEL,
            temperature=temperature if temperature is not None else settings.DEFAULT_TEMPERATURE,
            max_tokens=max_tokens or settings.DEFAULT_MAX_TOKENS,
            system_prompt=system_prompt,
            created_at=datetime.utcnow()
        )


@dataclass
class LLMResponse:
    """Represents the result of an LLM generation request."""
    request_id: UUID
    response: str
    model: str
    tokens_used: Dict[str, int]  # Keys: "input", "output"
    duration_seconds: float
    created_at: datetime
