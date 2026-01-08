"""Pydantic request models for admin API."""

from pydantic import BaseModel, Field
from typing import Optional


class LoadModelRequest(BaseModel):
    """Request to load a model."""
    model_id: str = Field(..., description="Model identifier to load")
    priority: Optional[str] = Field(
        None,
        description="Priority override (HIGH, NORMAL, LOW)"
    )


class UnloadModelRequest(BaseModel):
    """Request to unload a model."""
    model_id: str = Field(..., description="Model identifier to unload")


class EvictRequest(BaseModel):
    """Request to trigger emergency eviction."""
    priority: str = Field(
        "NORMAL",
        description="Priority threshold for eviction (HIGH, NORMAL, LOW)"
    )
