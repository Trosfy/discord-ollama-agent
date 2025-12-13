"""Intelligent request routing service using gpt-oss:20b."""
import sys
sys.path.insert(0, '/shared')

from enum import Enum
from typing import Dict
import asyncio

from strands import Agent
from strands.models.ollama import OllamaModel
from app.config import settings
from app.utils.model_utils import get_ollama_keep_alive
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
    """Routes requests to appropriate models based on classification (Coordination Only - SRP)."""

    def __init__(self, output_detector=None, input_detector=None):
        """
        Initialize router service with detectors (Dependency Injection).

        Args:
            output_detector: OutputArtifactDetector instance
            input_detector: InputArtifactDetector instance
        """
        self.router_model_id = settings.ROUTER_MODEL  # gpt-oss:20b
        self.ollama_host = settings.OLLAMA_HOST
        self.classification_prompt = self._build_classification_prompt()
        self.output_detector = output_detector
        self.input_detector = input_detector

    def _build_classification_prompt(self) -> str:
        """Build the router classification prompt."""
        return """You are a request classifier for an AI assistant system.

Analyze the user's request and classify it into ONE of these routes:

1. SELF_HANDLE - Simple questions, general conversation, quick facts
   Examples: "What is Python?", "Explain recursion", "Tell me about HTTP"

2. SIMPLE_CODE - Any coding task (simple or complex), bug fixes, design, architecture
   Examples: "Write a function to reverse a string", "Design a REST API",
             "Build a distributed caching system", "Fix this syntax error"

3. REASONING - Analytical tasks: comparisons, trade-off analysis, decision-making (with limited web research)
   Examples: "Compare REST vs GraphQL", "Should I use microservices or monolith?",
             "Analyze pros/cons of Redis vs Memcached", "Which framework should I choose?"

4. RESEARCH - Deep research requiring extensive web searches and many sources
   Examples: "Research the history of Bitcoin regulation", "Find latest developments in quantum computing",
             "Investigate current state of AI legislation", "Research blockchain use cases in healthcare"

5. MATH - Mathematical problems, calculations, equations, integrals, derivatives
   Examples: "integrate 4x^6 + 2x^3 + 7x - 4", "solve the equation 2x + 5 = 13",
             "calculate the derivative of sin(x) * cos(x)", "evaluate the limit as x approaches 0",
             "find the area under the curve y = x^2 from 0 to 5"
   Keywords: integrate, derivative, differentiate, solve equation, calculate, evaluate, limit,
             summation, factorial, logarithm, exponential, trigonometric, matrix, vector

Output ONLY the route name (e.g., "SIMPLE_CODE"), nothing else."""

    async def _rephrase_for_content_generation(self, user_message: str) -> str:
        """
        Rephrase user message to remove file creation language using LLM.

        Uses the router model (already warm from classification) to intelligently
        strip file creation phrases while preserving the core request.

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
            # Expert-crafted prompt: Learning by example for small models
            rephrase_prompt = """Transform user requests by removing file/storage references. Keep the core task.

EXAMPLES:
"write a summary about climate change and save it to summary.txt" → write a summary about climate change
"create me a quicksort file in c++" → implement quicksort in c++
"explain quantum physics, put into explanation.md" → explain quantum physics
"make a shopping list and save as list.txt" → make a shopping list
"generate meeting notes into notes.txt" → generate meeting notes
"why btc pump from 89k to 92k? put into .md file" → why btc pump from 89k to 92k?
"make me a recipe for pasta file" → give me a recipe for pasta
"write a poem about spring, create poem.txt" → write a poem about spring

Pattern: Remove filenames (.txt, .md, .py) and saving phrases ("save to", "put into", "create file"). Keep the action and topic.

Now transform:"""

            # Reuse router model (already warm from classification)
            router_model = OllamaModel(
                host=self.ollama_host,
                model_id=self.router_model_id,
                temperature=0.1,  # Low for deterministic output
                keep_alive="120s"
            )

            # Follow same pattern as classification
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

    async def classify_request(self, user_message: str, file_refs: list = []) -> dict:
        """
        Classify user request and detect preprocessing/postprocessing needs.

        NEW: Filters message if OUTPUT_ARTIFACT detected to remove file language.

        Uses gpt-oss:20b for route classification and detectors for artifact detection.

        Args:
            user_message: User's input message
            file_refs: List of uploaded file references (default: [])

        Returns:
            Dict with route, preprocessing, postprocessing, model, mode, filtered_prompt

        Raises:
            Exception: If classification fails
        """
        # Step 1: Classify main route
        route = await self._classify_route_llm(user_message)

        # Step 2: Detect artifacts
        input_artifact = False
        output_artifact = False

        if self.input_detector:
            input_artifact = self.input_detector.detect(file_refs)

        if self.output_detector:
            output_artifact = await self.output_detector.detect(user_message)

        # Step 3: Build preprocessing/postprocessing lists
        preprocessing = ['INPUT_ARTIFACT'] if input_artifact else []
        postprocessing = ['OUTPUT_ARTIFACT'] if output_artifact else []

        # Step 4: Filter message if OUTPUT_ARTIFACT detected (NEW)
        filtered_prompt = None
        if output_artifact:
            filtered_prompt = await self._rephrase_for_content_generation(user_message)
            logger.info(f"✂️  Filtered prompt for clean generation:")
            logger.info(f"   Original: {user_message[:80]}...")
            logger.info(f"   Cleaned:  {filtered_prompt[:80]}...")

        # Step 5: Get model config for route
        config = self._get_model_config(route)

        # Step 6: Return combined config with optional filtered prompt
        return {
            'route': route.value,
            'preprocessing': preprocessing,
            'postprocessing': postprocessing,
            'filtered_prompt': filtered_prompt,  # NEW: For orchestrator to use
            **config
        }

    async def _classify_route_llm(self, user_message: str) -> RouteType:
        """
        Classify user request into route using LLM.

        Args:
            user_message: User's input message

        Returns:
            RouteType enum indicating the appropriate route
        """
        try:
            logger.info(f"🔀 Classifying request: {user_message[:100]}...")

            # Create Ollama model via Strands (consistent with rest of codebase)
            router_model = OllamaModel(
                host=self.ollama_host,
                model_id=self.router_model_id,
                temperature=0.1,  # Low temperature for consistent classification
                keep_alive="120s"  # Keep router loaded for SELF_HANDLE reuse (2 minutes)
            )

            # Create Strands Agent for classification (no tools needed)
            loop = asyncio.get_event_loop()
            agent = Agent(
                model=router_model,
                tools=[],  # No tools - pure classification
                system_prompt=self.classification_prompt
            )

            # Invoke agent via Strands
            response = await loop.run_in_executor(None, agent, f"USER REQUEST: {user_message}")
            route_str = str(response).strip().upper()

            # Parse route
            try:
                route = RouteType[route_str]
                logger.info(f"✅ Classified as: {route.value}")
                return route
            except KeyError:
                # Fallback: try to find route name in response
                for route_type in RouteType:
                    if route_type.value in route_str:
                        logger.warning(f"⚠️ Extracted route from response: {route_type.value}")
                        return route_type

                # Last resort fallback
                logger.warning(f"⚠️ Classification unclear: '{route_str}', defaulting to REASONING")
                return RouteType.REASONING

        except Exception as e:
            logger.error(f"❌ Classification failed: {e}, defaulting to REASONING")
            return RouteType.REASONING  # Most capable fallback

    def _get_model_config(self, route: RouteType) -> Dict[str, str]:
        """
        Get model configuration for a route (private helper).

        Args:
            route: Classified route type

        Returns:
            Dict with 'model' and 'mode'
        """
        route_configs = {
            RouteType.SELF_HANDLE: {
                'model': settings.ROUTER_MODEL,  # gpt-oss:20b
                'mode': 'single'
            },
            RouteType.SIMPLE_CODE: {
                'model': settings.CODER_MODEL,  # qwen2.5-coder:7b
                'mode': 'single'
            },
            RouteType.REASONING: {
                'model': settings.REASONING_MODEL,  # magistral:24b (best for <40K tokens)
                'mode': 'single'
            },
            RouteType.RESEARCH: {
                'model': settings.RESEARCH_MODEL,  # deepseek-r1:14b (handles >40K tokens well)
                'mode': 'single'
            },
            RouteType.MATH: {
                'model': settings.MATH_MODEL,  # rnj-1:8b
                'mode': 'single'
            }
        }

        return route_configs.get(route, route_configs[RouteType.REASONING])
