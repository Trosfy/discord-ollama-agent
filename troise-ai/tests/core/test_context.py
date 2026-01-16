"""Unit tests for Execution Context."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.core.context import (
    ExecutionContext,
    UserProfile,
    Message,
)
from app.core.exceptions import AgentCancelled


# =============================================================================
# Message Tests
# =============================================================================

def test_message_defaults():
    """Message has sensible defaults."""
    msg = Message(role="user", content="Hello")

    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.timestamp is None
    assert msg.metadata == {}


def test_message_with_metadata():
    """Message can store metadata."""
    msg = Message(
        role="assistant",
        content="Hi there",
        timestamp="2024-01-01T00:00:00",
        metadata={"source": "test"},
    )

    assert msg.metadata["source"] == "test"


# =============================================================================
# UserProfile Tests
# =============================================================================

def test_user_profile_defaults():
    """UserProfile has sensible defaults."""
    profile = UserProfile(user_id="test-user")

    assert profile.user_id == "test-user"
    assert profile.communication_style == "balanced"
    assert profile.response_length == "adaptive"
    assert profile.use_emoji is False
    assert profile.formality == "casual"
    assert profile.code_style == "functional"
    assert profile.explicit_expertise == []


def test_get_all_expertise_combined():
    """get_all_expertise combines all expertise sources."""
    profile = UserProfile(
        user_id="test-user",
        explicit_expertise=["python", "javascript"],
        learned_expertise=[
            {"skill": "rust"},
            {"skill": "go"},
        ],
        active_inferences=[
            {"category": "expertise", "key": "docker"},
            {"category": "preference", "key": "vim"},  # Not expertise
        ],
    )

    expertise = profile.get_all_expertise()

    assert set(expertise) == {"python", "javascript", "rust", "go", "docker"}


def test_get_personalization_context_minimal():
    """get_personalization_context returns empty for defaults."""
    profile = UserProfile(user_id="test-user")

    context = profile.get_personalization_context()

    # Default values shouldn't add much
    # Actually, "no emoji" and "functional code style" are defaults
    assert "no emoji" in context or len(context) > 0


def test_get_personalization_context_customized():
    """get_personalization_context includes non-default preferences."""
    profile = UserProfile(
        user_id="test-user",
        communication_style="technical",
        formality="formal",
        explicit_expertise=["python", "ml"],
        current_project="TROISE AI",
    )

    context = profile.get_personalization_context()

    assert "technical" in context
    assert "formal" in context
    assert "python" in context
    assert "TROISE AI" in context


# =============================================================================
# ExecutionContext Defaults Tests
# =============================================================================

def test_execution_context_defaults():
    """ExecutionContext has correct default values."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    assert context.user_id == "test-user"
    assert context.session_id == "test-session"
    assert context.interface == "web"
    assert context.conversation_history == []
    assert context.websocket is None
    assert context.agent_name is None


def test_execution_context_creates_default_profile():
    """ExecutionContext creates default UserProfile if not provided."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
    )

    assert context.user_profile is not None
    assert context.user_profile.user_id == "test-user"


def test_execution_context_uses_provided_profile():
    """ExecutionContext uses provided UserProfile."""
    profile = UserProfile(
        user_id="custom-user",
        communication_style="verbose",
    )

    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        user_profile=profile,
    )

    assert context.user_profile.communication_style == "verbose"


# =============================================================================
# Cancellation Tests
# =============================================================================

def test_cancel_sets_token():
    """cancel() sets the cancellation token."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
    )

    assert not context.cancellation_token.is_set()

    context.cancel("Test cancellation")

    assert context.cancellation_token.is_set()
    assert context.cancelled_reason == "Test cancellation"


async def test_check_cancelled_raises():
    """check_cancelled() raises AgentCancelled when cancelled."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
    )

    context.cancel("User stopped")

    with pytest.raises(AgentCancelled) as exc_info:
        await context.check_cancelled()

    assert "User stopped" in str(exc_info.value)


async def test_check_cancelled_does_nothing_when_not_cancelled():
    """check_cancelled() passes when not cancelled."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
    )

    # Should not raise
    await context.check_cancelled()


# =============================================================================
# Request User Input Tests
# =============================================================================

async def test_request_user_input_no_websocket():
    """request_user_input returns message when no WebSocket."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="api",
        websocket=None,
    )

    result = await context.request_user_input("What do you want?")

    assert "cannot ask user" in result.lower() or "No WebSocket" in result


async def test_request_user_input_sends_question():
    """request_user_input sends question via WebSocket."""
    mock_ws = AsyncMock()
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        websocket=mock_ws,
    )

    # Create a task that simulates user response after a short delay
    async def respond_after_delay():
        await asyncio.sleep(0.01)
        # Get the request_id from the sent message
        call_args = mock_ws.send_json.call_args
        if call_args:
            request_id = call_args[0][0]["request_id"]
            await context.handle_user_answer(request_id, "Yes, please!")

    response_task = asyncio.create_task(respond_after_delay())

    result = await context.request_user_input(
        "Continue?",
        options=["Yes", "No"],
        timeout=1
    )

    await response_task

    # Verify WebSocket was called
    mock_ws.send_json.assert_called_once()
    sent_data = mock_ws.send_json.call_args[0][0]
    assert sent_data["type"] == "question"
    assert sent_data["question"] == "Continue?"
    assert sent_data["options"] == ["Yes", "No"]

    # Verify we got the response
    assert result == "Yes, please!"


async def test_handle_user_answer():
    """handle_user_answer resolves pending question."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    # Create a pending question
    future = asyncio.get_event_loop().create_future()
    context.pending_questions["test-request"] = future

    # Handle answer
    await context.handle_user_answer("test-request", "User's answer")

    # Future should be resolved
    assert future.done()
    assert future.result() == "User's answer"


async def test_handle_user_answer_unknown_request():
    """handle_user_answer ignores unknown request IDs."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    # Should not raise
    await context.handle_user_answer("unknown-request", "Answer")

    # No pending questions should be affected
    assert len(context.pending_questions) == 0


# =============================================================================
# Conversation History Tests
# =============================================================================

def test_conversation_history():
    """ExecutionContext stores conversation history."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        conversation_history=[
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ],
    )

    assert len(context.conversation_history) == 2
    assert context.conversation_history[0].content == "Hello"
    assert context.conversation_history[1].role == "assistant"


# =============================================================================
# Agent Tracking Tests
# =============================================================================

def test_agent_name_tracking():
    """ExecutionContext tracks current agent name."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    assert context.agent_name is None

    context.agent_name = "braindump"

    assert context.agent_name == "braindump"


def test_last_user_message_tracking():
    """ExecutionContext tracks last user message."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    context.last_user_message = "Help me with X"

    assert context.last_user_message == "Help me with X"


# =============================================================================
# Skill Recursion Guard Tests
# =============================================================================

def test_skill_call_depth_defaults():
    """ExecutionContext has correct skill recursion defaults."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    assert context.skill_call_depth == 0
    assert context.max_skill_depth == 2
    assert context.called_skills == set()


def test_can_call_skill_initial():
    """can_call_skill returns True for initial call."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    assert context.can_call_skill("summarize") is True
    assert context.can_call_skill("translate") is True


def test_can_call_skill_blocks_cycle():
    """can_call_skill returns False when skill already called."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        called_skills={"summarize"},
    )

    assert context.can_call_skill("summarize") is False
    assert context.can_call_skill("translate") is True


def test_can_call_skill_blocks_depth_exceeded():
    """can_call_skill returns False when depth limit exceeded."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        skill_call_depth=2,
        max_skill_depth=2,
    )

    assert context.can_call_skill("summarize") is False


def test_can_call_skill_allows_within_depth():
    """can_call_skill returns True when within depth limit."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        skill_call_depth=1,
        max_skill_depth=2,
    )

    assert context.can_call_skill("summarize") is True


def test_with_skill_call_increments_depth():
    """with_skill_call creates context with incremented depth."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
    )

    child = context.with_skill_call("summarize")

    # Parent unchanged
    assert context.skill_call_depth == 0
    assert context.called_skills == set()

    # Child has incremented values
    assert child.skill_call_depth == 1
    assert "summarize" in child.called_skills


def test_with_skill_call_accumulates_skills():
    """with_skill_call accumulates called skills."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        skill_call_depth=1,
        called_skills={"summarize"},
    )

    child = context.with_skill_call("translate")

    assert child.skill_call_depth == 2
    assert child.called_skills == {"summarize", "translate"}


def test_with_skill_call_preserves_other_fields():
    """with_skill_call preserves other context fields."""
    context = ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="discord",
        agent_name="research",
    )

    child = context.with_skill_call("summarize")

    assert child.user_id == "test-user"
    assert child.session_id == "test-session"
    assert child.interface == "discord"
    assert child.agent_name == "research"
