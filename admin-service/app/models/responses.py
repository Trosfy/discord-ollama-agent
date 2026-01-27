"""Pydantic response models for admin API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ModelInfo(BaseModel):
    """Model info - mirrors troise-ai /models response."""
    name: str = Field(..., description="Model identifier")
    vram_size_gb: float = Field(..., description="VRAM size in GB")
    priority: str = Field(..., description="Model priority")
    backend: Optional[Dict[str, Any]] = Field(default={"type": "ollama"}, description="Backend configuration")
    api_managed: bool = Field(default=True, description="Whether model can be loaded/unloaded via API")

    # Capability flags (pass-through from troise-ai)
    supports_tools: bool = Field(default=False, description="Whether model supports tool use")
    supports_vision: bool = Field(default=False, description="Whether model supports vision")
    supports_thinking: bool = Field(default=False, description="Whether model supports thinking")
    thinking_format: Optional[str] = Field(default=None, description="Thinking format (boolean or level)")
    default_thinking_level: Optional[str] = Field(default=None, description="Default thinking level")
    context_window: Optional[int] = Field(default=None, description="Context window size")

    # Runtime state (added by admin-service)
    is_loaded: Optional[bool] = Field(default=None, description="Whether model is currently loaded")
    last_accessed: Optional[str] = Field(default=None, description="Last access timestamp")


class ModelListResponse(BaseModel):
    """Response for listing models."""
    models: List[ModelInfo] = Field(..., description="List of models")
    count: int = Field(..., description="Total count of models")


class LoadModelResponse(BaseModel):
    """Response for model load operation."""
    status: str = Field(..., description="Operation status")
    model_id: str = Field(..., description="Model identifier")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class UnloadModelResponse(BaseModel):
    """Response for model unload operation."""
    status: str = Field(..., description="Operation status")
    model_id: str = Field(..., description="Model identifier")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class EvictResponse(BaseModel):
    """Response for emergency eviction operation."""
    status: str = Field(..., description="Operation status")
    evicted: bool = Field(..., description="Whether a model was evicted")
    model_id: Optional[str] = Field(None, description="Evicted model ID")
    size_gb: Optional[float] = Field(None, description="Freed VRAM in GB")
    message: str = Field(..., description="Human-readable message")
