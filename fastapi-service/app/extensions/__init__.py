"""
File operation extensions for Discord-Trollama Agent.

Implements SOLID principles with extension pattern for POST-PROCESSING only:
- IFileExtension: Interface (Dependency Inversion)
- ExtensionOrchestrator: Coordinator (Single Responsibility)
- DiscordFileExtension: Discord artifact registration (Open/Closed)

NOTE: File extraction happens in PREPROCESSING via FileExtractionRouter, not extensions.
"""
from app.extensions.interface import IFileExtension
from app.extensions.orchestrator import ExtensionOrchestrator
from app.extensions.discord_extension import DiscordFileExtension

__all__ = [
    "IFileExtension",
    "ExtensionOrchestrator",
    "DiscordFileExtension",
]
