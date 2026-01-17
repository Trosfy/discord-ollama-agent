"""Graph node adapters for TROISE AI.

Adapts agents and other components to the IGraphNode interface
for use in graph-based workflows (Dependency Inversion Principle).
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .interfaces.graph import GraphState, NodeResult, IGraphNode

if TYPE_CHECKING:
    from .context import ExecutionContext
    from .base_agent import BaseAgent
    from .streaming import AgentStreamHandler
    from .tool_factory import ToolFactory

logger = logging.getLogger(__name__)


class AgentNode:
    """Adapts a BaseAgent to the IGraphNode interface.

    Wraps an agent to participate in graph execution. Handles:
    - Converting graph state to agent input
    - Converting agent result to NodeResult
    - Optional prompt variant override for shared agents (like explorer)

    Example:
        explorer_agent = ExplorerAgent(...)
        node = AgentNode(explorer_agent, prompt_variant="code")
        result = await node.execute(state, context)
    """

    def __init__(
        self,
        agent: "BaseAgent",
        prompt_variant: Optional[str] = None,
        state_key: Optional[str] = None,
        tool_override: Optional[List[str]] = None,
        tool_limits: Optional[Dict[str, int]] = None,
    ):
        """Initialize agent node.

        Args:
            agent: The underlying BaseAgent instance.
            prompt_variant: Optional graph domain for prompt variant selection.
                          Overrides context.graph_domain for this node.
            state_key: Optional key to store output in state (defaults to node name).
            tool_override: Optional list of tool names to use instead of agent's default tools.
                          Allows graph YAML to specify per-node tool lists.
            tool_limits: Optional tool call limits (e.g., {"web_fetch": 3}).
                        Limits persist for the entire node execution.
        """
        self._agent = agent
        self._prompt_variant = prompt_variant
        self._state_key = state_key or agent.name
        self._tool_override = tool_override
        self._tool_limits = tool_limits or {}
        self.name = agent.name

    @property
    def tools(self) -> List[str]:
        """Get tool names from underlying agent."""
        return getattr(self._agent, "tools", [])

    async def execute(
        self,
        state: GraphState,
        context: "ExecutionContext",
        input_text: Optional[str] = None,
        tool_factory: Optional["ToolFactory"] = None,
    ) -> NodeResult:
        """Execute the agent as a graph node.

        Args:
            state: Current graph state.
            context: Execution context.
            input_text: Input text for the agent.
            tool_factory: Factory for creating agent-specific tools (respects skip_universal_tools).

        Returns:
            NodeResult with agent output and state updates.
        """
        # Set tool limits on context BEFORE creating tools
        # NOTE: Mutation is intentional - limits persist for entire node execution
        # (follows graph_domain pattern below at lines 100-102)
        if self._tool_limits:
            context.tool_call_limits.update(self._tool_limits)
            logger.debug(f"AgentNode '{self.name}' set tool limits: {self._tool_limits}")

        # Create agent-specific tools using factory (respects skip_universal_tools config)
        # If tool_override is set, use those tools instead of agent's default
        if tool_factory and hasattr(self._agent, 'set_tools'):
            agent_tools = tool_factory.create_tools_for_agent(
                self._agent.name,
                context,
                tool_names=self._tool_override,
            )
            self._agent.set_tools(agent_tools)
            logger.debug(f"Injected {len(agent_tools)} tools into agent '{self._agent.name}'")

        # Build input from state or provided input
        agent_input = self._build_input(state, input_text)

        # Set prompt variant if specified (for shared agents like explorer)
        original_graph_domain = getattr(context, "graph_domain", None)
        if self._prompt_variant:
            context.graph_domain = self._prompt_variant

        try:
            # Execute agent
            logger.info(f"AgentNode '{self.name}' executing with input length {len(agent_input)}")

            result = await self._agent.execute(
                input=agent_input,
                context=context,
                stream_handler=None,  # Streaming handled at graph level
            )

            # Build state updates
            state_updates = self._extract_state_updates(result)

            return NodeResult(
                node_name=self.name,
                content=result.content,
                success=True,
                state_updates=state_updates,
                tool_calls=result.tool_calls,
            )

        except Exception as e:
            logger.error(f"AgentNode '{self.name}' failed: {e}")
            return NodeResult(
                node_name=self.name,
                content=f"Error: {str(e)}",
                success=False,
                error=str(e),
            )

        finally:
            # Restore original graph domain
            if self._prompt_variant and original_graph_domain is not None:
                context.graph_domain = original_graph_domain

    def _build_input(
        self,
        state: GraphState,
        input_text: Optional[str] = None,
    ) -> str:
        """Build agent input from state and provided input.

        For first nodes: uses input_text directly.
        For subsequent nodes: may incorporate previous outputs from state.
        For citation_formatter: appends collected sources from web_fetch.

        Args:
            state: Current graph state.
            input_text: Optional explicit input text.

        Returns:
            Input string for the agent.
        """
        if input_text:
            base_input = input_text
        else:
            # If no input provided, use original input from state
            base_input = state.get("input", "")

        # For citation_formatter, append collected sources from web_fetch
        # These are the only URLs that should be cited (actually fetched pages)
        if self.name == "citation_formatter":
            sources = state.get("collected_sources", [])
            if sources:
                sources_text = "\n\n## Collected Sources (from web_fetch)\n"
                sources_text += "These are the ONLY pages that were actually read. "
                sources_text += "Use ONLY these URLs for citations:\n\n"
                for i, src in enumerate(sources, 1):
                    sources_text += f"{i}. [{src['title']}]({src['url']})\n"
                base_input += sources_text

        return base_input

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract state updates from agent result.

        Can be overridden by subclasses to parse structured outputs.

        Args:
            result: AgentResult from agent execution.

        Returns:
            Dictionary of state updates.
        """
        updates = {
            f"{self._state_key}_output": result.content,
            f"{self._state_key}_tool_calls": result.tool_calls,
        }

        # Extract structured data from metadata if present
        if hasattr(result, "metadata") and result.metadata:
            for key, value in result.metadata.items():
                if key not in ("agent", "model", "tools_used"):
                    updates[f"{self._state_key}_{key}"] = value

        return updates


class CodeReviewerNode(AgentNode):
    """Specialized node for code review with structured output parsing.

    Extracts review issues from the agent's output and stores them
    in state for conditional edge evaluation.

    Output behavior (smart passthrough):
    - APPROVED: Returns original code (passthrough to user)
    - NEEDS_REVISION: Returns code + review (enriched for debugger)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._input_code: Optional[str] = None  # Store input for passthrough

    async def execute(
        self,
        state: GraphState,
        context: "ExecutionContext",
        input_text: Optional[str] = None,
        tool_factory: Optional["ToolFactory"] = None,
    ) -> NodeResult:
        """Execute code review with smart passthrough.

        Args:
            state: Current graph state.
            context: Execution context.
            input_text: Input text (code from previous node).
            tool_factory: Factory for creating agent-specific tools.

        Returns:
            NodeResult with appropriate content based on verdict:
            - APPROVED: Returns original code for user
            - NEEDS_REVISION: Returns code + review for debugger
        """
        # Store input code for passthrough
        self._input_code = input_text

        # Execute normal review
        result = await super().execute(state, context, input_text, tool_factory)

        # Determine output based on review result
        # Check review_passed from state_updates (set by _extract_state_updates)
        if self._input_code and result.state_updates:
            review_passed = result.state_updates.get("review_passed", False)

            if review_passed:
                # APPROVED: Return code only (for user)
                output_content = self._input_code
                logger.debug(f"CodeReviewerNode: APPROVED - returning original code")
            else:
                # NEEDS_REVISION: Return code + review (for debugger)
                output_content = f"""## CODE TO FIX
{self._input_code}

## REVIEW FEEDBACK
{result.content}"""
                logger.debug(f"CodeReviewerNode: NEEDS_REVISION - returning code + review")

            # Create new result with updated content
            result = NodeResult(
                node_name=result.node_name,
                content=output_content,
                success=result.success,
                state_updates=result.state_updates,
                tool_calls=result.tool_calls,
                error=result.error,
            )

        return result

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract review issues from code reviewer output.

        Parses the structured verdict format from the prompt:
        - VERDICT: APPROVED → code passes review
        - VERDICT: NEEDS_REVISION → code needs fixes
        """
        updates = super()._extract_state_updates(result)
        content = result.content.lower()

        # Parse explicit verdicts (matches prompt format)
        approved = "verdict: approved" in content
        needs_revision = (
            "verdict: needs_revision" in content or
            "verdict: needs revision" in content
        )

        if approved and not needs_revision:
            # Explicit approval
            has_issues = False
        elif needs_revision:
            # Explicit rejection
            has_issues = True
        else:
            # No clear verdict - fallback to strong signals only
            # Requires bracketed severity markers to reduce false positives
            issue_indicators = [
                "[critical]", "[high]", "[medium]",
                "needs fixing", "must fix", "must be fixed",
                "security vulnerability", "logic error",
                "will cause", "will fail", "will crash"
            ]
            has_issues = any(indicator in content for indicator in issue_indicators)

        updates["review_issues"] = [result.content] if has_issues else []
        updates["review_passed"] = not has_issues

        return updates


class TestGeneratorNode(AgentNode):
    """Specialized node for test generation with result tracking."""

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract test results from test generator output."""
        updates = super()._extract_state_updates(result)

        # Check for test execution results (simplified)
        content = result.content.lower()
        tests_passed = "passed" in content and "failed" not in content
        tests_failed = "failed" in content or "error" in content

        updates["test_results"] = {
            "passed": tests_passed and not tests_failed,
            "content": result.content,
        }

        return updates


class FactCheckerNode(AgentNode):
    """Specialized node for fact checking with claim verification tracking."""

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract verification status from fact checker output."""
        updates = super()._extract_state_updates(result)

        # Parse verification status (simplified)
        content = result.content.lower()
        has_unverified = any(word in content for word in [
            "unverified", "unable to verify", "could not confirm",
            "needs more", "insufficient", "no source"
        ])

        updates["unverified_claims"] = [result.content] if has_unverified else []
        updates["facts_verified"] = not has_unverified

        return updates


class VaultConnectorNode(AgentNode):
    """Specialized node for vault connection tracking."""

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract vault connections from connector output."""
        updates = super()._extract_state_updates(result)

        # Count connections mentioned (simplified - look for [[wiki links]])
        import re
        wiki_links = re.findall(r'\[\[([^\]]+)\]\]', result.content)
        updates["vault_connections"] = wiki_links
        updates["connection_count"] = len(wiki_links)

        return updates


class KnowledgeExplorerNode(AgentNode):
    """Specialized node for knowledge exploration with scoring."""

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract knowledge score from explorer output."""
        updates = super()._extract_state_updates(result)

        # Estimate knowledge score based on content length and structure
        content = result.content
        word_count = len(content.split())

        # Simple heuristic: more content = more knowledge found
        # Normalize to 0-1 range
        score = min(1.0, word_count / 500)

        # Boost if content has structured elements
        if "```" in content or "- " in content or "1." in content:
            score = min(1.0, score + 0.2)

        updates["knowledge_score"] = score
        updates["has_sufficient_knowledge"] = score >= 0.7

        return updates


# =============================================================================
# Swarm Node Adapters (Phase 2: Strands Swarm Integration)
# =============================================================================


@dataclass
class SwarmAgentConfig:
    """Configuration for deferred swarm agent creation.

    Stores agent configuration at graph load time. Actual Strands Agent
    and model creation is deferred to execution time to route through
    VRAMOrchestrator for proper VRAM management.

    NOTE: system_prompt is NOT stored here - prompts are composed at
    execution time using PromptComposer to ensure template placeholders
    like {interface_context} are properly filled.
    """
    name: str
    model_id: str
    model_role: str  # For profile lookup (e.g., "research", "code")
    temperature: float
    max_tokens: int
    tools: List[str] = field(default_factory=list)


class SwarmNode:
    """Adapts a Strands Swarm to the IGraphNode interface.

    Creates Strands agents lazily at execution time to route model
    creation through VRAMOrchestrator for proper VRAM management.

    SOLID Compliance:
    - SRP: Only responsible for executing swarm and converting result
    - OCP: Registered in SPECIALIZED_SWARM_NODES for loader discovery
    - LSP: Substitutable for any IGraphNode in graph execution
    - DIP: Depends on GraphState abstraction, not concrete state

    Example:
        swarm_node = SwarmNode(
            agent_configs=[SwarmAgentConfig(...)],
            entry_point_name="deep_research",
            name="research_swarm",
        )
        result = await swarm_node.execute(state, context)
    """

    def __init__(
        self,
        agent_configs: List[SwarmAgentConfig],
        entry_point_name: str,
        name: str,
        max_handoffs: int = 20,
        max_iterations: int = 20,
        state_key: Optional[str] = None,
    ):
        """Initialize swarm node with deferred agent creation.

        Args:
            agent_configs: List of agent configurations for lazy creation.
            entry_point_name: Name of the entry point agent.
            name: Unique node identifier for this swarm.
            max_handoffs: Maximum handoffs between agents (default 20).
            max_iterations: Maximum iterations (default 20).
            state_key: Optional key for storing output in state.
        """
        self._agent_configs = agent_configs
        self._entry_point_name = entry_point_name
        self._max_handoffs = max_handoffs
        self._max_iterations = max_iterations
        self.name = name
        self._state_key = state_key or name

    @property
    def tools(self) -> List[str]:
        """Get union of all tool names from swarm agents.

        Returns:
            Empty list - swarm tools are managed internally.
        """
        # Swarm tools are managed by Strands SDK internally
        return []

    async def execute(
        self,
        state: GraphState,
        context: "ExecutionContext",
        input_text: Optional[str] = None,
        tool_factory: Optional["ToolFactory"] = None,
    ) -> NodeResult:
        """Execute the swarm as a graph node.

        Creates Strands agents with models from VRAMOrchestrator at
        execution time for proper VRAM management.

        Args:
            state: Current graph state.
            context: Execution context (must have vram_orchestrator).
            input_text: Input text for the swarm.
            tool_factory: Factory for tools (param for interface consistency).

        Returns:
            NodeResult with swarm output and state updates.
        """
        import asyncio

        try:
            from strands import Agent as StrandsAgent
            from strands.multiagent import Swarm
        except ImportError as e:
            logger.error(f"Strands SDK not available: {e}")
            return NodeResult(
                node_name=self.name,
                content=f"Error: Strands SDK not available: {e}",
                success=False,
                error=str(e),
            )

        # Build input from state or provided input
        swarm_input = self._build_input(state, input_text)

        logger.info(f"SwarmNode '{self.name}' executing with input length {len(swarm_input)}")

        try:
            # Get VRAMOrchestrator and PromptComposer from context
            vram_orchestrator = context.vram_orchestrator
            prompt_composer = context.prompt_composer

            # Build Strands agents with VRAM-managed models
            strands_agents = []
            for config in self._agent_configs:
                # Get model through VRAMOrchestrator for proper VRAM management
                model = await vram_orchestrator.get_model(
                    model_id=config.model_id,
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                )

                logger.debug(
                    f"SwarmNode '{self.name}': Created model for agent '{config.name}' "
                    f"(model={config.model_id})"
                )

                # Create tools for this agent via tool_factory
                agent_tools = []
                if tool_factory and config.tools:
                    agent_tools = tool_factory.create_tools_for_agent(
                        config.name,
                        context,
                        tool_names=config.tools,
                    )
                    logger.debug(
                        f"SwarmNode '{self.name}': Created {len(agent_tools)} tools "
                        f"for agent '{config.name}': {config.tools}"
                    )

                # Compose system prompt at execution time with full context
                # This ensures {interface_context}, {personalization_context} are filled
                system_prompt = prompt_composer.compose_agent_prompt(
                    agent_name=config.name,
                    interface=context.interface,
                    user_profile=context.user_profile,
                    graph_domain=getattr(context, "graph_domain", None),
                )

                logger.debug(
                    f"SwarmNode '{self.name}': Composed prompt for agent '{config.name}' "
                    f"(length={len(system_prompt)})"
                )

                strands_agent = StrandsAgent(
                    name=config.name,
                    system_prompt=system_prompt,
                    model=model,
                    tools=agent_tools,
                )
                strands_agents.append(strands_agent)

            # Build swarm with configured agents
            entry_point = next(
                (a for a in strands_agents if a.name == self._entry_point_name),
                strands_agents[0]
            )

            swarm = Swarm(
                nodes=strands_agents,
                entry_point=entry_point,
                max_handoffs=self._max_handoffs,
                max_iterations=self._max_iterations,
            )

            logger.info(
                f"SwarmNode '{self.name}': Built swarm with {len(strands_agents)} agents, "
                f"entry_point='{self._entry_point_name}'"
            )

            # Execute swarm (Strands Swarm supports async via invoke_async)
            if hasattr(swarm, "invoke_async"):
                swarm_result = await swarm.invoke_async(swarm_input)
            else:
                # Fallback for sync-only Strands versions
                swarm_result = await asyncio.to_thread(swarm, swarm_input)

            # Extract state updates following existing pattern
            state_updates = self._extract_state_updates(swarm_result)

            return NodeResult(
                node_name=self.name,
                content=self._extract_content_from_swarm(swarm_result),
                success=True,
                state_updates=state_updates,
                tool_calls=getattr(swarm_result, "tool_calls", []),
            )

        except Exception as e:
            logger.error(f"SwarmNode '{self.name}' failed: {e}")
            return NodeResult(
                node_name=self.name,
                content=f"Error: {str(e)}",
                success=False,
                error=str(e),
            )

    def _build_input(
        self,
        state: GraphState,
        input_text: Optional[str] = None,
    ) -> str:
        """Build swarm input from state and provided input.

        Follows same pattern as AgentNode._build_input().
        """
        if input_text:
            return input_text
        return state.get("input", "")

    def _extract_content_from_swarm(self, swarm_result) -> str:
        """Extract text content from Strands SwarmResult.

        SwarmResult has nested structure:
        - swarm_result.results: dict of agent_name → NodeResult
        - node_result.result: AgentResult
        - agent_result.message: dict with 'content' key
        - message['content']: list of blocks with 'text' key

        Args:
            swarm_result: Strands SwarmResult object.

        Returns:
            Extracted text content or string representation as fallback.
        """
        if not hasattr(swarm_result, 'results') or not swarm_result.results:
            return str(swarm_result)

        contents = []
        for agent_name, node_result in swarm_result.results.items():
            try:
                if not hasattr(node_result, 'result'):
                    continue

                agent_result = node_result.result

                # Handle Strands AgentResult with message dict
                if hasattr(agent_result, 'message'):
                    message = agent_result.message
                    if isinstance(message, dict):
                        content_blocks = message.get("content", [])
                        for block in content_blocks:
                            if isinstance(block, dict) and "text" in block:
                                contents.append(block["text"])
                # Fallback for other result types with .content
                elif hasattr(agent_result, 'content'):
                    contents.append(str(agent_result.content))

            except Exception as e:
                logger.debug(f"Error extracting content from agent {agent_name}: {e}")

        return "\n".join(contents).strip() if contents else str(swarm_result)

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract state updates from swarm result.

        Follows same pattern as AgentNode._extract_state_updates().
        Can be overridden by subclasses for domain-specific extraction.

        Args:
            result: Strands AgentResult from swarm execution.

        Returns:
            Dictionary of state updates.
        """
        content = self._extract_content_from_swarm(result)
        updates = {
            f"{self._state_key}_output": content,
        }

        # Extract swarm-specific metadata if available
        if hasattr(result, "agents_executed"):
            updates[f"{self._state_key}_agents_used"] = result.agents_executed
        if hasattr(result, "handoff_count"):
            updates[f"{self._state_key}_handoff_count"] = result.handoff_count

        return updates


class QualitySwarmNode(SwarmNode):
    """Specialized swarm node for code quality assurance.

    Extracts review status and test results from swarm output
    for downstream conditional edge evaluation.

    Follows existing pattern of specialized nodes like:
    - CodeReviewerNode
    - TestGeneratorNode
    """

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract quality metrics from swarm result."""
        updates = super()._extract_state_updates(result)

        content_text = self._extract_content_from_swarm(result)
        content = content_text.lower()

        # Check for review issues (same logic as CodeReviewerNode)
        has_issues = any(word in content for word in [
            "issue", "bug", "error", "problem", "fix",
            "vulnerability", "security", "performance"
        ])
        updates["review_issues"] = [content_text] if has_issues else []
        updates["review_passed"] = not has_issues

        # Check for test results (same logic as TestGeneratorNode)
        tests_passed = "passed" in content and "failed" not in content
        tests_failed = "failed" in content or "error" in content
        updates["test_results"] = {
            "passed": tests_passed and not tests_failed,
            "content": content_text,
        }

        return updates


class ResearchSwarmNode(SwarmNode):
    """Specialized swarm node for research collaboration.

    Extracts fact verification status from swarm output.

    Follows existing pattern of FactCheckerNode.
    """

    def _extract_state_updates(self, result: Any) -> dict:
        """Extract research metrics from swarm result."""
        updates = super()._extract_state_updates(result)

        content_text = self._extract_content_from_swarm(result)
        content = content_text.lower()

        # Check for unverified claims (same logic as FactCheckerNode)
        has_unverified = any(word in content for word in [
            "unverified", "unable to verify", "could not confirm",
            "needs more", "insufficient", "no source"
        ])
        updates["unverified_claims"] = [content_text] if has_unverified else []
        updates["facts_verified"] = not has_unverified

        return updates
