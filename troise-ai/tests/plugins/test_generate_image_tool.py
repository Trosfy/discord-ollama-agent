"""Unit tests for Generate Image Tool using FLUX 2.dev via ComfyUI.

Tests cover:
- Input validation (prompt required)
- Aspect ratio dimension mapping
- Error handling (storage unavailable, memory errors, value errors)
- Successful image generation and storage upload
- Schema generation
- Factory function
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict

from app.plugins.tools.generate_image.tool import (
    GenerateImageTool,
    create_generate_image_tool,
)
from app.core.context import ExecutionContext, UserProfile
from app.core.container import Container
from app.core.interfaces.services import IVRAMOrchestrator
from app.core.interfaces.storage import IFileStorage


# Sample PNG bytes for mocking ComfyUI response
MOCK_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...'


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
    )


@pytest.fixture
def mock_container():
    """Create mock DI container."""
    container = MagicMock(spec=Container)
    return container


@pytest.fixture
def generate_image_tool(mock_context, mock_container):
    """Create GenerateImageTool with mocks."""
    return GenerateImageTool(context=mock_context, container=mock_container)


# =============================================================================
# Input Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_missing_prompt(generate_image_tool, mock_context, mock_container):
    """execute() returns error when no prompt provided."""
    result = await generate_image_tool.execute({}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "error" in content
    assert "prompt" in content["error"].lower()


@pytest.mark.asyncio
async def test_execute_empty_prompt(generate_image_tool, mock_context, mock_container):
    """execute() returns error for empty prompt."""
    result = await generate_image_tool.execute({"prompt": "   "}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "required" in content["error"].lower()


@pytest.mark.asyncio
async def test_execute_whitespace_only_prompt(generate_image_tool, mock_context, mock_container):
    """execute() returns error for whitespace-only prompt."""
    result = await generate_image_tool.execute({"prompt": "\n\t  "}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "prompt" in content["error"].lower()


# =============================================================================
# Aspect Ratio Tests
# =============================================================================

def test_aspect_ratio_dimensions():
    """ASPECT_RATIOS contains correct dimensions for all supported ratios."""
    assert GenerateImageTool.ASPECT_RATIOS["1:1"] == (1024, 1024)
    assert GenerateImageTool.ASPECT_RATIOS["16:9"] == (1344, 768)
    assert GenerateImageTool.ASPECT_RATIOS["9:16"] == (768, 1344)
    assert GenerateImageTool.ASPECT_RATIOS["4:3"] == (1152, 896)
    assert GenerateImageTool.ASPECT_RATIOS["3:4"] == (896, 1152)


def test_aspect_ratio_all_present():
    """All documented aspect ratios are present in ASPECT_RATIOS."""
    expected = ["1:1", "16:9", "9:16", "4:3", "3:4"]
    for ratio in expected:
        assert ratio in GenerateImageTool.ASPECT_RATIOS


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_storage_not_available(generate_image_tool, mock_context, mock_container):
    """execute() returns error when storage is not available."""
    # Mock orchestrator with successful ComfyUI client
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    # No storage available
    mock_container.try_resolve.return_value = None

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "storage" in content["error"].lower()


@pytest.mark.asyncio
async def test_execute_memory_error(generate_image_tool, mock_context, mock_container):
    """execute() handles MemoryError gracefully."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API: get_diffusion_context raises MemoryError (async method)
    mock_orchestrator.get_diffusion_context = AsyncMock(side_effect=MemoryError("Out of GPU memory"))
    mock_container.resolve.return_value = mock_orchestrator

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "memory" in content["error"].lower()


@pytest.mark.asyncio
async def test_execute_value_error(generate_image_tool, mock_context, mock_container):
    """execute() handles ValueError (model not in profile)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API: get_diffusion_context raises ValueError (async method)
    mock_orchestrator.get_diffusion_context = AsyncMock(
        side_effect=ValueError("Model 'flux2-dev-nvfp4' not in profile")
    )
    mock_container.resolve.return_value = mock_orchestrator

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "not in profile" in content["error"]


@pytest.mark.asyncio
async def test_execute_runtime_error(generate_image_tool, mock_context, mock_container):
    """execute() handles RuntimeError (backend not available)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API: get_diffusion_context raises RuntimeError (async method)
    mock_orchestrator.get_diffusion_context = AsyncMock(
        side_effect=RuntimeError("ComfyUI backend not configured")
    )
    mock_container.resolve.return_value = mock_orchestrator

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "ComfyUI backend not configured" in content["error"]


@pytest.mark.asyncio
async def test_execute_generic_exception(generate_image_tool, mock_context, mock_container):
    """execute() handles unexpected exceptions gracefully."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API: get_diffusion_context raises generic exception (async method)
    mock_orchestrator.get_diffusion_context = AsyncMock(side_effect=Exception("Unexpected error"))
    mock_container.resolve.return_value = mock_orchestrator

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "failed" in content["error"].lower()


# =============================================================================
# Success Case Tests
# =============================================================================

@pytest.mark.asyncio
async def test_execute_success(generate_image_tool, mock_context, mock_container):
    """execute() generates image and uploads to storage successfully."""
    # Mock orchestrator with ComfyUI client
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config) - async method
    mock_workflow_config = {"unet_name": "test.safetensors"}
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, mock_workflow_config))
    mock_container.resolve.return_value = mock_orchestrator

    # Mock storage
    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="storage-key-123")
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute(
        {"prompt": "a beautiful cat", "aspect_ratio": "16:9"},
        mock_context,
    )

    assert result.success is True
    content = json.loads(result.content)
    assert content["success"] is True
    assert content["width"] == 1344
    assert content["height"] == 768
    assert content["aspect_ratio"] == "16:9"
    assert "file_id" in content
    assert content["prompt_used"] == "a beautiful cat"

    # Verify ComfyUI client was called correctly
    mock_comfyui.generate_image.assert_called_once()
    call_kwargs = mock_comfyui.generate_image.call_args.kwargs
    assert call_kwargs["prompt"] == "a beautiful cat"
    assert call_kwargs["width"] == 1344
    assert call_kwargs["height"] == 768
    # Verify workflow_config was passed
    assert call_kwargs["workflow_config"] == mock_workflow_config


@pytest.mark.asyncio
async def test_execute_success_with_seed(generate_image_tool, mock_context, mock_container):
    """execute() uses provided seed for reproducibility."""
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="storage-key-456")
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute(
        {"prompt": "a cat", "seed": 42},
        mock_context,
    )

    assert result.success is True
    content = json.loads(result.content)
    assert content["seed"] == 42

    # Verify seed was passed to ComfyUI
    call_kwargs = mock_comfyui.generate_image.call_args.kwargs
    assert call_kwargs["seed"] == 42


@pytest.mark.asyncio
async def test_execute_default_aspect_ratio(generate_image_tool, mock_context, mock_container):
    """execute() uses 1:1 aspect ratio by default."""
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="storage-key")
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute(
        {"prompt": "a cat"},  # No aspect_ratio specified
        mock_context,
    )

    assert result.success is True
    content = json.loads(result.content)
    assert content["width"] == 1024
    assert content["height"] == 1024
    assert content["aspect_ratio"] == "1:1"


@pytest.mark.asyncio
async def test_execute_default_inference_steps(generate_image_tool, mock_context, mock_container):
    """execute() uses 28 inference steps by default."""
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="storage-key")
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute(
        {"prompt": "a cat"},
        mock_context,
    )

    assert result.success is True
    content = json.loads(result.content)
    assert content["num_inference_steps"] == 28

    # Verify default steps passed to ComfyUI
    call_kwargs = mock_comfyui.generate_image.call_args.kwargs
    assert call_kwargs["steps"] == 28


@pytest.mark.asyncio
async def test_execute_comfyui_returns_none(generate_image_tool, mock_context, mock_container):
    """execute() handles ComfyUI returning None (generation failed)."""
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=None)  # Generation failed
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    mock_storage = MagicMock()
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute({"prompt": "a cat"}, mock_context)

    assert result.success is False
    content = json.loads(result.content)
    assert "failed" in content["error"].lower() or "no image" in content["error"].lower()


@pytest.mark.asyncio
async def test_execute_random_seed_returns_string(generate_image_tool, mock_context, mock_container):
    """execute() returns 'random' for seed when not provided."""
    mock_orchestrator = MagicMock()
    mock_comfyui = MagicMock()
    mock_comfyui.generate_image = AsyncMock(return_value=MOCK_PNG_BYTES)
    mock_orchestrator.get_profile_model.return_value = "flux2-dev-nvfp4"
    # New API returns tuple of (client, workflow_config)
    mock_orchestrator.get_diffusion_context = AsyncMock(return_value=(mock_comfyui, {"workflow": "config"}))
    mock_container.resolve.return_value = mock_orchestrator

    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="storage-key")
    mock_container.try_resolve.return_value = mock_storage

    result = await generate_image_tool.execute(
        {"prompt": "a cat"},  # No seed specified
        mock_context,
    )

    assert result.success is True
    content = json.loads(result.content)
    assert content["seed"] == "random"


# =============================================================================
# Schema Tests
# =============================================================================

def test_to_schema(generate_image_tool):
    """to_schema() returns correct tool schema."""
    schema = generate_image_tool.to_schema()

    assert schema["name"] == "generate_image"
    assert "description" in schema
    assert "parameters" in schema
    assert "prompt" in schema["parameters"]["properties"]
    assert "aspect_ratio" in schema["parameters"]["properties"]
    assert "num_inference_steps" in schema["parameters"]["properties"]
    assert "guidance_scale" in schema["parameters"]["properties"]
    assert "seed" in schema["parameters"]["properties"]
    assert "prompt" in schema["parameters"]["required"]


def test_tool_name():
    """Tool has correct name attribute."""
    assert GenerateImageTool.name == "generate_image"


def test_tool_description():
    """Tool has a meaningful description."""
    assert "FLUX" in GenerateImageTool.description
    assert "image" in GenerateImageTool.description.lower()


def test_schema_aspect_ratio_enum():
    """Schema aspect_ratio has correct enum values."""
    enum_values = GenerateImageTool.parameters["properties"]["aspect_ratio"]["enum"]
    assert "1:1" in enum_values
    assert "16:9" in enum_values
    assert "9:16" in enum_values
    assert "4:3" in enum_values
    assert "3:4" in enum_values


def test_schema_inference_steps_limits():
    """Schema num_inference_steps has correct min/max limits."""
    steps = GenerateImageTool.parameters["properties"]["num_inference_steps"]
    assert steps["minimum"] == 20
    assert steps["maximum"] == 50
    assert steps["default"] == 28


def test_schema_guidance_scale_limits():
    """Schema guidance_scale has correct min/max limits."""
    guidance = GenerateImageTool.parameters["properties"]["guidance_scale"]
    assert guidance["minimum"] == 1.0
    assert guidance["maximum"] == 10.0
    assert guidance["default"] == 4.0


# =============================================================================
# Factory Tests
# =============================================================================

def test_create_generate_image_tool_factory():
    """create_generate_image_tool() creates tool instance."""
    context = ExecutionContext(
        user_id="test",
        session_id="test",
        interface="web",
    )
    container = MagicMock(spec=Container)

    tool = create_generate_image_tool(context, container)

    assert isinstance(tool, GenerateImageTool)
    assert tool._context == context
    assert tool._container == container


def test_create_generate_image_tool_preserves_context():
    """create_generate_image_tool() preserves context attributes."""
    context = ExecutionContext(
        user_id="user-123",
        session_id="session-456",
        interface="discord",
    )
    container = MagicMock(spec=Container)

    tool = create_generate_image_tool(context, container)

    assert tool._context.user_id == "user-123"
    assert tool._context.session_id == "session-456"
    assert tool._context.interface == "discord"
