"""
Data Transfer Objects — request and response models for all API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal
import time

from ..config import settings


class GenerateRequest(BaseModel):
    """Request DTO for text generation"""
    prompt: str = Field(..., description="The prompt to generate from", min_length=1)
    model: str = Field(default=settings.DEFAULT_MODEL, description="Model to use")
    temperature: float = Field(
        default=settings.DEFAULT_TEMPERATURE,
        ge=settings.MIN_TEMPERATURE,
        le=settings.MAX_TEMPERATURE,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=settings.DEFAULT_MAX_TOKENS,
        ge=settings.MIN_TOKENS,
        le=settings.MAX_TOKENS_LIMIT,
        description="Maximum tokens to generate"
    )
    system_prompt: Optional[str] = Field(None, description="System prompt (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Extract invoice number and total from: Invoice #12345, Total: $500",
                "model": "llama3.2:3b",
                "temperature": 0.1,
                "max_tokens": 2000,
                "system_prompt": "You are an expert in data extraction"
            }
        }


class GenerateResponse(BaseModel):
    """Response DTO for text generation"""
    request_id: str
    response: str
    model: str
    tokens_used: Dict[str, int]
    duration_seconds: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "response": "Invoice Number: 12345\nTotal: $500.00",
                "model": "llama3.2:3b",
                "tokens_used": {"input": 25, "output": 15},
                "duration_seconds": 1.8
            }
        }


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str
    ollama_connected: bool


# ---------------------------------------------------------------------------
# OpenAI-compatible DTOs  (v1/models  &  v1/chat/completions)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single message in an OpenAI-style conversation"""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible POST /v1/chat/completions request body"""
    model: str = Field(default=settings.DEFAULT_MODEL, description="Model to use")
    messages: List[ChatMessage] = Field(..., min_length=1, description="Conversation messages")
    temperature: float = Field(
        default=settings.DEFAULT_TEMPERATURE,
        ge=settings.MIN_TEMPERATURE,
        le=settings.MAX_TEMPERATURE,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=settings.DEFAULT_MAX_TOKENS,
        ge=settings.MIN_TOKENS,
        le=settings.MAX_TOKENS_LIMIT,
        description="Maximum tokens to generate"
    )
    stream: bool = Field(default=False, description="Streaming (not supported, always false)")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "mistral:7b",
                "messages": [
                    {"role": "system", "content": "You are an expert data extraction assistant."},
                    {"role": "user", "content": "Extract the invoice number from: Invoice #98765, Total $250"}
                ],
                "temperature": 0.1,
                "max_tokens": 2000
            }
        }


class ChatCompletionChoiceMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible POST /v1/chat/completions response"""
    id: str
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": 1710000000,
                "model": "mistral:7b",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Invoice Number: 98765"},
                        "finish_reason": "stop"
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
            }
        }


class OAIModelObject(BaseModel):
    """A single model entry in OpenAI format"""
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "ollama"


class OAIModelsResponse(BaseModel):
    """OpenAI-compatible GET /v1/models response"""
    object: str = "list"
    data: List[OAIModelObject]
