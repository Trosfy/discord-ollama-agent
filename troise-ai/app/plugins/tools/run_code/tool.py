"""Run code tool implementation.

Executes code in a sandboxed environment with timeout protection.
Supports Python by default, with optional language extensions.
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Default execution limits
DEFAULT_TIMEOUT = 30  # seconds
MAX_OUTPUT_SIZE = 10000  # characters

# Supported languages and their execution commands
LANGUAGE_CONFIGS = {
    "python": {
        "extension": ".py",
        "command": [sys.executable, "-u"],
        "file_arg": True,
    },
    "javascript": {
        "extension": ".js",
        "command": ["node"],
        "file_arg": True,
    },
    "bash": {
        "extension": ".sh",
        "command": ["bash"],
        "file_arg": True,
    },
    "shell": {
        "extension": ".sh",
        "command": ["sh"],
        "file_arg": True,
    },
}


class RunCodeTool:
    """
    Tool for executing code in a sandboxed environment.

    Executes code with timeout protection and captures
    stdout/stderr output. Uses temporary files for isolation.
    """

    name = "run_code"
    description = """Execute code and return the output.
Use this when you need to:
- Run Python, JavaScript, or shell scripts
- Test code snippets
- Perform calculations or data processing
- Verify code functionality

Code runs in a sandboxed environment with a timeout.
Returns stdout, stderr, and exit code."""

    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The code to execute"
            },
            "language": {
                "type": "string",
                "description": "Programming language (python, javascript, bash)",
                "enum": ["python", "javascript", "bash", "shell"],
                "default": "python"
            },
            "timeout": {
                "type": "integer",
                "description": "Execution timeout in seconds (default: 30, max: 60)",
                "default": 30
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for code execution (optional)"
            },
        },
        "required": ["code"]
    }

    def __init__(
        self,
        context: ExecutionContext,
        container: Container,
        sandbox_dir: str = None,
        allowed_languages: list = None,
    ):
        """
        Initialize the run code tool.

        Args:
            context: Execution context.
            container: DI container for service resolution.
            sandbox_dir: Directory for sandboxed execution.
            allowed_languages: List of allowed languages.
        """
        self._context = context
        self._container = container
        self._sandbox_dir = sandbox_dir or tempfile.gettempdir()
        self._allowed_languages = allowed_languages or list(LANGUAGE_CONFIGS.keys())

    async def _execute_code(
        self,
        code: str,
        language: str,
        timeout: int,
        working_dir: str = None,
    ) -> Dict[str, Any]:
        """
        Execute code in subprocess with timeout.

        Args:
            code: Source code to execute.
            language: Programming language.
            timeout: Timeout in seconds.
            working_dir: Working directory.

        Returns:
            Dict with stdout, stderr, exit_code, timed_out.
        """
        config = LANGUAGE_CONFIGS[language]

        # Create temporary file for code
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=config["extension"],
            delete=False,
            dir=self._sandbox_dir,
        ) as f:
            f.write(code)
            code_file = f.name

        try:
            # Build command
            command = config["command"].copy()
            if config.get("file_arg"):
                command.append(code_file)

            # Set up environment
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONUNBUFFERED"] = "1"

            # Determine working directory
            cwd = working_dir or self._sandbox_dir

            # Run the code
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )

                return {
                    "stdout": stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE],
                    "stderr": stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE],
                    "exit_code": process.returncode,
                    "timed_out": False,
                }

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

                return {
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout} seconds",
                    "exit_code": -1,
                    "timed_out": True,
                }

        finally:
            # Clean up temporary file
            try:
                os.unlink(code_file)
            except OSError:
                pass

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute code and return output.

        Args:
            params: Tool parameters (code, language, timeout, working_dir).
            context: Execution context.

        Returns:
            ToolResult with execution results as JSON.
        """
        code = params.get("code", "").strip()
        language = params.get("language", "python").lower()
        timeout = min(params.get("timeout", DEFAULT_TIMEOUT), 60)
        working_dir = params.get("working_dir")

        # Validate input
        if not code:
            return ToolResult(
                content=json.dumps({
                    "error": "Code is required",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }),
                success=False,
                error="Code is required"
            )

        if language not in self._allowed_languages:
            return ToolResult(
                content=json.dumps({
                    "error": f"Language '{language}' is not allowed. Supported: {', '.join(self._allowed_languages)}",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }),
                success=False,
                error=f"Language '{language}' is not allowed"
            )

        if language not in LANGUAGE_CONFIGS:
            return ToolResult(
                content=json.dumps({
                    "error": f"Language '{language}' is not supported",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }),
                success=False,
                error=f"Language '{language}' is not supported"
            )

        # Validate working directory if specified
        if working_dir:
            working_path = Path(working_dir)
            if not working_path.exists():
                return ToolResult(
                    content=json.dumps({
                        "error": f"Working directory does not exist: {working_dir}",
                        "stdout": "",
                        "stderr": "",
                        "exit_code": -1,
                    }),
                    success=False,
                    error=f"Working directory does not exist: {working_dir}"
                )

        try:
            # Execute the code
            result = await self._execute_code(
                code=code,
                language=language,
                timeout=timeout,
                working_dir=working_dir,
            )

            success = result["exit_code"] == 0 and not result["timed_out"]

            logger.info(
                f"Code execution: language={language}, "
                f"exit_code={result['exit_code']}, "
                f"timed_out={result['timed_out']}"
            )

            return ToolResult(
                content=json.dumps({
                    "language": language,
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "exit_code": result["exit_code"],
                    "timed_out": result["timed_out"],
                    "success": success,
                }),
                success=True,  # Tool executed successfully, even if code failed
            )

        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return ToolResult(
                content=json.dumps({
                    "error": str(e),
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": -1,
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


def create_run_code_tool(
    context: ExecutionContext,
    container: Container,
) -> RunCodeTool:
    """
    Factory function to create run_code tool.

    Args:
        context: Execution context.
        container: DI container for service resolution.

    Returns:
        Configured RunCodeTool instance.
    """
    # Get sandbox directory from config if available
    from app.core.config import Config
    config = container.try_resolve(Config)
    sandbox_dir = None
    if config and hasattr(config, 'sandbox_dir'):
        sandbox_dir = config.sandbox_dir

    return RunCodeTool(
        context=context,
        container=container,
        sandbox_dir=sandbox_dir,
    )
