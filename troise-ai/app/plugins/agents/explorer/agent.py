"""Explorer Agent implementation.

Generic exploration agent that gathers context before other agents act.
Prompt variants differentiate behavior by graph domain:
- CODE: Codebase structure, patterns, dependencies
- RESEARCH: Existing knowledge + web exploration
- BRAINDUMP: Vault context for thought capture

Prompt resolution order (PromptComposer):
1. variants/{profile}/{graph_domain}/explorer.prompt (most specific)
2. variants/{profile}/explorer.prompt (profile only)
3. explorer.prompt (base)
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class ExplorerAgent(BaseAgent):
    """
    Generic explorer agent with domain-specific prompt variants.

    Supports all exploration modes through prompt variants:
    - code: Codebase structure, patterns, dependencies (read_file, brain_search)
    - research: Existing knowledge + web exploration (brain_search, web_search, web_fetch)
    - braindump: Vault context for thought capture (brain_search, brain_fetch)

    The agent behavior is controlled by prompt variants, not code branching.
    This follows OCP - new domains can be added via new prompt files.

    Example:
        agent = ExplorerAgent(
            vram_orchestrator=orchestrator,
            tools=[read_file, brain_search, web_search],
            prompt_composer=composer,
        )
        # When context.graph_domain = "code", uses code/explorer.prompt variant
        result = await agent.execute("Explore the authentication module", context)
    """

    name = "explorer"
    category = "shared"
    # Union of all exploration tools - variants use what they need
    tools = ["read_file", "brain_search", "brain_fetch", "web_search", "web_fetch"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the explorer agent.

        Args:
            vram_orchestrator: VRAM orchestrator for model access.
            tools: List of Strands tool instances.
            prompt_composer: PromptComposer for building system prompts.
            config: Agent configuration.
        """
        config = config or {}
        # Low temperature for factual exploration
        config.setdefault("temperature", 0.2)
        config.setdefault("max_tokens", 4096)
        # Use general model for exploration (fast, factual)
        config.setdefault("model_role", "general")
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    def _build_system_prompt(self, context: ExecutionContext) -> str:
        """Build system prompt with graph domain variant support.

        Overrides base method to pass graph_domain for domain-specific
        prompt selection.

        Args:
            context: Execution context with graph_domain.

        Returns:
            Formatted system prompt (domain-specific if available).
        """
        # Get graph_domain from context (set by GraphExecutor)
        graph_domain = getattr(context, "graph_domain", None)

        return self._prompt_composer.compose_agent_prompt(
            agent_name=self.name,
            interface=context.interface,
            user_profile=context.user_profile,
            graph_domain=graph_domain,
        )

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Explore and gather context based on graph domain.

        The actual exploration behavior is controlled by the prompt variant,
        not by code branching. This makes adding new domains trivial.

        Args:
            input: User's request or exploration query.
            context: Execution context with graph_domain for variant selection.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with exploration findings.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
