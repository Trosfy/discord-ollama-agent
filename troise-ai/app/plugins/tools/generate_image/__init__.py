"""Generate Image Tool - Creates images using FLUX 2.dev via VRAMOrchestrator."""

from .tool import GenerateImageTool, create_generate_image_tool

PLUGIN = {
    "name": "generate_image",
    "type": "tool",
    "description": "Generate images from text prompts using FLUX 2.dev",
    "factory": create_generate_image_tool,
}

__all__ = ["GenerateImageTool", "create_generate_image_tool", "PLUGIN"]
