"""
Ollama LLM adapter — implements ILLMProvider against the Ollama HTTP API.
"""
import httpx
import json
import time
import asyncio
from typing import AsyncIterator, List, Optional
from uuid import uuid4
from datetime import datetime

from ...domain.ports import ILLMProvider
from ...domain.entities import LLMRequest, LLMResponse
from ...domain.exceptions import LLMConnectionError, LLMTimeoutError, LLMBusyError


class OllamaAdapter(ILLMProvider):
    """ILLMProvider implementation that proxies requests to a local Ollama server.

    Enforces single-request concurrency: concurrent calls raise LLMBusyError
    rather than queuing, to avoid unbounded memory growth on the GPU.
    """

    def __init__(self, base_url: str = "http://ollama:11434", timeout: Optional[float] = None, keep_alive: str = "5m"):
        self.base_url = base_url
        # None disables the httpx timeout entirely; otherwise wrap the value.
        timeout_config = None if timeout is None else httpx.Timeout(timeout)
        self.client = httpx.AsyncClient(timeout=timeout_config)
        self._processing = False  # True while a generate request is in flight.
        self._lock = asyncio.Lock()  # Guards _processing for async-safe access.
        self.keep_alive = keep_alive  # How long Ollama keeps the model loaded (e.g. "5m", "-1").
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from request. Raises LLMBusyError if already processing."""
        # Fast path: avoid lock acquisition when visibly busy.
        if self._processing:
            raise LLMBusyError(
                "LLM is currently processing another request. Please try again later."
            )

        # Double-checked locking pattern for async safety.
        async with self._lock:
            if self._processing:
                raise LLMBusyError(
                    "LLM is currently processing another request. Please try again later."
                )
            self._processing = True
        
        try:
            start_time = time.time()

            payload = {
                "model": request.model,
                "prompt": request.prompt,
                "stream": False,
                "think": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                }
            }

            if request.system_prompt:
                payload["system"] = request.system_prompt

            try:
                response = await self.client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                return LLMResponse(
                    request_id=request.id,
                    response=data["response"],
                    model=request.model,
                    tokens_used={
                        "input": data.get("prompt_eval_count", 0),
                        "output": data.get("eval_count", 0)
                    },
                    duration_seconds=time.time() - start_time,
                    created_at=request.created_at
                )

            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"Ollama timeout: {str(e)}")
            except httpx.HTTPError as e:
                raise LLMConnectionError(f"Ollama connection failed: {str(e)}")

        finally:
            # Always release the lock so subsequent requests are not blocked.
            async with self._lock:
                self._processing = False

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream text generation, yielding text tokens as they arrive from Ollama.

        Uses Ollama's streaming NDJSON API (stream=True on /api/generate).
        Raises LLMBusyError if another request is already in flight.
        """
        if self._processing:
            raise LLMBusyError(
                "LLM is currently processing another request. Please try again later."
            )

        async with self._lock:
            if self._processing:
                raise LLMBusyError(
                    "LLM is currently processing another request. Please try again later."
                )
            self._processing = True

        try:
            payload = {
                "model": request.model,
                "prompt": request.prompt,
                "stream": True,
                "think": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens
                }
            }

            if request.system_prompt:
                payload["system"] = request.system_prompt

            try:
                async with self.client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break

            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"Ollama timeout: {str(e)}")
            except httpx.HTTPError as e:
                raise LLMConnectionError(f"Ollama connection failed: {str(e)}")

        finally:
            async with self._lock:
                self._processing = False

    async def list_models(self) -> List[str]:
        """Return the names of all models currently available in Ollama."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"Failed to list models: {str(e)}")

    async def preload_model(self, model_name: str) -> bool:
        """Warm up a model by sending an empty prompt so it is held in GPU memory.

        Raises LLMConnectionError if Ollama is unreachable.
        """
        try:
            payload = {
                "model": model_name,
                "prompt": "",
                "stream": False,
                "keep_alive": self.keep_alive
            }
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            raise LLMConnectionError(f"Failed to preload model {model_name}: {str(e)}")
