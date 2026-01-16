"""Read file tool implementation.

Reads file contents from the filesystem with optional
line range selection and encoding detection.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Maximum file size to read (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum lines to return
MAX_LINES = 5000

# Common text file extensions
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css",
    ".sh", ".bash", ".zsh", ".fish",
    ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs", ".rb",
    ".sql", ".graphql", ".proto",
    ".env", ".gitignore", ".dockerignore",
    ".csv", ".log", ".ini", ".cfg", ".conf",
}


class ReadFileTool:
    """
    Tool for reading file contents.

    Reads files with optional line range selection,
    encoding detection, and size limits.
    """

    name = "read_file"
    description = """Read contents of a file from the filesystem.
Use this when you need to:
- Read source code files
- Examine configuration files
- Review documentation
- Check log files

Returns file contents with optional line numbers.
Supports text files up to 10MB."""

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read"
            },
            "start_line": {
                "type": "integer",
                "description": "Starting line number (1-indexed, optional)"
            },
            "end_line": {
                "type": "integer",
                "description": "Ending line number (inclusive, optional)"
            },
            "show_line_numbers": {
                "type": "boolean",
                "description": "Include line numbers in output (default: true)",
                "default": True
            },
        },
        "required": ["path"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        allowed_paths: List[str] = None,
    ):
        """
        Initialize the read file tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            allowed_paths: List of allowed base paths (security).
        """
        self._context = context
        self._container = container
        self._allowed_paths = allowed_paths or []

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

    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding (simple heuristic)."""
        try:
            with open(file_path, "rb") as f:
                raw = f.read(1024)

            # Check for BOM
            if raw.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
            if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                return 'utf-16'

            # Try UTF-8
            try:
                raw.decode('utf-8')
                return 'utf-8'
            except UnicodeDecodeError:
                pass

            # Fall back to latin-1
            return 'latin-1'

        except Exception:
            return 'utf-8'

    def _is_text_file(self, path: Path) -> bool:
        """Check if file appears to be text."""
        if path.suffix.lower() in TEXT_EXTENSIONS:
            return True

        # Check file contents for binary markers
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                # If there are null bytes, it's likely binary
                if b'\x00' in chunk:
                    return False
                return True
        except Exception:
            return False

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Read file contents.

        Args:
            params: Tool parameters (path, start_line, end_line, show_line_numbers).
            context: Execution context.

        Returns:
            ToolResult with file contents as JSON.
        """
        file_path_str = params.get("path", "").strip()
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        show_line_numbers = params.get("show_line_numbers", True)

        if not file_path_str:
            return ToolResult(
                content=json.dumps({
                    "error": "Path is required",
                    "content": None
                }),
                success=False,
                error="Path is required"
            )

        file_path = Path(file_path_str).expanduser()

        # Check if file exists
        if not file_path.exists():
            return ToolResult(
                content=json.dumps({
                    "error": f"File not found: {file_path_str}",
                    "content": None
                }),
                success=False,
                error=f"File not found: {file_path_str}"
            )

        if not file_path.is_file():
            return ToolResult(
                content=json.dumps({
                    "error": f"Not a file: {file_path_str}",
                    "content": None
                }),
                success=False,
                error=f"Not a file: {file_path_str}"
            )

        # Security check
        if not self._is_path_allowed(file_path):
            return ToolResult(
                content=json.dumps({
                    "error": "Access denied: path not in allowed directories",
                    "content": None
                }),
                success=False,
                error="Access denied"
            )

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return ToolResult(
                content=json.dumps({
                    "error": f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})",
                    "content": None,
                    "file_size": file_size,
                }),
                success=False,
                error="File too large"
            )

        # Check if text file
        if not self._is_text_file(file_path):
            return ToolResult(
                content=json.dumps({
                    "error": "Cannot read binary file",
                    "content": None,
                    "hint": "This appears to be a binary file"
                }),
                success=False,
                error="Cannot read binary file"
            )

        try:
            # Detect encoding and read file
            encoding = self._detect_encoding(file_path)

            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Apply line range if specified
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else total_lines

                # Clamp to valid range
                start_idx = max(0, start_idx)
                end_idx = min(total_lines, end_idx)

                lines = lines[start_idx:end_idx]
                displayed_start = start_idx + 1
            else:
                displayed_start = 1

            # Limit total lines
            if len(lines) > MAX_LINES:
                lines = lines[:MAX_LINES]
                truncated = True
            else:
                truncated = False

            # Format output
            if show_line_numbers:
                formatted_lines = []
                for i, line in enumerate(lines):
                    line_num = displayed_start + i
                    formatted_lines.append(f"{line_num:4d}| {line.rstrip()}")
                content = "\n".join(formatted_lines)
            else:
                content = "".join(lines)

            logger.info(f"Read file: {file_path_str} ({len(lines)} lines)")

            return ToolResult(
                content=json.dumps({
                    "path": str(file_path.resolve()),
                    "content": content,
                    "total_lines": total_lines,
                    "lines_returned": len(lines),
                    "truncated": truncated,
                    "encoding": encoding,
                }),
                success=True,
            )

        except Exception as e:
            logger.error(f"Read file error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "content": None
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


def create_read_file_tool(
    context: ExecutionContext,
    container: Container,
) -> ReadFileTool:
    """
    Factory function to create read_file tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured ReadFileTool instance.
    """
    # Get allowed paths from config if available
    from app.core.config import Config
    config = container.try_resolve(Config)
    allowed_paths = None
    if config and hasattr(config, 'allowed_file_paths'):
        allowed_paths = config.allowed_file_paths

    return ReadFileTool(
        context=context,
        container=container,
        allowed_paths=allowed_paths,
    )
