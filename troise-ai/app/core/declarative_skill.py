"""Generic executor for declarative markdown-based skills.

Executes any skill defined in SKILL.md (Claude format) or skill.md
(legacy format) by building messages and calling the LLM with
skill-specific parameters.

Uses VRAMOrchestrator for model management and Ollama for chat completions.
Supports loading references from references/ directory for SKILL.md skills.
"""
import logging
from typing import Any, Dict, List, TYPE_CHECKING

import ollama

from .config import Config
from .container import Container
from .context import ExecutionContext
from .interfaces.skill import SkillResult
from .skill_loader import DeclarativeSkillDef

if TYPE_CHECKING:
    from ..prompts import PromptComposer
    from .interfaces.services import IVRAMOrchestrator

logger = logging.getLogger(__name__)


class DeclarativeSkill:
    """Generic executor for declarative skills.

    Uses VRAMOrchestrator for model management.

    Executes any skill defined in SKILL.md or skill.md format by:
    1. Building system prompt with context injection via PromptComposer
    2. Including loaded references (for SKILL.md with references/ directory)
    3. Adding few-shot examples as messages
    4. Optionally including conversation history
    5. Calling LLM with skill-specific parameters

    Example:
        skill_def = skill_loader.load_skill(Path("skills/summarize/SKILL.md"))
        skill = DeclarativeSkill(skill_def, vram_orchestrator, prompt_composer, container)
        result = await skill.execute("Summarize this text...", context)
    """

    def __init__(
        self,
        skill_def: DeclarativeSkillDef,
        vram_orchestrator: "IVRAMOrchestrator",
        prompt_composer: "PromptComposer",
        container: Container,
    ):
        """Initialize the declarative skill executor.

        Args:
            skill_def: Parsed skill definition from skill.md.
            vram_orchestrator: VRAMOrchestrator for model management.
            prompt_composer: PromptComposer for interface/personalization layers.
            container: DI container for resolving dependencies.
        """
        self._skill_def = skill_def
        self._orchestrator = vram_orchestrator
        self._prompt_composer = prompt_composer
        self._container = container
        self._ollama_host: str = None

        # Get Ollama host from config
        config = container.resolve(Config)
        self._config = config

        # Expose name/category for registry compatibility
        self.name = skill_def.name
        self.category = skill_def.category

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
    ) -> SkillResult:
        """Execute the skill with the given input.

        Args:
            input: User input to process.
            context: Execution context with interface and user info.

        Returns:
            SkillResult with the LLM response and metadata.
        """
        messages = self._build_messages(input, context)

        # Get model from config based on skill's model_task
        model = self._config.get_model_for_task(self._skill_def.model_task)

        # Get model capabilities to find Ollama host
        model_caps = self._config.get_model_capabilities(model)
        if model_caps:
            self._ollama_host = model_caps.backend.host

        # Ensure model is loaded via VRAMOrchestrator
        await self._orchestrator.request_load(model)

        logger.debug(
            f"Skill '{self.name}' calling LLM with model: {model}, "
            f"temp: {self._skill_def.temperature}, "
            f"messages: {len(messages)}"
        )

        # Use Ollama client directly for chat (supports multi-turn messages)
        client = ollama.Client(host=self._ollama_host)

        try:
            response = client.chat(
                model=model,
                messages=messages,
                options={
                    "temperature": self._skill_def.temperature,
                    "num_predict": self._skill_def.max_tokens,
                },
            )

            content = response.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"Skill '{self.name}' LLM call failed: {e}")
            raise

        return SkillResult(
            content=content,
            metadata={
                "skill": self.name,
                "model": model,
                "output_format": self._skill_def.output_format,
                "declarative": True,
            },
        )

    def _build_messages(
        self,
        input: str,
        context: ExecutionContext,
    ) -> List[Dict[str, Any]]:
        """Build the messages array for LLM call.

        Message order:
        1. System prompt (with context injected)
        2. Few-shot examples (user/assistant pairs)
        3. Conversation history (if enabled)
        4. Current user input

        Args:
            input: Current user input.
            context: Execution context.

        Returns:
            List of message dicts for the LLM.
        """
        messages = []

        # 1. System prompt with context injection
        system_prompt = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        # 2. Few-shot examples (if defined)
        for example in self._skill_def.examples:
            messages.append({"role": "user", "content": example.user})
            messages.append({"role": "assistant", "content": example.assistant})

        # 3. Conversation history (if enabled)
        if self._skill_def.include_history and context.conversation_history:
            history = context.conversation_history[-self._skill_def.history_turns :]
            for msg in history:
                messages.append({"role": msg.role, "content": msg.content})

        # 4. Current user input
        user_content = self._format_user_input(input)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_system_prompt(self, context: ExecutionContext) -> str:
        """Build system prompt with context, references, and guardrails.

        Uses PromptComposer to inject interface and personalization layers,
        then appends loaded references (for SKILL.md format) and guardrails.

        Args:
            context: Execution context.

        Returns:
            Formatted system prompt string.
        """
        # Use PromptComposer to compose skill prompt with interface and personalization
        prompt = self._prompt_composer.compose_skill_prompt(
            skill_system_prompt=self._skill_def.system_prompt,
            interface=context.interface,
            user_profile=context.user_profile,
        )

        # Append loaded references (for SKILL.md format with references/ directory)
        if self._skill_def.references_content:
            references_text = self._format_references()
            prompt += f"\n\n{references_text}"

        # Append guardrails if defined
        if self._skill_def.guardrails:
            prompt += f"\n\n<guardrails>\n{self._skill_def.guardrails}\n</guardrails>"

        return prompt

    def _format_references(self) -> str:
        """Format loaded references for inclusion in system prompt.

        References are formatted as tagged sections with filename as header.

        Returns:
            Formatted references text.
        """
        if not self._skill_def.references_content:
            return ""

        sections = []
        for filename, content in self._skill_def.references_content.items():
            # Use filename (without extension) as section header
            name = filename.rsplit(".", 1)[0] if "." in filename else filename
            sections.append(f"<reference name=\"{name}\">\n{content.strip()}\n</reference>")

        return "\n\n".join(sections)

    def _format_user_input(self, input: str) -> str:
        """Format user input with optional template.

        Args:
            input: Raw user input.

        Returns:
            Formatted user input string.
        """
        if self._skill_def.user_prompt_template:
            try:
                return self._skill_def.user_prompt_template.format(input=input)
            except KeyError:
                # If template has other placeholders, just replace {input}
                return self._skill_def.user_prompt_template.replace("{input}", input)
        return input
