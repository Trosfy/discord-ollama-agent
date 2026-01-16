"""TROISE AI Preprocessing Module.

Handles preprocessing of user messages and files before routing:
- PromptSanitizer: Extract clean intent from user messages
- FileExtractionRouter: Route files to extractors, store for tool access
- OutputArtifactDetector: Detect if user wants file output
"""
from .prompt_sanitizer import PromptSanitizer, SanitizedPrompt
from .extraction_router import FileExtractionRouter, FileRef, FileContent
from .artifact_detector import OutputArtifactDetector

__all__ = [
    # Prompt Sanitization
    "PromptSanitizer",
    "SanitizedPrompt",
    # File Extraction
    "FileExtractionRouter",
    "FileRef",
    "FileContent",
    # Artifact Detection
    "OutputArtifactDetector",
]
