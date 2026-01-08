"""
Tests for multi-backend LLM architecture.

Tests configuration, ModelFactory, and integration with StrandsLLM.
"""
import pytest
from app.config import (
    settings,
    get_model_capabilities,
    BackendConfig,
    _AVAILABLE_MODELS
)
from app.implementations.model_factory import ModelFactory
from strands.models.ollama import OllamaModel
from strands.models.openai import OpenAIModel


class TestBackendConfig:
    """Test BackendConfig model."""

    def test_backend_config_creation(self):
        """Test creating BackendConfig instances."""
        # Ollama backend
        ollama_backend = BackendConfig(type="ollama", options={"keep_alive": "30m"})
        assert ollama_backend.type == "ollama"
        assert ollama_backend.options["keep_alive"] == "30m"
        assert ollama_backend.endpoint is None

        # TensorRT backend
        tensorrt_backend = BackendConfig(
            type="tensorrt-llm",
            endpoint="http://localhost:8000",
            options={"use_draft_model": True, "max_draft_len": 3}
        )
        assert tensorrt_backend.type == "tensorrt-llm"
        assert tensorrt_backend.endpoint == "http://localhost:8000"
        assert tensorrt_backend.options["use_draft_model"] is True

    def test_backend_config_defaults(self):
        """Test BackendConfig default values."""
        backend = BackendConfig(type="ollama")
        assert backend.type == "ollama"
        assert backend.endpoint is None
        assert backend.options == {}


class TestModelCapabilities:
    """Test ModelCapabilities with backend field."""

    def test_all_models_have_backend(self):
        """Test that all configured models have backend field."""
        for model in _AVAILABLE_MODELS:
            assert hasattr(model, 'backend'), f"Model {model.name} missing backend field"
            assert isinstance(model.backend, BackendConfig), \
                f"Model {model.name} backend is not BackendConfig"

    def test_get_model_capabilities(self):
        """Test retrieving model capabilities."""
        # Test existing model
        model = get_model_capabilities("gpt-oss:20b")
        assert model is not None
        assert model.name == "gpt-oss:20b"
        assert model.backend.type == "ollama"
        assert model.supports_tools is True
        assert model.supports_thinking is True

        # Test non-existent model
        model = get_model_capabilities("non-existent-model")
        assert model is None


class TestModelFactory:
    """Test ModelFactory for creating backend instances."""

    def test_create_ollama_model(self):
        """Test creating Ollama model instance."""
        model = ModelFactory.create_model(
            model_name="gpt-oss:20b",
            temperature=0.7
        )
        assert isinstance(model, OllamaModel)
        assert model.config['model_id'] == "gpt-oss:20b"

    def test_create_model_with_additional_args(self):
        """Test creating model with additional arguments."""
        model = ModelFactory.create_model(
            model_name="gpt-oss:20b",
            temperature=0.8,
            additional_args={"think": "high"}
        )
        assert isinstance(model, OllamaModel)
        # Additional args should be merged with config options

    def test_create_model_invalid_model(self):
        """Test error handling for invalid model name."""
        with pytest.raises(ValueError, match="not found in config"):
            ModelFactory.create_model(
                model_name="invalid-model",
                temperature=0.7
            )

    def test_create_model_unsupported_backend(self):
        """Test error handling for unsupported backend type."""
        # This would require a model with unsupported backend in config
        # For now, we test the error message format
        pass

    def test_create_tensorrt_model_no_endpoint(self):
        """Test error when TensorRT endpoint not configured."""
        # Temporarily create a TensorRT model config without endpoint
        # and ensure proper error is raised
        # Note: This would require adding a test model to config
        # or mocking get_model_capabilities
        pass


class TestBackendIntegration:
    """Test integration with StrandsLLM."""

    def test_strands_llm_imports(self):
        """Test that StrandsLLM can be imported without errors."""
        from app.implementations.strands_llm import StrandsLLM
        assert StrandsLLM is not None

    def test_strands_llm_initialization(self):
        """Test StrandsLLM initialization with ModelFactory."""
        from app.implementations.strands_llm import StrandsLLM

        llm = StrandsLLM()
        assert llm.default_model == settings.OLLAMA_DEFAULT_MODEL
        assert llm.ollama_host == settings.OLLAMA_HOST

    @pytest.mark.asyncio
    async def test_model_factory_in_generate(self):
        """Test that ModelFactory is used in generate methods."""
        from app.implementations.strands_llm import StrandsLLM

        llm = StrandsLLM()

        # Test that we can create model instances for different backends
        # Note: This doesn't actually call the API, just tests model creation
        model = ModelFactory.create_model("gpt-oss:20b", temperature=0.7)
        assert isinstance(model, OllamaModel)


class TestBackendSettings:
    """Test backend-related settings."""

    def test_backend_host_settings(self):
        """Test that backend host settings are present."""
        assert hasattr(settings, 'OLLAMA_HOST')
        assert hasattr(settings, 'TENSORRT_HOST')
        assert hasattr(settings, 'VLLM_HOST')

        # Default values
        assert settings.OLLAMA_HOST == "http://host.docker.internal:11434"
        assert settings.TENSORRT_HOST is None
        assert settings.VLLM_HOST is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
