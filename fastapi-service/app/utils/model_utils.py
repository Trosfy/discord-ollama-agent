"""Utility functions for model configuration."""
from app.config import settings, get_model_capabilities
import logging_client
from typing import Optional

logger = logging_client.setup_logger('fastapi')


def get_ollama_keep_alive(model_name: Optional[str] = None) -> str:
    """
    Get Ollama keep_alive parameter from model capabilities or config.

    Respects per-model keep_alive settings from ModelCapabilities.
    Falls back to priority-based defaults or global setting if not specified.

    Args:
        model_name: Model identifier (e.g., "gpt-oss:20b")
                    If None, uses global OLLAMA_KEEP_ALIVE setting

    Returns:
        str: Formatted keep_alive value for OllamaModel

    Examples:
        - gpt-oss:20b → "30m" (HIGH priority, per-model setting)
        - Unknown model → "1800s" (global default)
    """
    # Try to get per-model keep_alive setting
    if model_name:
        capabilities = get_model_capabilities(model_name)

        if capabilities:
            # Check for explicit keep_alive in backend options
            keep_alive = capabilities.backend.options.get("keep_alive")
            if keep_alive:
                logger.debug(f"Using per-model keep_alive for {model_name}: {keep_alive}")
                return keep_alive

            # Fallback: Use priority to determine default keep_alive
            priority_defaults = {
                "CRITICAL": "60m",  # Critical models stay hot
                "HIGH": "30m",       # Router, fast coder
                "NORMAL": "15m",     # Standard models
                "LOW": "5m"          # Large models, evict quickly
            }
            default = priority_defaults.get(capabilities.priority, "15m")
            logger.debug(f"Using priority-based keep_alive for {model_name}: {default} (priority={capabilities.priority})")
            return default

    # Fallback to global setting (for backward compatibility)
    if settings.OLLAMA_KEEP_ALIVE >= 0:
        return f"{settings.OLLAMA_KEEP_ALIVE}s"
    return "-1"


async def force_unload_model(model_id: str) -> None:
    """
    Force unload model immediately via VRAMOrchestrator.

    Uses the orchestrator's mark_as_unloaded() method which:
    - Routes to correct backend manager (Ollama, TensorRT, vLLM)
    - Updates VRAM registry
    - Ensures multi-backend compatibility

    Args:
        model_id: Model identifier (e.g., "gpt-oss:20b")
    """
    try:
        from app.services.vram import get_orchestrator

        orchestrator = get_orchestrator()
        await orchestrator.mark_as_unloaded(model_id)

        logger.debug(f"✅ Force unload complete for {model_id} via orchestrator")
    except Exception as e:
        logger.warning(f"⚠️  Force unload failed for {model_id}: {e}")
