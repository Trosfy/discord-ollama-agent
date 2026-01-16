"""Unit tests for Read File Tool."""
import json
import pytest
import tempfile
import os
from pathlib import Path

from app.plugins.tools.read_file import ReadFileTool, create_read_file_tool
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
def read_file_tool(mock_context, mock_container):
    """Create read file tool with mock dependencies."""
    return ReadFileTool(
        context=mock_context,
        container=mock_container,
    )


@pytest.fixture
def temp_text_file():
    """Create temporary text file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def temp_python_file():
    """Create temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write('def hello():\n    print("Hello, World!")\n\nhello()\n')
        path = f.name
    yield path
    os.unlink(path)


# =============================================================================
# Input Validation Tests
# =============================================================================

async def test_execute_missing_path(read_file_tool, mock_context):
    """execute() returns error when no path provided."""
    params = {}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


async def test_execute_file_not_found(read_file_tool, mock_context):
    """execute() returns error for non-existent file."""
    params = {"path": "/nonexistent/file.txt"}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "not found" in content["error"].lower()


async def test_execute_not_a_file(read_file_tool, mock_context):
    """execute() returns error when path is a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        params = {"path": tmpdir}

        result = await read_file_tool.execute(params, mock_context)

        assert result.success is False
        content = json.loads(result.content)
        assert "not a file" in content["error"].lower()


# =============================================================================
# Read Tests
# =============================================================================

async def test_execute_read_text_file(read_file_tool, mock_context, temp_text_file):
    """execute() reads text file content."""
    params = {"path": temp_text_file}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "Line 1" in content["content"]
    assert content["total_lines"] == 5


async def test_execute_read_python_file(read_file_tool, mock_context, temp_python_file):
    """execute() reads Python file content."""
    params = {"path": temp_python_file}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "def hello" in content["content"]


async def test_execute_with_line_numbers(read_file_tool, mock_context, temp_text_file):
    """execute() includes line numbers by default."""
    params = {"path": temp_text_file, "show_line_numbers": True}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "1|" in content["content"] or "   1|" in content["content"]


async def test_execute_without_line_numbers(read_file_tool, mock_context, temp_text_file):
    """execute() can exclude line numbers."""
    params = {"path": temp_text_file, "show_line_numbers": False}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    # Should not have line number prefixes
    assert content["content"].startswith("Line 1")


# =============================================================================
# Line Range Tests
# =============================================================================

async def test_execute_start_line(read_file_tool, mock_context, temp_text_file):
    """execute() respects start_line parameter."""
    params = {
        "path": temp_text_file,
        "start_line": 3,
        "show_line_numbers": False,
    }

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "Line 3" in content["content"]
    assert "Line 1" not in content["content"]


async def test_execute_end_line(read_file_tool, mock_context, temp_text_file):
    """execute() respects end_line parameter."""
    params = {
        "path": temp_text_file,
        "end_line": 2,
        "show_line_numbers": False,
    }

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "Line 1" in content["content"]
    assert "Line 2" in content["content"]
    assert "Line 3" not in content["content"]


async def test_execute_line_range(read_file_tool, mock_context, temp_text_file):
    """execute() respects both start and end line."""
    params = {
        "path": temp_text_file,
        "start_line": 2,
        "end_line": 4,
        "show_line_numbers": False,
    }

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["lines_returned"] == 3


# =============================================================================
# Binary File Tests
# =============================================================================

async def test_execute_binary_file_rejected(read_file_tool, mock_context):
    """execute() rejects binary files."""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(b"\x00\x01\x02\x03\x04\x05")
        path = f.name

    try:
        params = {"path": path}

        result = await read_file_tool.execute(params, mock_context)

        assert result.success is False
        content = json.loads(result.content)
        assert "binary" in content["error"].lower()
    finally:
        os.unlink(path)


# =============================================================================
# Encoding Tests
# =============================================================================

async def test_execute_utf8_file(read_file_tool, mock_context):
    """execute() reads UTF-8 encoded files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello 世界 🌍")
        path = f.name

    try:
        params = {"path": path}

        result = await read_file_tool.execute(params, mock_context)

        assert result.success is True
        content = json.loads(result.content)
        assert "世界" in content["content"]
    finally:
        os.unlink(path)


# =============================================================================
# File Size Tests
# =============================================================================

async def test_execute_large_file_truncated(read_file_tool, mock_context):
    """execute() truncates files exceeding max lines."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for i in range(6000):  # More than MAX_LINES (5000)
            f.write(f"Line {i}\n")
        path = f.name

    try:
        params = {"path": path}

        result = await read_file_tool.execute(params, mock_context)

        assert result.success is True
        content = json.loads(result.content)
        assert content["truncated"] is True
        assert content["lines_returned"] <= 5000
    finally:
        os.unlink(path)


# =============================================================================
# Security Tests
# =============================================================================

async def test_execute_path_restriction(mock_context, mock_container):
    """execute() respects allowed_paths restriction."""
    with tempfile.TemporaryDirectory() as allowed_dir:
        with tempfile.TemporaryDirectory() as other_dir:
            # Create file in other directory
            other_file = Path(other_dir) / "secret.txt"
            other_file.write_text("secret content")

            # Tool restricted to allowed_dir
            tool = ReadFileTool(
                context=mock_context,
                container=mock_container,
                allowed_paths=[allowed_dir],
            )

            params = {"path": str(other_file)}

            result = await tool.execute(params, mock_context)

            assert result.success is False
            content = json.loads(result.content)
            assert "denied" in content["error"].lower()


async def test_execute_no_path_restriction(read_file_tool, mock_context, temp_text_file):
    """execute() allows all paths when no restriction set."""
    params = {"path": temp_text_file}

    result = await read_file_tool.execute(params, mock_context)

    assert result.success is True


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(read_file_tool):
    """to_schema() returns correct tool schema."""
    schema = read_file_tool.to_schema()

    assert schema["name"] == "read_file"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "path" in props
    assert "start_line" in props
    assert "end_line" in props
    assert "show_line_numbers" in props

    assert "path" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert ReadFileTool.name == "read_file"


def test_tool_description():
    """Tool has description."""
    assert ReadFileTool.description
    assert "read" in ReadFileTool.description.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_read_file_tool_factory():
    """create_read_file_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_read_file_tool(context, container)

    assert isinstance(tool, ReadFileTool)
    assert tool._context == context
    assert tool._container == container
