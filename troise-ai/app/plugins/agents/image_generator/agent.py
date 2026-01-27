"""Image Generator Agent implementation.

Handles image generation requests by:
1. Understanding what the user wants to create
2. Crafting effective prompts for FLUX 2.dev
3. Selecting appropriate aspect ratios and parameters
4. Calling the generate_image tool
5. Presenting results to the user
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.core.base_agent import BaseAgent
from app.core.context import ExecutionContext
from app.core.interfaces.agent import AgentResult

if TYPE_CHECKING:
    from app.core.streaming import AgentStreamHandler


class ImageGeneratorAgent(BaseAgent):
    """
    Image generation agent using FLUX 2.dev.

    Uses the image_handler model role (profile.image_handler_model) to:
    - Interpret user requests for images
    - Craft detailed, effective prompts for the FLUX model
    - Select appropriate aspect ratios and generation parameters
    - Call the generate_image tool which uses FLUX 2.dev

    The actual image generation is done by the generate_image tool which
    uses VRAMOrchestrator to manage the FLUX model in VRAM.

    Example:
        agent = ImageGeneratorAgent(
            vram_orchestrator=orchestrator,
            tools=[generate_image_tool],
            prompt_composer=composer,
        )
        result = await agent.execute("Create a cyberpunk cityscape", context)
    """

    name = "image_generator"
    category = "image"
    tools = ["generate_image"]

    def __init__(
        self,
        vram_orchestrator,
        tools: List[Any],
        prompt_composer,
        config: Dict[str, Any] = None,
    ):
        """Initialize the image generator agent.

        Args:
            vram_orchestrator: VRAM orchestrator for model access.
            tools: List of Strands tool instances (should include generate_image).
            prompt_composer: PromptComposer for building system prompts.
            config: Agent configuration.
        """
        config = config or {}
        # Creative temperature for prompt crafting
        config.setdefault("temperature", 0.7)
        config.setdefault("max_tokens", 2048)
        # Use image_handler model role (maps to profile.image_handler_model)
        config.setdefault("model_role", "image_handler")
        super().__init__(vram_orchestrator, tools, prompt_composer, config)

    async def execute(
        self,
        input: str,
        context: ExecutionContext,
        stream_handler: Optional["AgentStreamHandler"] = None,
    ) -> AgentResult:
        """
        Generate an image based on user request.

        The agent will:
        1. Analyze the user's request
        2. Craft a detailed prompt optimized for FLUX 2.dev
        3. Choose appropriate aspect ratio and parameters
        4. Call generate_image tool
        5. Present the result

        Args:
            input: User's image generation request.
            context: Execution context.
            stream_handler: Optional handler for streaming to WebSocket.

        Returns:
            AgentResult with generated image file_id and metadata.
        """
        return await self._execute_with_streaming(
            input=input,
            context=context,
            stream_handler=stream_handler,
        )
