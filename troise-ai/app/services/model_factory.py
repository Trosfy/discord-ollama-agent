"""Model factory for creating Strands model instances.

Creates appropriate Strands Model implementations (OllamaModel, OpenAIModel)
based on backend configuration. Centralizes model creation for consistency.

Example:
    factory = ModelFactory(config)
    model = factory.create_model("magistral:24b", temperature=0.7)
    agent = Agent(model=model, tools=[...])
"""
import logging
from typing import Any, Dict, Optional, Union

from app.core.config import Config, ModelCapabilities
from app.core.models import ExtendedOllamaModel, ExtendedOpenAIModel

logger = logging.getLogger(__name__)


class ModelFactory:
    """
    Factory for creating Strands model instances based on backend config.

    Supports:
    - Ollama backend: Creates OllamaModel
    - SGLang/vLLM backend: Creates OpenAIModel (OpenAI-compatible API)

    Example:
        factory = ModelFactory(config)

        # Router model (no thinking)
        router_model = factory.create_model(
            "gpt-oss:20b",
            temperature=0.1,
            max_tokens=50,
            additional_args=None,
        )

        # General model (with thinking)
        general_model = factory.create_model(
            "gpt-oss:70b",
            temperature=0.7,
            max_tokens=4096,
            additional_args={"think": "high"},
        )
    """

    def __init__(self, config: Config):
        """
        Initialize the model factory.

        Args:
            config: Application configuration with backend settings.
        """
        self._config = config

    def create_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        additional_args: Optional[Dict[str, Any]] = None,
        keep_alive: str = "10m",
    ) -> Union[ExtendedOllamaModel, ExtendedOpenAIModel]:
        """
        Create appropriate Strands model based on backend type.

        Args:
            model_id: Model identifier (e.g., "magistral:24b").
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            additional_args: Backend-specific args (e.g., {"think": "high"}).
                For Ollama, these are spread at top-level of request.
                For OpenAI-compatible, these are merged into params.
            keep_alive: How long to keep model loaded (Ollama only).

        Returns:
            ExtendedOllamaModel or ExtendedOpenAIModel instance.

        Raises:
            ValueError: If model is not in profile or backend unsupported.
        """
        model_caps = self._config.get_model_capabilities(model_id)
        if not model_caps:
            raise ValueError(f"Model '{model_id}' not in profile")

        backend = model_caps.backend
        backend_type = backend.type.lower()

        logger.debug(
            f"Creating model: {model_id}, backend={backend_type}, "
            f"temp={temperature}, max_tokens={max_tokens}, "
            f"additional_args={additional_args}"
        )

        if backend_type == "ollama":
            return self._create_ollama_model(
                model_id=model_id,
                host=backend.host,
                temperature=temperature,
                max_tokens=max_tokens,
                additional_args=additional_args,
                keep_alive=keep_alive,
            )
        elif backend_type in ("sglang", "vllm"):
            return self._create_openai_model(
                model_id=model_id,
                host=backend.host,
                temperature=temperature,
                max_tokens=max_tokens,
                additional_args=additional_args,
            )
        else:
            raise ValueError(f"Unsupported backend type: {backend_type}")

    def _create_ollama_model(
        self,
        model_id: str,
        host: str,
        temperature: float,
        max_tokens: int,
        additional_args: Optional[Dict[str, Any]],
        keep_alive: str,
    ) -> ExtendedOllamaModel:
        """
        Create ExtendedOllamaModel for Ollama backend.

        Uses ExtendedOllamaModel to fix the token count swap bug in
        Strands SDK (input/output tokens were reversed).

        Args:
            model_id: Model identifier.
            host: Ollama server URL.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            additional_args: Top-level params (e.g., {"think": "high"}).
            keep_alive: How long to keep model loaded.

        Returns:
            Configured ExtendedOllamaModel instance.
        """
        logger.info(
            f"Creating ExtendedOllamaModel: {model_id} @ {host}, "
            f"additional_args={additional_args}, keep_alive={keep_alive}"
        )

        return ExtendedOllamaModel(
            host=host,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            keep_alive=keep_alive,
            additional_args=additional_args,
        )

    def _create_openai_model(
        self,
        model_id: str,
        host: str,
        temperature: float,
        max_tokens: int,
        additional_args: Optional[Dict[str, Any]],
    ) -> ExtendedOpenAIModel:
        """
        Create ExtendedOpenAIModel for SGLang/vLLM backends.

        Uses ExtendedOpenAIModel to extract reasoning_tokens from
        completion_tokens_details when available.

        Args:
            model_id: Model identifier.
            host: Backend server URL.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            additional_args: Additional params to merge.

        Returns:
            Configured ExtendedOpenAIModel instance.
        """
        logger.info(
            f"Creating ExtendedOpenAIModel: {model_id} @ {host}/v1, "
            f"additional_args={additional_args}"
        )

        # Build params dict
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Merge additional args if provided
        if additional_args:
            params.update(additional_args)

        return ExtendedOpenAIModel(
            client_args={
                "base_url": f"{host.rstrip('/')}/v1",
                "api_key": "dummy",  # Required but not used for local backends
            },
            model_id=model_id,
            params=params,
        )
