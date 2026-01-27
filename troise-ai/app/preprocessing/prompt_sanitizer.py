"""Prompt sanitizer for extracting clean user intent.

FastAPI-style approach:
- Simple rephrase prompt (removes file creation language)
- Heuristics for action_type (no LLM needed)
- Regex for expected_filename (no LLM needed)

Skip LLM entirely for simple messages like "hi".
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from strands import Agent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.interfaces.services import IVRAMOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class SanitizedPrompt:
    """Clean user intent extracted from raw message."""
    intent: str              # Core user intent (clean, focused)
    original: str            # Original message (preserved)
    has_files: bool          # Whether files were mentioned
    file_references: List[str]  # Extracted file names (for context)
    action_type: str         # "create", "modify", "analyze", "query"
    expected_filename: Optional[str] = None  # Expected output filename


class PromptSanitizer:
    """Extract clean user intent from raw message.

    Uses VRAMOrchestrator + Strands Agent for LLM operations.
    FastAPI-style approach:
    - Simple rephrase prompt for messages with file creation language
    - Heuristics for action_type (no LLM)
    - Regex for expected_filename (no LLM)

    Skip LLM entirely for simple messages like "hi".
    """

    # Circuit breaker settings
    MAX_FAILURES = 3
    SKIP_DURATION = 60  # seconds

    # Patterns that indicate file creation language (need rephrase)
    FILE_PATTERNS = [
        "save to", "save as", "put into", "create file", "write to",
        "output to", "export to", "into a file", "as a file",
        "give me the", "give me a",
        # Common file extensions
        ".txt", ".md", ".py", ".json", ".js", ".ts", ".yaml", ".yml",
        ".csv", ".xml", ".html", ".css", ".sh", ".sql",
        # Systems programming
        ".cpp", ".c", ".h", ".hpp", ".cc", ".cxx",
        # JVM and compiled
        ".java", ".kt", ".go", ".rs", ".swift",
        # Scripting
        ".rb", ".php", ".pl", ".lua",
    ]

    REPHRASE_PROMPT = """Reasoning: none

Rephrase by removing file references. Do NOT write code or explain - output ONLY the rephrased request.

EXAMPLES:
"write a summary and save to summary.txt" → write a summary
"create me a quicksort file in c++" → implement quicksort in c++
"make a shopping list and save as list.txt" → make a shopping list"""

    def __init__(
        self,
        config: "Config",
        vram_orchestrator: "IVRAMOrchestrator",
    ):
        """Initialize sanitizer.

        Args:
            config: Application configuration.
            vram_orchestrator: VRAM orchestrator for model access.
        """
        self._config = config
        self._orchestrator = vram_orchestrator
        self._failure_count = 0
        self._skip_until: Optional[float] = None
        self._rephrase_prompt = self._load_rephrase_prompt()

    def _load_rephrase_prompt(self) -> str:
        """Load rephrase prompt from file, fallback to default."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "preprocessing" / "rephrase.prompt"
        try:
            return prompt_path.read_text()
        except FileNotFoundError:
            logger.warning(f"Rephrase prompt not found at {prompt_path}, using default")
            return self.REPHRASE_PROMPT

    async def sanitize(
        self,
        message: str,
        file_refs: List[str] = None,
    ) -> SanitizedPrompt:
        """Extract clean intent from user message.

        Args:
            message: Raw user message.
            file_refs: Known file references (optional).

        Returns:
            SanitizedPrompt with clean intent and metadata.
        """
        start_time = time.time()
        logger.debug(f"Sanitizing: input_len={len(message)}, has_files={bool(file_refs)}")

        # 1. Rephrase only if message contains file creation language
        if self._needs_rephrase(message):
            clean_intent = await self._rephrase(message)
        else:
            clean_intent = message  # No LLM needed

        # 2. Action type: heuristics (no LLM)
        action_type = self._detect_action_type(message)

        # 3. Expected filename: regex extraction (no LLM)
        expected_filename = self._extract_filename(message) if action_type == "create" else None

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Sanitized: action_type={action_type}, "
            f"expected_filename={expected_filename}, duration={duration_ms:.0f}ms"
        )

        return SanitizedPrompt(
            intent=clean_intent,
            original=message,
            has_files=bool(file_refs),
            file_references=file_refs or [],
            action_type=action_type,
            expected_filename=expected_filename,
        )

    def _needs_rephrase(self, message: str) -> bool:
        """Check if message contains file creation language that needs cleaning."""
        lower = message.lower()
        return any(pattern in lower for pattern in self.FILE_PATTERNS)

    async def _rephrase(self, message: str) -> str:
        """Remove file creation language from message using LLM.

        Uses VRAMOrchestrator + Strands Agent (same pattern as Router).
        Falls back to original message on error.
        """
        # Circuit breaker check
        if self._skip_until and time.time() < self._skip_until:
            logger.warning("PromptSanitizer circuit breaker active, skipping rephrase")
            return message

        try:
            # Get router model (fast, small) through VRAMOrchestrator
            router_model_id = self._config.profile.router_model
            model = await self._orchestrator.get_model(
                model_id=router_model_id,
                temperature=0.1,
                max_tokens=2000,  # Room for thinking tokens + rephrased output
            )

            # Create minimal Strands Agent for rephrase (same pattern as Router)
            agent = Agent(
                model=model,
                tools=[],  # No tools - pure text transformation
                system_prompt=self._rephrase_prompt,
            )

            # Run agent synchronously in executor (Strands Agent is sync)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent, message)
            result = str(response).strip()

            # Reset failure count on success
            self._failure_count = 0

            # Log full sanitized output for debugging (helps catch thinking tokens leaking)
            logger.info(
                f"Sanitizer output: len={len(result)}, "
                f"original_len={len(message)}, "
                f"content='{result[:200]}{'...' if len(result) > 200 else ''}'"
            )

            if result:
                return result
            return message

        except Exception as e:
            logger.warning(f"Rephrase failed: {e}, using original message")
            self._handle_failure()
            return message

    def _handle_failure(self):
        """Handle a failure by incrementing counter and potentially activating circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self.MAX_FAILURES:
            self._skip_until = time.time() + self.SKIP_DURATION
            logger.warning(
                f"PromptSanitizer circuit breaker activated for {self.SKIP_DURATION}s"
            )

    def _detect_action_type(self, message: str) -> str:
        """Detect action type using heuristics (no LLM needed)."""
        lower_msg = message.lower()

        if any(word in lower_msg for word in ["create", "write", "generate", "make", "build"]):
            return "create"
        elif any(word in lower_msg for word in ["fix", "modify", "update", "improve", "refactor", "change"]):
            return "modify"
        elif any(word in lower_msg for word in ["analyze", "summarize", "review", "explain", "describe"]):
            return "analyze"

        return "query"

    def _extract_filename(self, message: str) -> Optional[str]:
        """Extract expected filename from message using regex."""
        patterns = [
            # "called foo.py", "named config.json"
            r'(?:called?|named?)\s+["\']?([a-zA-Z0-9_.-]+\.[a-z]+)["\']?',
            # "save to/as summary.txt", "put into notes.md"
            r'(?:save|put|write|output|export)\s+(?:to|as|into)\s+["\']?([a-zA-Z0-9_.-]+\.[a-z]+)["\']?',
            # "give me the foo.cpp file", "give me a config.yaml"
            r'give\s+me\s+(?:the\s+|a\s+)?["\']?([a-zA-Z0-9_.-]+\.[a-z]+)["\']?',
            # "give me the .cpp file" → infer name from context (returns extension only)
            r'give\s+me\s+(?:the\s+|a\s+)?\.([a-z]+)\s+file',
            # Common standalone filenames
            r'\b(Dockerfile|Makefile|README\.md|docker-compose\.ya?ml|\.gitignore|\.env)\b',
            # Generic "create X.ext" pattern
            r'create\s+(?:a\s+)?["\']?([a-zA-Z0-9_.-]+\.[a-z]+)["\']?',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                filename = match.group(1)
                # Handle extension-only matches (e.g., ".cpp file" → "output.cpp")
                if not '.' in filename and len(filename) <= 5:
                    filename = f"output.{filename}"
                logger.debug(f"Extracted filename: {filename}")
                return filename

        return None  # Let postprocessing infer from content

    def build_agent_prompt(
        self,
        sanitized: SanitizedPrompt,
        file_context: str,
    ) -> str:
        """Build clean prompt for main agent.

        Main agent receives:
        1. Clean intent (what to do)
        2. Pre-analyzed file context (what files contain)

        NOT raw file content. NOT file handling instructions.

        Args:
            sanitized: Sanitized prompt with clean intent.
            file_context: Pre-analyzed file context from ContextBuilder.

        Returns:
            Clean prompt for main agent.
        """
        parts = []

        # System context (file analysis) - if any
        if file_context:
            parts.append(file_context)
            parts.append("")  # Separator

        # Clean user intent
        parts.append(f"**User Request:** {sanitized.intent}")

        return "\n".join(parts)
