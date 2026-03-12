# Architecture  Ollama LLM Gateway

## Overview

The service follows **Clean Architecture** (Ports & Adapters). Each layer depends only on the layer inside it; infrastructure details never leak into business logic.

```
+-------------------------------------------------------------+
|  Interface Adapters  (controllers.py, dtos.py)              |
|  - HTTP handlers, DI factories, request/response mapping    |
+-------------------------------------------------------------+
|  Application  (use_cases.py)                                |
|  - GenerateTextUseCase -- orchestrates ports, no infra deps |
+-------------------------------------------------------------+
|  Domain  (entities.py, ports.py, exceptions.py)             |
|  - LLMRequest / LLMResponse, ILLMProvider / ILogger /       |
|    IMetrics interfaces, domain exceptions                   |
+-------------------------------------------------------------+
|  Infrastructure  (adapters)                                 |
|  - OllamaAdapter, SeqLogger, PrometheusMetrics, FastAPI app |
+-------------------------------------------------------------+
```

**Rule:** arrows point inward only. `GenerateTextUseCase` knows `ILLMProvider`, never `OllamaAdapter`.

---

## Ports and adapters

| Port | Adapter | Location |
|---|---|---|
| `ILLMProvider` | `OllamaAdapter` | `infrastructure/llm/ollama_adapter.py` |
| `ILogger` | `SeqLogger`, `ConsoleLogger` | `infrastructure/observability/seq_logger.py` |
| `IMetrics` | `PrometheusMetrics`, `NoOpMetrics` | `infrastructure/observability/prometheus_adapter.py` |

Swapping an adapter (e.g. replacing Ollama with OpenAI) requires only:
1. Create a new class that implements the relevant port.
2. Update the factory function in `controllers.py`.

No other files change.

---

## Dependency injection

FastAPI's `Depends()` wires concrete adapters into the use case at request time.

```
get_generate_use_case()
  |
  +- get_llm_provider()  -> OllamaAdapter
  +- get_logger()        -> SeqLogger
  +- get_metrics()       -> PrometheusMetrics
```

All three factories return module-level singletons (initialised once, reused across requests).

---

## Request flow

```
HTTP request
   |
   v
Controller handler (controllers.py)
   |  Maps DTO -> LLMRequest domain entity
   |  (for /v1/chat/completions: extracts system prompt,
   |   serialises conversation history into the prompt)
   v
GenerateTextUseCase.execute(request)
   |
   +- logger.info("LLM generation started", ...)
   +- metrics.set_gauge("llm_active_requests", 1)
   +- metrics.record_histogram("llm_prompt_length", ...)
   |
   +- llm.generate(request)  <--- OllamaAdapter -> Ollama HTTP API
   |
   +- metrics.increment_counter("llm_requests_total", ...)
   +- metrics.record_histogram("llm_duration_seconds", ...)
   +- metrics.record_histogram("llm_tokens_total", ...)   x2
   +- metrics.set_gauge("llm_last_request_timestamp", ...)
   +- logger.info("LLM generation completed", ...)
   |
   +- [finally] metrics.set_gauge("llm_active_requests", 0)
   |
   v
Controller maps LLMResponse -> response DTO -> JSON
```

---

## Endpoints

### Native API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Ollama connectivity check |
| POST | `/api/v1/generate` | Generate text from a raw prompt |
| GET | `/api/v1/models` | List available models (OpenAI format) |
| GET | `/metrics` | Prometheus scrape endpoint |
| GET | `/docs` | Swagger UI |

### OpenAI-compatible API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/models` | OpenAI-format model list |
| POST | `/v1/chat/completions` | OpenAI-format chat completion |

`/api/v1/models` and `/v1/models` return the same `OAIModelsResponse` shape.

`/v1/chat/completions` maps the `messages` array to the internal `LLMRequest`:

- First `system` message -> `system_prompt`
- Prior `user`/`assistant` turns -> serialised conversation history prepended to prompt
- Last `user` message -> prompt

---

## Concurrency model

Ollama processes one generate request at a time.
`OllamaAdapter` uses a double-checked async lock pattern: concurrent calls raise `LLMBusyError` immediately (HTTP 503) rather than queuing.

```python
if self._processing:            # fast path -- no lock acquisition
    raise LLMBusyError(...)

async with self._lock:          # safe check under lock
    if self._processing:
        raise LLMBusyError(...)
    self._processing = True

try:
    ...                         # generate
finally:
    async with self._lock:
        self._processing = False
```

---

## Observability

### Seq (structured logs)

Runs as a **separate container** outside this compose stack.
`SeqLogger` sends batched CLEF events to the ingestion endpoint via `seqlog`.
Falls back to stdout automatically when the endpoint is unreachable.

| Setting | Purpose |
|---|---|
| `SEQ_SERVER_URL` | Ingestion HTTP endpoint (default: `http://host.docker.internal:5340`) |
| `SEQ_API_KEY` | Authentication (optional) |
| `LOG_FALLBACK_TO_CONSOLE` | Enable/disable stdout fallback |

### Prometheus

`PrometheusMetrics` wraps `prometheus_client` primitives.
All metric objects are module-level singletons to avoid duplicate-registration errors on hot-reload.

| Metric | Type | Labels |
|---|---|---|
| `llm_requests_total` | Counter | `model`, `status` |
| `llm_duration_seconds` | Histogram | `model` |
| `llm_tokens_total` | Histogram | `model`, `type` |
| `llm_prompt_length` | Histogram | `model` |
| `llm_active_requests` | Gauge | - |
| `llm_last_request_timestamp` | Gauge | - |

---

## Adding a new LLM provider

1. Create `app/infrastructure/llm/<name>_adapter.py` implementing `ILLMProvider`.
2. In `controllers.py`, update `get_llm_provider()` to return the new adapter.
3. Add any required settings to `config.py` and `.env.example`.

Nothing else changes.