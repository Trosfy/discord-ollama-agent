"""Output artifact detection service (Single Responsibility Principle)."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from strands import Agent
from strands.models.ollama import OllamaModel
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
            model: Model to use for detection (default: gpt-oss:20b)
        """
        self.ollama_host = ollama_host
        self.model = model

        # Initialize PromptComposer (modular prompt system)
        self.prompt_composer = PromptComposer()
        self.detection_prompt = self.prompt_composer.get_detection_prompt()

        logger.info(f"✅ OutputArtifactDetector initialized with model: {self.model}")
        logger.info("✅ Detection prompt loaded from JSON config")

    async def detect(self, user_message: str) -> bool:
        """
        Use LLM to intelligently detect user intent for file creation.

        Args:
            user_message: User's input message

        Returns:
            True if user wants file output, False otherwise
        """
        try:
            logger.info(f"🔍 Detecting OUTPUT_ARTIFACT intent: {user_message[:100]}...")

            # Create Ollama model via Strands
            model = OllamaModel(
                host=self.ollama_host,
                model_id=self.model,
                temperature=0.1  # Low temperature for consistent detection
            )

            # Create Strands Agent for detection
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=model,
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
