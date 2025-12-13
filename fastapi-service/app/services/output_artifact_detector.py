"""Output artifact detection service (Single Responsibility Principle)."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from strands import Agent
from strands.models.ollama import OllamaModel
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
        self.detection_prompt = self._build_detection_prompt()
        logger.info(f"✅ OutputArtifactDetector initialized with model: {self.model}")

    def _build_detection_prompt(self) -> str:
        """Build the output artifact detection prompt."""
        return """You are an intent classifier for file creation requests.

Analyze the user's message and determine if they want you to CREATE A FILE as output.

Examples of file creation intent:
- "create a Python file for quicksort" → YES
- "generate a config.json for my app" → YES
- "make a markdown document about REST APIs" → YES
- "save this as a script" → YES
- "write a function to reverse a string" → NO (just wants code, not a file)
- "explain how to create a file in Python" → NO (asking for explanation, not requesting file creation)
- "what's the difference between lists and tuples?" → NO (question, no file requested)

Output ONLY "YES" if user wants a file created, or "NO" if they don't. Nothing else."""

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
