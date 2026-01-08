"""
Default Model Registry - Common Ollama models with default capabilities.

This profile serves as a fallback registry for user-selected models not in active profile.
Models defined here are available globally, regardless of which profile is active.

Purpose:
- Provide sensible defaults for common Ollama models
- Enable users to select any Ollama model without profile configuration
- Maintain consistency across model capabilities

Not a VRAM profile - does NOT participate in profile selection/switching.
"""
from typing import List
from app.config import ModelCapabilities, BackendConfig


# Common Ollama models with default capabilities
# VRAM sizes based on actual Ollama model sizes (measured via /api/tags)
DEFAULT_MODELS: List[ModelCapabilities] = [
    # === Small Models (< 10GB) ===
    # Matches actual installed models from `ollama list`
    ModelCapabilities(
        name="qwen3:4b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=2.5,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="rnj-1:8b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=5.1,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="qwen3-vl:8b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_vision=True,
        supports_tools=False,  # Vision model - no tools
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=6.1,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="deepseek-ocr:3b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=6.7,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="ministral-3:14b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_vision=True,
        supports_tools=True,
        supports_thinking=False,
        context_window=131072,
        vram_size_gb=9.1,
        priority="NORMAL"
    ),

    # === Medium Models (10-20GB) ===
    ModelCapabilities(
        name="gpt-oss:20b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=True,
        thinking_format="level",
        default_thinking_level="medium",
        context_window=131072,
        vram_size_gb=13.0,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="magistral:24b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=14.0,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="devstral-small-2:24b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=15.0,
        priority="NORMAL"
    ),

    # === Large Models (20-80GB) ===
    ModelCapabilities(
        name="nemotron-3-nano:30b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=24.0,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="deepseek-r1:70b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=False,  # Reasoning model - no tools
        supports_thinking=True,
        thinking_format="boolean",
        context_window=131072,
        vram_size_gb=42.0,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="gpt-oss:120b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=True,
        thinking_format="level",
        default_thinking_level="high",
        context_window=131072,
        vram_size_gb=65.0,
        priority="NORMAL"
    ),

    ModelCapabilities(
        name="devstral-2:123b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=False,
        context_window=32768,
        vram_size_gb=74.0,
        priority="NORMAL"
    ),

    # === Embedding Models ===
    ModelCapabilities(
        name="qwen3-embedding:4b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=False,  # Embedding models don't support tools
        supports_thinking=False,
        context_window=8192,
        vram_size_gb=2.5,
        priority="LOW"
    ),
]


def get_default_model_capabilities(model_name: str) -> ModelCapabilities | None:
    """
    Get default capabilities for a model by name.

    Args:
        model_name: Model identifier

    Returns:
        ModelCapabilities if found in default registry, None otherwise
    """
    for model in DEFAULT_MODELS:
        if model.name == model_name:
            return model
    return None


def get_generic_ollama_capabilities(model_name: str) -> ModelCapabilities:
    """
    Generate generic capabilities for unknown Ollama models.

    Used as last resort when model not found in any profile or default registry.

    Args:
        model_name: Model identifier

    Returns:
        Generic ModelCapabilities with safe defaults
    """
    from app.config import settings

    return ModelCapabilities(
        name=model_name,
        backend=BackendConfig(
            type="ollama",
            endpoint=settings.OLLAMA_HOST,
            options={"keep_alive": "10m"}
        ),
        supports_tools=True,  # Assume most models support tools
        supports_thinking=False,
        thinking_format="boolean",
        context_window=32768,
        vram_size_gb=8.0,  # Conservative estimate
        priority="NORMAL"
    )
