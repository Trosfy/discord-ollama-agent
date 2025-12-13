"""Pydantic models for API responses."""
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class QueuedResponse(BaseModel):
    """Response when request is queued."""

    request_id: str
    status: str = "queued"
    queue_position: int
    eta_seconds: int


class ProcessingResponse(BaseModel):
    """Response when request is being processed."""

    request_id: str
    status: str = "processing"


class CompletedResponse(BaseModel):
    """Response when request is completed."""

    request_id: str
    status: str = "completed"
    response: str
    tokens_used: int
    model: str


class FailedResponse(BaseModel):
    """Response when request fails."""

    request_id: str
    status: str = "failed"
    error: str
    attempt: int


class UserResponse(BaseModel):
    """User information response."""

    user_id: str
    discord_username: str
    user_tier: str
    preferred_model: str
    temperature: float
    tokens_remaining: int
    weekly_budget: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    services: Dict[str, bool]
