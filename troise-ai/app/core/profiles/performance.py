"""Performance profile for 128GB VRAM systems.

This profile is optimized for maximum quality and speed by using
the largest available models for all text-based tasks, minimizing
model switching overhead while maximizing response quality.
"""
import os
from typing import List

from ..config import ModelCapabilities, BackendConfig


class PerformanceProfile:
    """
    Performance configuration profile for 128GB VRAM systems.

    Model selection prioritizes using the single best model for
    all text tasks, reducing model loading/unloading overhead and
    maximizing response quality through larger model capabilities.

    Total VRAM footprint: ~100.6GB (76 + 13 + 9.1 + 2.5)
    Active models: All models can remain loaded simultaneously
    """

    def __init__(self):
        """Initialize the performance profile with model configurations."""
        self._models = self._build_models()
        self._model_map = {m.name: m for m in self._models}

    @property
    def profile_name(self) -> str:
        """Profile identifier."""
        return "performance"

    @property
    def available_models(self) -> List[ModelCapabilities]:
        """Models available in this profile."""
        return self._models

    @property
    def router_model(self) -> str:
        """Model for request classification.

        Uses 20B model for fast, reliable routing decisions.
        The 120B model returns empty responses for short classification prompts.
        """
        return "gpt-oss:20b"

    @property
    def general_model(self) -> str:
        """Model for GENERAL classification - general conversation agent."""
        return "gpt-oss:120b"

    @property
    def research_model(self) -> str:
        """Model for RESEARCH classification - deep research agent."""
        return "gpt-oss:120b"

    @property
    def code_model(self) -> str:
        """Model for CODE classification - agentic code agent."""
        return "gpt-oss:120b"

    @property
    def braindump_model(self) -> str:
        """Model for BRAINDUMP classification - braindump agent."""
        return "gpt-oss:120b"

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
            # Primary model for all text tasks - CRITICAL priority
            # GPT-OSS uses think levels: "low", "medium", "high" (not true/false)
            ModelCapabilities(
                name="gpt-oss:120b",
                backend=ollama,
                vram_size_gb=76.0,
                priority="CRITICAL",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="medium",
                context_window=65536,
                options={"think": "medium", "num_ctx": 65536},
            ),

            # Fast router model - NORMAL priority (routing doesn't need 120B quality)
            # GPT-OSS uses think levels: "low" for fastest responses
            ModelCapabilities(
                name="gpt-oss:20b",
                backend=ollama,
                vram_size_gb=13.0,
                priority="NORMAL",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=True,  # GPT-OSS always thinks, but "low" is fast
                thinking_format="level",
                default_thinking_level="low",
                context_window=32768,
                options={"think": "low"},
            ),

            # Vision model - HIGH priority (always needed for vision tasks)
            ModelCapabilities(
                name="ministral-3:14b",
                backend=ollama,
                vram_size_gb=9.1,
                priority="HIGH",
                supports_tools=False,
                supports_vision=True,
                supports_thinking=False,
                context_window=32768,
            ),

            # Embedding model - HIGH priority (always needed for RAG)
            ModelCapabilities(
                name="qwen3-embedding:4b",
                backend=ollama,
                vram_size_gb=2.5,
                priority="HIGH",
                supports_tools=False,
                supports_vision=False,
                supports_thinking=False,
                context_window=8192,
            ),
        ]
