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


async def check_ollama_model_loaded(model_name: str = None) -> bool:
    """
    Check if specified model is loaded in Ollama.

    Args:
        model_name: Model name to check (defaults to profile's router model)

    Returns:
        True if model is available, False otherwise
    """
    if model_name is None:
        # Use profile's router model if not specified
        from app.config import get_active_profile
        try:
            profile = get_active_profile()
            model_name = profile.router_model
        except RuntimeError:
            # Fallback to hardcoded default if profile not available
            model_name = settings.OLLAMA_DEFAULT_MODEL

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.OLLAMA_HOST}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m['name'] for m in data.get('models', [])]
                    return model_name in models
                return False
    except Exception:
        return False


async def check_vram_status() -> dict:
    """
    Check VRAM orchestrator status.

    Returns:
        Dict with 'healthy' boolean and status details
    """
    try:
        from app.services.vram import get_orchestrator
        orchestrator = get_orchestrator()
        status = await orchestrator.get_status()

        # Determine health
        usage_pct = status['memory']['usage_pct']
        psi_some = status['memory'].get('psi_some_avg10', 0)
        psi_full = status['memory'].get('psi_full_avg10', 0)

        # Health thresholds from research
        healthy = (
            usage_pct < 90.0 and          # Under 90% usage
            psi_some < 50.0 and            # PSI some <50%
            psi_full < 15.0                # PSI full <15%
        )

        warning = (
            usage_pct > 80.0 or
            psi_some > 20.0 or
            psi_full > 5.0
        )

        return {
            'healthy': healthy,
            'warning': warning,
            'usage_pct': usage_pct,
            'psi_some_avg10': psi_some,
            'psi_full_avg10': psi_full,
            'loaded_models': len(status['loaded_models']),
            'available_gb': status['memory']['available_gb']
        }
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }
