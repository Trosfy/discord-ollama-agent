"""Write file tool implementation.

Writes or appends content to files with backup support
and safe overwrite protection.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Maximum content size to write (5 MB)
MAX_CONTENT_SIZE = 5 * 1024 * 1024


class WriteFileTool:
    """
    Tool for writing content to files.

    Writes files with backup support, parent directory creation,
    and optional append mode.
    """

    name = "write_file"
    description = """Write content to a file on the filesystem.
Use this when you need to:
- Create new source code files
- Write configuration files
- Save generated content
- Update existing files

Supports creating parent directories and backup of existing files."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            },
            "mode": {
                "type": "string",
                "description": "Write mode: 'overwrite' (default), 'append', or 'create_only'",
                "enum": ["overwrite", "append", "create_only"],
                "default": "overwrite"
            },
            "create_dirs": {
                "type": "boolean",
                "description": "Create parent directories if they don't exist (default: true)",
                "default": True
            },
            "backup": {
                "type": "boolean",
                "description": "Create backup of existing file before overwriting (default: false)",
                "default": False
            },
        },
        "required": ["path", "content"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        allowed_paths: List[str] = None,
        backup_dir: str = None,
    ):
        """
        Initialize the write file tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            allowed_paths: List of allowed base paths (security).
            backup_dir: Directory for backups.
        """
        self._context = context
        self._container = container
        self._allowed_paths = allowed_paths or []
        self._backup_dir = backup_dir

    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if not self._allowed_paths:
            return True  # No restrictions

        resolved = path.resolve()
        for allowed in self._allowed_paths:
            allowed_path = Path(allowed).resolve()
            if str(resolved).startswith(str(allowed_path)):
                return True
        return False

    def _create_backup(self, file_path: Path) -> Optional[str]:
        """Create backup of existing file."""
        if not file_path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self._backup_dir:
            backup_base = Path(self._backup_dir)
            backup_base.mkdir(parents=True, exist_ok=True)
            backup_path = backup_base / f"{file_path.name}.{timestamp}.bak"
        else:
            backup_path = file_path.with_suffix(f".{timestamp}.bak")

        shutil.copy2(file_path, backup_path)
        return str(backup_path)

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Write content to file.

        Args:
            params: Tool parameters (path, content, mode, create_dirs, backup).
            context: Execution context.

        Returns:
            ToolResult with write status as JSON.
        """
        file_path_str = params.get("path", "").strip()
        content = params.get("content", "")
        mode = params.get("mode", "overwrite")
        create_dirs = params.get("create_dirs", True)
        backup = params.get("backup", False)

        if not file_path_str:
            return ToolResult(
                content=json.dumps({
                    "error": "Path is required",
                    "written": False
                }),
                success=False,
                error="Path is required"
            )

        # Check content size
        content_size = len(content.encode("utf-8"))
        if content_size > MAX_CONTENT_SIZE:
            return ToolResult(
                content=json.dumps({
                    "error": f"Content too large: {content_size} bytes (max: {MAX_CONTENT_SIZE})",
                    "written": False
                }),
                success=False,
                error="Content too large"
            )

        file_path = Path(file_path_str).expanduser()

        # Security check
        if not self._is_path_allowed(file_path):
            return ToolResult(
                content=json.dumps({
                    "error": "Access denied: path not in allowed directories",
                    "written": False
                }),
                success=False,
                error="Access denied"
            )

        # Handle create_only mode
        if mode == "create_only" and file_path.exists():
            return ToolResult(
                content=json.dumps({
                    "error": f"File already exists: {file_path_str}",
                    "written": False,
                    "hint": "Use mode='overwrite' to replace existing file"
                }),
                success=False,
                error="File already exists"
            )

        # Create parent directories
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        elif not file_path.parent.exists():
            return ToolResult(
                content=json.dumps({
                    "error": f"Parent directory does not exist: {file_path.parent}",
                    "written": False,
                    "hint": "Set create_dirs=true to create parent directories"
                }),
                success=False,
                error="Parent directory does not exist"
            )

        try:
            # Create backup if requested
            backup_path = None
            if backup and file_path.exists():
                backup_path = self._create_backup(file_path)

            # Write file
            if mode == "append":
                write_mode = "a"
            else:
                write_mode = "w"

            with open(file_path, write_mode, encoding="utf-8") as f:
                f.write(content)

            # Get file stats
            file_stats = file_path.stat()

            logger.info(f"Wrote file: {file_path_str} ({content_size} bytes)")

            result = {
                "path": str(file_path.resolve()),
                "written": True,
                "bytes_written": content_size,
                "mode": mode,
                "file_size": file_stats.st_size,
            }

            if backup_path:
                result["backup_path"] = backup_path

            return ToolResult(
                content=json.dumps(result),
                success=True,
            )

        except PermissionError:
            return ToolResult(
                content=json.dumps({
                    "error": f"Permission denied: {file_path_str}",
                    "written": False
                }),
                success=False,
                error="Permission denied"
            )
        except Exception as e:
            logger.error(f"Write file error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "written": False
                }),
                success=False,
                error=str(e)
            )

    def to_schema(self) -> Dict[str, Any]:
        """Return tool schema for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def create_write_file_tool(
    context: ExecutionContext,
    container: Container,
) -> WriteFileTool:
    """
    Factory function to create write_file tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured WriteFileTool instance.
    """
    # Get allowed paths and backup dir from config if available
    from app.core.config import Config
    config = container.try_resolve(Config)
    allowed_paths = None
    backup_dir = None

    if config:
        if hasattr(config, 'allowed_file_paths'):
            allowed_paths = config.allowed_file_paths
        if hasattr(config, 'backup_dir'):
            backup_dir = config.backup_dir

    return WriteFileTool(
        context=context,
        container=container,
        allowed_paths=allowed_paths,
        backup_dir=backup_dir,
    )
