"""
Discord webhook service for admin event notifications.

Refactored to use Strategy pattern for event formatting.
Follows Open/Closed Principle: New event types can be added by registering
new formatters without modifying this service.
"""
import httpx
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from app.config import settings
from app.services.webhook.registry import EventFormatterRegistry, get_default_registry

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Discord webhook service for sending admin event notifications.

    Uses EventFormatterRegistry for extensible event formatting.
    New event types can be added by registering formatters with the registry.

    Sends formatted Discord embeds for:
    - Model loaded/unloaded
    - Emergency evictions
    - User banned/unbanned
    - Tokens granted
    - Maintenance mode changes
    - Service health alerts
    - And more...
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        rate_limit: int = 10,
        formatter_registry: Optional[EventFormatterRegistry] = None
    ):
        """
        Initialize webhook service.

        Args:
            webhook_url: Discord webhook URL (defaults to settings)
            rate_limit: Max webhooks per minute (for rate limiting)
            formatter_registry: Custom formatter registry (defaults to global registry)
        """
        self.webhook_url = webhook_url or settings.DISCORD_ADMIN_WEBHOOK_URL
        self.rate_limit = rate_limit
        self.enabled = bool(self.webhook_url)
        self.formatter_registry = formatter_registry or get_default_registry()

        if not self.enabled:
            logger.warning("Webhook service disabled - no webhook URL configured")

    async def send_event(
        self,
        event_type: str,
        data: Dict,
        color: Optional[int] = None
    ) -> bool:
        """
        Send event notification to Discord webhook.

        Args:
            event_type: Type of event (model_loaded, user_banned, etc.)
            data: Event data dictionary
            color: Optional Discord embed color code

        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Webhook disabled, skipping event: {event_type}")
            return False

        try:
            # Get formatter from registry and format embed
            formatter = self.formatter_registry.get(event_type)
            embed = formatter.format(data)

            # Override color if specified
            if color is not None:
                embed["color"] = color

            # Skip if formatter returned None (e.g., filtered events)
            if embed is None:
                logger.debug(f"Event filtered by formatter: {event_type}")
                return False

            # Send to Discord webhook
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json={"embeds": [embed]},
                    timeout=10.0
                )
                response.raise_for_status()

            logger.info(f"Webhook sent successfully: {event_type}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to send webhook for {event_type}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending webhook: {e}")
            return False
