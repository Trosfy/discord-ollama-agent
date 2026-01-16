"""Output artifact detector for preprocessing.

Detects if user wants file output from their request.
Uses small/fast model for binary classification.
Only triggers postprocessing if detected.
"""
import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

from strands import Agent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.interfaces.services import IVRAMOrchestrator

logger = logging.getLogger(__name__)


class OutputArtifactDetector:
    """Detect if user wants file output.

    Uses VRAMOrchestrator + Strands Agent for binary classification.
    Only triggers postprocessing if detected.

    Includes circuit breaker for resilience.

    Example:
        detector = OutputArtifactDetector(config, vram_orchestrator)

        if await detector.detect("create a Dockerfile for my app"):
            # User wants file output, enable artifact extraction
            artifact_requested = True
    """

    # Circuit breaker settings
    MAX_FAILURES = 3
    SKIP_DURATION = 60  # seconds

    DETECTION_PROMPT = """Reasoning: low

You are a binary classifier. Does this request ask for a file to be created or generated?
Answer only YES or NO, nothing else."""

    def __init__(
        self,
        config: "Config",
        vram_orchestrator: "IVRAMOrchestrator",
    ):
        """Initialize detector.

        Args:
            config: Application configuration.
            vram_orchestrator: VRAM orchestrator for model access.
        """
        self._config = config
        self._orchestrator = vram_orchestrator
        self._failure_count = 0
        self._skip_until: Optional[float] = None

    async def detect(self, message: str) -> bool:
        """Detect if user wants file output.

        Args:
            message: User's message.

        Returns:
            True if user likely wants file output.
        """
        # Circuit breaker: use heuristic if too many failures
        if self._skip_until and time.time() < self._skip_until:
            logger.warning("ArtifactDetector circuit breaker active, using heuristic")
            return self._heuristic_detect(message)

        try:
            # Get router model (fast, small) through VRAMOrchestrator
            router_model_id = self._config.profile.router_model
            model = await self._orchestrator.get_model(
                model_id=router_model_id,
                temperature=0.1,
                max_tokens=100,  # Room for thinking + YES/NO
            )

            # Create Strands Agent for classification
            agent = Agent(
                model=model,
                tools=[],  # No tools - pure classification
                system_prompt=self.DETECTION_PROMPT,
            )

            # Run agent synchronously (Strands Agent is sync)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent, message)
            response_str = str(response).strip()

            logger.debug(f"ArtifactDetector response: '{response_str}'")

            # Reset failure count on success
            self._failure_count = 0

            return response_str.upper().startswith("YES")

        except Exception as e:
            logger.error(f"ArtifactDetector error: {e}")
            self._handle_failure()
            return self._heuristic_detect(message)

    def _handle_failure(self):
        """Handle failure and potentially activate circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self.MAX_FAILURES:
            self._skip_until = time.time() + self.SKIP_DURATION
            logger.warning(
                f"ArtifactDetector circuit breaker activated for {self.SKIP_DURATION}s"
            )

    def _heuristic_detect(self, message: str) -> bool:
        """Heuristic detection when LLM unavailable.

        Args:
            message: User's message.

        Returns:
            True if message likely requests file output.
        """
        lower_msg = message.lower()

        # Strong indicators of file output request
        create_words = ["create", "write", "generate", "make", "build"]
        file_words = ["file", "script", "dockerfile", "config", "code", ".py", ".js", ".ts"]

        has_create = any(word in lower_msg for word in create_words)
        has_file = any(word in lower_msg for word in file_words)

        # Explicit file output patterns
        file_patterns = [
            "save as",
            "save to",
            "output to",
            "export as",
            "create a file",
            "write a file",
        ]
        has_explicit = any(pattern in lower_msg for pattern in file_patterns)

        return has_explicit or (has_create and has_file)
