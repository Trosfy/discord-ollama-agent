"""Pydantic models for API requests."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MessageRequest(BaseModel):
    """Request from Discord bot to process a message."""

    user_id: str
    thread_id: str
    message: str
    message_id: str
    channel_id: str
    guild_id: Optional[str] = None


class QueuedRequest(BaseModel):
    """Internal queue request representation."""

    request_id: str
    user_id: str
    thread_id: str
    message: str
    message_id: str
    channel_id: str
    estimated_tokens: int
    enqueued_at: datetime
    attempt: int = 0
    state: str = "queued"  # queued, processing, completed, failed, cancelled


class CancelRequest(BaseModel):
    """Request to cancel a queued message."""

    request_id: str
    message_id: str


class GrantTokensRequest(BaseModel):
    """Admin request to grant bonus tokens."""

    user_id: str
    amount: int = Field(gt=0)


class UpdatePreferencesRequest(BaseModel):
    """User request to update preferences."""

    preferred_model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    base_prompt: Optional[str] = Field(None, max_length=500)
