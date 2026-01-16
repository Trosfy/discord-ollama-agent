"""LLM-based artifact extraction handler.

Fallback for when:
- Small model didn't use write_file tool
- Model outputted content inline

Uses VRAMOrchestrator + Strands Agent for extraction.
"""
import asyncio
import json
import logging
import re
from typing import List, Optional, TYPE_CHECKING

from strands import Agent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.interfaces.services import IVRAMOrchestrator
    from app.core.executor import ExecutionResult

from ..artifact_chain import Artifact
from ..sanitizer import ContentSanitizer

logger = logging.getLogger(__name__)


class LLMExtractionHandler:
    """Use a larger model to extract file content from response.

    Uses VRAMOrchestrator + Strands Agent for LLM operations.

    Fallback for when:
    - Small model didn't use write_file tool
    - Model outputted content inline

    Example:
        handler = LLMExtractionHandler(config, vram_orchestrator)

        if handler.can_handle(result):
            artifacts = await handler.handle(result)
            # Returns artifacts extracted by the model
    """

    EXTRACTION_PROMPT = """Reasoning: low

You are a JSON extraction assistant. Extract file content from responses.

Return ONLY valid JSON in one of these formats:
1. If file content found: {"filename": "name.ext", "content": "...", "type": "code|text|data"}
2. If no file content: {"found": false}

Only extract actual file content (code, configs, data), not conversational text."""

    def __init__(
        self,
        config: "Config",
        vram_orchestrator: "IVRAMOrchestrator",
        sanitizer: Optional[ContentSanitizer] = None,
    ):
        """Initialize handler.

        Args:
            config: Application configuration.
            vram_orchestrator: VRAM orchestrator for model access.
            sanitizer: Content sanitizer for post-processing.
        """
        self._config = config
        self._orchestrator = vram_orchestrator
        self._sanitizer = sanitizer or ContentSanitizer()

    def can_handle(self, result: "ExecutionResult") -> bool:
        """Check if result has content to extract from.

        Args:
            result: Execution result.

        Returns:
            True (can always try LLM extraction).
        """
        return bool(result.content)

    async def handle(self, result: "ExecutionResult") -> List[Artifact]:
        """Extract artifacts using LLM.

        Args:
            result: Execution result.

        Returns:
            List of extracted artifacts.
        """
        # Format the content for extraction
        user_message = f"""Extract the file content from this response:

{result.content[:5000]}

Return JSON only."""

        try:
            # Get router model (fast) through VRAMOrchestrator
            router_model_id = self._config.profile.router_model
            model = await self._orchestrator.get_model(
                model_id=router_model_id,
                temperature=0.1,
                max_tokens=2048,
            )

            # Create Strands Agent for extraction
            agent = Agent(
                model=model,
                tools=[],  # No tools - pure extraction
                system_prompt=self.EXTRACTION_PROMPT,
            )

            # Run agent synchronously (Strands Agent is sync)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent, user_message)
            response_str = str(response).strip()

            # Try to extract JSON
            json_match = re.search(r'\{[^{}]*\}', response_str, re.DOTALL)
            if not json_match:
                logger.debug("No JSON found in extraction response")
                return []

            data = json.loads(json_match.group())

            if data.get("found") is False:
                return []

            filename = data.get("filename", "output.txt")
            content = data.get("content", "")
            artifact_type = data.get("type", "text")

            if not content:
                return []

            # Sanitize content
            clean_content = self._sanitizer.sanitize(content, artifact_type)

            return [Artifact(
                filename=filename,
                content=clean_content,
                source="llm_extraction",
                confidence=0.8,
                metadata={
                    "model": router_model_id,
                    "artifact_type": artifact_type,
                },
            )]

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extraction response: {e}")
            return []

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []
