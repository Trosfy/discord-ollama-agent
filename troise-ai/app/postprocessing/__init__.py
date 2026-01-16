"""TROISE AI Postprocessing Module.

Handles postprocessing of agent/skill responses:
- ArtifactExtractionChain: Chain of Responsibility for artifact extraction
- ContentSanitizer: Strip preamble/postamble from extracted content
- Handlers: Tool, LLM, and Regex-based extraction
"""
from .artifact_chain import ArtifactExtractionChain, Artifact
from .sanitizer import ContentSanitizer
from .handlers import (
    IArtifactHandler,
    ToolArtifactHandler,
    LLMExtractionHandler,
    RegexFallbackHandler,
)

__all__ = [
    # Chain
    "ArtifactExtractionChain",
    "Artifact",
    # Sanitizer
    "ContentSanitizer",
    # Handlers
    "IArtifactHandler",
    "ToolArtifactHandler",
    "LLMExtractionHandler",
    "RegexFallbackHandler",
]
