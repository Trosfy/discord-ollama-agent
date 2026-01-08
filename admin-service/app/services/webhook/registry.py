"""
Event Formatter Registry

Central registry for event formatters following the Registry pattern.
Implements Open/Closed Principle: New formatters can be registered without
modifying existing code.
"""

from typing import Dict, Optional
import logging

from .formatters import (
    EventFormatter,
    ModelLoadedFormatter,
    ModelUnloadedFormatter,
    EmergencyEvictionFormatter,
    UserBannedFormatter,
    UserUnbannedFormatter,
    TokensGrantedFormatter,
    MaintenanceEnabledFormatter,
    MaintenanceDisabledFormatter,
    QueuePurgedFormatter,
    ServiceHealthAlertFormatter,
    GenericFormatter
)

logger = logging.getLogger(__name__)


class EventFormatterRegistry:
    """
    Registry for event formatters.

    Responsibilities:
    - Register formatters for event types
    - Retrieve formatter for given event type
    - Provide fallback for unknown event types

    Example:
        registry = EventFormatterRegistry()
        registry.register("model_loaded", ModelLoadedFormatter())
        formatter = registry.get("model_loaded")
        embed = formatter.format(data)
    """

    def __init__(self):
        """Initialize registry with default formatters."""
        self._formatters: Dict[str, EventFormatter] = {}
        self._default_formatter = GenericFormatter()
        self._register_defaults()

    def _register_defaults(self):
        """Register all default formatters."""
        self.register("model_loaded", ModelLoadedFormatter())
        self.register("model_unloaded", ModelUnloadedFormatter())
        self.register("emergency_eviction", EmergencyEvictionFormatter())
        self.register("user_banned", UserBannedFormatter())
        self.register("user_unbanned", UserUnbannedFormatter())
        self.register("tokens_granted", TokensGrantedFormatter())
        self.register("maintenance_enabled", MaintenanceEnabledFormatter())
        self.register("maintenance_disabled", MaintenanceDisabledFormatter())
        self.register("queue_purged", QueuePurgedFormatter())
        self.register("service_health_alert", ServiceHealthAlertFormatter())

        logger.debug(f"Registered {len(self._formatters)} default formatters")

    def register(self, event_type: str, formatter: EventFormatter) -> None:
        """
        Register a formatter for an event type.

        Args:
            event_type: Event type identifier (e.g., "model_loaded")
            formatter: Formatter instance implementing EventFormatter

        Example:
            registry.register("custom_event", CustomEventFormatter())
        """
        if not isinstance(formatter, EventFormatter):
            raise TypeError(f"Formatter must implement EventFormatter interface")

        self._formatters[event_type] = formatter
        logger.debug(f"Registered formatter for event type: {event_type}")

    def get(self, event_type: str) -> EventFormatter:
        """
        Get formatter for event type.

        Args:
            event_type: Event type identifier

        Returns:
            EventFormatter: Formatter for event type (or default generic formatter)

        Example:
            formatter = registry.get("model_loaded")
            embed = formatter.format(data)
        """
        formatter = self._formatters.get(event_type, self._default_formatter)

        if formatter == self._default_formatter:
            logger.debug(f"Using default formatter for unknown event type: {event_type}")

        return formatter

    def has(self, event_type: str) -> bool:
        """
        Check if formatter exists for event type.

        Args:
            event_type: Event type identifier

        Returns:
            bool: True if formatter registered

        Example:
            if registry.has("model_loaded"):
                print("Formatter exists")
        """
        return event_type in self._formatters

    def unregister(self, event_type: str) -> bool:
        """
        Unregister a formatter.

        Args:
            event_type: Event type identifier

        Returns:
            bool: True if formatter was removed, False if not found

        Example:
            registry.unregister("custom_event")
        """
        if event_type in self._formatters:
            del self._formatters[event_type]
            logger.debug(f"Unregistered formatter for event type: {event_type}")
            return True
        return False

    def get_registered_types(self) -> list:
        """
        Get list of all registered event types.

        Returns:
            list: List of registered event type identifiers

        Example:
            types = registry.get_registered_types()
            # ["model_loaded", "model_unloaded", ...]
        """
        return list(self._formatters.keys())

    def clear(self) -> None:
        """
        Clear all registered formatters.

        Warning: This removes all formatters including defaults.
        Use _register_defaults() to restore defaults after clearing.
        """
        self._formatters.clear()
        logger.warning("Cleared all formatters from registry")


# Singleton instance for global use
_default_registry = EventFormatterRegistry()


def get_default_registry() -> EventFormatterRegistry:
    """
    Get the default global formatter registry.

    Returns:
        EventFormatterRegistry: Default registry instance

    Example:
        from app.services.webhook.registry import get_default_registry

        registry = get_default_registry()
        formatter = registry.get("model_loaded")
    """
    return _default_registry
