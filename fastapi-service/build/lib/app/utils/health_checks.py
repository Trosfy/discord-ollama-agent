"""Health check utilities."""
import aiohttp
from app.config import settings


async def check_dynamodb() -> bool:
    """
    Check if DynamoDB Local is accessible.

    Returns:
        True if DynamoDB is responsive, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                settings.DYNAMODB_ENDPOINT,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 400  # DynamoDB returns 400 for root
    except Exception:
        return False


async def check_ollama() -> bool:
    """
    Check if Ollama is accessible.

    Returns:
        True if Ollama is responsive, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.OLLAMA_HOST}/api/version",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


async def check_ollama_model_loaded() -> bool:
    """
    Check if default model is loaded in Ollama.

    Returns:
        True if default model is available, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.OLLAMA_HOST}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m['name'] for m in data.get('models', [])]
                    return settings.OLLAMA_DEFAULT_MODEL in models
                return False
    except Exception:
        return False
