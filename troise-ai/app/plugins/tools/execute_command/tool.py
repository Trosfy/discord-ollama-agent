"""Execute command tool implementation.

Executes shell commands via the TUI's command execution capability.
Commands are sent to the TUI for execution and results are returned.
Supports command approval for dangerous commands.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.context import ExecutionContext
from app.core.container import Container
from app.core.interfaces.tool import ToolResult

logger = logging.getLogger(__name__)

# Commands that require explicit user approval
DANGEROUS_PATTERNS = [
    "rm ",
    "rm\t",
    "rmdir",
    "sudo ",
    "chmod ",
    "chown ",
    "mv /",
    "cp /",
    "dd ",
    "mkfs",
    "> /dev/",
    ":(){ :|:",  # Fork bomb
    "wget ",
    "curl ",
    "pip install",
    "npm install",
    "apt ",
    "yum ",
    "dnf ",
    "pacman ",
    "git push",
    "git reset --hard",
    "docker rm",
    "docker rmi",
    "kubectl delete",
]


def is_dangerous_command(command: str) -> bool:
    """Check if a command is potentially dangerous.

    Args:
        command: Command string to check.

    Returns:
        True if command matches dangerous patterns.
    """
    cmd_lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in cmd_lower:
            return True
    return False


class ExecuteCommandTool:
    """
    Tool for executing shell commands via TUI.

    Commands are sent to the connected TUI client for execution.
    The TUI handles:
    - Command execution in user's environment
    - Approval prompts for dangerous commands
    - Streaming output back to agent

    This differs from run_code tool:
    - run_code: Executes code files in sandbox
    - execute_command: Runs shell commands in user's environment via TUI
    """

    name = "execute_command"
    description = """Execute a shell command on the user's machine.
Use this when you need to:
- Run git commands (git status, git log, git diff)
- Check system status (ls, cat, pwd, df, du)
- Build or test projects (npm run, cargo build, make)
- Manage files (mkdir, touch, find)

IMPORTANT: Commands run in the user's actual environment.
Dangerous commands (rm, sudo, etc.) will prompt for user approval.
Prefer this over run_code for simple shell operations."""

    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for command execution (optional, defaults to TUI's current directory)"
            },
            "timeout": {
                "type": "integer",
                "description": "Command timeout in seconds (default: 60, max: 300)",
                "default": 60
            },
            "requires_approval": {
                "type": "boolean",
                "description": "Force user approval prompt (auto-detected for dangerous commands)",
                "default": False
            },
        },
        "required": ["command"]
    }

    def __init__(self, context: ExecutionContext, container: Container):
        """
        Initialize the execute command tool.

        Args:
            context: Execution context with TUI connection.
            container: DI container for service resolution.
        """
        self._context = context
        self._container = container

    async def execute(
        self,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a shell command via TUI.

        Args:
            params: Tool parameters (command, working_dir, timeout, requires_approval).
            context: Execution context.

        Returns:
            ToolResult with command output.
        """
        command = params.get("command", "").strip()
        working_dir = params.get("working_dir")
        timeout = min(params.get("timeout", 60), 300)
        force_approval = params.get("requires_approval", False)

        if not command:
            return ToolResult(
                content=json.dumps({
                    "error": "Command is required",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                }),
                success=False,
                error="Command is required"
            )

        # Determine if approval is needed
        requires_approval = force_approval or is_dangerous_command(command)

        try:
            # Request command execution via TUI
            result = await context.execute_command(
                command=command,
                working_dir=working_dir,
                timeout=timeout,
                requires_approval=requires_approval,
            )

            logger.info(
                f"Command execution: cmd={command[:50]}..., "
                f"exit_code={result.get('exit_code', -1)}, "
                f"approval_required={requires_approval}"
            )

            return ToolResult(
                content=json.dumps({
                    "command": command,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("exit_code", -1),
                    "status": result.get("status", "completed"),
                    "working_dir": result.get("working_dir", working_dir),
                }),
                success=result.get("status") != "error",
            )

        except TimeoutError:
            logger.warning(f"Command timed out: {command[:50]}...")
            return ToolResult(
                content=json.dumps({
                    "command": command,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": -1,
                    "status": "timeout",
                }),
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return ToolResult(
                content=json.dumps({
                    "command": command,
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": -1,
                    "status": "error",
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


def create_execute_command_tool(
    context: ExecutionContext,
    container: Container,
) -> ExecuteCommandTool:
    """
    Factory function to create execute_command tool.

    Args:
        context: Execution context with TUI connection.
        container: DI container.

    Returns:
        Configured ExecuteCommandTool instance.
    """
    return ExecuteCommandTool(context=context, container=container)
