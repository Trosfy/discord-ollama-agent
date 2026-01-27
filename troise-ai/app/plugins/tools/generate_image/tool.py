"""Generate image tool using FLUX 2.dev NVFP4 via ComfyUI.

Generates images from text prompts using the FLUX 2.dev NVFP4 diffusion model.
The model runs via ComfyUI backend for native NVFP4 support on Blackwell GPUs.
VRAMOrchestrator handles model validation and backend resolution.
"""
import json
import logging
import uuid
from typing import Any, Dict

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.services import IVRAMOrchestrator
from app.core.interfaces.storage import IFileStorage
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)


class GenerateImageTool:
    """
    Generate images using FLUX 2.dev NVFP4 via ComfyUI backend.

    Uses VRAMOrchestrator to resolve the ComfyUI client for image generation.
    The FLUX 2.dev NVFP4 quantized model (~20GB) runs in ComfyUI with native
    NVFP4 support for ~3x performance on Blackwell GPUs.

    Generated images are uploaded to IFileStorage (MinIO) and returned as file_id.
    """

    name = "generate_image"
    description = """Generate an image from a text description using FLUX 2.dev.

Use this tool when you need to create, generate, or draw an image.
Provide a detailed prompt describing the desired image.

Returns a file_id that can be used to display the generated image."""

    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed text description of the image to generate. Be specific about style, lighting, composition, colors, and mood."
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                "default": "1:1",
                "description": "Aspect ratio for the generated image. 1:1 for square, 16:9 for landscape, 9:16 for portrait."
            },
            "num_inference_steps": {
                "type": "integer",
                "minimum": 20,
                "maximum": 50,
                "default": 28,
                "description": "Number of inference steps. Higher values produce better quality but take longer. Default is 28."
            },
            "guidance_scale": {
                "type": "number",
                "minimum": 1.0,
                "maximum": 10.0,
                "default": 4.0,
                "description": "How closely to follow the prompt. Higher values follow prompt more strictly. Default is 4.0."
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducibility. If not provided, a random seed is used."
            },
        },
        "required": ["prompt"]
    }

    ASPECT_RATIOS = {
        "1:1": (1024, 1024),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
        "4:3": (1152, 896),
        "3:4": (896, 1152),
    }

    def __init__(self, context: ExecutionContext, container: Container):
        """
        Initialize the generate image tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
        """
        self._context = context
        self._container = container

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Generate an image using ComfyUI backend.

        Args:
            params: Tool parameters (prompt, aspect_ratio, etc.).
            context: Execution context.

        Returns:
            ToolResult with file_id and metadata on success, error on failure.
        """
        prompt = params.get("prompt", "").strip()
        if not prompt:
            return ToolResult(
                content=json.dumps({"error": "prompt is required"}),
                success=False,
                error="prompt is required"
            )

        aspect_ratio = params.get("aspect_ratio", "1:1")
        num_steps = params.get("num_inference_steps", 28)
        guidance = params.get("guidance_scale", 4.0)
        seed = params.get("seed")

        width, height = self.ASPECT_RATIOS.get(aspect_ratio, (1024, 1024))

        try:
            # Get ComfyUI client and workflow config via VRAMOrchestrator
            # This calls request_load() to ensure VRAM is available (evicts LLMs if needed)
            orchestrator = self._container.resolve(IVRAMOrchestrator)
            # Get the image model from profile (e.g., "flux2-dev-nvfp4")
            image_model = orchestrator.get_profile_model("image")
            comfyui, workflow_config = await orchestrator.get_diffusion_context(image_model)

            # Generate image via ComfyUI (config from profile, not hardcoded)
            logger.info(f"Generating image: {prompt[:50]}... ({width}x{height})")

            image_bytes = await comfyui.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                steps=num_steps,
                guidance=guidance,
                seed=seed,
                workflow_config=workflow_config,
            )

            if not image_bytes:
                return ToolResult(
                    content=json.dumps({
                        "error": "Image generation failed. ComfyUI returned no image."
                    }),
                    success=False,
                    error="Generation failed"
                )

            logger.info(f"Image generated successfully")

            # Upload to storage
            storage = self._container.try_resolve(IFileStorage)
            if storage is None:
                return ToolResult(
                    content=json.dumps({
                        "error": "Storage service not available. Cannot save generated image."
                    }),
                    success=False,
                    error="Storage not available"
                )

            # Generate file ID and upload
            file_id = str(uuid.uuid4())
            composite_id = await storage.upload(
                file_id=file_id,
                content=image_bytes,
                mimetype="image/png",
                session_id=context.session_id,
            )

            # Build actual S3 key for external interfaces
            # MinIO stores at: session_id/file_id.png
            # upload() returns composite: session_id:file_id
            # External interfaces need the actual S3 key
            storage_key = f"{context.session_id}/{file_id}.png"

            logger.info(f"Image uploaded: file_id={file_id}, storage_key={storage_key}")

            # Seed is random if not provided (ComfyUI generates internally)
            actual_seed = seed if seed is not None else "random"

            return ToolResult(
                content=json.dumps({
                    "success": True,
                    "file_id": file_id,
                    "storage_key": storage_key,
                    "format": "png",
                    "width": width,
                    "height": height,
                    "aspect_ratio": aspect_ratio,
                    "seed": actual_seed,
                    "num_inference_steps": num_steps,
                    "guidance_scale": guidance,
                    "prompt_used": prompt,
                }),
                success=True,
            )

        except MemoryError as e:
            logger.error(f"Memory error during image generation: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": "Not enough GPU memory for image generation. The system may need to free some models first.",
                    "suggestion": "Try again in a moment, or request a smaller image."
                }),
                success=False,
                error=str(e)
            )

        except ValueError as e:
            # Model not in profile or not a diffusion model
            logger.error(f"Configuration error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                }),
                success=False,
                error=str(e)
            )

        except RuntimeError as e:
            # ComfyUI backend not available
            logger.error(f"Runtime error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                }),
                success=False,
                error=str(e)
            )

        except Exception as e:
            logger.error(f"Image generation failed: {e}", exc_info=True)
            return ToolResult(
                content=json.dumps({
                    "error": f"Image generation failed: {str(e)}"
                }),
                success=False,
                error=str(e)
            )

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def create_generate_image_tool(
    context: ExecutionContext,
    container: Container,
) -> GenerateImageTool:
    """
    Factory function to create generate_image tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured GenerateImageTool instance.
    """
    return GenerateImageTool(
        context=context,
        container=container,
    )
