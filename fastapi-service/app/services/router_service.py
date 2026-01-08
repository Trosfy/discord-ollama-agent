"""Intelligent request routing service using LLM-based classification."""
import sys
sys.path.insert(0, '/shared')

from enum import Enum
from typing import Dict
import asyncio

from strands import Agent
from strands.models.ollama import OllamaModel
from app.config import settings
from app.utils.model_utils import get_ollama_keep_alive
from app.routing import Router
from app.prompts import PromptComposer
import logging_client

logger = logging_client.setup_logger('fastapi')


class RouteType(Enum):
    """Available request routes."""
    SELF_HANDLE = "SELF_HANDLE"
    SIMPLE_CODE = "SIMPLE_CODE"
    REASONING = "REASONING"
    RESEARCH = "RESEARCH"
    MATH = "MATH"


class RouterService:
    """Routes requests to appropriate models using LLM-based classification with modular prompts."""

    def __init__(self, output_detector=None, input_detector=None):
        """
        Initialize router service with LLM-based Router (Dependency Injection).

        Uses LLM (gpt-oss:20b) for intelligent classification with prompts loaded
        from JSON config, combining flexibility with maintainability.

        Args:
            output_detector: OutputArtifactDetector instance
            input_detector: InputArtifactDetector instance
        """
        self.router_model_id = settings.ROUTER_MODEL  # gpt-oss:20b
        self.ollama_host = settings.OLLAMA_HOST
        self.output_detector = output_detector
        self.input_detector = input_detector

        # Initialize PromptComposer (modular prompt system)
        self.prompt_composer = PromptComposer()

        # Initialize Router with LLM classification
        self.router = Router(
            prompt_composer=self.prompt_composer,
            ollama_host=self.ollama_host,
            router_model_id=self.router_model_id
        )

        logger.info("✅ RouterService initialized with LLM-based routing")
        logger.info("🎯 Classification prompt loaded from JSON config")

    async def _rephrase_for_content_generation(self, user_message: str) -> str:
        """
        Rephrase user message to remove file creation language using LLM.

        Uses the router model to intelligently strip file creation phrases
        while preserving the core request.

        Examples:
        - "put into .md file" → removed
        - "create me a quicksort file in c++" → "implement quicksort in c++"
        - "save to bitcoin.md" → removed

        Args:
            user_message: Original user message

        Returns:
            Rephrased message focused on content, not file creation
        """
        try:
            # Get rephrase prompt from PromptComposer (modular system)
            rephrase_prompt = self.prompt_composer.get_rephrase_prompt()

            # Use router model for rephrasing
            router_model = OllamaModel(
                host=self.ollama_host,
                model_id=self.router_model_id,
                temperature=0.1,  # Low for deterministic output
                keep_alive="120s"
            )

            # Create agent with rephrase prompt
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=router_model,
                tools=[],
                system_prompt=rephrase_prompt
            )

            # Invoke with minimal user context
            response = await loop.run_in_executor(None, agent, f"Input: {user_message}")
            rephrased = str(response).strip()

            # Remove common prefixes the model might add
            for prefix in ["Output:", "output:", "Rephrased:", "rephrased:"]:
                if rephrased.startswith(prefix):
                    rephrased = rephrased[len(prefix):].strip()

            return rephrased

        except Exception as e:
            logger.warning(f"⚠️  LLM rephrasing failed: {e}, using original message")
            return user_message  # Graceful fallback

    async def classify_request(
        self,
        user_message: str,
        file_refs: list = [],
        artifact_detection_model: str = None
    ) -> dict:
        """
        Classify user request and detect preprocessing/postprocessing needs.

        Uses LLM-based classification with prompts loaded from JSON config.
        The Router handles classification logic using settings.ROUTER_MODEL.

        Args:
            user_message: User's input message
            file_refs: List of uploaded file references (default: [])
            artifact_detection_model: Model for artifact detection (from profile).
                                      If None, falls back to settings.ROUTER_MODEL.

        Returns:
            Dict with route, preprocessing, postprocessing, model, mode, filtered_prompt

        Raises:
            Exception: If classification fails
        """
        # Step 1: Route using LLM-based Router (always uses settings.ROUTER_MODEL)
        context = {'file_refs': file_refs}
        route_handler = await self.router.route(user_message, context)

        logger.info(f"🎯 Routed to: {route_handler.get_route_name()} (LLM classification)")

        # Step 2: Detect artifacts
        input_artifact = False
        output_artifact = False

        if self.input_detector:
            input_artifact = self.input_detector.detect(file_refs)

        if self.output_detector:
            # Use profile-specific model for artifact detection
            output_artifact = await self.output_detector.detect(
                user_message,
                model=artifact_detection_model
            )

        # Step 3: Build preprocessing/postprocessing lists
        preprocessing = ['INPUT_ARTIFACT'] if input_artifact else []
        postprocessing = ['OUTPUT_ARTIFACT'] if output_artifact else []

        # Step 4: Filter message if OUTPUT_ARTIFACT detected
        filtered_prompt = None
        if output_artifact:
            filtered_prompt = await self._rephrase_for_content_generation(user_message)
            logger.info(f"✂️  Filtered prompt for clean generation:")
            logger.info(f"   Original: {user_message[:80]}...")
            logger.info(f"   Cleaned:  {filtered_prompt[:80]}...")

        # Step 5: Get config from route handler
        config = route_handler.get_config()

        # Step 6: Return combined config with optional filtered prompt
        return {
            **config,
            'preprocessing': preprocessing,
            'postprocessing': postprocessing,
            'filtered_prompt': filtered_prompt,
        }

