"""Minimal message classification leveraging agentic LLM capabilities."""
import re


def is_simple_greeting(message: str) -> bool:
    """
    Detect obvious greetings to save LLM costs on trivial interactions.

    This is intentionally minimal - only catches clear-cut cases.
    Everything else is handled by the agent's natural language understanding.

    Args:
        message: User's message content

    Returns:
        True if message is an obvious greeting, False otherwise
    """
    message_lower = message.lower().strip()

    # Only catch extremely obvious greetings
    # Intentionally conservative to avoid false positives
    greeting_patterns = [
        r'^hi+$',
        r'^hello+$',
        r'^hey+$',
        r'^hi there$',
        r'^hello there$',
        r'^hey there$',
        r'^good (morning|afternoon|evening|night)$',
        r'^yo+$',
        r"^what'?s up$",
        r'^sup+$',
    ]

    return any(re.match(pattern, message_lower) for pattern in greeting_patterns)


def get_greeting_response() -> str:
    """Return friendly greeting without LLM call."""
    return (
        "Hey there! I'm ready to help you with research, comparisons, "
        "or any questions you have. Just let me know what you need!"
    )
