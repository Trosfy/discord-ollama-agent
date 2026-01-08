"""Configuration manager for persisting and applying system settings.

This service manages runtime configuration changes and persists them to disk.
Settings are stored in a JSON file that can be read by all services.
"""
import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Any
import logging_client

logger = logging_client.setup_logger('fastapi')

# Configuration file path (shared volume)
CONFIG_FILE = Path("/shared/trollama_config.json")


class ConfigManager:
    """Manages system configuration persistence and application."""

    def __init__(self):
        self.config_file = CONFIG_FILE
        self._ensure_config_file()

    def _ensure_config_file(self):
        """Ensure configuration file exists with defaults."""
        if not self.config_file.exists():
            # Create with defaults from environment
            from app.config import settings
            default_config = {
                "DEFAULT_MODEL": settings.DEFAULT_MODEL,
                "ROUTER_MODEL": settings.ROUTER_MODEL,
                "MAX_QUEUE_SIZE": settings.MAX_QUEUE_SIZE,
                "STREAM_CHUNK_INTERVAL": settings.STREAM_CHUNK_INTERVAL,
                "ENABLE_STREAMING": settings.ENABLE_STREAMING,
                "VRAM_CONSERVATIVE_MODE": settings.VRAM_CONSERVATIVE_MODE,
                "MAINTENANCE_MODE": settings.MAINTENANCE_MODE,
                "MAINTENANCE_MODE_HARD": settings.MAINTENANCE_MODE_HARD
            }
            self._write_config(default_config)
            logger.info(f"Created default configuration file at {self.config_file}")

    def _write_config(self, config: Dict[str, Any]):
        """Write configuration to disk."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to write configuration: {e}")
            raise

    def _read_config(self) -> Dict[str, Any]:
        """Read configuration from disk."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read configuration: {e}")
            raise

    async def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self._read_config()

    async def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary of settings to update

        Returns:
            Updated configuration dictionary
        """
        config = self._read_config()

        # Update values
        for key, value in updates.items():
            if key in config:
                config[key] = value
                logger.info(f"Updated config: {key} = {value}")

        # Write back to disk
        self._write_config(config)

        # Apply runtime changes
        await self._apply_runtime_changes(updates)

        return config

    async def _apply_runtime_changes(self, updates: Dict[str, Any]):
        """
        Apply configuration changes to running system.

        This updates the runtime settings object and triggers any necessary
        system-level changes.
        """
        from app.config import settings

        # Update runtime settings
        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
                logger.info(f"Applied runtime change: {key} = {value}")

        # Trigger specific actions for certain settings
        if "VRAM_CONSERVATIVE_MODE" in updates:
            await self._handle_vram_mode_change(updates["VRAM_CONSERVATIVE_MODE"])

        if "MAINTENANCE_MODE" in updates or "MAINTENANCE_MODE_HARD" in updates:
            await self._handle_maintenance_mode_change(
                updates.get("MAINTENANCE_MODE", False),
                updates.get("MAINTENANCE_MODE_HARD", False)
            )

    async def _handle_vram_mode_change(self, conservative_mode: bool):
        """Handle VRAM mode changes - unload models if switching to conservative."""
        if conservative_mode:
            logger.info("Switching to conservative VRAM mode - unloading all models")
            try:
                # Unload all loaded models
                import aiohttp
                from app.config import settings

                async with aiohttp.ClientSession() as session:
                    # Get loaded models
                    async with session.get(f"{settings.OLLAMA_BASE_URL}/api/ps") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for model in data.get("models", []):
                                model_name = model.get("name")
                                # Unload each model
                                await session.post(
                                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                                    json={
                                        "model": model_name,
                                        "prompt": "",
                                        "keep_alive": 0
                                    }
                                )
                                logger.info(f"Unloaded model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to unload models: {e}")

    async def _handle_maintenance_mode_change(self, soft: bool, hard: bool):
        """Handle maintenance mode changes."""
        if hard:
            logger.warning("HARD MAINTENANCE MODE ENABLED - All requests will be rejected")
        elif soft:
            logger.warning("SOFT MAINTENANCE MODE ENABLED - New requests blocked, queue continues")
        else:
            logger.info("Maintenance mode disabled")

    async def reload_from_disk(self):
        """Reload configuration from disk and apply to runtime."""
        config = self._read_config()
        await self._apply_runtime_changes(config)
        logger.info("Configuration reloaded from disk")


# Global instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get global ConfigManager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
