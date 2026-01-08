"""Pydantic response models for admin API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ModelInfo(BaseModel):
    """Information about a model."""
    name: str = Field(..., description="Model identifier")
    vram_size_gb: float = Field(..., description="VRAM size in GB")
    priority: str = Field(..., description="Model priority")
    backend: Dict[str, Any] = Field(..., description="Backend configuration")
    capabilities: Optional[List[str]] = Field(None, description="Model capabilities")
    is_loaded: Optional[bool] = Field(None, description="Whether model is currently loaded")
    last_accessed: Optional[str] = Field(None, description="Last access timestamp")


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
