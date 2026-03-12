"""
Ollama API - Main entry point
"""
from .infrastructure.web.app import create_app

app = create_app()
