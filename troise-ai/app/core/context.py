"""Execution context for skills and agents."""
import asyncio
import uuid
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket
    from .interfaces.vram_orchestrator import IVRAMOrchestrator

from .exceptions import AgentCancelled


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserConfig:
    """User-provided configuration overrides from web-service.

    Allows users to override default model selection and agent behavior
    through the web interface. When model is specified, routing is bypassed
    (DIRECT route) and the specified model is used for execution.

    Attributes:
        model: Direct model ID to use (bypasses router classification).
        temperature: Override agent's default temperature.
        thinking_enabled: Enable extended reasoning (if model supports it).
        enable_web_search: Toggle web search capability.
    """
    model: Optional[str] = None
    temperature: Optional[float] = None
    thinking_enabled: Optional[bool] = None
    enable_web_search: Optional[bool] = None


@dataclass
class UserProfile:
    """User profile loaded from Obsidian and DynamoDB."""
    user_id: str

    # From Obsidian ai-preferences.yaml
    communication_style: str = "balanced"
    response_length: str = "adaptive"
    use_emoji: bool = False
    formality: str = "casual"
    code_style: str = "functional"
    explicit_expertise: List[str] = field(default_factory=list)

    # From Obsidian ai-learned.yaml
    learned_expertise: List[Dict] = field(default_factory=list)
    learned_patterns: List[Dict] = field(default_factory=list)

    # From DynamoDB (temporary inferences)
    active_inferences: List[Dict] = field(default_factory=list)

    # Context
    current_project: Optional[str] = None

    def get_all_expertise(self) -> List[str]:
        """Get combined expertise from all sources."""
        expertise = set(self.explicit_expertise)
        expertise.update(e.get("skill", "") for e in self.learned_expertise)
        expertise.update(
            i["key"] for i in self.active_inferences
            if i.get("category") == "expertise"
        )
        return list(expertise)

    def get_personalization_context(self) -> str:
        """Generate prompt context from profile."""
        parts = []

        if self.communication_style != "balanced":
            parts.append(f"User prefers {self.communication_style} communication style.")

        if self.formality != "casual":
            parts.append(f"Use {self.formality} tone.")

        all_expertise = self.get_all_expertise()
        if all_expertise:
            parts.append(f"User has expertise in: {', '.join(all_expertise)}. Skip basic explanations in these areas.")

        if self.current_project:
            parts.append(f"Currently working on: {self.current_project}")

        if not self.use_emoji:
            parts.append("User prefers no emoji in responses.")

        if self.code_style:
            parts.append(f"User prefers {self.code_style} code style.")

        return "\n".join(parts) if parts else ""


@dataclass
class ExecutionContext:
    """
    Context for skill/agent execution.

    Provides access to:
    - User information and preferences
    - Interface-specific context
    - Conversation history
    - WebSocket for streaming/questions
    - Cancellation support
    - Preprocessing results (file analysis, sanitized intent)
    """
    user_id: str
    session_id: str
    interface: str  # "discord", "web", "cli", "api"
    conversation_history: List[Message] = field(default_factory=list)
    user_profile: UserProfile = None

    # Interface-specific context
    discord_channel_id: Optional[str] = None
    discord_guild_id: Optional[str] = None
    discord_message_channel_id: Optional[str] = None  # Original channel for reactions
    discord_message_id: Optional[str] = None  # Original message ID for reactions

    # Request tracking (for Discord streaming state)
    request_id: Optional[str] = None

    # User configuration overrides (from web-service)
    user_config: Optional[UserConfig] = None

    # WebSocket for streaming and questions
    websocket: Optional["WebSocket"] = None

    # Cancellation support
    cancellation_token: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled_reason: Optional[str] = None

    # Pending questions (for ask_user tool)
    pending_questions: Dict[str, asyncio.Future] = field(default_factory=dict)

    # Pending commands (for execute_command tool - CLI/TUI)
    pending_commands: Dict[str, asyncio.Future] = field(default_factory=dict)

    # Agent name (for tracking who learned what)
    agent_name: Optional[str] = None

    # Last user message (for evidence in inferences)
    last_user_message: Optional[str] = None

    # Skill recursion guards (for use_skill tool)
    skill_call_depth: int = 0
    max_skill_depth: int = 2
    called_skills: Set[str] = field(default_factory=set)

    # =========================================================================
    # Graph Execution Context
    # =========================================================================

    # Graph domain for prompt variant selection ('code', 'research', 'braindump')
    graph_domain: Optional[str] = None

    # Graph state (set by GraphExecutor during graph execution)
    graph_state: Optional[Any] = None  # GraphState instance

    # VRAMOrchestrator (set by executor before graph execution, used by SwarmNode)
    vram_orchestrator: Optional["IVRAMOrchestrator"] = None

    # PromptComposer (set by executor before graph execution, used by SwarmNode)
    prompt_composer: Optional[Any] = None  # PromptComposer instance

    # Collected sources from web_fetch (captured by SourceCaptureHook)
    # Only web_fetch URLs are captured - these are actually read sources
    collected_sources: List[Dict[str, str]] = field(default_factory=list)

    # Generated images from generate_image tool (captured by ImageCaptureHook)
    # List of dicts: {"file_id": str, "storage_key": str, "width": int, "height": int, ...}
    generated_images: List[Dict[str, Any]] = field(default_factory=list)

    # Tool call tracking (incremented after successful calls only)
    tool_call_counts: Dict[str, int] = field(default_factory=dict)

    # Tool call limits (tool_name -> max_calls, e.g. {"web_fetch": 3})
    tool_call_limits: Dict[str, int] = field(default_factory=dict)

    # =========================================================================
    # Preprocessing Context (session-scoped)
    # =========================================================================

    # Session-scoped file storage (prevents data collision between sessions)
    file_store: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # File analyses from FileAnalysisAgent
    file_analyses: List[Any] = field(default_factory=list)  # List[FileAnalysis]

    # System context (pre-analyzed file info for agent prompt)
    system_context: str = ""

    # Clean user intent (from PromptSanitizer)
    clean_intent: Optional[str] = None

    # Action type for execution (create, modify, analyze, query)
    action_type: str = "query"

    # Expected output filename (from preprocessing)
    expected_filename: Optional[str] = None

    # Raw file contents (for modify actions)
    raw_file_contents: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.user_profile is None:
            self.user_profile = UserProfile(user_id=self.user_id)

    # Cancellation support

    def cancel(self, reason: str = "User cancelled"):
        """Signal cancellation to agent."""
        self.cancelled_reason = reason
        self.cancellation_token.set()

    async def check_cancelled(self):
        """Check if cancelled, raise if so. Call periodically in tools."""
        if self.cancellation_token.is_set():
            raise AgentCancelled(self.cancelled_reason)

    # Question support for ask_user tool

    async def request_user_input(
        self,
        question: str,
        options: List[str] = None,
        timeout: int = 300
    ) -> str:
        """Send question to user, wait for response."""
        if not self.websocket:
            return "[No WebSocket connection - cannot ask user]"

        # Import here to avoid circular dependency
        from app.adapters.websocket.factory import get_message_builder

        request_id = str(uuid.uuid4())

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.pending_questions[request_id] = future

        # Use interface-appropriate builder for message construction
        builder = get_message_builder(self)
        message = builder.build_question(question, options, request_id, self)
        await self.websocket.send_json(message)

        try:
            # Wait for response with timeout
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.pending_questions.pop(request_id, None)

    async def handle_user_answer(self, request_id: str, answer: str):
        """Called when user responds to a question."""
        if request_id in self.pending_questions:
            self.pending_questions[request_id].set_result(answer)

    # Skill recursion support for use_skill tool

    def can_call_skill(self, skill_name: str) -> bool:
        """
        Check if a skill can be called from current context.

        Prevents:
        - Infinite recursion (depth limit)
        - Cycles (same skill called again)

        Args:
            skill_name: Name of the skill to call.

        Returns:
            True if the skill can be called, False otherwise.
        """
        return (
            self.skill_call_depth < self.max_skill_depth
            and skill_name not in self.called_skills
        )

    def with_skill_call(self, skill_name: str) -> "ExecutionContext":
        """
        Create a child context for calling a skill.

        Increments depth and adds skill to called set.

        Args:
            skill_name: Name of the skill being called.

        Returns:
            New ExecutionContext with updated recursion tracking.
        """
        return replace(
            self,
            skill_call_depth=self.skill_call_depth + 1,
            called_skills=self.called_skills | {skill_name},
        )

    # Tool call limiting support

    def can_call_tool(self, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if a tool can be called (limit not exceeded).

        Args:
            tool_name: Name of the tool to check.

        Returns:
            Tuple of (can_call, error_message).
            If can_call is False, error_message explains why.
        """
        limit = self.tool_call_limits.get(tool_name)
        if limit is None:
            return True, None

        current = self.tool_call_counts.get(tool_name, 0)
        if current >= limit:
            return False, f"Tool '{tool_name}' reached limit of {limit} successful calls."
        return True, None

    def record_successful_tool_call(self, tool_name: str) -> None:
        """
        Record a successful tool call.

        Only successful calls count toward limits.

        Args:
            tool_name: Name of the tool that succeeded.
        """
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1

    def with_tool_limits(self, limits: Dict[str, int]) -> "ExecutionContext":
        """
        Create a child context with fresh tool counts and specified limits.

        Used for isolated sub-agents (e.g., research_topics per-topic agents)
        that need their own tool call tracking.

        Args:
            limits: Tool name to max calls mapping (e.g., {"web_fetch": 5}).

        Returns:
            New ExecutionContext with reset counts and specified limits.
        """
        return replace(
            self,
            tool_call_counts={},  # Reset counts for child
            tool_call_limits=limits,
        )

    # Command execution support for execute_command tool (CLI/TUI)

    async def execute_command(
        self,
        command: str,
        working_dir: str = None,
        timeout: int = 60,
        requires_approval: bool = False,
    ) -> Dict[str, Any]:
        """
        Request command execution via TUI.

        Sends command to the TUI client for execution.
        TUI handles approval prompts and actual execution.

        Args:
            command: Shell command to execute.
            working_dir: Working directory (optional).
            timeout: Timeout in seconds.
            requires_approval: Whether to prompt user for approval.

        Returns:
            Dict with stdout, stderr, exit_code, status.
        """
        if not self.websocket:
            return {
                "stdout": "",
                "stderr": "No WebSocket connection - cannot execute command",
                "exit_code": -1,
                "status": "error",
            }

        # Import here to avoid circular dependency
        from app.adapters.websocket.factory import get_message_builder

        request_id = str(uuid.uuid4())

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.pending_commands[request_id] = future

        # Build and send command execution request
        builder = get_message_builder(self)
        message = builder.build_execute_command(
            command=command,
            request_id=request_id,
            working_dir=working_dir,
            requires_approval=requires_approval,
            context=self,
        )
        await self.websocket.send_json(message)

        try:
            # Wait for response with timeout
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Command timed out after {timeout} seconds")
        finally:
            self.pending_commands.pop(request_id, None)

    async def handle_command_result(
        self,
        request_id: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        status: str = "completed",
    ):
        """Called when TUI sends back command execution result."""
        if request_id in self.pending_commands:
            self.pending_commands[request_id].set_result({
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "status": status,
            })
