"""Strands + Ollama LLM implementation."""
import sys
sys.path.insert(0, '/shared')

import asyncio
import re
import random
from typing import List, Dict, AsyncIterator, Optional
from functools import wraps
import tiktoken

from strands import Agent
from strands.models.ollama import OllamaModel
from strands.hooks import HookProvider, AfterToolCallEvent

from app.interfaces.llm import LLMInterface
from app.config import settings, get_model_capabilities
from app.utils.model_utils import get_ollama_keep_alive
from app.streaming import StreamProcessor, StreamFilter, StreamLogger
from app.prompts import PromptComposer
from app.implementations.model_factory import ModelFactory
from app.services.vram import get_orchestrator
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


def create_async_limited_fetch_wrapper(base_tool, max_calls: int):
    """
    Create async fetch wrapper with call limiting.

    Args:
        base_tool: The async fetch_webpage tool (DecoratedFunctionTool from Strands)
        max_calls: Maximum number of fetch calls allowed

    Returns:
        Wrapped DecoratedFunctionTool with call limiting
    """
    call_count = {"count": 0}  # Mutable counter for closure

    # Import tool decorator
    from strands import tool

    # Extract spec from base tool
    tool_name = base_tool.tool_name
    tool_spec = base_tool.tool_spec

    # Create wrapper function
    async def limited_fetch(url: str, use_cache: bool = True, max_retries: int = 3):
        """Limited async fetch that enforces max_calls limit."""
        if call_count["count"] >= max_calls:
            logger.warning(f"🚫 Fetch limit reached ({max_calls} fetches)")
            return {
                "error": f"Fetch limit reached ({max_calls} fetches). Please synthesize the information you already have."
            }

        call_count["count"] += 1
        logger.info(f"📄 Fetch {call_count['count']}/{max_calls}: {url}")
        return await base_tool(url, use_cache, max_retries)

    # Re-decorate with @tool using original spec
    # This creates a proper DecoratedFunctionTool that Strands recognizes
    decorated = tool(
        name=tool_name,
        description=tool_spec.get('description', '')
    )(limited_fetch)

    return decorated


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


def _get_status_indicator(route: str, enable_thinking: bool) -> str:
    """
    Get a randomized status indicator based on route and thinking mode.

    Args:
        route: Route name (REASONING, RESEARCH, SIMPLE_CODE, SELF_HANDLE)
        enable_thinking: Whether thinking mode is enabled

    Returns:
        Randomized status message
    """
    if enable_thinking:
        # Thinking mode indicators
        messages = [
            "*Thinking...*",
            "*Analyzing...*",
            "*Considering...*",
            "*Pondering...*"
        ]
    elif route == "RESEARCH":
        messages = [
            "*Researching...*",
            "*Gathering information...*",
            "*Looking into this...*"
        ]
    elif route == "SIMPLE_CODE":
        messages = [
            "*Crafting code...*",
            "*Writing...*",
            "*Coding...*"
        ]
    else:
        # General processing indicators
        messages = [
            "*Processing...*",
            "*Working on it...*",
            "*One moment...*"
        ]

    return random.choice(messages) + "\n\n"


class StrandsLLM(LLMInterface):
    """Strands agent with Ollama backend and custom tools."""

    def __init__(self):
        self.ollama_host = settings.OLLAMA_HOST
        self.default_model = settings.OLLAMA_DEFAULT_MODEL
        self.keep_alive = get_ollama_keep_alive(self.default_model)  # Per-model keep_alive (respects priority)

        # Initialize Ollama model
        self.model = OllamaModel(
            host=self.ollama_host,
            model_id=self.default_model,
            keep_alive=self.keep_alive  # Control VRAM management (per-model keep_alive from ModelCapabilities)
        )

        # Initialize extension orchestrator for POST-PROCESSING only
        # (NO ImageOCRExtension - OCR happens in preprocessing via FileExtractionRouter)
        from app.extensions import ExtensionOrchestrator, DiscordFileExtension
        self.extension_orchestrator = ExtensionOrchestrator([
            DiscordFileExtension(),  # ONLY for artifact registration (post-processing)
        ])
        logger.info("✅ ExtensionOrchestrator initialized with Discord extension (post-processing only)")

        # Initialize custom tools + Strands file tools (wrapped with extensions)
        from app.tools import web_search, fetch_webpage, list_attachments
        from app.tools.strands_tools_wrapped import (
            file_read_wrapped,
            file_write_wrapped,
            set_orchestrator
        )

        # Set orchestrator for wrapped tools
        set_orchestrator(self.extension_orchestrator)

        self.base_fetch_webpage = fetch_webpage  # Store reference for wrapper
        self.custom_tools = [
            web_search,
            fetch_webpage,
            list_attachments,
            file_read_wrapped,   # Strands tool + extensions (PDF, OCR, Discord)
            file_write_wrapped,  # Strands tool + extensions (Discord artifact registration)
        ]
        logger.info("✅ Custom tools initialized (web_search, fetch_webpage, list_attachments, file_read, file_write)")

        # Initialize prompt composer (modular prompt architecture)
        self.prompt_composer = PromptComposer()
        logger.info("✅ PromptComposer initialized (modular prompt system)")

        # Token counter (approximate)
        self.encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")

        # Request context for extensions (set per-request)
        self.current_request_context = {}

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

        # Create model instance using ModelFactory
        model_instance = await ModelFactory.create_model(
            model_name=model_id,
            temperature=temperature
        )

        # Build combined system prompt
        system_prompt = self._build_system_prompt(user_base_prompt)

        # Format context as prompt
        prompt = self._format_context(context, system_prompt)

        # Create reference capturing hook
        ref_hook = ReferenceCapturingHook()

        # Create limited fetch wrapper with SOLID composition (max 2 calls)
        from app.tools import web_search, list_attachments, file_read_wrapped
        limiter = CallLimiter(max_calls=2)
        stripper = ContentStripper()
        limited_fetch = create_limited_fetch_wrapper(
            self.base_fetch_webpage,
            limiter=limiter,
            stripper=stripper
        )
        # Note: get_file_content deprecated - content is prepended to message via file_context_builder
        agent_tools = [web_search, limited_fetch, list_attachments]

        # Check if model supports tools
        model_caps = get_model_capabilities(model_id)
        supports_tools = model_caps and model_caps.supports_tools
        if not supports_tools:
            logger.info(f"⚠️  Model {model_id} doesn't support tools - running without tools")
            agent_tools = []

        # Run agent with custom tools and hook
        loop = asyncio.get_event_loop()
        try:
            # Create agent with limited tools and hook
            agent = Agent(
                model=model_instance,
                tools=agent_tools if supports_tools else [],
                system_prompt=system_prompt,
                hooks=[ref_hook] if supports_tools else []
            )

            # Capture current request context for executor thread
            from app.dependencies import get_current_request, set_current_request
            current_request_snapshot = get_current_request().copy()

            def run_agent_with_context():
                """Run agent in executor thread with proper context propagation."""
                # Set context in executor thread (ContextVars don't auto-propagate to threads)
                set_current_request(current_request_snapshot)
                return agent(prompt)

            response = await loop.run_in_executor(None, run_agent_with_context)

            return {
                'content': str(response),
                'model': model_id,
                'references': ref_hook.references
            }
        except Exception as e:
            # Clean up registry on generation failure (prevents waiting for reconciliation)
            if settings.VRAM_ENABLE_ORCHESTRATOR:
                try:
                    orchestrator = get_orchestrator()
                    await orchestrator.mark_model_unloaded(model_id, crashed=True)
                    logger.error(f"❌ Generation failed for {model_id}, cleaned up registry: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"❌ Registry cleanup failed after generation error: {cleanup_error}")
            raise Exception(f"LLM generation failed: {str(e)}")

    async def generate_with_route(
        self,
        context: List[Dict],
        route_config: Dict,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None,
        user_thinking_enabled: Optional[bool] = None
    ) -> Dict:
        """
        Generate response based on route configuration with optimized system prompt.

        Args:
            context: Conversation history
            route_config: Dict with 'model', 'mode', and 'route' from router
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)
            user_thinking_enabled: User's thinking mode preference (None=auto, True=force on, False=force off)

        Returns:
            Dict with 'content', 'model', 'references'
        """
        # Extract config
        model = route_config.get('model')
        route = route_config.get('route')  # Route name for prompt selection

        if not model:
            raise Exception(f"No model specified in route config: {route_config}")

        # Build route-specific system prompt
        if route:
            system_prompt = self._build_route_system_prompt(route_config, user_base_prompt)
        else:
            # Fallback to general prompt if route missing
            system_prompt = self._build_system_prompt(user_base_prompt)

        # Check if model supports thinking mode and apply user preference
        model_caps = get_model_capabilities(model)

        # Determine if thinking should be enabled
        if user_thinking_enabled is False:
            # User explicitly disabled thinking
            enable_thinking = False
            additional_args = None
        elif user_thinking_enabled is True:
            # User explicitly enabled thinking (only if model supports it)
            enable_thinking = model_caps and model_caps.supports_thinking
            if enable_thinking:
                # Apply appropriate format based on model capabilities
                if model_caps.thinking_format == "level":
                    additional_args = {'think': model_caps.default_thinking_level}  # 'high', 'medium', or 'low'
                    logger.info(f"🧠 Enabling thinking mode (think={model_caps.default_thinking_level}) for {model} on {route} route (user preference: {user_thinking_enabled})")
                else:
                    additional_args = {'think': True}
                    logger.info(f"🧠 Enabling thinking mode for {model} on {route} route (user preference: {user_thinking_enabled})")
            else:
                additional_args = None
                if model_caps:
                    logger.warning(f"⚠️  User requested thinking mode but {model} doesn't support it")
        else:
            # Auto mode: enable for RESEARCH route only if model supports it
            enable_thinking = (
                model_caps and
                model_caps.supports_thinking and
                route == "RESEARCH"  # Only RESEARCH, not REASONING
            )

            # Build additional args with flexible format
            if enable_thinking:
                # Determine thinking parameter based on model capabilities
                if model_caps.thinking_format == "level":
                    # gpt-oss:20b uses think with string level ('high', 'medium', 'low')
                    thinking_level = model_caps.default_thinking_level  # "high"
                    additional_args = {'think': thinking_level}
                    logger.info(f"🧠 Enabling thinking mode (think={thinking_level}) for {model} on {route} route")
                else:
                    # Other models use boolean 'think' parameter
                    additional_args = {'think': True}
                    logger.info(f"🧠 Enabling thinking mode for {model} on {route} route")
            else:
                additional_args = None

        # Create model instance with route-specific prompt and flexible thinking parameters
        # ModelFactory handles backend selection (Ollama, TensorRT-LLM, vLLM)
        user_selected = route_config.get('user_selected_model', False)
        model_instance = await ModelFactory.create_model(
            model_name=model,
            temperature=temperature,
            additional_args=additional_args,
            user_selected=user_selected
        )

        # Format context as prompt
        prompt = self._format_context(context, system_prompt)

        # Create reference capturing hook
        ref_hook = ReferenceCapturingHook()

        # Provide tools with profile-aware fetch limiting
        from app.config import get_active_profile
        profile = get_active_profile()
        fetch_limit = profile.fetch_limits.get(route, profile.fetch_limits.get('default', 5))

        from app.tools import web_search, fetch_webpage, list_attachments, file_read_wrapped

        # Conditionally apply fetch limiter (-1 = no limit)
        if fetch_limit > 0:
            limited_fetch = create_async_limited_fetch_wrapper(fetch_webpage, max_calls=fetch_limit)
            agent_tools = [web_search, limited_fetch, list_attachments, file_read_wrapped]
        else:
            # No limit, use original fetch_webpage
            agent_tools = [web_search, fetch_webpage, list_attachments, file_read_wrapped]

        # Check if model supports tools
        supports_tools = model_caps and model_caps.supports_tools
        if supports_tools:
            if fetch_limit > 0:
                logger.info(f"🔧 Providing tools to {model} (max {fetch_limit} fetches enforced, profile={profile.profile_name}, route={route})")
            else:
                logger.info(f"🔧 Providing tools to {model} (NO FETCH LIMIT, profile={profile.profile_name}, route={route})")
        else:
            logger.info(f"⚠️  Model {model} doesn't support tools - running without tools")
            agent_tools = []

        # Run agent with route-optimized prompt
        loop = asyncio.get_event_loop()
        try:
            agent = Agent(
                model=model_instance,
                tools=agent_tools if supports_tools else [],
                system_prompt=system_prompt,
                hooks=[ref_hook] if supports_tools else []
            )

            # Capture current request context for executor thread
            from app.dependencies import get_current_request, set_current_request
            current_request_snapshot = get_current_request().copy()

            def run_agent_with_context():
                """Run agent in executor thread with proper context propagation."""
                # Set context in executor thread (ContextVars don't auto-propagate to threads)
                set_current_request(current_request_snapshot)
                return agent(prompt)

            response = await loop.run_in_executor(None, run_agent_with_context)

            # Extract and filter response content (same as streaming)
            response_content = str(response)

            # Filter thinking tags (same logic as streaming - line 595)
            response_content = re.sub(r'<think>.*?</think>', ' ', response_content, flags=re.DOTALL)

            # Clean up spacing (same as streaming - lines 599-605)
            response_content = re.sub(r'([a-z])(\[)', r'\1 \2', response_content)
            response_content = re.sub(r'([a-z])(`)', r'\1 \2', response_content)
            response_content = re.sub(r' +', ' ', response_content)

            return {
                'content': response_content.strip(),
                'model': model,
                'references': ref_hook.references
            }
        except Exception as e:
            # Clean up registry on generation failure (prevents waiting for reconciliation)
            if settings.VRAM_ENABLE_ORCHESTRATOR:
                try:
                    orchestrator = get_orchestrator()
                    await orchestrator.mark_model_unloaded(model, crashed=True)
                    logger.error(f"❌ Generation failed for {model}, cleaned up registry: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"❌ Registry cleanup failed after generation error: {cleanup_error}")
            raise Exception(f"LLM generation failed: {str(e)}")

    async def generate_stream(
        self,
        context: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response (basic version without routing).

        For route-aware streaming, use generate_stream_with_route().
        """
        if not model:
            model = settings.OLLAMA_DEFAULT_MODEL

        system_prompt = self._build_system_prompt(user_base_prompt)
        prompt = self._format_context(context, system_prompt)

        model_instance = await ModelFactory.create_model(
            model_name=model,
            temperature=temperature
        )

        try:
            agent = Agent(
                model=model_instance,
                system_prompt=system_prompt
            )

            # Use stream_async for streaming
            async for chunk in agent.stream_async(prompt):
                yield str(chunk)

        except Exception as e:
            # Clean up registry on streaming generation failure (prevents waiting for reconciliation)
            if settings.VRAM_ENABLE_ORCHESTRATOR:
                try:
                    orchestrator = get_orchestrator()
                    await orchestrator.mark_model_unloaded(model, crashed=True)
                    logger.error(f"❌ Basic streaming generation failed for {model}, cleaned up registry: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"❌ Registry cleanup failed after basic streaming error: {cleanup_error}")
            raise Exception(f"LLM streaming generation failed: {str(e)}")

    async def generate_stream_with_route(
        self,
        context: List[Dict],
        route_config: Dict,
        temperature: float = 0.7,
        user_base_prompt: Optional[str] = None,
        user_thinking_enabled: Optional[bool] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response based on route configuration.

        Args:
            context: Conversation history
            route_config: Dict with 'model', 'mode', and 'route' from router
            temperature: Temperature for generation
            user_base_prompt: User's custom base prompt (optional)
            user_thinking_enabled: User's thinking mode preference (None=auto, True=force on, False=force off)

        Yields:
            Chunks of generated text
        """
        # Extract config
        model = route_config.get('model')
        route = route_config.get('route')

        if not model:
            raise Exception(f"No model specified in route config: {route_config}")

        # Build route-specific system prompt
        if route:
            system_prompt = self._build_route_system_prompt(route_config, user_base_prompt)
        else:
            system_prompt = self._build_system_prompt(user_base_prompt)

        # Check if model supports thinking mode and apply user preference
        model_caps = get_model_capabilities(model)

        # Determine if thinking should be enabled (same logic as generate_with_route)
        if user_thinking_enabled is False:
            # User explicitly disabled thinking
            enable_thinking = False
            additional_args = None
        elif user_thinking_enabled is True:
            # User explicitly enabled thinking (only if model supports it)
            enable_thinking = model_caps and model_caps.supports_thinking
            if enable_thinking:
                # Apply appropriate format based on model capabilities
                if model_caps.thinking_format == "level":
                    additional_args = {'think': model_caps.default_thinking_level}  # 'high', 'medium', or 'low'
                    logger.info(f"🧠 Enabling thinking mode (think={model_caps.default_thinking_level}) for {model} on {route} route (streaming, user preference: {user_thinking_enabled})")
                else:
                    additional_args = {'think': True}
                    logger.info(f"🧠 Enabling thinking mode for {model} on {route} route (streaming, user preference: {user_thinking_enabled})")
            else:
                additional_args = None
                if model_caps:
                    logger.warning(f"⚠️  User requested thinking mode but {model} doesn't support it")
        else:
            # Auto mode: enable for RESEARCH route only if model supports it
            enable_thinking = (
                model_caps and
                model_caps.supports_thinking and
                route == "RESEARCH"  # Only RESEARCH, not REASONING
            )

            # Build additional args with flexible format
            if enable_thinking:
                # Determine thinking parameter based on model capabilities
                if model_caps.thinking_format == "level":
                    # gpt-oss:20b uses think with string level ('high', 'medium', 'low')
                    thinking_level = model_caps.default_thinking_level  # "high"
                    additional_args = {'think': thinking_level}
                    logger.info(f"🧠 Enabling thinking mode (think={thinking_level}) for {model} on {route} route (streaming)")
                else:
                    # Other models use boolean 'think' parameter
                    additional_args = {'think': True}
                    logger.info(f"🧠 Enabling thinking mode for {model} on {route} route (streaming)")
            else:
                additional_args = None

        # Create model instance with flexible thinking parameters
        # ModelFactory handles backend selection (Ollama, TensorRT-LLM, vLLM)
        user_selected = route_config.get('user_selected_model', False)
        model_instance = await ModelFactory.create_model(
            model_name=model,
            temperature=temperature,
            additional_args=additional_args,
            user_selected=user_selected
        )

        # Format context as prompt
        prompt = self._format_context(context, system_prompt)

        # Create reference capturing hook and store as instance variable
        # so orchestrator can access references after streaming completes
        self.last_ref_hook = ReferenceCapturingHook()
        ref_hook = self.last_ref_hook

        # Provide tools with profile-aware fetch limiting
        from app.config import get_active_profile
        profile = get_active_profile()
        fetch_limit = profile.fetch_limits.get(route, profile.fetch_limits.get('default', 5))

        from app.tools import web_search, fetch_webpage, list_attachments, file_read_wrapped

        # Conditionally apply fetch limiter (-1 = no limit)
        if fetch_limit > 0:
            limited_fetch = create_async_limited_fetch_wrapper(fetch_webpage, max_calls=fetch_limit)
            agent_tools = [web_search, limited_fetch, list_attachments, file_read_wrapped]
        else:
            # No limit, use original fetch_webpage
            agent_tools = [web_search, fetch_webpage, list_attachments, file_read_wrapped]

        # Check if model supports tools
        supports_tools = model_caps and model_caps.supports_tools
        if supports_tools:
            if fetch_limit > 0:
                logger.info(f"🔧 Providing tools (streaming) to {model} (max {fetch_limit} fetches enforced, profile={profile.profile_name}, route={route})")
            else:
                logger.info(f"🔧 Providing tools (streaming) to {model} (NO FETCH LIMIT, profile={profile.profile_name}, route={route})")
        else:
            logger.info(f"⚠️  Model {model} doesn't support tools - streaming without tools")
            agent_tools = []

        try:
            agent = Agent(
                model=model_instance,
                tools=agent_tools if supports_tools else [],
                system_prompt=system_prompt,
                hooks=[ref_hook] if supports_tools else []
            )

            # Capture current request context
            from app.dependencies import get_current_request, set_current_request
            current_request_snapshot = get_current_request().copy()

            # Set context for async streaming (ContextVars should propagate in async context)
            set_current_request(current_request_snapshot)

            # ============================================================
            # NEW: Create streaming components (SOLID composition)
            # ============================================================
            processor = StreamProcessor()
            stream_filter = StreamFilter(
                enable_think_filter=True,
                enable_spacing_fixer=True
            )
            stream_logger = StreamLogger(debug_enabled=True)

            # Yield status indicator (randomized based on route and thinking mode)
            status_message = _get_status_indicator(route, enable_thinking)
            yield status_message

            # SIMPLIFIED streaming loop using extracted classes
            async for chunk in agent.stream_async(prompt):
                # Extract content using StreamProcessor
                text = processor.extract_content(chunk)
                if text is None:
                    continue  # Skip invalid/event-only chunks

                # Apply filters using StreamFilter
                original = text
                text = stream_filter.apply(text)

                # Log using StreamLogger
                stream_logger.log_chunk(original, text)

                # Yield processed chunk
                yield text

            # Flush any buffered content from stateful filters
            final_chunk = stream_filter.flush()
            if final_chunk:
                logger.debug(f"🔄 Flushing final buffer: {len(final_chunk)} chars")
                yield final_chunk

            # Log final stats and save thinking token count for TPS calculation
            stats = processor.get_stats()
            stream_stats = stream_filter.get_stats()
            stats.update(stream_stats)
            logger.info(f"📊 Streaming complete: {stats}")

            # Store thinking token count for TPS calculation in orchestrator
            think_filter_stats = stream_stats.get('think_filter', {})
            self.last_thinking_tokens = think_filter_stats.get('discarded_size', 0)
            logger.debug(f"💭 Thinking tokens: {self.last_thinking_tokens}")

        except Exception as e:
            # Clean up registry on streaming generation failure (prevents waiting for reconciliation)
            if settings.VRAM_ENABLE_ORCHESTRATOR:
                try:
                    orchestrator = get_orchestrator()

                    # NEW: Detect connection errors for circuit breaker
                    error_msg = str(e).lower()
                    is_connection_error = (
                        "connection" in error_msg or
                        "connect" in error_msg or
                        "refused" in error_msg or
                        "timeout" in error_msg or
                        "unreachable" in error_msg
                    )

                    model_caps = get_model_capabilities(model)
                    is_sglang = model_caps and model_caps.backend.type == "sglang"

                    if is_connection_error and is_sglang:
                        # Record in crash tracker to trigger circuit breaker
                        logger.warning(
                            f"⚠️  SGLang connection error during streaming for {model}, "
                            f"marking as crashed for circuit breaker"
                        )
                        await orchestrator.mark_model_unloaded(
                            model,
                            crashed=True,
                            crash_reason="sglang_connection_error"
                        )
                    else:
                        # Normal crash (not connection error)
                        await orchestrator.mark_model_unloaded(model, crashed=True)

                    logger.error(f"❌ Streaming generation failed for {model}, cleaned up registry: {str(e)}")
                except Exception as cleanup_error:
                    logger.error(f"❌ Registry cleanup failed after streaming error: {cleanup_error}")
            raise Exception(f"LLM streaming generation failed: {str(e)}")

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

    def _get_tool_usage_rules(self) -> str:
        """Common tool usage rules for all prompts."""
        return """TOOL USAGE RULES:

FILE UPLOADS - list_attachments and get_file_content tools:
- Use list_attachments to see what files user uploaded
- Use get_file_content(file_id) to read file contents
- The file content is already extracted (OCR for images, direct read for text/code)"""

    def _get_format_rules(self) -> str:
        """Common formatting rules for all prompts."""
        return """DISCORD FORMATTING RULES - FOLLOW EXACTLY:

ALLOWED FORMATTING (Discord-supported):
✓ **Bold text** using **text**
✓ *Italic text* using *text*
✓ `Inline code` using `text`
✓ ```Code blocks``` using triple backticks
✓ Bullet lists using - or *
✓ Numbered lists using 1., 2., 3.
✓ [Links](URL) using [text](url)

FORBIDDEN FORMATTING (Discord does NOT support):
❌ NO markdown headers (##, ###, ####) - use **bold text** for headings instead
❌ NO tables with pipes (|) - use bullet lists instead
❌ NO horizontal rules (---) - use blank lines instead
❌ NO bracket citations [1], [2], [3] - cite by name inline

Example (comparison - use bold for headings, bullets for data):
**WebGL vs WebGPU comparison:**

- **WebGL**: High-level API, OpenGL ES-based, simpler but limited performance
- **WebGPU**: Low-level API, modern GPU APIs (Vulkan/Metal/D3D12), better performance, steeper learning curve

Example (explanation with formatting):
**WebGPU** is an emerging web standard that provides *high-performance graphics*. It replaces **WebGL** with a modern API based on Vulkan, Metal, and Direct3D 12."""

    def _get_role_layer(self) -> str:
        """LAYER 1: Define agent role and identity."""
        return """You are a helpful Discord assistant. You chat naturally with users, provide information, help with code, and conduct research when needed.

Your primary role is conversational - you are CHATTING with users, not writing files or generating raw output."""

    def _get_file_creation_protocol(self) -> str:
        """LAYER 2: File creation protocol (overrides default formatting)."""
        return """🚨 YOU ARE CHATTING IN DISCORD - NEVER FORMAT AS A FILE 🚨

FORBIDDEN PHRASES (DO NOT USE):
❌ "Here's the markdown content for your file:"
❌ "Markdown File Content:"
❌ "File Content:"
❌ "```markdown" wrapper around response
❌ DO NOT wrap entire response in code blocks

CORRECT APPROACH - Just chat naturally:
✅ "Here's my analysis of why Bitcoin pumped: **Bitcoin Price Analysis** - The price..."
✅ "Here's the implementation: ```python\ndef quicksort()...```"

KEY RULE: You are having a CONVERSATION. Not showing what a file looks like.

WRONG (showing file):
"Here's the markdown content:
```markdown
# Bitcoin Analysis
```"

RIGHT (chatting):
"Here's my Bitcoin analysis: **Bitcoin Analysis** - The pump was driven by..."

The system will extract content automatically. Just respond naturally."""

    def _get_task_layer(self, route: str) -> str:
        """LAYER 3: Task-specific instructions (route logic)."""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")

        if route == "REASONING":
            return f"""Date: {current_date}

TASK: Analytical reasoning, research, comparisons, trade-off analysis.

APPROACH:
1. For current/factual questions: Use web_search → fetch_webpage (2-3 sources max)
2. For conceptual questions: Use knowledge base
3. Synthesize information from multiple perspectives
4. Present evidence-based analysis

ANALYSIS FRAMEWORK:
- Identify key factors and trade-offs
- Compare options objectively
- Provide clear recommendations with reasoning
- Support claims with evidence
- Acknowledge limitations

{self._get_tool_usage_rules()}

SOURCE CITATION (when using web tools):
- Cite sources inline: "According to TechCrunch..."
- NO bracket citations [1] [2] [3]
- List sources at end with clickable links:

Sources:
- [Source Title](full_url)"""

        elif route == "SIMPLE_CODE":
            return f"""Date: {current_date}

TASK: Code generation, debugging, explanations.

APPROACH:
- Write clean, working code with explanations
- Include error handling where appropriate
- Explain key logic and design choices
- Provide usage examples when helpful

{self._get_tool_usage_rules()}"""

        elif route == "RESEARCH":
            return f"""Date: {current_date}

TASK: Deep research requiring 4-5 web sources.

APPROACH:
1. Use web_search to find 4-5 relevant sources
2. Use fetch_webpage to retrieve content (up to 5 fetches)
3. Cross-reference information
4. Synthesize comprehensive report
5. Cite all sources

{self._get_tool_usage_rules()}

SOURCE CITATION:
- Reference sources inline: "According to (Source)..."
- NO bracket citations [1] [2] [3]
- List sources at end with clickable links:

Sources:
- [Source Title](full_url)"""

        elif route == "MATH":
            return f"""Date: {current_date}

TASK: Solve mathematical problems with step-by-step explanations.

APPROACH:
1. Break down the problem into clear steps
2. Show your work and reasoning at each step
3. Provide a clearly marked final answer
4. Use proper mathematical notation with Unicode characters

MATHEMATICAL FORMATTING - CRITICAL FOR DISCORD:
- Superscripts: x², x³, x⁴, x⁵, x⁶, x⁷, x⁸, x⁹, x¹⁰
- Subscripts: x₀, x₁, x₂, a₁, aₙ
- Fractions: Use Unicode symbols (½, ¼, ¾, ⅔, ⅓, ⅕, ⅙, ⅛) when available
- For complex fractions not in Unicode: (numerator)/(denominator)
- Mathematical symbols: ∫ (integral), ∑ (sum), ∂ (partial), √ (root), π, ∞, ±, ≈, ≠, ≤, ≥
- Examples:
  ✓ ∫ x² dx = ⅓x³ + C  or  ∫ x² dx = (1/3)x³ + C
  ✓ d/dx(x³) = 3x²
  ✓ lim[x→0] (sin x)/x = 1
  ✓ ∑ᵢ₌₁ⁿ i² = n(n+1)(2n+1)/6
  ✗ Never use: LaTeX \\frac{{a}}{{b}} or $$math$$ notation (Discord doesn't render)

UNICODE CHARACTER REFERENCE:
Superscripts: ⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁺ ⁻ ⁽ ⁾ ⁿ
Subscripts: ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ ₊ ₋ ₍ ₎
Fractions: ½ ⅓ ⅔ ¼ ¾ ⅕ ⅖ ⅗ ⅘ ⅙ ⅐ ⅛ ⅑ ⅒
Math: ∫ ∑ ∏ ∂ √ ∛ ∜ π ∞ ± ∓ × ÷ ≈ ≠ ≤ ≥ ⊂ ⊃ ∈ ∉ ∀ ∃ ∇ ∆

{self._get_tool_usage_rules()}

WEB SEARCH USAGE:
- DEFAULT: Solve using your mathematical knowledge (you are an expert)
- ONLY use web_search/fetch_webpage if user EXPLICITLY requests:
  * "search for..." / "look up..." / "find information about..."
  * "what is the formula for..." (when asking about a specific named theorem/formula)
- DO NOT search for standard calculus/algebra operations
- Examples where search is NOT needed:
  * "integrate x^2" → solve directly
  * "solve 2x + 5 = 13" → solve directly
  * "find derivative of sin(x)" → solve directly

RESPONSE STRUCTURE - MANDATORY:
Your response MUST follow this exact structure:

[Brief acknowledgment of the problem]

**Step-by-Step Breakdown:**
1. [First step with clear explanation]
2. [Second step with work shown]
3. [Continue for all steps...]

**Final Answer:**
[Clearly formatted final result]

FORMATTING EXAMPLES:

Example 1 (Integration):
Let me solve this integral step by step.

**Step-by-Step Breakdown:**
1. First, I'll integrate each term separately using the power rule
2. For ∫ 4x⁶ dx: Apply ∫ xⁿ dx = xⁿ⁺¹/(n+1)
   → 4x⁷/7 or (4/7)x⁷
3. For ∫ 2x³ dx: Same rule
   → 2x⁴/4 = x⁴/2 or ½x⁴
4. For ∫ 7x dx:
   → 7x²/2
5. For ∫ -4 dx:
   → -4x
6. Add constant of integration C

**Final Answer:**
∫ (4x⁶ + 2x³ + 7x - 4) dx = (4/7)x⁷ + ½x⁴ + (7/2)x² - 4x + C

Example 2 (Equation):
I'll solve this linear equation for x.

**Step-by-Step Breakdown:**
1. Start with: 2x + 5 = 13
2. Subtract 5 from both sides: 2x = 8
3. Divide both sides by 2: x = 4

**Final Answer:**
x = 4

Example 3 (Derivative):
Let me find this derivative using the product rule.

**Step-by-Step Breakdown:**
1. Given: f(x) = sin(x) × cos(x)
2. Product rule: (uv)' = u'v + uv'
3. Let u = sin(x), v = cos(x)
4. Then u' = cos(x), v' = -sin(x)
5. Apply rule: cos(x) × cos(x) + sin(x) × (-sin(x))
6. Simplify: cos²(x) - sin²(x)

**Final Answer:**
d/dx[sin(x) × cos(x)] = cos²(x) - sin²(x)"""

        else:  # SELF_HANDLE
            return f"""Date: {current_date}

TASK: General assistance - code, questions, research, conversation.

{self._get_tool_usage_rules()}"""

    def _get_format_layer(self, context: str = 'standard') -> str:
        """LAYER 4: Format rules (context-aware, no conflicting examples)."""
        base_format = """FORMAT RULES:
- Use **bold text** for headings
- Use bullet lists with - for comparisons/data
- Use ```language for code blocks
- NO tables with pipes (|)
- NO ##headers (Discord doesn't render them well)
- NO bracket citations [1] [2] [3] (use inline names)"""

        if context == 'file_creation':
            # When file creation detected, emphasize conversational start
            return f"""{base_format}

CRITICAL FOR FILE REQUESTS:
- ALWAYS start with conversational intro ("Here's...", "Here's my analysis...")
- NEVER start directly with content headings or code
- The system extracts file content from your conversational response"""

        else:
            # Standard context - include SAFE example (starts with intro)
            return f"""{base_format}

Example (conversational start):
Here are the key points:

**Key points:**
- **Point 1**: Description
- **Point 2**: Description"""

    def _get_critical_output_format(self, route: str = "general") -> str:
        """Get critical output format rules for specific route type."""
        if route == "code":
            return """CRITICAL OUTPUT FORMAT:
- Use **bold text** for section headings (NOT ##headers)
- Use code blocks with ```language for all code
- Use `inline code` for function names, variables, keywords
- NO tables with pipes (|)
- NO ##headers, ###headers, etc.

If you use ##headers or tables, the response will be rejected."""

        elif route in ["reasoning", "research"]:
            return """CRITICAL OUTPUT FORMAT:
- Use **bold text** for headings (NOT ##headers)
- Use bullet lists with - for data/comparisons
- Use *italic* for emphasis when helpful
- NO tables with pipes (|)
- NO ##headers, ###headers
- NO bracket citations [1], [2], [3]

Example of correct formatting:
**Key findings:**
- **Item 1**: Description with details
- **Item 2**: Description with details
- **Item 3**: Description with details

If you use ##headers, tables, or bracket citations, the response will be rejected."""

        else:  # general
            return """CRITICAL OUTPUT FORMAT:
- Use **bold text** for headings (NOT ##headers)
- Use bullet lists with - for comparisons/lists
- Use *italic* for emphasis when helpful
- NO tables with pipes (|)
- NO bracket citations [1], [2], [3]

If you use ##headers, tables, or bracket citations, the response will be rejected."""

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
        route_config: Dict,
        user_base_prompt: Optional[str] = None
    ) -> str:
        """
        Build system prompt using modular PromptComposer (REFACTORED).

        This method now delegates to PromptComposer which loads prompts
        from JSON configs and composes them using the 5-layer architecture:
        1. ROLE & IDENTITY - Who you are
        2. CRITICAL PROTOCOLS - Special cases (file creation, thinking mode)
        3. TASK DEFINITION - What to do (route-specific)
        4. FORMAT RULES - How to format (context-aware)
        5. USER CUSTOMIZATION - User preferences

        Args:
            route_config: Dict with 'route', 'model', 'postprocessing' from router
            user_base_prompt: User's custom base prompt (optional)

        Returns:
            Composed system prompt with proper layer ordering
        """
        route = route_config.get('route')
        model = route_config.get('model')
        postprocessing = route_config.get('postprocessing', [])

        # Determine format context based on postprocessing
        format_context = 'file_creation' if 'OUTPUT_ARTIFACT' in postprocessing else 'standard'

        # Get context window from model capabilities (for performance variants)
        context_window = None
        if model:
            model_caps = get_model_capabilities(model)
            if model_caps and hasattr(model_caps, 'context_window'):
                context_window = model_caps.context_window

        # Get source from route_config for format-aware prompting (discord vs webui)
        source = route_config.get('source', 'discord')

        # Use PromptComposer for modular prompt composition
        return self.prompt_composer.compose_route_prompt(
            route=route,
            postprocessing=postprocessing,
            format_context=format_context,
            user_base_prompt=user_base_prompt,
            context_window=context_window,
            source=source
        )

    def _build_self_handle_prompt(self, current_date: str) -> str:
        """System prompt for SELF_HANDLE route (gpt-oss:20b)."""
        return f"""Date: {current_date}

You're a helpful Discord assistant for quick questions and general conversation.

TASK: Answer questions clearly and concisely. For factual questions, provide accurate information. For explanations, keep them accessible and practical.

{self._get_tool_usage_rules()}

{self._get_format_rules()}

RESPONSE STYLE:
- Be conversational but informative
- Keep responses under 500 words
- Use simple language, avoid jargon unless necessary
- Don't dive into excessive technical detail

{self._get_critical_output_format("general")}"""

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

{self._get_tool_usage_rules()}

{self._get_format_rules()}

RESPONSE FORMAT:
- Brief explanation (1-2 sentences)
- Code block with full implementation
- Usage example if helpful
- Keep total response under 1000 words

{self._get_critical_output_format("code")}"""

    def _build_reasoning_prompt(self, current_date: str) -> str:
        """System prompt for REASONING route (magistral:24b)."""
        return f"""Date: {current_date}

You're an analytical assistant specialized in research, comparisons, and deep analysis. You have web search tools available.

TASK: Research questions, compare options, analyze trade-offs, investigate complex topics.

RESEARCH PROCESS:
1. For current/factual questions: Use web_search → fetch_webpage (LIMIT: 2-3 sources max)
2. For conceptual questions: Use your knowledge base
3. Synthesize information from multiple perspectives
4. Present structured, evidence-based analysis

IMPORTANT: Only fetch 2-3 webpages max. Use web_search first to find relevant sources, then use fetch_webpage on the most relevant 2-3 URLs.

ANALYSIS FRAMEWORK:
- Identify key factors and trade-offs
- Compare options objectively (pros/cons)
- Provide clear recommendations with reasoning
- Support claims with evidence (cite sources when using web tools)
- Acknowledge limitations or uncertainties

{self._get_tool_usage_rules()}

{self._get_format_rules()}

RESPONSE STRUCTURE:
- Brief summary/recommendation upfront
- Detailed analysis with key factors
- Trade-offs and considerations
- Clear conclusion
- Keep under 1500 words

SOURCE CITATION (when using web tools):
- Cite sources by name inline: "According to TechCrunch..." or "A report from Bloomberg states..."
- DO NOT use bracket citations like [1], [2], [3]
- REQUIRED: List sources at end with clickable links in this format:

Sources:
- [Source Title](full_url)
- [Another Source](full_url)

Example:
Sources:
- [Bitcoin price today is up over $92,000](https://www.economictimes.com/news/bitcoin-price-today)
- [Crypto Prices Today: Bitcoin at $92,454.54](https://analyticsinsight.net/crypto-prices-today)

{self._get_critical_output_format("reasoning")}"""

    def _build_research_prompt(self, current_date: str) -> str:
        """System prompt for RESEARCH route (magistral:24b) - for extensive web research."""
        return f"""Date: {current_date}

You're a research assistant specialized in deep investigation and comprehensive information gathering. You have web search tools available.

TASK: Conduct thorough research on complex topics requiring multiple sources and extensive web searches.

RESEARCH PROCESS:
1. Use web_search to find 4-5 relevant sources
2. Use fetch_webpage to retrieve detailed content from each source (LIMIT: up to 5 fetches)
3. Cross-reference information across sources
4. Synthesize findings into a comprehensive report
5. Cite all sources used

IMPORTANT: You can fetch up to 5 webpages. Use web_search first to identify the best sources, then use fetch_webpage on the top 4-5 URLs.

RESEARCH APPROACH:
- Cast a wide net: Search from multiple angles
- Verify information across sources
- Look for recent developments and current state
- Include historical context when relevant
- Note conflicting information or debates
- Highlight gaps in available information

{self._get_tool_usage_rules()}

{self._get_format_rules()}

RESPONSE STRUCTURE:
- Executive summary (2-3 sentences)
- Main findings organized by theme/topic
- Supporting evidence with source citations
- Key takeaways or implications
- Can be longer (2000-2500 words) given research depth

SOURCE CITATION:
- Reference sources inline: "According to (Source)..." or just cite by name
- DO NOT use bracket citations like [1], [2], [3] - use inline names instead
- REQUIRED: List sources at end with clickable links in this format:

Sources:
- [Source Title](full_url)
- [Another Source](full_url)

Example:
Sources:
- [Bitcoin price today is up over $92,000](https://www.economictimes.com/news/bitcoin-price-today)
- [Crypto Prices Today: Bitcoin at $92,454.54](https://analyticsinsight.net/crypto-prices-today)

{self._get_critical_output_format("research")}"""

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
