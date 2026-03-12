# Ollama LLM Gateway

Generic LLM service using Ollama with full observability (Seq + Prometheus).  
Exposes both a native API and an **OpenAI-compatible API** (`/v1/chat/completions`, `/v1/models`).

---

## Architecture

Clean Architecture with 4 layers:

| Layer | Responsibility |
|---|---|
| **Domain** | Entities, Ports, Exceptions (pure business logic — no external dependencies) |
| **Application** | Use Cases (orchestration) |
| **Infrastructure** | Adapters: Ollama, Seq, Prometheus, FastAPI web factory |
| **Interface Adapters** | Controllers, DTOs (HTTP layer + DI wiring) |

---

## Stack

- **Python 3.11** + FastAPI + Uvicorn
- **Ollama** (LLM engine) — internal port `11434`, exposed `11435`
- **Seq** (structured logging) — **external container**, ingestion port `5340`
- **Prometheus** (metrics scraping) — port `9091`
- **Docker Compose** (orchestration — only `ollama`, `ollama-api`, `prometheus`)

> **Seq runs in a separate container** (not part of this stack).  
> Point `SEQ_SERVER_URL` in `.env` to your Seq ingestion endpoint.

---

## Quick Start

### 1. Configure environment

```powershell
# Copy the example and edit as needed
Copy-Item .env.example .env
```

Key variables in `.env`:

| Variable | Dev value | Description |
|---|---|---|
| `SEQ_SERVER_URL` | `http://host.docker.internal:5340` | Seq ingestion URL (external container) |
| `SEQ_API_KEY` | `<your-key>` | Seq API key |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama internal URL |
| `DEFAULT_MODEL` | `mistral:7b` | Model preloaded at startup |

### 2. Start services

```powershell
docker-compose up -d
```

### 3. Download a model

```powershell
docker exec -it ollama-api-ollama ollama pull mistral:7b
```

### 4. Verify

```powershell
curl http://localhost:8003/health
```

---

## API Endpoints

### Native API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check (Ollama connectivity) |
| POST | `/api/v1/generate` | Generate text from a raw prompt |
| GET | `/api/v1/models` | List available models (OpenAI format) |
| GET | `/metrics` | Prometheus metrics |
| GET | `/docs` | Swagger UI |

### OpenAI-compatible API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/models` | List models — identical to OpenAI `GET /v1/models` |
| POST | `/v1/chat/completions` | Chat completion — identical to OpenAI `POST /v1/chat/completions` |

> Use these endpoints as a drop-in replacement in any client that supports OpenAI:  
> OpenAI SDK, LangChain, LiteLLM, n8n AI nodes, etc.

---

## Request & Response examples

### `POST /api/v1/generate`

**Request**
```json
{
  "prompt": "Extract invoice number and total from: Invoice #12345, Total: $500",
  "model": "mistral:7b",
  "temperature": 0.1,
  "max_tokens": 2000,
  "system_prompt": "You are an expert in data extraction"
}
```

**Response**
```json
{
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "response": "Invoice Number: 12345\nTotal: $500.00",
  "model": "mistral:7b",
  "tokens_used": { "input": 25, "output": 15 },
  "duration_seconds": 1.8
}
```

---

### `POST /v1/chat/completions`

**Request**
```json
{
  "model": "mistral:7b",
  "messages": [
    { "role": "system", "content": "You are an expert data extraction assistant." },
    { "role": "user", "content": "Extract the invoice number from: Invoice #98765, Total $250" }
  ],
  "temperature": 0.1,
  "max_tokens": 2000
}
```

**Response**
```json
{
  "id": "chatcmpl-abc123def456",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "mistral:7b",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "Invoice Number: 98765" },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 30, "completion_tokens": 8, "total_tokens": 38 }
}
```

---

### `GET /v1/models` · `GET /api/v1/models`

**Response** (same shape on both endpoints)
```json
{
  "object": "list",
  "data": [
    { "id": "mistral:7b", "object": "model", "created": 1710000000, "owned_by": "ollama" },
    { "id": "llama3.2:3b", "object": "model", "created": 1710000000, "owned_by": "ollama" }
  ]
}
```

---

## Observability

### Seq (structured logs)

Seq runs as a **separate container** outside this compose stack.

| Env | `SEQ_SERVER_URL` | Notes |
|---|---|---|
| Dev (Docker Desktop) | `http://host.docker.internal:5340` | `host.docker.internal` resolves to the Windows/Mac host |
| Pre-prod (Linux VM) | `http://<seq-host-ip>:5340` | Use host IP or a shared Docker network alias |

If Seq is unreachable, the service falls back to console logging automatically (`LOG_FALLBACK_TO_CONSOLE=true`).

### Prometheus (metrics)

UI available at `http://localhost:9091`.

| Metric | Labels | Type |
|---|---|---|
| `llm_requests_total` | `model`, `status` | Counter |
| `llm_duration_seconds` | `model` | Histogram |
| `llm_tokens_total` | `model`, `type` | Histogram |
| `llm_prompt_length` | `model` | Histogram |
| `llm_active_requests` | — | Gauge |
| `llm_last_request_timestamp` | — | Gauge |

---

## Services & ports

| Service | Host port | Internal port | Description |
|---------|-----------|---------------|-------------|
| `ollama-api` | `8003` | `8000` | FastAPI application |
| `ollama` | `11435` | `11434` | Ollama LLM engine |
| `prometheus` | `9091` | `9090` | Prometheus metrics |
| Seq (external) | `5340` | — | Ingestion (separate container) |

---

## Project structure

```
ollama-api/
├── app/
│   ├── config.py                    # Settings (pydantic-settings, reads .env)
│   ├── main.py                      # App entry point
│   ├── domain/                      # Pure business logic — no external deps
│   │   ├── entities.py              # LLMRequest, LLMResponse
│   │   ├── ports.py                 # ILLMProvider, ILogger, IMetrics
│   │   └── exceptions.py            # LLMBusyError, LLMError, etc.
│   ├── application/
│   │   └── use_cases.py             # GenerateTextUseCase
│   ├── infrastructure/              # External adapters (implement domain ports)
│   │   ├── llm/
│   │   │   └── ollama_adapter.py    # OllamaAdapter → ILLMProvider
│   │   ├── observability/
│   │   │   ├── seq_logger.py        # SeqLogger + ConsoleLogger → ILogger
│   │   │   └── prometheus_adapter.py # PrometheusMetrics → IMetrics
│   │   └── web/
│   │       └── app.py               # FastAPI factory + middleware
│   └── interface_adapters/          # HTTP layer + dependency injection wiring
│       ├── controllers.py           # All endpoints + DI factories
│       └── dtos.py                  # Request/Response Pydantic models
├── .env.example                     # Environment template (commit this)
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Recommended models

```powershell
docker exec -it ollama-api-ollama ollama pull llama3.2:3b   # Small & fast (3B)
docker exec -it ollama-api-ollama ollama pull mistral:7b    # Medium (7B) — default
docker exec -it ollama-api-ollama ollama pull codellama:13b # Code generation (13B)
```

---

## Integration examples

### OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8003",
    api_key="not-needed"  # Required by SDK but not validated by this service
)

response = client.chat.completions.create(
    model="mistral:7b",
    messages=[
        {"role": "system", "content": "You are a data extraction expert."},
        {"role": "user", "content": "Extract invoice number from: Invoice #12345"}
    ],
    temperature=0.1
)
print(response.choices[0].message.content)
```

### LiteLLM

```python
import litellm

response = litellm.completion(
    model="openai/mistral:7b",
    api_base="http://localhost:8003",
    api_key="not-needed",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### n8n HTTP Request node (native API)

```javascript
const response = await $http.request({
  method: 'POST',
  url: 'http://ollama-api:8000/api/v1/generate',
  body: {
    prompt: `Extract structured data from: ${invoiceText}`,
    model: 'mistral:7b',
    temperature: 0.1,
    max_tokens: 2000
  }
});
return response.data.response;
```

---

## Production / pre-prod deployment

1. Install Docker + Docker Compose on target VM
2. Clone this repository
3. `cp .env.example .env` and set:
   - `SEQ_SERVER_URL` → your pre-prod Seq ingestion URL (port `5340`)
   - `SEQ_API_KEY` → pre-prod API key
   - `DEFAULT_MODEL` → your preferred model
4. `docker-compose up -d`
5. Pull the model: `docker exec -it ollama-api-ollama ollama pull mistral:7b`
6. Open firewall port `8003`

---

## Notes

- **Single-request concurrency**: Ollama processes one LLM request at a time. Concurrent requests receive `503 LLM_BUSY` with `retry_after: 30`.
- **Seq decoupled**: Excluded from this compose stack by design. Runs independently in every environment. Falls back to console logging if unreachable.
- **Extensible**: Swap Ollama for any other LLM by implementing `ILLMProvider` in a new adapter — use cases and domain logic are untouched.

## Architecture

Clean Architecture with 4 layers:
- **Domain**: Entities, Ports, Exceptions (business logic)
- **Application**: Use Cases (orchestration)
- **Infrastructure**: Adapters (Ollama, SEQ, Prometheus, FastAPI)
- **Interface Adapters**: Controllers, DTOs (HTTP layer)

## Stack

- **Python 3.11** + FastAPI + Uvicorn
- **Ollama** (LLM engine)
- **SEQ** (structured logging) - port 5342
- **Prometheus** (metrics) - port 9091
- **Docker Compose** (orchestration)

## Quick Start

### 1. Start services
```powershell
docker-compose up -d
```

### 2. Download a model
```powershell
docker exec -it ollama ollama pull llama3.2:3b
```

### 3. Test the API
```powershell
curl -X POST http://localhost:8000/api/v1/generate `
  -H "Content-Type: application/json" `
  -d '{
    "prompt": "Extract invoice number and total from: Invoice #12345, Total: $500",
    "model": "llama3.2:3b",
    "temperature": 0.1,
    "max_tokens": 2000
  }'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root info |
| `/health` | GET | Health check |
| `/api/v1/generate` | POST | Generate text from prompt |
| `/api/v1/models` | GET | List available models |
| `/metrics` | GET | Prometheus metrics |
| `/docs` | GET | Swagger UI |

## Example Request

```json
{
  "prompt": "Extract invoice number and total from: Invoice #12345, Total: $500",
  "model": "llama3.2:3b",
  "temperature": 0.1,
  "max_tokens": 2000,
  "system_prompt": "You are an expert in data extraction"
}
```

## Example Response

```json
{
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "response": "Invoice Number: 12345\nTotal: $500.00",
  "model": "llama3.2:3b",
  "tokens_used": {
    "input": 25,
    "output": 15
  },
  "duration_seconds": 1.8
}
```

## Observability

- **SEQ Logs**: http://localhost:5342
- **Prometheus Metrics**: http://localhost:9091

### Available Metrics

- `llm_requests_total{model, status}` - Total requests by model and status
- `llm_duration_seconds{model}` - Request duration by model
- `llm_tokens_total{model, type}` - Total tokens (input/output) by model
- `llm_prompt_length{model}` - Prompt length by model
- `llm_active_requests` - Currently active requests
- `llm_last_request_timestamp` - Timestamp of last request

## Services & Ports

| Service | Port | Description |
|---------|------|-------------|
| ollama-api | 8000 | FastAPI application |
| ollama | 11434 | Ollama engine |
| seq | 5342 | SEQ logging UI |
| prometheus | 9091 | Prometheus metrics |

## Development

### Project Structure
```
ollama-api/
├── app/
│   ├── domain/              # Business logic
│   │   ├── entities.py      # LLMRequest, LLMResponse
│   │   ├── ports.py         # ILLMProvider, ILogger, IMetrics
│   │   └── exceptions.py    # Custom exceptions
│   ├── application/         # Use cases
│   │   └── use_cases.py     # GenerateTextUseCase
│   ├── infrastructure/      # External adapters
│   │   ├── llm/
│   │   │   └── ollama_adapter.py
│   │   ├── observability/
│   │   │   ├── seq_logger.py
│   │   │   └── prometheus_adapter.py
│   │   └── web/
│   │       └── app.py       # FastAPI factory
│   └── interface_adapters/  # HTTP layer
│       ├── controllers.py   # Endpoints
│       └── dtos.py          # Request/Response models
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

### Recommended Models

```powershell
# Small & fast (3B parameters)
docker exec -it ollama ollama pull llama3.2:3b

# Medium (7B parameters)
docker exec -it ollama ollama pull mistral:7b

# Code generation (13B parameters)
docker exec -it ollama ollama pull codellama:13b
```

## Integration Example (n8n)

```javascript
// HTTP Request node
const response = await $http.request({
  method: 'POST',
  url: 'http://localhost:8000/api/v1/generate',
  body: {
    prompt: `Extract structured data from: ${invoiceText}`,
    model: 'llama3.2:3b',
    temperature: 0.1,
    max_tokens: 2000
  }
});

return response.data.response;
```

## Production Deployment

This service is designed to run on a separate VM with Ollama.

### VM Setup
1. Install Docker + Docker Compose
2. Clone this repository
3. Run `docker-compose up -d`
4. Download required models
5. Configure firewall (allow port 8000)

### Update n8n endpoint
```javascript
url: 'http://llm.company.com:8000/api/v1/generate'
```

## Notes

- **Separation**: This service is independent of invoice-automation
- **Reusability**: Designed for multiple automations (prompt/model as parameters)
- **Consistency**: Mirrors extractor architecture for maintainability
- **Scalability**: Can run on dedicated VM with GPU support
