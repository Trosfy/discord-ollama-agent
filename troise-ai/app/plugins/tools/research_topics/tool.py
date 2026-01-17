"""Research Topics Tool - Spawns parallel sub-agents for each topic.

This tool enables the Agent-as-Tool pattern for parallel research:
- Lead researcher calls research_topics(topics=[...]) with a list of topics
- Tool internally spawns sub-agents via asyncio.gather() for parallel execution
- Results are combined and returned to the lead researcher

This bypasses the unreliable autonomous handoff mechanism in Strands Swarm,
providing 100% deterministic parallel research execution.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Maximum web_fetch calls per research topic sub-agent
# Each topic gets isolated counting (child context)
MAX_FETCHES_PER_TOPIC = 5


class ResearchTopicsTool:
    """Tool that spawns parallel sub-agents for multiple research topics.

    The lead researcher passes a list of topics, and this tool:
    1. Creates a sub-agent for each topic
    2. Executes all sub-agents in parallel via asyncio.gather()
    3. Combines and returns all results

    This implements the "Agent-as-Tool" pattern from AWS Strands SDK,
    enabling hierarchical delegation with parallel execution.
    """

    name = "research_topics"
    description = """Research multiple topics in parallel.

Use this tool to investigate multiple aspects of the user's question simultaneously.
Each topic is researched by a dedicated specialist sub-agent in parallel.

WHEN TO USE:
- When a question has 2-5 distinct sub-topics to explore
- When you need comprehensive coverage of different angles
- When topics can be researched independently

HOW TO USE:
1. Break the user's question into 2-5 specific, researachable topics
2. Call this tool ONCE with ALL topics as a list
3. Synthesize the combined findings from all topics

EXAMPLE:
User: "What's the impact of AI on healthcare?"
Call: research_topics(topics=[
    "AI diagnostic tools accuracy and adoption",
    "AI drug discovery breakthroughs",
    "AI healthcare cost savings",
    "AI patient privacy concerns"
])"""

    parameters = {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of specific topics to research (2-5 topics recommended)",
                "minItems": 1,
                "maxItems": 5
            }
        },
        "required": ["topics"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
    ):
        """Initialize the research topics tool.

        Args:
            context: Execution context with user info, vram_orchestrator, etc.
            container: DI container for resolving services.
        """
        self._context = context
        self._container = container

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """Execute parallel research on all topics.

        Args:
            params: Tool parameters (topics list).
            context: Execution context.

        Returns:
            ToolResult with combined research from all topics.
        """
        topics = params.get("topics", [])

        if not topics:
            return ToolResult(
                content=json.dumps({"error": "No topics provided"}),
                success=False,
                error="Topics list is required"
            )

        logger.info(
            f"ResearchTopicsTool: Starting parallel research on {len(topics)} topics: "
            f"{[t[:30] + '...' if len(t) > 30 else t for t in topics]}"
        )

        # Get dependencies
        vram_orchestrator = context.vram_orchestrator
        if not vram_orchestrator:
            return ToolResult(
                content=json.dumps({"error": "VRAMOrchestrator not available"}),
                success=False,
                error="VRAMOrchestrator not available in context"
            )

        # Resolve ToolFactory from container for creating sub-agent tools
        from app.core.tool_factory import ToolFactory
        try:
            tool_factory = self._container.resolve(ToolFactory)
        except Exception as e:
            logger.error(f"Failed to resolve ToolFactory: {e}")
            return ToolResult(
                content=json.dumps({"error": "ToolFactory not available"}),
                success=False,
                error=str(e)
            )

        # Create async tasks for each topic
        tasks = []
        for topic in topics:
            task = self._research_single_topic(
                topic=topic,
                vram_orchestrator=vram_orchestrator,
                tool_factory=tool_factory,
                context=context,
            )
            tasks.append(task)

        # Execute all research in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        combined_content = []
        success_count = 0
        error_count = 0

        for topic, result in zip(topics, results):
            if isinstance(result, Exception):
                combined_content.append(
                    f"## Research: {topic}\n\n"
                    f"Error: {str(result)}\n"
                )
                error_count += 1
                logger.error(f"Research failed for topic '{topic}': {result}")
            else:
                combined_content.append(f"## Research: {topic}\n\n{result}\n")
                success_count += 1
                logger.info(
                    f"Research completed for topic '{topic}' "
                    f"({len(result)} chars)"
                )

        final_content = "\n---\n\n".join(combined_content)

        logger.info(
            f"ResearchTopicsTool: Completed {len(topics)} topics "
            f"(success={success_count}, errors={error_count}, "
            f"total_chars={len(final_content)})"
        )

        return ToolResult(
            content=final_content,
            success=True,
        )

    async def _research_single_topic(
        self,
        topic: str,
        vram_orchestrator,
        tool_factory,
        context: ExecutionContext,
    ) -> str:
        """Research a single topic using a sub-agent.

        Args:
            topic: The specific topic to research.
            vram_orchestrator: For getting models.
            tool_factory: For creating tools.
            context: Execution context.

        Returns:
            Research findings as formatted string.
        """
        try:
            from strands import Agent as StrandsAgent
        except ImportError as e:
            logger.error(f"Strands SDK not available: {e}")
            raise RuntimeError(f"Strands SDK not available: {e}")

        # Get model for research sub-agent
        # Use the "research" role from the profile to get appropriate model
        model_id = vram_orchestrator.get_profile_model("research")

        model = await vram_orchestrator.get_model(
            model_id=model_id,
            temperature=0.7,
            max_tokens=4096,
        )

        logger.debug(f"Created model for topic '{topic[:20]}...': {model_id}")

        # Create child context with per-topic web_fetch limit (isolated counting)
        # NOTE: Child context ensures parallel topics don't share counts
        topic_context = context.with_tool_limits({"web_fetch": MAX_FETCHES_PER_TOPIC})

        # Create tools for sub-agent (web_search, web_fetch) with limited context
        sub_agent_tools = tool_factory.create_tools(
            tool_names=["web_search", "web_fetch"],
            context=topic_context,
        )

        logger.debug(
            f"Created {len(sub_agent_tools)} tools for topic researcher: "
            f"['web_search', 'web_fetch'] (web_fetch limit: {MAX_FETCHES_PER_TOPIC})"
        )

        # Build sub-agent system prompt
        system_prompt = f"""You are a focused research specialist. Research this ONE topic thoroughly.

TOPIC: {topic}

INSTRUCTIONS:
1. Use web_search to find 3-5 relevant, authoritative sources
2. Use web_fetch to read the most promising sources
3. Extract key facts and findings
4. Cite EVERY fact with its source URL

OUTPUT FORMAT:
### Key Findings
- Finding 1
  Source: [Title](URL)
- Finding 2
  Source: [Title](URL)
- Finding 3
  Source: [Title](URL)

### Sources Consulted
1. [Title](URL) - Brief description of what you learned

RULES:
- Only cite URLs you actually fetched with web_fetch
- web_search results are previews, NOT citable sources
- Be thorough but focused on the specific topic
- Mark uncertain claims as "(needs verification)"
"""

        # Create sub-agent with safe name (remove spaces/special chars)
        safe_name = topic[:20].replace(" ", "_").replace("/", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")

        sub_agent = StrandsAgent(
            name=f"researcher_{safe_name}",
            system_prompt=system_prompt,
            model=model,
            tools=sub_agent_tools,
        )

        logger.info(f"Executing sub-agent for topic: {topic[:30]}...")

        # Execute sub-agent
        # Strands Agent can be called directly or via invoke_async
        if hasattr(sub_agent, "invoke_async"):
            result = await sub_agent.invoke_async(f"Research this topic: {topic}")
        else:
            # Fallback for sync-only versions
            result = await asyncio.to_thread(sub_agent, f"Research this topic: {topic}")

        return self._extract_content(result)

    def _extract_content(self, result) -> str:
        """Extract text content from Strands AgentResult.

        Args:
            result: Strands AgentResult object.

        Returns:
            Extracted text content as string.
        """
        # Handle different result structures
        if hasattr(result, "message"):
            message = result.message
            if isinstance(message, dict):
                content_blocks = message.get("content", [])
                texts = []
                for block in content_blocks:
                    if isinstance(block, dict) and "text" in block:
                        texts.append(block["text"])
                if texts:
                    return "\n".join(texts)

        # Fallback: try string conversion
        if hasattr(result, "text"):
            return result.text

        return str(result)

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def create_research_topics_tool(
    context: ExecutionContext,
    container: Container,
) -> ResearchTopicsTool:
    """Factory function to create research_topics tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured ResearchTopicsTool instance.
    """
    return ResearchTopicsTool(context=context, container=container)
