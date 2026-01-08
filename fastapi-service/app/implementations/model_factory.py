"""
Factory for creating Strands model instances based on backend configuration.

This module provides a centralized way to create model instances for different backends
(Ollama, TensorRT-LLM, vLLM) following SOLID principles.
"""
from typing import Union, Optional, Dict, Any
from strands.models.ollama import OllamaModel
from strands.models.openai import OpenAIModel

from app.config import settings, get_model_capabilities
from app.services.vram import get_orchestrator
import logging_client

logger = logging_client.setup_logger('model_factory')


class ModelFactory:
    """
    Factory for creating Strands model instances based on backend configuration.

    SOLID Benefits:
    - Single Responsibility: Only handles model instantiation
    - Open/Closed: Easy to extend with new backends without modifying existing code
    - Dependency Inversion: StrandsLLM depends on this factory, not concrete models
    """

    @staticmethod
    async def create_model(
        model_name: str,
        temperature: float = 0.7,
        additional_args: Optional[Dict[str, Any]] = None,
        user_selected: bool = False
    ) -> Union[OllamaModel, OpenAIModel]:
        """
        Create a Strands model instance based on backend configuration.

        NEW: Integrates with VRAMOrchestrator to ensure memory availability.

        Args:
            model_name: Model identifier from config
            temperature: Generation temperature
            additional_args: Backend-specific options (merged with config)

        Returns:
            Configured Strands model instance (OllamaModel or OpenAIModel)

        Raises:
            ValueError: If model not found in config or backend not supported
            MemoryError: If insufficient VRAM available after eviction
        """
        # Get model capabilities (returns defaults for Ollama models not in profile)
        model_caps = get_model_capabilities(model_name)

        if not model_caps:
            # Model not found and no defaults available (likely SGLang)
            if user_selected:
                raise ValueError(f"Model {model_name} not found in config (external backend models must be in profile)")
            else:
                raise ValueError(f"Model {model_name} not found in config")

        # Log if using capabilities from default registry or generic
        if user_selected and "/" not in model_name:
            # Check if model is in active profile
            from app.config import get_active_profile
            profile_models = [m.name for m in get_active_profile().available_models]
            if model_name not in profile_models:
                # Check if it's from default registry or generic
                from app.config.profiles.default import get_default_model_capabilities
                if get_default_model_capabilities(model_name):
                    logger.info(f"🎯 User selected {model_name} - using default registry capabilities")
                else:
                    logger.info(f"🎯 User selected {model_name} - using generic Ollama capabilities")

        # Coordinate with VRAM orchestrator if enabled
        # IMPORTANT: Only orchestrate Ollama models (local memory management)
        # External backends (sglang, tensorrt-llm, vllm) manage their own memory
        orchestrator = None
        orchestration_succeeded = False

        if settings.VRAM_ENABLE_ORCHESTRATOR and model_caps.backend.type == "ollama":
            orchestrator = get_orchestrator()
            try:
                await orchestrator.request_model_load(
                    model_name, temperature, additional_args
                )
                orchestration_succeeded = True
            except Exception as e:
                # User-selected models may not be in profile config - expected behavior
                if user_selected:
                    logger.info(f"ℹ️  VRAM orchestration skipped for user-selected {model_name}: {e}")
                    logger.info(f"✅ Proceeding with model load (default capabilities)")
                else:
                    logger.error(f"❌ VRAM orchestration failed for {model_name}: {e}")
                    logger.warning(f"⚠️  Continuing with model load despite orchestrator failure")
        elif model_caps.backend.type != "ollama":
            logger.debug(
                f"⏭️  Skipping VRAM orchestration for {model_name} "
                f"(external backend: {model_caps.backend.type})"
            )

        # Original model creation logic
        backend_config = model_caps.backend
        merged_args = {**backend_config.options, **(additional_args or {})}

        # Try to create model - clean up registry if it fails
        try:
            if backend_config.type == "ollama":
                model = ModelFactory._create_ollama_model(
                    model_name, temperature, merged_args
                )
            elif backend_config.type in ("tensorrt-llm", "vllm", "sglang"):
                model = ModelFactory._create_openai_model(
                    model_name, temperature, backend_config, merged_args
                )
            else:
                raise ValueError(f"Unsupported backend type: {backend_config.type}")

            # Model created successfully
            return model

        except Exception as e:
            # Model creation or load failed - clean up registry if we registered it
            if orchestration_succeeded and orchestrator:
                logger.error(
                    f"❌ Model {model_name} failed to load - cleaning up registry: {e}"
                )
                try:
                    # NEW: Detect connection errors for circuit breaker
                    error_msg = str(e).lower()
                    is_connection_error = (
                        "connection" in error_msg or
                        "connect" in error_msg or
                        "refused" in error_msg or
                        "timeout" in error_msg or
                        "unreachable" in error_msg
                    )

                    model_caps = get_model_capabilities(model_name)
                    is_sglang = model_caps and model_caps.backend.type == "sglang"

                    if is_connection_error and is_sglang:
                        # Record in crash tracker to trigger circuit breaker
                        logger.warning(
                            f"⚠️  SGLang connection error detected for {model_name}, "
                            f"marking as crashed for circuit breaker"
                        )
                        await orchestrator.mark_model_unloaded(
                            model_name,
                            crashed=True,
                            crash_reason="sglang_connection_error"
                        )
                    else:
                        # Normal unload (not connection error)
                        await orchestrator.mark_model_unloaded(model_name, crashed=False)

                except Exception as cleanup_error:
                    logger.error(f"❌ Registry cleanup failed: {cleanup_error}")

            # Re-raise the original exception
            raise

    @staticmethod
    def _create_ollama_model(
        model_name: str,
        temperature: float,
        options: Dict[str, Any]
    ) -> OllamaModel:
        """Create Ollama model instance."""
        return OllamaModel(
            host=settings.OLLAMA_HOST,
            model_id=model_name,
            temperature=temperature,
            additional_args=options
        )

    @staticmethod
    def _create_openai_model(
        model_name: str,
        temperature: float,
        backend_config,
        options: Dict[str, Any]
    ) -> OpenAIModel:
        """Create OpenAI-compatible model instance (TensorRT-LLM, vLLM, SGLang)."""
        endpoint = backend_config.endpoint
        if not endpoint:
            # Fallback to settings
            if backend_config.type == "tensorrt-llm":
                endpoint = settings.TENSORRT_HOST
            elif backend_config.type == "vllm":
                endpoint = settings.VLLM_HOST
            elif backend_config.type == "sglang":
                endpoint = settings.SGLANG_ENDPOINT

        if not endpoint:
            raise ValueError(
                f"No endpoint configured for {backend_config.type}. "
                f"Please set {backend_config.type.upper().replace('-', '_')}_HOST in settings."
            )

        # Model name mapping for OpenAI-compatible backends
        model_id_for_api = model_name
        if backend_config.type == "sglang":
            sglang_model_mappings = {
                # DEPRECATED: Eagle3 model (SGLang not in use)
                # "gpt-oss-120b-eagle3": "openai/gpt-oss-120b",
            }
            model_id_for_api = sglang_model_mappings.get(model_name, model_name)
            if model_id_for_api != model_name:
                logger.info(f"🔀 Mapping {model_name} → {model_id_for_api} for SGLang")

        return OpenAIModel(
            client_args={
                "base_url": f"{endpoint}/v1",
                "api_key": "dummy"  # Not needed for self-hosted
            },
            model_id=model_id_for_api,  # Use mapped name
            params={
                "temperature": temperature,
                **options
            }
        )
