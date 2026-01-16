"""Unit tests for Write File Tool."""
import json
import pytest
import tempfile
import os
from pathlib import Path

from app.plugins.tools.write_file import WriteFileTool, create_write_file_tool
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
def write_file_tool(mock_context, mock_container):
    """Create write file tool with mock dependencies."""
    return WriteFileTool(
        context=mock_context,
        container=mock_container,
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# =============================================================================
# Input Validation Tests
# =============================================================================

async def test_execute_missing_path(write_file_tool, mock_context):
    """execute() returns error when no path provided."""
    params = {"content": "test"}

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


async def test_execute_missing_content(write_file_tool, mock_context, temp_dir):
    """execute() allows empty content (creates empty file)."""
    params = {
        "path": os.path.join(temp_dir, "empty.txt"),
        "content": "",
    }

    result = await write_file_tool.execute(params, mock_context)

    # Empty content is valid
    assert result.success is True


# =============================================================================
# Write Tests
# =============================================================================

async def test_execute_write_new_file(write_file_tool, mock_context, temp_dir):
    """execute() creates new file with content."""
    file_path = os.path.join(temp_dir, "new_file.txt")
    params = {
        "path": file_path,
        "content": "Hello, World!",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["written"] is True

    # Verify file content
    with open(file_path) as f:
        assert f.read() == "Hello, World!"


async def test_execute_overwrite_existing_file(write_file_tool, mock_context, temp_dir):
    """execute() overwrites existing file by default."""
    file_path = os.path.join(temp_dir, "existing.txt")

    # Create existing file
    with open(file_path, "w") as f:
        f.write("old content")

    params = {
        "path": file_path,
        "content": "new content",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True

    with open(file_path) as f:
        assert f.read() == "new content"


async def test_execute_append_mode(write_file_tool, mock_context, temp_dir):
    """execute() appends content in append mode."""
    file_path = os.path.join(temp_dir, "append.txt")

    # Create existing file
    with open(file_path, "w") as f:
        f.write("line 1\n")

    params = {
        "path": file_path,
        "content": "line 2\n",
        "mode": "append",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True

    with open(file_path) as f:
        content = f.read()
        assert "line 1" in content
        assert "line 2" in content


async def test_execute_create_only_mode_new_file(write_file_tool, mock_context, temp_dir):
    """execute() creates file in create_only mode."""
    file_path = os.path.join(temp_dir, "create_only.txt")
    params = {
        "path": file_path,
        "content": "new file content",
        "mode": "create_only",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    assert os.path.exists(file_path)


async def test_execute_create_only_mode_existing_file(write_file_tool, mock_context, temp_dir):
    """execute() fails in create_only mode for existing file."""
    file_path = os.path.join(temp_dir, "existing.txt")

    # Create existing file
    with open(file_path, "w") as f:
        f.write("existing content")

    params = {
        "path": file_path,
        "content": "new content",
        "mode": "create_only",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "already exists" in content["error"].lower()


# =============================================================================
# Directory Creation Tests
# =============================================================================

async def test_execute_creates_parent_dirs(write_file_tool, mock_context, temp_dir):
    """execute() creates parent directories by default."""
    file_path = os.path.join(temp_dir, "nested", "deep", "file.txt")
    params = {
        "path": file_path,
        "content": "nested content",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    assert os.path.exists(file_path)


async def test_execute_no_create_dirs(write_file_tool, mock_context, temp_dir):
    """execute() fails without create_dirs when parent missing."""
    file_path = os.path.join(temp_dir, "missing", "file.txt")
    params = {
        "path": file_path,
        "content": "content",
        "create_dirs": False,
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "does not exist" in content["error"].lower()


# =============================================================================
# Backup Tests
# =============================================================================

async def test_execute_with_backup(write_file_tool, mock_context, temp_dir):
    """execute() creates backup when requested."""
    file_path = os.path.join(temp_dir, "backup_test.txt")

    # Create existing file
    with open(file_path, "w") as f:
        f.write("original content")

    params = {
        "path": file_path,
        "content": "new content",
        "backup": True,
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "backup_path" in content

    # Verify backup exists
    assert os.path.exists(content["backup_path"])
    with open(content["backup_path"]) as f:
        assert f.read() == "original content"


async def test_execute_no_backup_for_new_file(write_file_tool, mock_context, temp_dir):
    """execute() doesn't create backup for new file."""
    file_path = os.path.join(temp_dir, "new_file.txt")
    params = {
        "path": file_path,
        "content": "new content",
        "backup": True,
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert "backup_path" not in content or content.get("backup_path") is None


# =============================================================================
# Content Size Tests
# =============================================================================

async def test_execute_large_content_rejected(write_file_tool, mock_context, temp_dir):
    """execute() rejects content exceeding max size."""
    file_path = os.path.join(temp_dir, "large.txt")
    # 6 MB content (exceeds 5 MB limit)
    large_content = "x" * (6 * 1024 * 1024)

    params = {
        "path": file_path,
        "content": large_content,
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "too large" in content["error"].lower()


# =============================================================================
# Security Tests
# =============================================================================

async def test_execute_path_restriction(mock_context, mock_container, temp_dir):
    """execute() respects allowed_paths restriction."""
    allowed_dir = os.path.join(temp_dir, "allowed")
    os.makedirs(allowed_dir)

    other_dir = os.path.join(temp_dir, "other")
    os.makedirs(other_dir)

    tool = WriteFileTool(
        context=mock_context,
        container=mock_container,
        allowed_paths=[allowed_dir],
    )

    # Try to write outside allowed path
    params = {
        "path": os.path.join(other_dir, "secret.txt"),
        "content": "secret content",
    }

    result = await tool.execute(params, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "denied" in content["error"].lower()


async def test_execute_within_allowed_path(mock_context, mock_container, temp_dir):
    """execute() allows write within allowed path."""
    tool = WriteFileTool(
        context=mock_context,
        container=mock_container,
        allowed_paths=[temp_dir],
    )

    file_path = os.path.join(temp_dir, "allowed.txt")
    params = {
        "path": file_path,
        "content": "allowed content",
    }

    result = await tool.execute(params, mock_context)

    assert result.success is True


# =============================================================================
# Unicode Tests
# =============================================================================

async def test_execute_unicode_content(write_file_tool, mock_context, temp_dir):
    """execute() handles unicode content correctly."""
    file_path = os.path.join(temp_dir, "unicode.txt")
    params = {
        "path": file_path,
        "content": "Hello 世界 🌍 émojis",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True

    with open(file_path, encoding="utf-8") as f:
        assert f.read() == "Hello 世界 🌍 émojis"


# =============================================================================
# Result Format Tests
# =============================================================================

async def test_execute_result_format(write_file_tool, mock_context, temp_dir):
    """execute() returns complete result information."""
    file_path = os.path.join(temp_dir, "result_test.txt")
    params = {
        "path": file_path,
        "content": "test content",
    }

    result = await write_file_tool.execute(params, mock_context)

    assert result.success is True
    content = json.loads(result.content)
    assert content["written"] is True
    assert content["bytes_written"] > 0
    assert content["mode"] == "overwrite"
    assert content["file_size"] > 0
    assert "path" in content


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(write_file_tool):
    """to_schema() returns correct tool schema."""
    schema = write_file_tool.to_schema()

    assert schema["name"] == "write_file"
    assert "description" in schema
    assert "parameters" in schema
    assert schema["parameters"]["type"] == "object"

    props = schema["parameters"]["properties"]
    assert "path" in props
    assert "content" in props
    assert "mode" in props
    assert "create_dirs" in props
    assert "backup" in props

    assert "path" in schema["parameters"]["required"]
    assert "content" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert WriteFileTool.name == "write_file"


def test_tool_description():
    """Tool has description."""
    assert WriteFileTool.description
    assert "write" in WriteFileTool.description.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

def test_create_write_file_tool_factory():
    """create_write_file_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = Container()

    tool = create_write_file_tool(context, container)

    assert isinstance(tool, WriteFileTool)
    assert tool._context == context
    assert tool._container == container
