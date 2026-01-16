"""Image file extractor using vision model."""
import base64
import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import ollama

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.interfaces.services import IVRAMOrchestrator

from .interface import ExtractionResult

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Extract text/description from images using vision model.

    Uses VRAMOrchestrator to manage vision model loading, then calls
    the Ollama API directly for vision (image analysis).

    Useful for screenshots, diagrams, and documents as images.
    """

    MIMETYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
        "image/bmp",
    ]

    VISION_PROMPT = """Describe this image in detail. Include:
1. What type of image it is (screenshot, diagram, photo, etc.)
2. Key text visible in the image
3. Main elements and their layout
4. Any code, errors, or technical content visible

Be thorough but concise."""

    def __init__(
        self,
        config: Optional["Config"] = None,
        vram_orchestrator: Optional["IVRAMOrchestrator"] = None,
    ):
        """Initialize image extractor.

        Args:
            config: Application configuration. If None, vision is disabled.
            vram_orchestrator: VRAM orchestrator for model management.
        """
        self._config = config
        self._orchestrator = vram_orchestrator
        self._ollama_host: Optional[str] = None

        # Get Ollama host from config
        if config:
            vision_model = config.profile.vision_model
            model_caps = config.get_model_capabilities(vision_model)
            if model_caps:
                self._ollama_host = model_caps.backend.host

    @property
    def supported_mimetypes(self) -> List[str]:
        return self.MIMETYPES

    async def extract(self, file_path: str, mimetype: str) -> ExtractionResult:
        """Extract description from image.

        Args:
            file_path: Path to the image file.
            mimetype: MIME type of the image.

        Returns:
            ExtractionResult with image description.
        """
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                text="",
                extractor_name="ImageExtractor",
                status="error",
                error_message=f"File not found: {file_path}",
            )

        if not self._config or not self._orchestrator:
            # No vision model configured
            return ExtractionResult(
                text=f"[Image: {path.name}]",
                extractor_name="ImageExtractor",
                status="partial",
                error_message="Vision model not available",
                metadata={"filename": path.name, "mimetype": mimetype},
            )

        try:
            # Get vision model from profile
            vision_model = self._config.profile.vision_model

            # Ensure vision model is loaded via VRAMOrchestrator
            await self._orchestrator.request_load(vision_model)

            # Read and encode image
            image_data = path.read_bytes()
            image_b64 = base64.b64encode(image_data).decode("utf-8")
            logger.info(
                f"ImageExtractor: Encoded {path.name} ({len(image_data)} bytes), "
                f"calling vision model {vision_model}"
            )

            # Use Ollama API directly for vision
            # Note: We use the sync client since we're in an async context
            # and ollama's async client has issues with some setups
            client = ollama.Client(host=self._ollama_host)

            try:
                logger.info(f"ImageExtractor: Calling Ollama vision API")
                response = client.chat(
                    model=vision_model,
                    messages=[{
                        "role": "user",
                        "content": self.VISION_PROMPT,
                        "images": [image_b64],
                    }],
                    options={
                        "temperature": 0.1,
                        "num_predict": 1024,
                    },
                )

                result_text = response.get("message", {}).get("content", "")
                logger.info(
                    f"ImageExtractor: Got response ({len(result_text)} chars): "
                    f"{result_text[:100]}..."
                )

            except Exception as e:
                logger.warning(f"Vision model failed: {e}")
                return ExtractionResult(
                    text=f"[Image: {path.name}]",
                    extractor_name="ImageExtractor",
                    status="partial",
                    error_message=f"Vision model error: {str(e)}",
                    metadata={"filename": path.name, "mimetype": mimetype},
                )

            return ExtractionResult(
                text=result_text,
                extractor_name="ImageExtractor",
                status="success",
                metadata={
                    "filename": path.name,
                    "mimetype": mimetype,
                    "size_bytes": len(image_data),
                    "model": vision_model,
                },
            )

        except Exception as e:
            logger.error(f"Failed to extract from image {file_path}: {e}")
            return ExtractionResult(
                text=f"[Image: {path.name}]",
                extractor_name="ImageExtractor",
                status="error",
                error_message=str(e),
            )
