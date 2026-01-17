"""Vault Connector Agent implementation.

Finds links between new thoughts and existing knowledge.
Part of the BRAINDUMP graph workflow.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class VaultConnectorAgent(BaseAgent):
    """
    Vault connection agent for knowledge linking.

    Identifies connections between organized thoughts and
    existing notes in the knowledge vault.

    Example:
        agent = VaultConnectorAgent(orchestrator, tools, composer)
        result = await agent.execute(organized_thoughts, context)
        # result.content contains thoughts with vault links
    """

    name = "vault_connector"
    category = "braindump"
    # Uses brain_search and brain_fetch to find connections
    tools = ["brain_search", "brain_fetch"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the vault connector agent."""
        config = config or {}
        config.setdefault("temperature", 0.2)  # Factual connections
        config.setdefault("max_tokens", 4096)
        config.setdefault("model_role", "braindump")  # Use braindump model
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Find vault connections for thoughts.

        Args:
            input: Organized thoughts to connect.
            context: Execution context.
            stream_handler: Optional handler for streaming.

        Returns:
            AgentResult with connection suggestions.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
