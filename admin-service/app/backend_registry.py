"""
Backend Registry - SSOT for Model Backend Configuration

Centralized registry of all model backends (SGLang, Ollama, etc.) with their
endpoint configurations and parser strategies.

Following SOLID Principles:
- Single Responsibility: Backend configuration management
- Open/Closed: Extend by adding backends, closed for modification
- Liskov Substitution: All parsers interchangeable via IResponseParser
- Interface Segregation: Minimal, focused interfaces
- Dependency Inversion: Depends on IResponseParser abstraction
"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any

from app.response_parsers import OpenAIV1Parser, OllamaParser


class BackendEndpoint(BaseModel):
    """
    Backend endpoint configuration.

    Attributes:
        type: Backend identifier (e.g., "sglang", "ollama", "vllm")
        endpoint: Full URL to backend service
        models_endpoint: API path to list models (appended to endpoint)
        parser: Parser strategy for this backend's response format (IResponseParser)
        health_endpoint: Optional health check endpoint path
        enabled: Whether this backend is active
    """
    type: str
    endpoint: str
    models_endpoint: str
    parser: Any  # Parser instance (Protocol types don't work with Pydantic)
    health_endpoint: Optional[str] = None
    enabled: bool = True

    class Config:
        arbitrary_types_allowed = True  # Allow parser instances


class BackendRegistry:
    """
    Registry of all model backends to track.

    This is the Single Source of Truth (SSOT) for backend configurations.
    To add a new backend:
    1. Create parser class (if needed) in response_parsers.py
    2. Add entry to backends dict with parser instance

    Example - Adding vLLM:
        "vllm": BackendEndpoint(
            type="vllm",
            endpoint="http://trollama-vllm:8000",
            models_endpoint="/v1/models",
            parser=OpenAIV1Parser(),  # Reuse OpenAI parser!
            enabled=True
        )
    """

    backends: Dict[str, BackendEndpoint] = {
        "sglang": BackendEndpoint(
            type="sglang",
            endpoint="http://trollama-sglang:30000",
            models_endpoint="/v1/models",
            parser=OpenAIV1Parser(),  # SGLang uses OpenAI-compatible format
            health_endpoint="/health",
            enabled=False  # Disabled - container not running
        ),
        "ollama": BackendEndpoint(
            type="ollama",
            endpoint="http://host.docker.internal:11434",
            models_endpoint="/api/tags",
            parser=OllamaParser(),  # Ollama has custom format
            health_endpoint="/api/tags",
            enabled=True
        )
    }

    @classmethod
    def get_enabled_backends(cls) -> List[BackendEndpoint]:
        """
        Get list of enabled backends.

        Returns:
            List of enabled BackendEndpoint instances
        """
        return [backend for backend in cls.backends.values() if backend.enabled]
