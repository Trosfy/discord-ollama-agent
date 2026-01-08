"""Output artifact detection service (Single Responsibility Principle)."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from strands import Agent
from strands.models.ollama import OllamaModel
from strands.models.openai import OpenAIModel
from app.prompts import PromptComposer
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class OutputArtifactDetector:
    """Detects if user wants file output using LLM (Single Responsibility)."""

    def __init__(self, ollama_host: str, model: str = "gpt-oss:20b"):
        """
        Initialize output artifact detector.

        Args:
            ollama_host: URL of Ollama API server
            model: Initial model (will read dynamically from settings.ROUTER_MODEL)
        """
        self.ollama_host = ollama_host
        # Don't cache model - read dynamically from settings.ROUTER_MODEL

        # Initialize PromptComposer (modular prompt system)
        self.prompt_composer = PromptComposer()
        self.detection_prompt = self.prompt_composer.get_detection_prompt()

        logger.info(f"✅ OutputArtifactDetector initialized (initial model: {model})")
        logger.info("✅ Detection prompt loaded from JSON config")

    async def detect(self, user_message: str, model: str = None) -> bool:
        """
        Use LLM to intelligently detect user intent for file creation.

        Args:
            user_message: User's input message
            model: Override model (if None, reads from settings.ROUTER_MODEL).
                   Typically set to profile.artifact_detection_model.

        Returns:
            True if user wants file output, False otherwise
        """
        try:
            # Use provided model or fall back to router model
            from app.config import get_model_capabilities, settings
            detection_model = model or settings.ROUTER_MODEL
            logger.info(f"Detecting OUTPUT_ARTIFACT intent with model: {detection_model}")
            logger.debug(f"Message preview: {user_message[:100]}...")

            model_caps = get_model_capabilities(detection_model)

            if model_caps and model_caps.backend.type == "sglang":
                # DEPRECATED: Eagle3 model (SGLang not in use)
                logger.warning(f"⚠️  SGLang backend requested but deprecated (model: {detection_model})")
                model_caps = None  # Force Ollama path below

            if model_caps and model_caps.backend.type != "sglang":
                # Ollama model - use standard Ollama API
                detector_model_instance = OllamaModel(
                    host=self.ollama_host,
                    model_id=detection_model,
                    temperature=0.1  # Low temperature for consistent detection
                )
            else:
                # Fallback to default detection model (shouldn't happen with profiles)
                logger.warning(f"⚠️  No valid backend for detection model {detection_model}, using Ollama fallback")
                detector_model_instance = OllamaModel(
                    host=self.ollama_host,
                    model_id="qwen3:4b",  # Small, fast fallback for detection
                    temperature=0.1
                )

            # Create Strands Agent for detection
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=detector_model_instance,
                tools=[],  # No tools - pure classification
                system_prompt=self.detection_prompt
            )

            # Invoke agent
            response = await loop.run_in_executor(None, agent, f"USER MESSAGE: {user_message}")
            result = str(response).strip().upper()

            # Parse result
            intent_detected = 'YES' in result

            if intent_detected:
                logger.info("📦 OUTPUT_ARTIFACT detected: User wants file creation")
            else:
                logger.info("ℹ️  No OUTPUT_ARTIFACT: User doesn't want file creation")

            return intent_detected

        except Exception as e:
            logger.error(f"❌ OUTPUT_ARTIFACT detection failed: {e}, defaulting to False")
            return False  # Default: no output artifact
