"""Utility functions for model configuration."""
from app.config import settings
from strands.models.ollama import OllamaModel
import asyncio
import aiohttp
import logging_client

logger = logging_client.setup_logger('fastapi')


def get_ollama_keep_alive() -> str:
    """
    Get Ollama keep_alive parameter from config.

    Converts OLLAMA_KEEP_ALIVE integer setting to Ollama-compatible format:
    - 0 -> "0s" (immediate unload)
    - 300 -> "300s" (keep for 5 minutes)
    - -1 -> "-1" (never unload)

    Returns:
        str: Formatted keep_alive value for OllamaModel
    """
    if settings.OLLAMA_KEEP_ALIVE >= 0:
        return f"{settings.OLLAMA_KEEP_ALIVE}s"
    return "-1"


async def force_unload_model(model_id: str) -> None:
    """
    Force unload model immediately (override keep_alive).

    Polls Ollama's /api/ps endpoint to verify model is fully unloaded from VRAM
    before returning (prevents VRAM overlap on 16GB GPU).

    Used when router classified to non-SELF_HANDLE to free VRAM
    for different target model (16GB constraint).

    Args:
        model_id: Model identifier (e.g., "gpt-oss:20b")
    """
    try:
        from strands import Agent

        dummy_model = OllamaModel(
            host=settings.OLLAMA_HOST,
            model_id=model_id,
            keep_alive="0s"  # Override existing keep_alive
        )

        # Use Agent wrapper to trigger minimal inference (forces unload with keep_alive=0s)
        agent = Agent(model=dummy_model, tools=[])
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, agent, "x")  # Agent is callable

        logger.debug(f"🔽 Force unload requested for {model_id}")

        # Poll until model is truly unloaded from VRAM
        success = await _wait_for_model_unload(model_id)

        if success:
            logger.debug(f"✅ Confirmed {model_id} fully unloaded")
        else:
            logger.warning(f"⚠️  Could not confirm {model_id} unload - continuing anyway")
    except Exception as e:
        logger.warning(f"⚠️  Force unload failed for {model_id}: {e}")


async def _wait_for_model_unload(model_id: str, timeout: float = 10.0, poll_interval: float = 0.3) -> bool:
    """
    Poll Ollama's /api/ps endpoint until model disappears from VRAM.

    Args:
        model_id: Model identifier to wait for
        timeout: Maximum time to wait in seconds (default: 10s)
        poll_interval: Time between polls in seconds (default: 0.3s)

    Returns:
        bool: True if model unloaded successfully, False if timeout occurred
    """
    start_time = asyncio.get_event_loop().time()
    attempt = 0

    while True:
        attempt += 1

        try:
            # Check if model is still loaded in VRAM
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{settings.OLLAMA_HOST}/api/ps") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        loaded_models = [m['name'] for m in data.get('models', [])]

                        # Check if our model is still in the list
                        if model_id not in loaded_models:
                            # Model successfully unloaded!
                            logger.debug(f"🎯 {model_id} unloaded after {attempt} polls")
                            return True

        except Exception as e:
            logger.debug(f"⚠️  Poll attempt {attempt} failed: {e}")

        # Check timeout
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            logger.warning(f"⏱️  Timeout waiting for {model_id} to unload ({elapsed:.1f}s)")
            return False  # Timeout - continue anyway, don't block execution

        # Wait before next poll
        await asyncio.sleep(poll_interval)
