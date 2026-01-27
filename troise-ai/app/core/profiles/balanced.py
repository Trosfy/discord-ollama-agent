"""Balanced profile for 128GB VRAM systems.

This profile provides a diverse selection of models with varying
sizes and capabilities, allowing the system to choose the most
appropriate model for each task while maintaining flexibility.
"""
import os
from typing import List

from ..config import ModelCapabilities, BackendConfig


class BalancedProfile:
    """
    Balanced configuration profile for 128GB VRAM systems.

    Model selection emphasizes variety and appropriate model sizing
    for different task complexities. Includes both large models for
    complex reasoning and smaller models for quick responses.

    Total VRAM footprint: ~215.7GB (requires strategic model loading)
    Typical active set: ~90-110GB
    """

    def __init__(self):
        """Initialize the balanced profile with model configurations."""
        self._models = self._build_models()
        self._model_map = {m.name: m for m in self._models}

    @property
    def profile_name(self) -> str:
        """Profile identifier."""
        return "balanced"

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
        return "gpt-oss:120b"

    @property
    def research_model(self) -> str:
        """Model for RESEARCH classification - deep research agent."""
        return "magistral:24b"

    @property
    def code_model(self) -> str:
        """Model for CODE classification - agentic code agent."""
        return "devstral-small-2:24b"

    @property
    def braindump_model(self) -> str:
        """Model for BRAINDUMP classification - braindump agent."""
        return "magistral:24b"

    @property
    def vision_model(self) -> str:
        """Model for OCR and vision tasks."""
        return "ministral-3:14b"

    @property
    def embedding_model(self) -> str:
        """Model for text embeddings and RAG."""
        return "qwen3-embedding:4b"

    @property
    def image_handler_model(self) -> str:
        """LLM for image request handling - crafts prompts, selects params."""
        return "gpt-oss:20b"

    @property
    def image_model(self) -> str:
        """Diffusion model for actual image generation (NVFP4 via ComfyUI)."""
        return "flux2-dev-nvfp4"

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
            self.image_handler_model,
            self.image_model,
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

        # Diffusion backend (in-process, no HTTP) - BNB 4-bit fallback
        diffusion = BackendConfig(type="diffusion", host="local")

        # ComfyUI backend for NVFP4 image generation
        comfyui_host = os.getenv("COMFYUI_HOST", "http://localhost:8188")
        comfyui = BackendConfig(type="comfyui", host=comfyui_host)

        return [
            # Router and simple skill model - HIGH priority
            ModelCapabilities(
                name="gpt-oss:20b",
                backend=ollama,
                vram_size_gb=13.0,
                priority="HIGH",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=False,
                context_window=32768,
            ),

            # Complex skill model - HIGH priority (large but important)
            ModelCapabilities(
                name="gpt-oss:120b",
                backend=ollama,
                vram_size_gb=76.0,
                priority="HIGH",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="medium",
                context_window=65536,
            ),

            # General purpose model - HIGH priority
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

            # Code model (small) - NORMAL priority
            ModelCapabilities(
                name="devstral-small-2:24b",
                backend=ollama,
                vram_size_gb=15.0,
                priority="NORMAL",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=False,
                context_window=65536,
            ),

            # Code model (large) - LOW priority (loaded on demand)
            ModelCapabilities(
                name="devstral-2:123b",
                backend=ollama,
                vram_size_gb=74.0,
                priority="LOW",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="medium",
                context_window=131072,
            ),

            # Agent model - NORMAL priority
            ModelCapabilities(
                name="magistral:24b",
                backend=ollama,
                vram_size_gb=15.0,
                priority="NORMAL",
                supports_tools=True,
                supports_vision=False,
                supports_thinking=True,
                thinking_format="boolean",
                context_window=65536,
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

            # Image generation model (FLUX 2.dev NVFP4 via ComfyUI) - NORMAL priority
            ModelCapabilities(
                name="flux2-dev-nvfp4",
                backend=comfyui,
                model_type="diffusion",
                vram_size_gb=80.0,  # NVFP4 ~20GB model + ~60GB runtime overhead
                priority="NORMAL",
                api_managed=False,  # ComfyUI manages lifecycle
                supports_tools=False,
                supports_vision=False,
                supports_thinking=False,
                context_window=0,  # N/A for diffusion models
                options={
                    "workflow": {
                        "unet_name": "flux2-dev-nvfp4.safetensors",
                        "clip_name": "mistral_3_small_flux2_fp4_mixed.safetensors",
                        "clip_type": "flux2",
                        "vae_name": "flux2-vae.safetensors",
                        "latent_type": "EmptyFlux2LatentImage",
                        "sampler_name": "euler",
                        "scheduler": "simple",
                    }
                },
            ),

            # Image generation fallback (FLUX 2.dev BNB 4-bit) - LOW priority
            ModelCapabilities(
                name="flux2-dev-bnb4bit",
                backend=diffusion,
                model_type="diffusion",
                vram_size_gb=20.0,  # BNB 4-bit quantization similar footprint
                priority="LOW",
                supports_tools=False,
                supports_vision=False,
                supports_thinking=False,
                context_window=0,  # N/A for diffusion models
            ),
        ]
