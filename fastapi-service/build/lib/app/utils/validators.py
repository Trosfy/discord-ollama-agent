"""Input validation utilities."""
from typing import Optional
from app.config import settings


def validate_model(model: Optional[str]) -> str:
    """
    Validate and return a valid model name.

    Args:
        model: Model name to validate (None uses default)

    Returns:
        Valid model name

    Raises:
        ValueError: If model is not in available models list
    """
    if model is None:
        return settings.OLLAMA_DEFAULT_MODEL

    if model not in settings.AVAILABLE_MODELS:
        raise ValueError(
            f"Model '{model}' not available. "
            f"Choose from: {', '.join(settings.AVAILABLE_MODELS)}"
        )

    return model


def validate_temperature(temp: Optional[float]) -> float:
    """
    Validate temperature range.

    Args:
        temp: Temperature value (None uses default 0.7)

    Returns:
        Valid temperature value

    Raises:
        ValueError: If temperature is out of range [0.0, 2.0]
    """
    if temp is None:
        return 0.7

    if not 0.0 <= temp <= 2.0:
        raise ValueError("Temperature must be between 0.0 and 2.0")

    return temp
