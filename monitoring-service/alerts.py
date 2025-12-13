"""Alert management and notifications."""
import sys
sys.path.insert(0, '/shared')

import logging_client
from datetime import datetime

logger = logging_client.setup_logger('monitoring-service')


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self):
        self.sent_alerts = {}

    async def send_alert(self, service: str, message: str, severity: str, details: dict):
        """Send alert notification."""
        alert_key = f"{service}:{message}"

        # Prevent duplicate alerts
        if alert_key in self.sent_alerts:
            last_sent = self.sent_alerts[alert_key]
            if (datetime.utcnow() - last_sent).total_seconds() < 300:  # 5 min cooldown
                return

        # Log alert
        emoji = "🚨" if severity == "critical" else "⚠️"
        logger.error(f"{emoji} ALERT [{severity.upper()}] {service}: {message}")

        # TODO: Add email/Slack/Discord notifications here
        # await self._send_email(service, message, severity, details)
        # await self._send_slack(service, message, severity, details)

        self.sent_alerts[alert_key] = datetime.utcnow()
