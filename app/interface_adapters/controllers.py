"""
HTTP controllers — endpoint handlers and dependency injection factories.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import json as json_lib
import time
import uuid

from .dtos import (
    GenerateRequest, GenerateResponse, HealthResponse,
    ChatCompletionRequest, ChatCompletionResponse,
    ChatCompletionChoice, ChatCompletionChoiceMessage, ChatCompletionUsage,
    OAIModelsResponse, OAIModelObject,
)
from ..application.use_cases import GenerateTextUseCase
from ..domain.entities import LLMRequest
from ..domain.exceptions import LLMBusyError, LLMError
from ..infrastructure.llm.ollama_adapter import OllamaAdapter
from ..infrastructure.observability.seq_logger import SeqLogger
from ..infrastructure.observability.prometheus_adapter import PrometheusMetrics
from ..config import settings

router = APIRouter()

# Module-level singletons — instantiated once and reused across all requests.
_llm_provider = None
_logger = None
_metrics = None


# Dependency injection
def get_llm_provider():
    """Returns singleton instance of LLM provider"""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = OllamaAdapter(
            base_url=settings.OLLAMA_BASE_URL,
            timeout=settings.OLLAMA_TIMEOUT,
            keep_alive=settings.OLLAMA_KEEP_ALIVE
        )
    return _llm_provider


def get_logger():
    """Returns singleton instance of logger"""
    global _logger
    if _logger is None:
        _logger = SeqLogger(
            seq_url=settings.SEQ_SERVER_URL,
            api_key=settings.SEQ_API_KEY,
            level=settings.LOG_LEVEL,
            app_name=settings.APP_NAME,
            fallback_to_console=settings.LOG_FALLBACK_TO_CONSOLE
        )
    return _logger


def get_metrics():
    """Returns singleton instance of metrics"""
    global _metrics
    if _metrics is None:
        _metrics = PrometheusMetrics()
    return _metrics


def get_generate_use_case(
    llm=Depends(get_llm_provider),
    logger=Depends(get_logger),
    metrics=Depends(get_metrics)
) -> GenerateTextUseCase:
    """Assemble and return the GenerateTextUseCase with all dependencies injected."""
    return GenerateTextUseCase(llm, logger, metrics)


@router.get("/", tags=["system"])
async def root():
    """Root endpoint"""
    return {
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check(llm=Depends(get_llm_provider)):
    """Health check endpoint"""
    try:
        await llm.list_models()
        return HealthResponse(status="healthy", ollama_connected=True)
    except Exception:
        return HealthResponse(status="healthy", ollama_connected=False)


@router.post("/api/v1/generate", response_model=GenerateResponse, tags=["llm"])
async def generate_text(
    request: GenerateRequest,
    use_case: GenerateTextUseCase = Depends(get_generate_use_case)
):
    """
    Generate text from a prompt using specified LLM model
    
    This endpoint accepts a prompt and model parameters, then returns
    the generated text along with token usage and timing information.
    
    Note: Only ONE request can be processed at a time. If a request is already
    being processed, this endpoint will return 503 Service Unavailable.
    """
    try:
        llm_request = LLMRequest.create(
            prompt=request.prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt
        )

        result = await use_case.execute(llm_request)

        return GenerateResponse(
            request_id=str(result.request_id),
            response=result.response,
            model=result.model,
            tokens_used=result.tokens_used,
            duration_seconds=result.duration_seconds
        )

    except LLMBusyError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "LLM_BUSY",
                "message": str(e),
                "retry_after": 30
            }
        )
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/models", response_model=OAIModelsResponse, tags=["llm"])
async def list_models(llm=Depends(get_llm_provider)):
    """
    List all available LLM models in OpenAI format.

    Returns a list of model objects compatible with the OpenAI /v1/models schema.
    Also available at /v1/models for direct OpenAI SDK compatibility.
    """
    try:
        models = await llm.list_models()
        now = int(time.time())
        return OAIModelsResponse(
            data=[OAIModelObject(id=m, created=now) for m in models]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# OpenAI-compatible endpoints
# ---------------------------------------------------------------------------

@router.get("/v1/models", response_model=OAIModelsResponse, tags=["openai-compatible"])
async def oai_list_models(llm=Depends(get_llm_provider)):
    """
    List available models in OpenAI format.

    Compatible with clients that use the OpenAI SDK or any tool that
    expects the GET /v1/models response shape.
    """
    try:
        models = await llm.list_models()
        now = int(time.time())
        return OAIModelsResponse(
            data=[OAIModelObject(id=m, created=now) for m in models]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/chat/completions", tags=["openai-compatible"])
async def oai_chat_completions(
    request: ChatCompletionRequest,
    use_case: GenerateTextUseCase = Depends(get_generate_use_case),
    llm=Depends(get_llm_provider)
):
    """
    Generate a chat completion in OpenAI format.

    Maps the messages array to the internal LLMRequest:
    - The first `system` message becomes `system_prompt`.
    - All `user` / `assistant` turns except the last user message are
      serialised as conversation history and prepended to the prompt.
    - The last `user` message becomes the main prompt.

    When `stream=true` the response is sent as SSE (text/event-stream) using
    OpenAI chat-chunk format.  When `stream=false` (default) a single JSON
    object is returned.

    Compatible with clients built on the OpenAI SDK, LangChain, LiteLLM, etc.
    """
    # Extract system prompt from the first system message (if any).
    system_parts = [m.content for m in request.messages if m.role == "system"]
    system_prompt = "\n".join(system_parts) if system_parts else None

    # Separate system messages from the conversation turns.
    non_system = [m for m in request.messages if m.role != "system"]

    if not non_system or non_system[-1].role != "user":
        raise HTTPException(
            status_code=422,
            detail="The last non-system message must have role 'user'."
        )

    history = non_system[:-1]
    last_user_msg = non_system[-1].content

    # Serialise prior turns as "Role: content" lines prepended to the final prompt.
    if history:
        conversation = "\n".join(
            f"{m.role.capitalize()}: {m.content}" for m in history
        )
        prompt = f"{conversation}\nUser: {last_user_msg}"
    else:
        prompt = last_user_msg

    # ------------------------------------------------------------------
    # Streaming branch — return SSE when the client requests stream=true
    # ------------------------------------------------------------------
    if request.stream:
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model

        async def event_stream():
            try:
                llm_request = LLMRequest.create(
                    prompt=prompt,
                    model=model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    system_prompt=system_prompt
                )

                # Opening chunk: send the assistant role delta first.
                first_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]
                }
                yield f"data: {json_lib.dumps(first_chunk)}\n\n"

                # Stream content tokens.
                async for token in llm.generate_stream(llm_request):
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]
                    }
                    yield f"data: {json_lib.dumps(chunk)}\n\n"

                # Final chunk: empty delta + stop reason.
                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json_lib.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            except LLMBusyError as e:
                error_event = {"error": {"message": str(e), "type": "server_error", "code": 503}}
                yield f"data: {json_lib.dumps(error_event)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_event = {"error": {"message": str(e), "type": "server_error"}}
                yield f"data: {json_lib.dumps(error_event)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ------------------------------------------------------------------
    # Non-streaming branch (default)
    # ------------------------------------------------------------------
    try:
        llm_request = LLMRequest.create(
            prompt=prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_prompt=system_prompt
        )

        result = await use_case.execute(llm_request)

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            model=result.model,
            choices=[
                ChatCompletionChoice(
                    message=ChatCompletionChoiceMessage(content=result.response)
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=result.tokens_used.get("input", 0),
                completion_tokens=result.tokens_used.get("output", 0),
                total_tokens=(
                    result.tokens_used.get("input", 0)
                    + result.tokens_used.get("output", 0)
                )
            )
        )

    except LLMBusyError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "LLM_BUSY", "message": str(e), "retry_after": 30}
        )
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
