"""Ask user tool - enables agents to request user input."""
from .tool import create_ask_user_tool

PLUGIN = {
    "type": "tool",
    "name": "ask_user",
    "factory": create_ask_user_tool,
    "description": "Ask the user a question and wait for their response",
}
