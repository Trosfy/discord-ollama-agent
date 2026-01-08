"""
Response Parser Strategies for Model Backends

Implements Strategy Pattern (SOLID principles) to parse different backend API responses.
Each backend has its own parser class implementing the IResponseParser interface.
"""

from typing import Protocol, List, Dict, Any
from abc import abstractmethod


class IResponseParser(Protocol):
    """
    Response parser interface (Dependency Inversion Principle).

    Each backend has a different API response format.
    This interface allows backends to use different parsers without if/else chains.

    Following SOLID Principles:
    - Single Responsibility: Only parsing backend responses
    - Interface Segregation: Single focused method
    - Dependency Inversion: Clients depend on this abstraction
    """

    @abstractmethod
    def parse(self, data: Dict[str, Any], backend_type: str) -> List[Dict[str, Any]]:
        """
        Parse backend response into standardized model list.

        Args:
            data: Raw JSON response from backend
            backend_type: Backend type identifier (e.g., "sglang", "ollama")

        Returns:
            List of dicts with keys:
                - name: Model name/ID
                - size_gb: Model size in GB (0.0 if unavailable)
                - backend: Backend type
        """
        ...


class OpenAIV1Parser:
    """
    Parser for OpenAI-compatible /v1/models endpoints.

    Compatible backends: SGLang, vLLM, any OpenAI-compatible API
    API format: {"data": [{"id": "model-name", ...}, ...]}
    """

    def parse(self, data: Dict[str, Any], backend_type: str) -> List[Dict[str, Any]]:
        """Parse OpenAI v1 models format."""
        models = data.get("data", [])
        return [
            {
                "name": model.get("id", "unknown"),
                "size_gb": 0.0,  # OpenAI format doesn't include size
                "backend": backend_type
            }
            for model in models
        ]


class OllamaParser:
    """
    Parser for Ollama /api/tags endpoint.

    API format: {"models": [{"name": "...", "size": bytes}, ...]}
    """

    def parse(self, data: Dict[str, Any], backend_type: str) -> List[Dict[str, Any]]:
        """Parse Ollama tags format."""
        models = data.get("models", [])
        return [
            {
                "name": model.get("name", "unknown"),
                "size_gb": model.get("size", 0) / (1024**3),  # Convert bytes to GB
                "backend": backend_type
            }
            for model in models
        ]
