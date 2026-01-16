"""Status indicator messages for different interfaces."""
import random
from typing import Literal

InterfaceType = Literal["discord", "streamlit", "api"]
StatusType = Literal["thinking", "processing_files", "retrying"]

# Discord format: *<text>...*\n\n triggers AnimationManager dot cycling
# Animation: *Thinking.* → *Thinking..* → *Thinking...* (cycles every 1.1s)
STATUS_MESSAGES = {
    "discord": {
        "thinking": [
            "*Thinking...*",
            "*Processing...*",
            "*Working on it...*",
            "*One moment...*",
            "*Analyzing...*",
        ],
        "processing_files": [
            "*Processing files...*",
            "*Analyzing files...*",
            "*Reading your files...*",
            "*Examining attachments...*",
        ],
        "retrying": ["*Retrying with non-streaming mode...*"],
    },
    "streamlit": {
        "thinking": ["Thinking...", "Processing...", "Working on it..."],
        "processing_files": ["Processing files...", "Analyzing files..."],
        "retrying": ["Retrying..."],
    },
    "api": {
        "thinking": ["Processing..."],
        "processing_files": ["Processing files..."],
        "retrying": ["Retrying..."],
    },
}


def get_status_message(
    interface: InterfaceType = "discord",
    status_type: StatusType = "thinking"
) -> str:
    """
    Get randomized status message for interface.

    Discord messages use format *<text>...*\n\n which triggers
    the AnimationManager's dot cycling animation automatically.

    Args:
        interface: Target interface ("discord", "streamlit", "api")
        status_type: Type of status ("thinking", "processing_files", "retrying")

    Returns:
        Formatted status message with trailing newlines
    """
    messages = STATUS_MESSAGES.get(interface, STATUS_MESSAGES["discord"])
    pool = messages.get(status_type, ["*Processing...*"])
    return random.choice(pool) + "\n\n"
