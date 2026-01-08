"""
title: Current Date Context
author: claude
version: 1.0.0
required_open_webui_version: 0.3.30

Automatically injects current date and time into system context for all conversations.
This ensures models are aware of the current date when answering time-sensitive queries.

Works transparently as a filter - no user action required.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import pytz


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter priority (lower runs first)"
        )

        timezone: str = Field(
            default="UTC",
            description="Timezone for date/time (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo')"
        )

        date_format: str = Field(
            default="%Y-%m-%d",
            description="Date format (strftime format)"
        )

        time_format: str = Field(
            default="%H:%M:%S %Z",
            description="Time format (strftime format)"
        )

        include_day_of_week: bool = Field(
            default=True,
            description="Include day of week (e.g., 'Monday')"
        )

        context_message: str = Field(
            default="Current date and time: {datetime}",
            description="Message template (use {datetime} placeholder)"
        )

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Inject current date/time into system message before model sees the request.

        This runs on every request and adds temporal context automatically.
        """
        try:
            # Get current time in specified timezone
            tz = pytz.timezone(self.valves.timezone)
            now = datetime.now(tz)

            # Format datetime string
            date_str = now.strftime(self.valves.date_format)
            time_str = now.strftime(self.valves.time_format)

            # Build datetime display
            if self.valves.include_day_of_week:
                day_of_week = now.strftime("%A")
                datetime_str = f"{day_of_week}, {date_str} {time_str}"
            else:
                datetime_str = f"{date_str} {time_str}"

            # Create context message
            context = self.valves.context_message.format(datetime=datetime_str)

            # Inject into messages
            messages = body.get("messages", [])

            if messages:
                # Check if first message is a system message
                if messages[0].get("role") == "system":
                    # Append to existing system message
                    existing_content = messages[0].get("content", "")
                    messages[0]["content"] = f"{existing_content}\n\n{context}"
                else:
                    # Insert new system message at the beginning
                    messages.insert(0, {
                        "role": "system",
                        "content": context
                    })
            else:
                # No messages yet, create system message
                messages.append({
                    "role": "system",
                    "content": context
                })

            body["messages"] = messages

        except Exception as e:
            print(f"⚠ Date context filter error: {e}")
            # Don't block the request on error, just log it

        return body
