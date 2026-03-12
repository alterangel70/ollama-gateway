"""
FastAPI application factory.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager

from ...interface_adapters.controllers import router, get_llm_provider
from ...config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    if settings.OLLAMA_PRELOAD_MODEL:
        try:
            llm = get_llm_provider()
            await llm.preload_model(settings.DEFAULT_MODEL)
            print(f"Model {settings.DEFAULT_MODEL} preloaded and ready.")
        except Exception as e:
            print(f"Warning: could not preload model: {e}")

    yield


def create_app() -> FastAPI:
    """Create, configure, and return the FastAPI application."""
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )

    app.include_router(router)

    # Expose Prometheus metrics at the configured endpoint.
    Instrumentator().instrument(app).expose(app, endpoint=settings.METRICS_ENDPOINT)

    return app
