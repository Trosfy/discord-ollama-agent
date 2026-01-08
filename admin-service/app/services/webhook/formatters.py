"""
Event Formatter Strategies for Discord Webhooks

Implements the Strategy pattern for formatting Discord embeds.
Following Open/Closed Principle: Open for extension (add new formatters),
closed for modification (don't change existing formatters).
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime, timezone


# Discord embed color codes
COLORS = {
    "success": 3066993,   # Green
    "info": 3447003,      # Blue
    "warning": 15105570,  # Orange
    "error": 15158332,    # Red
    "default": 9807270    # Gray
}


class EventFormatter(ABC):
    """
    Abstract base class for event formatters.

    Each concrete formatter implements format() to create a Discord embed
    for a specific event type.
    """

    @abstractmethod
    def format(self, data: Dict) -> Dict:
        """
        Format event data into Discord embed.

        Args:
            data: Event data dictionary

        Returns:
            dict: Discord embed dictionary with title, description, color, fields
        """
        pass

    def get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()


class ModelLoadedFormatter(EventFormatter):
    """Format model loaded events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "✅ Model Loaded",
            "description": f"Model **{data.get('model_id')}** loaded successfully",
            "color": COLORS["success"],
            "fields": [
                {"name": "Model", "value": data.get("model_id", "unknown"), "inline": True},
                {"name": "VRAM Size", "value": f"{data.get('vram_size_gb', 0):.1f} GB", "inline": True},
                {"name": "Priority", "value": data.get("priority", "NORMAL"), "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class ModelUnloadedFormatter(EventFormatter):
    """Format model unloaded events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "🔄 Model Unloaded",
            "description": f"Model **{data.get('model_id')}** unloaded",
            "color": COLORS["info"],
            "fields": [
                {"name": "Model", "value": data.get("model_id", "unknown"), "inline": True},
                {"name": "Freed VRAM", "value": f"{data.get('freed_gb', 0):.1f} GB", "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class EmergencyEvictionFormatter(EventFormatter):
    """Format emergency eviction events."""

    def format(self, data: Dict) -> Dict:
        evicted = data.get("evicted", False)

        if evicted:
            return {
                "title": "🚨 Emergency Eviction",
                "description": f"Model **{data.get('model_id')}** evicted due to VRAM pressure",
                "color": COLORS["error"],
                "fields": [
                    {"name": "Model", "value": data.get("model_id", "unknown"), "inline": True},
                    {"name": "Freed VRAM", "value": f"{data.get('size_gb', 0):.1f} GB", "inline": True},
                    {"name": "Priority", "value": data.get("priority", "NORMAL"), "inline": True},
                    {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True},
                    {"name": "Reason", "value": data.get("reason", "Manual eviction"), "inline": False}
                ],
                "timestamp": self.get_timestamp()
            }
        else:
            return {
                "title": "⚠️ Eviction Attempted",
                "description": "No models available for eviction",
                "color": COLORS["warning"],
                "fields": [
                    {"name": "Priority", "value": data.get("priority", "NORMAL"), "inline": True},
                    {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
                ],
                "timestamp": self.get_timestamp()
            }


class UserBannedFormatter(EventFormatter):
    """Format user banned events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "🔨 User Banned",
            "description": f"User **{data.get('user_id')}** has been banned",
            "color": COLORS["error"],
            "fields": [
                {"name": "User ID", "value": data.get("user_id", "unknown"), "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True},
                {"name": "Reason", "value": data.get("reason", "No reason provided"), "inline": False}
            ],
            "timestamp": self.get_timestamp()
        }


class UserUnbannedFormatter(EventFormatter):
    """Format user unbanned events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "✅ User Unbanned",
            "description": f"User **{data.get('user_id')}** has been unbanned",
            "color": COLORS["success"],
            "fields": [
                {"name": "User ID", "value": data.get("user_id", "unknown"), "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class TokensGrantedFormatter(EventFormatter):
    """Format tokens granted events."""

    def format(self, data: Dict) -> Dict:
        amount = data.get("amount", 0)

        # Only send webhook for large grants (>10k tokens)
        if amount < 10000:
            return None

        return {
            "title": "💰 Bonus Tokens Granted",
            "description": f"**{amount:,}** tokens granted to user",
            "color": COLORS["info"],
            "fields": [
                {"name": "User ID", "value": data.get("user_id", "unknown"), "inline": True},
                {"name": "Amount", "value": f"{amount:,} tokens", "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True},
                {"name": "Reason", "value": data.get("reason", "No reason provided"), "inline": False}
            ],
            "timestamp": self.get_timestamp()
        }


class MaintenanceEnabledFormatter(EventFormatter):
    """Format maintenance enabled events."""

    def format(self, data: Dict) -> Dict:
        mode = data.get("mode", "soft")
        return {
            "title": "⚠️ Maintenance Mode Enabled",
            "description": f"**{mode.upper()}** maintenance mode activated",
            "color": COLORS["warning"],
            "fields": [
                {"name": "Mode", "value": mode.upper(), "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True},
                {"name": "Note", "value": "Soft: Queue still works\nHard: All requests rejected", "inline": False}
            ],
            "timestamp": self.get_timestamp()
        }


class MaintenanceDisabledFormatter(EventFormatter):
    """Format maintenance disabled events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "✅ Maintenance Mode Disabled",
            "description": "System returned to normal operation",
            "color": COLORS["success"],
            "fields": [
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class QueuePurgedFormatter(EventFormatter):
    """Format queue purged events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "🗑️ Queue Purged",
            "description": "Request queue has been purged",
            "color": COLORS["warning"],
            "fields": [
                {"name": "Requests Removed", "value": str(data.get("purged_count", 0)), "inline": True},
                {"name": "Admin", "value": f"<@{data.get('admin_user', 'unknown')}>", "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class ServiceHealthAlertFormatter(EventFormatter):
    """Format service health alert events."""

    def format(self, data: Dict) -> Dict:
        severity = data.get("severity", "warning")
        service = data.get("service", "unknown")

        return {
            "title": f"{'🚨' if severity == 'critical' else '⚠️'} Service Health Alert",
            "description": data.get("message", f"{service} is unhealthy"),
            "color": COLORS["error"] if severity == "critical" else COLORS["warning"],
            "fields": [
                {"name": "Service", "value": service, "inline": True},
                {"name": "Severity", "value": severity.upper(), "inline": True},
                {"name": "Consecutive Failures", "value": str(data.get("consecutive_failures", 0)), "inline": True},
                {"name": "Error", "value": data.get("error", "Unknown error"), "inline": False},
                {"name": "Status Code", "value": str(data.get("status_code", "N/A")), "inline": True}
            ],
            "timestamp": self.get_timestamp()
        }


class GenericFormatter(EventFormatter):
    """Format generic/unknown events."""

    def format(self, data: Dict) -> Dict:
        return {
            "title": "ℹ️ Admin Action",
            "description": str(data.get("message", "Admin action performed")),
            "color": COLORS["default"],
            "fields": [
                {"name": "Data", "value": str(data), "inline": False}
            ],
            "timestamp": self.get_timestamp()
        }
