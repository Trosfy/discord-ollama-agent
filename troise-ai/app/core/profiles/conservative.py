"""Conservative profile for 16GB VRAM systems.

This profile is optimized for memory-constrained environments,
using smaller models that can fit within 16GB of VRAM while
still providing reasonable capability across all task types.
"""
import os
from typing import List

from ..config import ModelCapabilities, BackendConfig


class ConservativeProfile:
    """
    Conservative configuration profile for 16GB VRAM systems.

    Model selection prioritizes fitting within memory constraints
    while maintaining capability for essential tasks. Models are
    sized to allow for reasonable concurrency without VRAM exhaustion.

    Total VRAM footprint: ~29.7GB (requires model swapping)
    Active models at any time: ~15-18GB typical
    """

    def __init__(self):
        """Initialize the conservative profile with model configurations."""
        self._models = self._build_models()
        self._model_map = {m.name: m for m in self._models}

    @property
    def profile_name(self) -> str:
        """Profile identifier."""
        return "conservative"

    @property
    def available_models(self) -> List[ModelCapabilities]:
        """Models available in this profile."""
        return self._models

    @property
    def router_model(self) -> str:
        """Model for request classification."""
        return "gpt-oss:20b"

    @property
    def general_model(self) -> str:
        """Model for GENERAL classification - general conversation agent."""
        return "gpt-oss:20b"

    @property
    def research_model(self) -> str:
        """Model for RESEARCH classification - deep research agent."""
        return "gpt-oss:20b"

    @property
    def code_model(self) -> str:
        """Model for CODE classification - agentic code agent."""
        return "rnj-1:8b"

    @property
    def braindump_model(self) -> str:
        """Model for BRAINDUMP classification - braindump agent."""
        return "gpt-oss:20b"

    @property
    def vision_model(self) -> str:
        """Model for OCR and vision tasks."""
        return "ministral-3:14b"

    @property
    def embedding_model(self) -> str:
        """Model for text embeddings and RAG."""
        return "qwen3-embedding:4b"

    def validate(self) -> None:
        """
        Validate all assigned models exist in available_models.

        Raises:
            ValueError: If any assigned model is not in available_models.
        """
        assigned_models = {
            self.router_model,
            self.general_model,
            self.research_model,
            self.code_model,
            self.braindump_model,
            self.vision_model,
            self.embedding_model,
        }

        available_names = {m.name for m in self._models}

        missing = assigned_models - available_names
        if missing:
            raise ValueError(
                f"Profile '{self.profile_name}' assigns models not in available_models: {missing}"
            )

    def _build_models(self) -> List[ModelCapabilities]:
        """Build the list of available models for this profile."""
        # Default Ollama backend (use env var for Docker compatibility)
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        ollama = BackendConfig(type="ollama", host=ollama_host)

        return [
            # Router and agent model - CRITICAL priority (never evict)
            ModelCapabilities(
                name="gpt-oss:20b",
                backend=ollama,
                vram_size_gb=13.0,
                priority="CRITICAL",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=False,
                context_window=32768,
            ),

            # Code and simple skill model - HIGH priority
            ModelCapabilities(
                name="rnj-1:8b",
                backend=ollama,
                vram_size_gb=5.1,
                priority="HIGH",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=False,
                context_window=32768,
            ),

            # Vision model - NORMAL priority
            ModelCapabilities(
                name="ministral-3:14b",
                backend=ollama,
                vram_size_gb=9.1,
                priority="NORMAL",
                supports_tools=False,
                supports_vision=True,
                supports_thinking=False,
                context_window=32768,
            ),

            # Embedding model - LOW priority
            ModelCapabilities(
                name="qwen3-embedding:4b",
                backend=ollama,
                vram_size_gb=2.5,
                priority="LOW",
                supports_tools=False,
                supports_vision=False,
                supports_thinking=False,
                context_window=8192,
            ),
        ]
