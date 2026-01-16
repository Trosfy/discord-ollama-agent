"""Unit tests for Run Code Tool."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from app.plugins.tools.run_code import RunCodeTool, create_run_code_tool
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_context():
    """Create mock execution context."""
    return ExecutionContext(
        user_id="test-user",
        session_id="test-session",
        interface="web",
        user_profile=UserProfile(user_id="test-user"),
        agent_name="test-agent",
    )


@pytest.fixture
def mock_container():
    """Create mock DI container."""
    return Container()


@pytest.fixture
def run_code_tool(mock_context, mock_container):
    """Create run code tool with mock dependencies."""
    return RunCodeTool(
        context=mock_context,
        container=mock_container,
    )


# =============================================================================
# Input Validation Tests
# =============================================================================

async def test_execute_missing_code(run_code_tool, mock_context):
    """execute() returns error when no code provided."""
    params = {}

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


async def test_execute_empty_code(run_code_tool, mock_context):
    """execute() returns error for empty code."""
    params = {"code": "   "}

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is False


async def test_execute_unsupported_language(run_code_tool, mock_context):
    """execute() returns error for unsupported language."""
    params = {
        "code": "print('hello')",
        "language": "cobol",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "not allowed" in content["error"].lower() or "not supported" in content["error"].lower()


# =============================================================================
# Python Execution Tests
# =============================================================================

async def test_execute_python_success(run_code_tool, mock_context):
    """execute() runs Python code successfully."""
    params = {
        "code": "print('Hello, World!')",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["exit_code"] == 0
    assert "Hello, World!" in content["stdout"]
    assert content["timed_out"] is False


async def test_execute_python_with_error(run_code_tool, mock_context):
    """execute() captures Python errors."""
    params = {
        "code": "raise ValueError('test error')",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True  # Tool succeeded, code failed
    content = json.loads(result.content)
    assert content["exit_code"] != 0
    assert "ValueError" in content["stderr"]


async def test_execute_python_syntax_error(run_code_tool, mock_context):
    """execute() captures Python syntax errors."""
    params = {
        "code": "def bad syntax",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["exit_code"] != 0
    assert "SyntaxError" in content["stderr"]


async def test_execute_python_multiline(run_code_tool, mock_context):
    """execute() runs multiline Python code."""
    params = {
        "code": """
def greet(name):
    return f"Hello, {name}!"

result = greet("World")
print(result)
""",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["exit_code"] == 0
    assert "Hello, World!" in content["stdout"]


# =============================================================================
# Timeout Tests
# =============================================================================

async def test_execute_timeout(run_code_tool, mock_context):
    """execute() times out long-running code."""
    params = {
        "code": "import time; time.sleep(100)",
        "language": "python",
        "timeout": 1,  # 1 second timeout
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["timed_out"] is True
    assert content["exit_code"] == -1


async def test_execute_default_timeout(run_code_tool, mock_context):
    """execute() uses default timeout of 30 seconds."""
    params = {
        "code": "print('quick')",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True


async def test_execute_timeout_capped_at_60(run_code_tool, mock_context):
    """execute() caps timeout at 60 seconds."""
    params = {
        "code": "print('test')",
        "language": "python",
        "timeout": 300,  # Request 300 seconds
    }

    # Should run successfully, timeout internally capped
    result = await run_code_tool.execute(params, mock_context)
    assert result.success is True


# =============================================================================
# Language Tests
# =============================================================================

async def test_execute_bash(run_code_tool, mock_context):
    """execute() runs bash scripts."""
    params = {
        "code": "echo 'Hello from bash'",
        "language": "bash",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["exit_code"] == 0
    assert "Hello from bash" in content["stdout"]


async def test_execute_shell(run_code_tool, mock_context):
    """execute() runs shell scripts."""
    params = {
        "code": "echo 'Hello from shell'",
        "language": "shell",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["exit_code"] == 0


async def test_execute_default_language_python(run_code_tool, mock_context):
    """execute() defaults to Python when no language specified."""
    params = {
        "code": "print('default python')",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["language"] == "python"
    assert "default python" in content["stdout"]


# =============================================================================
# Working Directory Tests
# =============================================================================

async def test_execute_with_working_dir(run_code_tool, mock_context):
    """execute() respects working directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        params = {
            "code": "import os; print(os.getcwd())",
            "language": "python",
            "working_dir": tmpdir,
        }

        result = await run_code_tool.execute(params, mock_context)

        assert result.success is True
        content = json.loads(result.content)
        assert tmpdir in content["stdout"]


async def test_execute_invalid_working_dir(run_code_tool, mock_context):
    """execute() returns error for non-existent working directory."""
    params = {
        "code": "print('test')",
        "language": "python",
        "working_dir": "/nonexistent/directory",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "does not exist" in content["error"]


# =============================================================================
# Output Handling Tests
# =============================================================================

async def test_execute_captures_stderr(run_code_tool, mock_context):
    """execute() captures stderr separately."""
    params = {
        "code": "import sys; sys.stderr.write('error output')",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "error output" in content["stderr"]


async def test_execute_large_output_truncated(run_code_tool, mock_context):
    """execute() truncates very large output."""
    params = {
        "code": "print('x' * 20000)",
        "language": "python",
    }

    result = await run_code_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    # Output should be truncated to MAX_OUTPUT_SIZE (10000)
    assert len(content["stdout"]) <= 10001


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(run_code_tool):
    """to_schema() returns correct tool schema."""
    schema = run_code_tool.to_schema()

    assert schema["name"] == "run_code"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "code" in props
    assert "language" in props
    assert "timeout" in props
    assert "working_dir" in props

    assert "code" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert RunCodeTool.name == "run_code"


def test_tool_description():
    """Tool has description."""
    assert RunCodeTool.description
    assert "execute" in RunCodeTool.description.lower() or "run" in RunCodeTool.description.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_run_code_tool_factory():
    """create_run_code_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_run_code_tool(context, container)

    assert isinstance(tool, RunCodeTool)
    assert tool._context == context
    assert tool._container == container
