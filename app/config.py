"""
Application configuration — all settings are read from environment variables or .env.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """All application settings. Values are loaded from environment variables.

    An .env file is read automatically if present (see class Config below).
    """
    
    # -------------------------------------------------------------------------
    # Application metadata
    # -------------------------------------------------------------------------
    APP_NAME: str = "ollama-api"
    APP_TITLE: str = "Ollama LLM Gateway"
    APP_DESCRIPTION: str = "Generic LLM service using Ollama with observability"
    APP_VERSION: str = "1.0.0"

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    METRICS_ENDPOINT: str = "/metrics"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: list = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]

    # -------------------------------------------------------------------------
    # Ollama
    # -------------------------------------------------------------------------
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_TIMEOUT: Optional[float] = None  # None = no timeout
    OLLAMA_KEEP_ALIVE: str = "5m"           # How long to keep the model loaded: "5m", "1h", "-1" (indefinite)
    OLLAMA_PRELOAD_MODEL: bool = True        # Warm up the default model at startup

    # -------------------------------------------------------------------------
    # Seq logging  (external container — not part of this compose stack)
    # -------------------------------------------------------------------------
    SEQ_SERVER_URL: str = "http://host.docker.internal:5340"  # Ingestion endpoint
    SEQ_API_KEY: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FALLBACK_TO_CONSOLE: bool = True  # Log to stdout when Seq is unreachable

    # -------------------------------------------------------------------------
    # LLM defaults  (overridable per request)
    # -------------------------------------------------------------------------
    DEFAULT_MODEL: str = "mistral:7b"
    DEFAULT_TEMPERATURE: float = 0.1
    DEFAULT_MAX_TOKENS: int = 4000
    MIN_TEMPERATURE: float = 0.0
    MAX_TEMPERATURE: float = 2.0
    MIN_TOKENS: int = 1
    MAX_TOKENS_LIMIT: int = 8192
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Module-level singleton — imported everywhere as `from app.config import settings`.
settings = Settings()
