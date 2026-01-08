"""Input validation utilities."""
from typing import Optional
from app.config import settings, get_available_model_names


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

    # Get list of available model names
    available_names = get_available_model_names()

    if model not in available_names:
        raise ValueError(
            f"Model '{model}' not available. "
            f"Choose from: {', '.join(available_names)}"
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
