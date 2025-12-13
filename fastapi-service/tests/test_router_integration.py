"""Integration tests for router service with orchestrator and LLM."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.orchestrator import Orchestrator
from app.services.router_service import RouterService, RouteType
from app.implementations.strands_llm import StrandsLLM


class TestRouterIntegration:
    """Test end-to-end routing integration."""

    @pytest.mark.asyncio
    async def test_self_handle_route_flow(self):
        """Test full flow for SELF_HANDLE route."""
        # Setup mocks
        mock_storage = AsyncMock()
        mock_llm = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_token_tracker = AsyncMock()
        mock_summarization = AsyncMock()
        mock_router = MagicMock()  # RouterService has sync methods

        # Configure mocks
        mock_storage.get_user.return_value = {
            'user_id': 'user_123',
            'tokens_remaining': 10000,
            'auto_summarize_threshold': 5000,
            'temperature': 0.7,
            'preferred_model': 'gpt-oss:20b'
        }
        mock_context_manager.get_thread_context.return_value = []
        mock_token_tracker.has_budget.return_value = True
        mock_token_tracker.count_tokens.return_value = 50

        # Mock router classification (classify_request is async, but get_model_for_route is sync)
        mock_router.classify_request = AsyncMock(return_value=RouteType.SELF_HANDLE)
        mock_router.get_model_for_route = MagicMock(return_value={
            'model': 'gpt-oss:20b',
            'mode': 'single',
            'route_type': 'SELF_HANDLE'
        })

        # Mock LLM response
        mock_llm.generate_with_route.return_value = {
            'content': 'HTTP is a protocol for transferring data on the web.',
            'model': 'gpt-oss:20b',
            'references': []
        }

        # Create orchestrator
        orchestrator = Orchestrator(
            storage=mock_storage,
            llm=mock_llm,
            context_manager=mock_context_manager,
            token_tracker=mock_token_tracker,
            summarization_service=mock_summarization,
            router_service=mock_router
        )

        # Process request
        request = {
            'request_id': 'req_123',
            'user_id': 'user_123',
            'thread_id': 'thread_456',
            'message_id': 'msg_789',
            'message': 'What is HTTP?',
            'estimated_tokens': 10
        }

        result = await orchestrator.process_request(request)

        # Verify router was called
        mock_router.classify_request.assert_called_once_with('What is HTTP?')
        mock_router.get_model_for_route.assert_called_once_with(RouteType.SELF_HANDLE)

        # Verify LLM was called with route config
        mock_llm.generate_with_route.assert_called_once()
        call_args = mock_llm.generate_with_route.call_args
        assert call_args.kwargs['route_config']['route_type'] == 'SELF_HANDLE'
        assert call_args.kwargs['route_config']['model'] == 'gpt-oss:20b'

        # Verify response
        assert result['response'] == 'HTTP is a protocol for transferring data on the web.'
        assert result['model'] == 'gpt-oss:20b'

    @pytest.mark.asyncio
    async def test_simple_code_route_flow(self):
        """Test full flow for SIMPLE_CODE route."""
        mock_storage = AsyncMock()
        mock_llm = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_token_tracker = AsyncMock()
        mock_summarization = AsyncMock()
        mock_router = MagicMock()  # RouterService has sync methods

        mock_storage.get_user.return_value = {
            'user_id': 'user_123',
            'tokens_remaining': 10000,
            'auto_summarize_threshold': 5000,
            'temperature': 0.7,
            'preferred_model': 'qwen2.5-coder:7b'
        }
        mock_context_manager.get_thread_context.return_value = []
        mock_token_tracker.has_budget.return_value = True
        mock_token_tracker.count_tokens.return_value = 100

        # Mock router classification to SIMPLE_CODE
        mock_router.classify_request = AsyncMock(return_value=RouteType.SIMPLE_CODE)
        mock_router.get_model_for_route = MagicMock(return_value={
            'model': 'qwen2.5-coder:7b',
            'mode': 'single',
            'route_type': 'SIMPLE_CODE'
        })

        # Mock LLM response with code
        mock_llm.generate_with_route.return_value = {
            'content': 'def reverse_string(s: str) -> str:\n    return s[::-1]',
            'model': 'qwen2.5-coder:7b',
            'references': []
        }

        orchestrator = Orchestrator(
            storage=mock_storage,
            llm=mock_llm,
            context_manager=mock_context_manager,
            token_tracker=mock_token_tracker,
            summarization_service=mock_summarization,
            router_service=mock_router
        )

        request = {
            'request_id': 'req_123',
            'user_id': 'user_123',
            'thread_id': 'thread_456',
            'message_id': 'msg_789',
            'message': 'Write a function to reverse a string',
            'estimated_tokens': 20
        }

        result = await orchestrator.process_request(request)

        # Verify routing to SIMPLE_CODE
        mock_router.classify_request.assert_called_once_with('Write a function to reverse a string')
        assert mock_router.get_model_for_route.call_args[0][0] == RouteType.SIMPLE_CODE

        # Verify correct model used
        call_args = mock_llm.generate_with_route.call_args
        assert call_args.kwargs['route_config']['model'] == 'qwen2.5-coder:7b'
        assert call_args.kwargs['route_config']['route_type'] == 'SIMPLE_CODE'

        # Verify code response
        assert 'def reverse_string' in result['response']
        assert result['model'] == 'qwen2.5-coder:7b'

    @pytest.mark.asyncio
    async def test_reasoning_route_flow(self):
        """Test full flow for REASONING route."""
        mock_storage = AsyncMock()
        mock_llm = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_token_tracker = AsyncMock()
        mock_summarization = AsyncMock()
        mock_router = MagicMock()  # RouterService has sync methods

        mock_storage.get_user.return_value = {
            'user_id': 'user_123',
            'tokens_remaining': 10000,
            'auto_summarize_threshold': 5000,
            'temperature': 0.7,
            'preferred_model': 'deepseek-r1:8b'
        }
        mock_context_manager.get_thread_context.return_value = []
        mock_token_tracker.has_budget.return_value = True
        mock_token_tracker.count_tokens.return_value = 200

        # Mock router classification to REASONING
        mock_router.classify_request = AsyncMock(return_value=RouteType.REASONING)
        mock_router.get_model_for_route = MagicMock(return_value={
            'model': 'deepseek-r1:8b',
            'mode': 'single',
            'route_type': 'REASONING'
        })

        # Mock LLM response with analysis
        mock_llm.generate_with_route.return_value = {
            'content': 'SQL vs NoSQL comparison: SQL provides ACID guarantees...',
            'model': 'deepseek-r1:8b',
            'references': [
                {'url': 'https://example.com/sql-nosql', 'title': 'Database Comparison Guide'}
            ]
        }

        orchestrator = Orchestrator(
            storage=mock_storage,
            llm=mock_llm,
            context_manager=mock_context_manager,
            token_tracker=mock_token_tracker,
            summarization_service=mock_summarization,
            router_service=mock_router
        )

        request = {
            'request_id': 'req_123',
            'user_id': 'user_123',
            'thread_id': 'thread_456',
            'message_id': 'msg_789',
            'message': 'Compare SQL vs NoSQL databases',
            'estimated_tokens': 25
        }

        result = await orchestrator.process_request(request)

        # Verify routing to REASONING
        mock_router.classify_request.assert_called_once_with('Compare SQL vs NoSQL databases')
        assert mock_router.get_model_for_route.call_args[0][0] == RouteType.REASONING

        # Verify correct model used
        call_args = mock_llm.generate_with_route.call_args
        assert call_args.kwargs['route_config']['model'] == 'deepseek-r1:8b'
        assert call_args.kwargs['route_config']['route_type'] == 'REASONING'

        # Verify references appended
        assert 'Database Comparison Guide' in result['response']
        assert result['model'] == 'deepseek-r1:8b'

    @pytest.mark.asyncio
    async def test_router_fallback_in_orchestrator(self):
        """Test orchestrator handles router fallback."""
        mock_storage = AsyncMock()
        mock_llm = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_token_tracker = AsyncMock()
        mock_summarization = AsyncMock()
        mock_router = MagicMock()  # RouterService has sync methods

        mock_storage.get_user.return_value = {
            'user_id': 'user_123',
            'tokens_remaining': 10000,
            'auto_summarize_threshold': 5000,
            'temperature': 0.7,
            'preferred_model': 'gpt-oss:20b'
        }
        mock_context_manager.get_thread_context.return_value = []
        mock_token_tracker.has_budget.return_value = True
        mock_token_tracker.count_tokens.return_value = 50

        # Mock router to return fallback (REASONING)
        mock_router.classify_request = AsyncMock(return_value=RouteType.REASONING)
        mock_router.get_model_for_route = MagicMock(return_value={
            'model': 'deepseek-r1:8b',
            'mode': 'single',
            'route_type': 'REASONING'
        })

        mock_llm.generate_with_route.return_value = {
            'content': 'Fallback response',
            'model': 'deepseek-r1:8b',
            'references': []
        }

        orchestrator = Orchestrator(
            storage=mock_storage,
            llm=mock_llm,
            context_manager=mock_context_manager,
            token_tracker=mock_token_tracker,
            summarization_service=mock_summarization,
            router_service=mock_router
        )

        request = {
            'request_id': 'req_123',
            'user_id': 'user_123',
            'thread_id': 'thread_456',
            'message_id': 'msg_789',
            'message': 'Some ambiguous question',
            'estimated_tokens': 15
        }

        result = await orchestrator.process_request(request)

        # Should fall back to REASONING
        assert mock_router.get_model_for_route.call_args[0][0] == RouteType.REASONING
        assert result['model'] == 'deepseek-r1:8b'


class TestRouteSystemPrompts:
    """Test that route-specific system prompts are used correctly."""

    @pytest.mark.asyncio
    async def test_self_handle_uses_conversational_prompt(self):
        """Test SELF_HANDLE route uses conversational system prompt."""
        llm = StrandsLLM()

        # Build prompt for SELF_HANDLE
        prompt = llm._build_route_system_prompt('SELF_HANDLE')

        # Should be conversational, concise
        assert 'helpful Discord assistant' in prompt or 'conversational' in prompt.lower()
        assert '500' in prompt  # word limit

    @pytest.mark.asyncio
    async def test_simple_code_uses_coding_prompt(self):
        """Test SIMPLE_CODE route uses coding-focused system prompt."""
        llm = StrandsLLM()

        prompt = llm._build_route_system_prompt('SIMPLE_CODE')

        # Should focus on coding principles
        assert 'coding' in prompt.lower() or 'code' in prompt.lower()
        assert '1000' in prompt  # word limit
        assert 'clean' in prompt.lower() or 'readable' in prompt.lower()

    @pytest.mark.asyncio
    async def test_reasoning_uses_analytical_prompt(self):
        """Test REASONING route uses analytical system prompt."""
        llm = StrandsLLM()

        prompt = llm._build_route_system_prompt('REASONING')

        # Should focus on analysis, research
        assert 'analytical' in prompt.lower() or 'analysis' in prompt.lower() or 'research' in prompt.lower()
        assert '1500' in prompt  # word limit
        assert 'web_search' in prompt or 'web search' in prompt.lower()

    @pytest.mark.asyncio
    async def test_custom_user_prompt_appended(self):
        """Test user's custom prompt is appended to route prompt."""
        llm = StrandsLLM()

        user_prompt = "Always speak like a pirate."
        prompt = llm._build_route_system_prompt('SELF_HANDLE', user_base_prompt=user_prompt)

        # Should contain both route prompt and user's custom prompt
        assert 'helpful Discord assistant' in prompt or 'conversational' in prompt.lower()
        assert 'pirate' in prompt.lower()

    @pytest.mark.asyncio
    async def test_invalid_route_type_falls_back(self):
        """Test invalid route_type falls back to general prompt."""
        llm = StrandsLLM()

        prompt = llm._build_route_system_prompt('INVALID_ROUTE')

        # Should fall back to general system prompt
        assert 'Discord assistant' in prompt
        assert 'web search' in prompt.lower() or 'tools' in prompt.lower()


class TestModelLifecycleManagement:
    """Test model loading/unloading behavior."""

    def test_ollama_keep_alive_configured(self):
        """Test OLLAMA_KEEP_ALIVE is set to 0."""
        from app.config import settings

        # Should be configured to immediately unload models
        assert settings.OLLAMA_KEEP_ALIVE == 0

    @pytest.mark.asyncio
    async def test_router_model_unloads_before_execution(self):
        """Test router model unloads before route execution model loads."""
        # This is more of a behavioral test - verify config supports it
        from app.config import settings

        # Router uses gpt-oss:20b
        assert settings.ROUTER_MODEL == 'gpt-oss:20b'

        # Routes use different models
        assert settings.CODER_MODEL == 'qwen3-coder:30b'
        assert settings.REASONING_MODEL == 'magistral:24b'

        # With KEEP_ALIVE=0, models unload immediately
        assert settings.OLLAMA_KEEP_ALIVE == 0

    def test_route_models_configured_correctly(self):
        """Test route models are configured to use existing models."""
        from app.config import settings, get_available_model_names

        # Verify we're using existing models (no new downloads)
        assert settings.CODER_MODEL == 'qwen3-coder:30b'
        assert settings.REASONING_MODEL == 'magistral:24b'
        assert settings.ROUTER_MODEL == 'gpt-oss:20b'

        # All should be in available models
        available_names = get_available_model_names()
        assert settings.CODER_MODEL in available_names
        assert settings.REASONING_MODEL in available_names
        assert settings.ROUTER_MODEL in available_names


class TestReferenceCapture:
    """Test reference capture across routes."""

    @pytest.mark.asyncio
    async def test_references_captured_in_reasoning_route(self):
        """Test web references are captured and appended in REASONING route."""
        mock_storage = AsyncMock()
        mock_llm = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_token_tracker = AsyncMock()
        mock_summarization = AsyncMock()
        mock_router = MagicMock()  # RouterService has sync methods

        mock_storage.get_user.return_value = {
            'user_id': 'user_123',
            'tokens_remaining': 10000,
            'auto_summarize_threshold': 5000,
            'temperature': 0.7,
            'preferred_model': 'deepseek-r1:8b'
        }
        mock_context_manager.get_thread_context.return_value = []
        mock_token_tracker.has_budget.return_value = True
        mock_token_tracker.count_tokens.return_value = 150

        mock_router.classify_request = AsyncMock(return_value=RouteType.REASONING)
        mock_router.get_model_for_route = MagicMock(return_value={
            'model': 'deepseek-r1:8b',
            'mode': 'single',
            'route_type': 'REASONING'
        })

        # Mock LLM response with references
        mock_llm.generate_with_route.return_value = {
            'content': 'Analysis of authentication methods...',
            'model': 'deepseek-r1:8b',
            'references': [
                {'url': 'https://example.com/auth', 'title': 'Authentication Guide'},
                {'url': 'https://example.com/oauth', 'title': 'OAuth Best Practices'}
            ]
        }

        orchestrator = Orchestrator(
            storage=mock_storage,
            llm=mock_llm,
            context_manager=mock_context_manager,
            token_tracker=mock_token_tracker,
            summarization_service=mock_summarization,
            router_service=mock_router
        )

        request = {
            'request_id': 'req_123',
            'user_id': 'user_123',
            'thread_id': 'thread_456',
            'message_id': 'msg_789',
            'message': 'Research authentication methods',
            'estimated_tokens': 20
        }

        result = await orchestrator.process_request(request)

        # Verify references are appended to response
        assert '**References:**' in result['response']
        assert '[1]' in result['response']
        assert '[2]' in result['response']
        assert 'Authentication Guide' in result['response']
        assert 'OAuth Best Practices' in result['response']
