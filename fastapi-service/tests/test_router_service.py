"""Tests for RouterService."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.router_service import RouterService, RouteType


class TestRouterClassification:
    """Test router classification accuracy."""

    @pytest.mark.asyncio
    async def test_classify_self_handle_simple_question(self):
        """Test SELF_HANDLE classification for simple questions."""
        router = RouterService()

        # Mock the Strands Agent response
        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SELF_HANDLE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SELF_HANDLE")

                route = await router.classify_request("What is Python?")

                assert route == RouteType.SELF_HANDLE

    @pytest.mark.asyncio
    async def test_classify_self_handle_explanation(self):
        """Test SELF_HANDLE classification for explanations."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SELF_HANDLE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SELF_HANDLE")

                route = await router.classify_request("Explain HTTP")

                assert route == RouteType.SELF_HANDLE

    @pytest.mark.asyncio
    async def test_classify_simple_code_basic_function(self):
        """Test SIMPLE_CODE classification for basic coding tasks."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SIMPLE_CODE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SIMPLE_CODE")

                route = await router.classify_request("Write a function to reverse a string")

                assert route == RouteType.SIMPLE_CODE

    @pytest.mark.asyncio
    async def test_classify_simple_code_complex_task(self):
        """Test SIMPLE_CODE classification for complex coding tasks."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SIMPLE_CODE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SIMPLE_CODE")

                route = await router.classify_request("Design a distributed caching system")

                assert route == RouteType.SIMPLE_CODE

    @pytest.mark.asyncio
    async def test_classify_simple_code_bug_fix(self):
        """Test SIMPLE_CODE classification for bug fixes."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SIMPLE_CODE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SIMPLE_CODE")

                route = await router.classify_request("Fix this syntax error: print('hello'")

                assert route == RouteType.SIMPLE_CODE

    @pytest.mark.asyncio
    async def test_classify_reasoning_comparison(self):
        """Test REASONING classification for comparisons."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "REASONING"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="REASONING")

                route = await router.classify_request("Compare React vs Vue")

                assert route == RouteType.REASONING

    @pytest.mark.asyncio
    async def test_classify_reasoning_analysis(self):
        """Test REASONING classification for analysis."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "REASONING"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="REASONING")

                route = await router.classify_request("Analyze microservices trade-offs")

                assert route == RouteType.REASONING

    @pytest.mark.asyncio
    async def test_classify_reasoning_research(self):
        """Test REASONING classification for research questions."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "REASONING"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="REASONING")

                route = await router.classify_request("Research authentication best practices")

                assert route == RouteType.REASONING


class TestRouterFallback:
    """Test router fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_invalid_route_name(self):
        """Test fallback when router returns invalid route name."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "INVALID_ROUTE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="INVALID_ROUTE")

                route = await router.classify_request("Some ambiguous question")

                # Should default to REASONING
                assert route == RouteType.REASONING

    @pytest.mark.asyncio
    async def test_fallback_classification_exception(self):
        """Test fallback when classification raises exception."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent_class.side_effect = Exception("Model unavailable")

            route = await router.classify_request("Some question")

            # Should default to REASONING
            assert route == RouteType.REASONING

    @pytest.mark.asyncio
    async def test_fallback_partial_match(self):
        """Test fallback when route name is embedded in response."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "I think this should be SIMPLE_CODE because..."
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="I think this should be SIMPLE_CODE because...")

                route = await router.classify_request("Write a function")

                # Should extract SIMPLE_CODE from response
                assert route == RouteType.SIMPLE_CODE


class TestRouterConfiguration:
    """Test router model configuration."""

    def test_get_model_for_self_handle(self):
        """Test model config for SELF_HANDLE route."""
        router = RouterService()

        config = router.get_model_for_route(RouteType.SELF_HANDLE)

        assert config['model'] == 'gpt-oss:20b'
        assert config['mode'] == 'single'
        assert config['route_type'] == 'SELF_HANDLE'

    def test_get_model_for_simple_code(self):
        """Test model config for SIMPLE_CODE route."""
        router = RouterService()

        config = router.get_model_for_route(RouteType.SIMPLE_CODE)

        assert config['model'] == 'qwen2.5-coder:7b'
        assert config['mode'] == 'single'
        assert config['route_type'] == 'SIMPLE_CODE'

    def test_get_model_for_reasoning(self):
        """Test model config for REASONING route."""
        router = RouterService()

        config = router.get_model_for_route(RouteType.REASONING)

        assert config['model'] == 'gpt-oss:20b'
        assert config['mode'] == 'single'
        assert config['route_type'] == 'REASONING'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_ambiguous_explanation_vs_code(self):
        """Test ambiguous query between explanation and code."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            # Could be either SELF_HANDLE or SIMPLE_CODE
            mock_agent.return_value = "SELF_HANDLE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SELF_HANDLE")

                route = await router.classify_request("Explain how to implement authentication")

                # Either SELF_HANDLE or SIMPLE_CODE is acceptable
                assert route in [RouteType.SELF_HANDLE, RouteType.SIMPLE_CODE]

    @pytest.mark.asyncio
    async def test_decision_question_routes_to_reasoning(self):
        """Test 'should I' questions route to REASONING."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "REASONING"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="REASONING")

                route = await router.classify_request("Should I use REST or GraphQL?")

                assert route == RouteType.REASONING

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Test router handles empty messages."""
        router = RouterService()

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SELF_HANDLE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SELF_HANDLE")

                route = await router.classify_request("")

                # Should handle gracefully, default to any route
                assert route in [RouteType.SELF_HANDLE, RouteType.SIMPLE_CODE, RouteType.REASONING]

    @pytest.mark.asyncio
    async def test_very_long_message(self):
        """Test router handles very long messages."""
        router = RouterService()

        long_message = "Write a function " * 1000  # Very long message

        with patch('app.services.router_service.Agent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.return_value = "SIMPLE_CODE"
            mock_agent_class.return_value = mock_agent

            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value="SIMPLE_CODE")

                route = await router.classify_request(long_message)

                assert route == RouteType.SIMPLE_CODE


class TestClassificationPrompt:
    """Test classification prompt building."""

    def test_classification_prompt_contains_routes(self):
        """Test classification prompt includes all routes."""
        router = RouterService()

        prompt = router._build_classification_prompt()

        assert "SELF_HANDLE" in prompt
        assert "SIMPLE_CODE" in prompt
        assert "REASONING" in prompt

    def test_classification_prompt_has_examples(self):
        """Test classification prompt includes examples."""
        router = RouterService()

        prompt = router._build_classification_prompt()

        # Should have examples for each route
        assert "Examples:" in prompt or "Example:" in prompt

    def test_classification_prompt_single_output(self):
        """Test classification prompt requests single route name."""
        router = RouterService()

        prompt = router._build_classification_prompt()

        assert "ONLY" in prompt or "only" in prompt
        assert "route name" in prompt.lower()
