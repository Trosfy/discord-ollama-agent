"""Vault Connector agent plugin definition."""
from .agent import VaultConnectorAgent


PLUGIN = {
    "type": "agent",
    "name": "vault_connector",
    "class": VaultConnectorAgent,
    "description": "Finds links between thoughts and existing vault knowledge",
    "category": "braindump",
    "tools": ["brain_search", "brain_fetch"],
    "config": {
        "temperature": 0.2,
        "max_tokens": 4096,
        "model_role": "braindump",
        "skip_universal_tools": True,  # Only needs brain_search/brain_fetch for vault
    },
}
