"""Strands + Ollama LLM implementation."""
import sys
sys.path.insert(0, '/shared')

import asyncio
import re
from typing import List, Dict, AsyncIterator, Optional
from functools import wraps
import tiktoken

from strands import Agent
from strands.models.ollama import OllamaModel
from strands.hooks import HookProvider, AfterToolCallEvent

from app.interfaces.llm import LLMInterface
from app.config import settings
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class ContentStripper:
    """Strips markdown and HTML from text. (Single Responsibility: Content Transformation)"""

    def strip(self, text: str) -> str:
        """Remove formatting from text."""
        # Remove markdown bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic*
        text = re.sub(r'__(.+?)__', r'\1', text)      # __bold__
        text = re.sub(r'_(.+?)_', r'\1', text)        # _italic_

        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove table separators
        text = re.sub(r'\|', '', text)

        # Remove horizontal rules
        text = re.sub(r'^[-=]{3,}$', '', text, flags=re.MULTILINE)

        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


class CallLimiter:
    """Limits number of calls to a resource. (Single Responsibility: Call Limiting)"""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.call_count = 0

    def can_call(self) -> bool:
        """Check if another call is allowed."""
        return self.call_count < self.max_calls

    def increment(self) -> None:
        """Record a call."""
        self.call_count += 1

    def get_status(self) -> Dict[str, int]:
        """Get current status."""
        return {
            'count': self.call_count,
            'max': self.max_calls,
            'remaining': self.max_calls - self.call_count
        }


def create_limited_fetch_wrapper(base_tool, limiter: CallLimiter, stripper: ContentStripper):
    """Factory function to create a limited fetch wrapper. (Single Responsibility: Coordination)"""

    @wraps(base_tool)
    def limited_fetch_wrapper(url: str) -> Dict[str, str]:
        # Check limit
        if not limiter.can_call():
            status = limiter.get_status()
            logger.info(f"🚫 Fetch limit reached ({status['max']} pages)")
            return {"error": f"Fetch limit reached ({status['max']} pages)"}

        # Call original tool
        result = base_tool(url)
        limiter.increment()

        status = limiter.get_status()
        logger.info(f"📄 Fetch call {status['count']}/{status['max']}: {url}")

        # Post-process content
        if 'content' in result and 'error' not in result:
            original_length = len(result['content'])
            result['content'] = stripper.strip(result['content'])
            cleaned_length = len(result['content'])
            logger.info(f"🧹 Stripped formatting: {original_length} → {cleaned_length} chars")

        return result

    # Copy Strands-specific attributes that @wraps doesn't copy
    for attr in ['name', 'description', 'parameters', 'func']:
        if hasattr(base_tool, attr):
            setattr(limited_fetch_wrapper, attr, getattr(base_tool, attr))

    return limited_fetch_wrapper


class ReferenceCapturingHook(HookProvider):
    """Hook to capture web page fetches for reference tracking."""

    def __init__(self):
        self.references: List[Dict[str, str]] = []

    def register_hooks(self, registry, **kwargs):
        """Register callbacks for tool call events."""
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)
        logger.info("✅ ReferenceCapturingHook registered")

    async def _on_after_tool_call(self, event: AfterToolCallEvent):
        """Capture fetch_webpage tool calls."""
        # Only track fetch_webpage tool
        if event.tool_use.get('name') != 'fetch_webpage':
            return

        logger.debug(f"🔍 DEBUG: fetch_webpage called, result type: {type(event.result)}")
        logger.debug(f"🔍 DEBUG: result: {event.result}")

        # Only track successful calls
        if not isinstance(event.result, dict) or event.result.get('status') != 'success':
            logger.debug(f"🔍 DEBUG: Skipping - not a successful dict result")
            return

        # Extract URL and title from tool result content
        result_content = event.result.get('content', [])
        logger.debug(f"🔍 DEBUG: result_content: {result_content}")

        for content_block in result_content:
            # The tool result is in 'text' field as a string representation
            if 'text' in content_block:
                import ast
                try:
                    # Parse the string representation of dict
                    data = ast.literal_eval(content_block['text'])
                    logger.debug(f"🔍 DEBUG: Parsed data: {data}")

                    url = data.get('url')
                    title = data.get('title')
                    logger.debug(f"🔍 DEBUG: Extracted - url: {url}, title: {title}")

                    if url and title:
                        # Avoid duplicates
                        if not any(ref['url'] == url for ref in self.references):
                            self.references.append({'url': url, 'title': title})
                            logger.debug(f"✅ DEBUG: Added reference: {title}")
                except (ValueError, SyntaxError) as e:
                    logger.warning(f"⚠️ DEBUG: Failed to parse tool result: {e}")
                break


class StrandsLLM(LLMInterface):
    """Strands agent with Ollama backend and custom tools."""

    def __init__(self):
        self.ollama_host = settings.OLLAMA_HOST
        self.default_model = settings.OLLAMA_DEFAULT_MODEL

        # Initialize Ollama model
        self.model = OllamaModel(
            host=self.ollama_host,
            model_id=self.default_model
        )

        # Initialize custom tools
        from app.tools import web_search, fetch_webpage
        self.base_fetch_webpage = fetch_webpage  # Store reference for wrapper
        self.custom_tools = [web_search, fetch_webpage]
        logger.info("✅ Custom web tools initialized (web_search, fetch_webpage)")

        # Token counter (approximate)
        self.encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # Agent will be created per-request with specific tools/config

    async def generate(
        self,
        context: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> Dict:
        """Generate complete response using Strands agent.

        Args:
            context: Conversation history
            model: Model to use (optional)
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)
        """
        # Select model
        model_id = model or self.default_model

        # Create model instance
        ollama_model = OllamaModel(
            host=self.ollama_host,
            model_id=model_id,
            temperature=temperature
        )

        # Build combined system prompt
        system_prompt = self._build_system_prompt(user_base_prompt)

        # Format context as prompt
        prompt = self._format_context(context, system_prompt)

        # Create reference capturing hook
        ref_hook = ReferenceCapturingHook()

        # Create limited fetch wrapper with SOLID composition (max 2 calls)
        from app.tools import web_search
        limiter = CallLimiter(max_calls=2)
        stripper = ContentStripper()
        limited_fetch = create_limited_fetch_wrapper(
            self.base_fetch_webpage,
            limiter=limiter,
            stripper=stripper
        )
        agent_tools = [web_search, limited_fetch]

        # Run agent with custom tools and hook
        loop = asyncio.get_event_loop()
        try:
            # Create agent with limited tools and hook
            agent = Agent(
                model=ollama_model,
                tools=agent_tools,
                system_prompt=system_prompt,
                hooks=[ref_hook]
            )

            response = await loop.run_in_executor(
                None,
                agent,
                prompt
            )

            return {
                'content': str(response),
                'model': model_id,
                'references': ref_hook.references
            }
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")

    async def generate_with_planning(
        self,
        context: List[Dict],
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> Dict:
        """
        Multi-agent generation: Planner → Executor.

        Phase 1: DeepSeek-R1:32b creates research plan
        Phase 2: gpt-oss:20b executes plan with tools

        Args:
            context: Conversation history
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Dict with 'content', 'model', 'references', and optionally 'plan'
        """
        # Extract user query from context
        user_query = context[-1]['content']
        logger.info(f"🧠 Multi-agent mode activated for: {user_query[:50]}...")

        # ═══════════════════════════════════════════════════════════
        # PHASE 1: Planning with DeepSeek-R1
        # ═══════════════════════════════════════════════════════════
        planner_model_id = settings.PLANNER_MODEL
        logger.info(f"🧠 Phase 1: Creating research plan ({planner_model_id})")

        planner_model = OllamaModel(
            host=self.ollama_host,
            model_id=planner_model_id,
            temperature=settings.PLANNER_TEMPERATURE
        )

        planning_prompt = self._build_planning_prompt(user_query)

        # Run planner (no tools needed)
        loop = asyncio.get_event_loop()
        try:
            planner_agent = Agent(
                model=planner_model,
                tools=[],  # NO TOOLS - pure reasoning
                system_prompt=planning_prompt
            )

            plan = await loop.run_in_executor(None, planner_agent, user_query)
            plan_text = str(plan).strip()
            logger.info(f"📋 Plan created ({len(plan_text)} chars)")
            logger.info(f"📋 Focused query: {plan_text}")

            # Use plan as-is (just clean whitespace)
            focused_query = plan_text if plan_text else user_query
            logger.info(f"🎯 Using focused query: {focused_query}")

            # Ollama will auto-unload deepseek-r1:8b when next model loads

            # ═══════════════════════════════════════════════════════════
            # PHASE 2: Execution with gpt-oss:20b
            # ═══════════════════════════════════════════════════════════
            logger.info("⚡ Phase 2: Executing plan (gpt-oss:20b)")

            executor_model = OllamaModel(
                host=self.ollama_host,
                model_id="gpt-oss:20b",
                temperature=temperature
            )

            # Build system prompt with focused query
            executor_system_prompt = self._build_execution_prompt(focused_query, user_base_prompt)

            # Simple user query instruction
            execution_instruction = f"USER QUERY: {user_query}"

            # Create reference capturing hook
            ref_hook = ReferenceCapturingHook()

            # Create limited fetch wrapper with SOLID composition (max 2 calls)
            from app.tools import web_search
            limiter = CallLimiter(max_calls=2)
            stripper = ContentStripper()
            limited_fetch = create_limited_fetch_wrapper(
                self.base_fetch_webpage,
                limiter=limiter,
                stripper=stripper
            )
            executor_tools = [web_search, limited_fetch]

            # Run executor WITH limited tools and hook
            executor_agent = Agent(
                model=executor_model,
                tools=executor_tools,
                system_prompt=executor_system_prompt,
                hooks=[ref_hook]
            )

            response = await loop.run_in_executor(None, executor_agent, execution_instruction)
            response_text = str(response)

            logger.info(f"✅ Multi-agent execution complete")
            logger.info(f"📊 References captured: {len(ref_hook.references)}")

            return {
                'content': response_text,
                'model': f'{planner_model_id}→{settings.EXECUTOR_MODEL}',
                'references': ref_hook.references,
                'plan': focused_query  # Include focused query for debugging
            }
        except Exception as e:
            logger.error(f"❌ Multi-agent execution failed: {str(e)}")
            raise Exception(f"Multi-agent generation failed: {str(e)}")

    async def generate_with_route(
        self,
        context: List[Dict],
        route_config: Dict,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> Dict:
        """
        Generate response based on route configuration with optimized system prompt.

        Args:
            context: Conversation history
            route_config: Dict with 'model', 'mode', and 'route_type' from router
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Dict with 'content', 'model', 'references'
        """
        # Extract config
        model = route_config.get('model')
        route_type = route_config.get('route_type')  # Route name for prompt selection

        if not model:
            raise Exception(f"No model specified in route config: {route_config}")

        # Build route-specific system prompt
        if route_type:
            system_prompt = self._build_route_system_prompt(route_type, user_base_prompt)
        else:
            # Fallback to general prompt if route_type missing
            system_prompt = self._build_system_prompt(user_base_prompt)

        # Create model instance with route-specific prompt
        ollama_model = OllamaModel(
            host=self.ollama_host,
            model_id=model,
            temperature=temperature
        )

        # Format context as prompt
        prompt = self._format_context(context, system_prompt)

        # Create reference capturing hook
        ref_hook = ReferenceCapturingHook()

        # Conditionally provide tools based on model
        # deepseek-r1 models don't support tool calling (pure reasoning models)
        agent_tools = []
        if 'deepseek-r1' not in model.lower():
            # Only provide tools for models that support them
            from app.tools import web_search
            limiter = CallLimiter(max_calls=2)
            stripper = ContentStripper()
            limited_fetch = create_limited_fetch_wrapper(
                self.base_fetch_webpage,
                limiter=limiter,
                stripper=stripper
            )
            agent_tools = [web_search, limited_fetch]
            logger.info(f"🔧 Providing tools (web_search, fetch_webpage) to {model}")
        else:
            logger.info(f"🧠 Pure reasoning mode for {model} (no tools)")

        # Run agent with route-optimized prompt
        loop = asyncio.get_event_loop()
        try:
            agent = Agent(
                model=ollama_model,
                tools=agent_tools,
                system_prompt=system_prompt,
                hooks=[ref_hook]
            )

            response = await loop.run_in_executor(None, agent, prompt)

            return {
                'content': str(response),
                'model': model,
                'references': ref_hook.references
            }
        except Exception as e:
            raise Exception(f"LLM generation failed: {str(e)}")

    async def generate_stream(
        self,
        context: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response (FUTURE IMPLEMENTATION).

        Strands supports streaming natively, this can be implemented
        when Discord message streaming is added.
        """
        # Placeholder for future streaming implementation
        raise NotImplementedError("Streaming not yet implemented")

    async def count_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken."""
        return len(self.encoder.encode(text))

    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ollama_host}/api/version",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def _get_format_rules(self) -> str:
        """Common formatting rules for all prompts."""
        return """FORMATTING RULES:

Choose format based on content:
- For comparisons, lists, multiple items → Use simple bullets
- For explanations, narratives → Use plain paragraphs

Example (comparison/list):
DDR5 RAM prices rose 40-60% in early 2025 due to supply constraints.

- 16GB kits: Started at $80, now $110-130 (38% increase)
- 32GB kits: Price jumped from $150 to $220 (47% increase)
- Main cause: TSMC production delays and AI server demand

Example (explanation):
DDR5 pricing surge is driven by AI demand. The dramatic price increases in DDR5 memory throughout 2025 are primarily caused by unprecedented demand from AI data centers. Manufacturers have shifted production capacity to high-bandwidth memory for AI accelerators, creating supply constraints for consumer DRAM.

FORBIDDEN: No pipes (|), no tables, no horizontal lines (---), no markdown (**text**, ##, ###). Use plain text only. Keep under 1500 characters."""

    def _build_system_prompt(self, user_base_prompt: Optional[str]) -> str:
        """Minimal system prompt for 20B models.

        Args:
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Combined system prompt optimized for 20B model constraints
        """
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Minimal prompt optimized for 20B models
        discord_system_prompt = f"""Date: {current_date}

You're a helpful Discord assistant with web search tools. For research: web_search → fetch_webpage on top 2-3 results (total) → answer. Be accurate and helpful.

{self._get_format_rules()}"""

        if user_base_prompt:
            return f"{discord_system_prompt}\n\n{user_base_prompt}"

        return discord_system_prompt

    def _build_route_system_prompt(
        self,
        route_type: str,
        user_base_prompt: Optional[str] = None
    ) -> str:
        """
        Build system prompt optimized for specific route.

        Args:
            route_type: Route name (SELF_HANDLE, SIMPLE_CODE, REASONING)
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Optimized system prompt for the route
        """
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Get route-specific prompt
        if route_type == "SELF_HANDLE":
            base_prompt = self._build_self_handle_prompt(current_date)
        elif route_type == "SIMPLE_CODE":
            base_prompt = self._build_coding_prompt(current_date)
        elif route_type == "REASONING":
            base_prompt = self._build_reasoning_prompt(current_date)
        else:
            # Fallback to general prompt
            base_prompt = self._build_system_prompt(user_base_prompt)
            return base_prompt

        # Append user's custom prompt if provided
        if user_base_prompt:
            return f"{base_prompt}\n\n{user_base_prompt}"

        return base_prompt

    def _build_self_handle_prompt(self, current_date: str) -> str:
        """System prompt for SELF_HANDLE route (gpt-oss:20b)."""
        return f"""Date: {current_date}

You're a helpful Discord assistant for quick questions and general conversation.

TASK: Answer questions clearly and concisely. For factual questions, provide accurate information. For explanations, keep them accessible and practical.

{self._get_format_rules()}

RESPONSE STYLE:
- Be conversational but informative
- Keep responses under 500 words
- Use simple language, avoid jargon unless necessary
- Don't dive into excessive technical detail"""

    def _build_coding_prompt(self, current_date: str) -> str:
        """System prompt for SIMPLE_CODE route (qwen2.5-coder:7b)."""
        return f"""Date: {current_date}

You're a coding assistant specialized in writing clean, practical code.

TASK: Help with coding tasks - write functions, fix bugs, design solutions, create implementations.

CODING PRINCIPLES:
1. Write clean, readable code with clear variable names
2. Include brief comments only where logic isn't obvious
3. Provide working examples with proper imports
4. Keep it simple - avoid over-engineering
5. Use standard libraries when possible
6. Follow language-specific best practices

{self._get_format_rules()}

RESPONSE FORMAT:
- Brief explanation (1-2 sentences)
- Code block with implementation
- Usage example if helpful
- Keep total response under 1000 words"""

    def _build_reasoning_prompt(self, current_date: str) -> str:
        """System prompt for REASONING route (gpt-oss:20b)."""
        return f"""Date: {current_date}

You're an analytical assistant specialized in research, comparisons, and deep analysis. You have web search tools available.

TASK: Research questions, compare options, analyze trade-offs, investigate complex topics.

RESEARCH PROCESS:
1. For current/factual questions: Use web_search → fetch_webpage (2-3 sources max)
2. For conceptual questions: Use your knowledge base
3. Synthesize information from multiple perspectives
4. Present structured, evidence-based analysis

ANALYSIS FRAMEWORK:
- Identify key factors and trade-offs
- Compare options objectively (pros/cons)
- Provide clear recommendations with reasoning
- Support claims with evidence (cite sources when using web tools)
- Acknowledge limitations or uncertainties

{self._get_format_rules()}

RESPONSE STRUCTURE:
- Brief summary/recommendation upfront
- Detailed analysis with key factors
- Trade-offs and considerations
- Clear conclusion
- Keep under 1500 words"""

    def _build_planning_prompt(self, user_query: str) -> str:
        """Ultra-minimal planner: output 1 focused sentence."""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        return f"""Date: {current_date}

Rephrase this query into 1 focused, search-optimized sentence:

{user_query}

Output just the sentence, nothing else."""

    def _build_execution_prompt(self, focused_query: str, user_base_prompt: Optional[str]) -> str:
        """Minimal prompt for 20B executor."""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        base = f"""Date: {current_date}

Research this: {focused_query}

Process: web_search → fetch_webpage on top 2-3 results (total) → synthesize your findings. Match user's language.

{self._get_format_rules()}"""

        if user_base_prompt:
            return f"{base}\n\n{user_base_prompt}"
        return base

    def _format_context(
        self,
        context: List[Dict],
        system_prompt: Optional[str]
    ) -> str:
        """Format conversation context as a prompt for Strands."""
        prompt_parts = []

        if system_prompt:
            prompt_parts.append(f"SYSTEM: {system_prompt}\n")

        for msg in context:
            role = msg['role'].upper()
            content = msg['content']
            prompt_parts.append(f"{role}: {content}")

        prompt_parts.append("ASSISTANT:")

        return "\n\n".join(prompt_parts)
