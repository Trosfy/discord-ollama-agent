"""Configuration management for TROISE AI."""
import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .interfaces import IConfigProfile

logger = logging.getLogger(__name__)


class ModelPriority(Enum):
    """Priority levels for model eviction."""
    CRITICAL = 1  # Never evict (router model)
    HIGH = 2      # Evict last
    NORMAL = 3    # Default
    LOW = 4       # Evict first


@dataclass
class BackendConfig:
    """Backend configuration for a model."""
    type: str  # ollama, sglang, vllm
    host: str = "http://localhost:11434"
    options: dict = field(default_factory=dict)
    dgx_script: str = None  # Path to start script on DGX


@dataclass
class ModelCapabilities:
    """Model capabilities and configuration."""
    name: str
    backend: BackendConfig
    vram_size_gb: float
    model_type: str = "llm"  # "llm" | "diffusion"
    priority: str = "NORMAL"  # CRITICAL, HIGH, NORMAL, LOW

    # Lifecycle management
    api_managed: bool = True  # True = load/unload via API, False = container-managed

    # Capability flags
    supports_tools: bool = False
    supports_vision: bool = False
    supports_thinking: bool = False

    # Thinking configuration
    thinking_format: str = None  # "boolean" or "level"
    default_thinking_level: str = None  # "low", "medium", "high"

    # Context limits
    context_window: int = 32768

    # Backend-specific options (e.g., {"think": False, "num_ctx": 8192})
    options: dict = field(default_factory=dict)


# =============================================================================
# RAG (Retrieval-Augmented Generation) Configuration
# =============================================================================

@dataclass
class FetchConfig:
    """HTTP fetch configuration for web content retrieval."""
    timeout_seconds: int = 30
    max_content_bytes: int = 5242880  # 5MB
    max_redirects: int = 5
    user_agent: str = "TroiseAI/1.0 (RAG Fetcher)"


@dataclass
class ParsingConfig:
    """HTML parsing configuration."""
    remove_tags: List[str] = field(default_factory=lambda: [
        "script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"
    ])
    extract_title: bool = True
    preserve_links: bool = False


@dataclass
class RAGConfig:
    """RAG (Retrieval-Augmented Generation) configuration."""
    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200
    tokenizer_encoding: str = "cl100k_base"
    separators: List[str] = field(default_factory=lambda: ["\n\n", "\n", ". ", " ", ""])

    # Retrieval
    vector_top_k: int = 7
    max_fetch_tokens: int = 7000

    # Cache
    web_cache_ttl_hours: int = 2
    ttl_by_domain: Dict[str, int] = field(default_factory=dict)

    # Nested configs
    fetch: FetchConfig = field(default_factory=FetchConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)

    @classmethod
    def from_dict(cls, data: Dict) -> "RAGConfig":
        """Create RAGConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        # Handle nested fetch config
        fetch_data = data.get("fetch", {})
        fetch_config = FetchConfig(
            timeout_seconds=fetch_data.get("timeout_seconds", 30),
            max_content_bytes=fetch_data.get("max_content_bytes", 5242880),
            max_redirects=fetch_data.get("max_redirects", 5),
            user_agent=fetch_data.get("user_agent", "TroiseAI/1.0 (RAG Fetcher)"),
        )

        # Handle nested parsing config
        parsing_data = data.get("parsing", {})
        parsing_config = ParsingConfig(
            remove_tags=parsing_data.get("remove_tags", [
                "script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"
            ]),
            extract_title=parsing_data.get("extract_title", True),
            preserve_links=parsing_data.get("preserve_links", False),
        )

        return cls(
            chunk_size=data.get("chunk_size", 1000),
            chunk_overlap=data.get("chunk_overlap", 200),
            tokenizer_encoding=data.get("tokenizer_encoding", "cl100k_base"),
            separators=data.get("separators", ["\n\n", "\n", ". ", " ", ""]),
            vector_top_k=data.get("vector_top_k", 7),
            max_fetch_tokens=data.get("max_fetch_tokens", 7000),
            web_cache_ttl_hours=data.get("web_cache_ttl_hours", 2),
            ttl_by_domain=data.get("ttl_by_domain", {}),
            fetch=fetch_config,
            parsing=parsing_config,
        )


# =============================================================================
# Tools Configuration
# =============================================================================

@dataclass
class ToolsConfig:
    """Tools configuration."""
    # Tools available to ALL agents automatically
    # ask_user removed - agents that need it add explicitly (e.g., agentic_code)
    universal_tools: List[str] = field(default_factory=lambda: [
        "remember", "recall", "web_search", "web_fetch"
    ])

    @classmethod
    def from_dict(cls, data: Dict) -> "ToolsConfig":
        """Create ToolsConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        return cls(
            universal_tools=data.get("universal_tools", [
                "remember", "recall", "web_search", "web_fetch"
            ]),
        )


# =============================================================================
# Session Configuration
# =============================================================================

@dataclass
class SessionConfig:
    """Session configuration."""
    # Max messages to load when resuming a session
    max_history_messages: int = 100
    # Max conversation turns to include in LLM context per request
    max_history_turns: int = 10

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionConfig":
        """Create SessionConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        return cls(
            max_history_messages=data.get("max_history_messages", 100),
            max_history_turns=data.get("max_history_turns", 10),
        )


# =============================================================================
# Skills Configuration
# =============================================================================

@dataclass
class SkillsConfig:
    """Skills configuration."""
    # Max recursion depth for skill-to-skill calls (via agents)
    max_skill_depth: int = 2

    @classmethod
    def from_dict(cls, data: Dict) -> "SkillsConfig":
        """Create SkillsConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        return cls(
            max_skill_depth=data.get("max_skill_depth", 2),
        )


# =============================================================================
# Queue Configuration
# =============================================================================

@dataclass
class QueueConfig:
    """Request queue configuration."""
    # Worker pool
    worker_count: int = 3

    # Timeouts
    default_timeout_seconds: int = 300  # 5 minutes
    skill_timeout_seconds: int = 120    # 2 minutes
    agent_timeout_seconds: int = 600    # 10 minutes
    image_timeout_seconds: int = 900    # 15 minutes for image generation
    timeout_buffer_seconds: int = 60    # Extra buffer for cleanup

    # Visibility and cleanup
    visibility_timeout_seconds: int = 300  # Mark as stuck after this
    image_visibility_timeout_seconds: int = 900  # Match image timeout (no early requeue)
    visibility_check_interval_seconds: int = 30  # Check for stuck requests every 30s
    result_ttl_seconds: int = 300  # Keep results for 5 minutes

    # Retry settings
    max_retries: int = 2  # Max retry attempts for stuck requests

    # Alerting thresholds
    alert_queue_depth: int = 10
    alert_wait_time_seconds: int = 60

    @classmethod
    def from_dict(cls, data: Dict) -> "QueueConfig":
        """Create QueueConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        return cls(
            worker_count=data.get("worker_count", 3),
            default_timeout_seconds=data.get("default_timeout_seconds", 300),
            skill_timeout_seconds=data.get("skill_timeout_seconds", 120),
            agent_timeout_seconds=data.get("agent_timeout_seconds", 600),
            image_timeout_seconds=data.get("image_timeout_seconds", 900),
            timeout_buffer_seconds=data.get("timeout_buffer_seconds", 60),
            visibility_timeout_seconds=data.get("visibility_timeout_seconds", 300),
            image_visibility_timeout_seconds=data.get("image_visibility_timeout_seconds", 900),
            visibility_check_interval_seconds=data.get("visibility_check_interval_seconds", 30),
            result_ttl_seconds=data.get("result_ttl_seconds", 300),
            max_retries=data.get("max_retries", 2),
            alert_queue_depth=data.get("alert_queue_depth", 10),
            alert_wait_time_seconds=data.get("alert_wait_time_seconds", 60),
        )

    def get_timeout_for_type(self, routing_type: str, classification: str = None) -> int:
        """Get timeout based on routing type and optional classification.

        Args:
            routing_type: Type of route - "skill", "agent", or "graph"
            classification: Optional request classification (e.g., "IMAGE")

        Returns:
            Appropriate timeout in seconds.
        """
        if classification == "IMAGE":
            return self.image_timeout_seconds
        if routing_type == "skill":
            return self.skill_timeout_seconds
        elif routing_type == "agent":
            return self.agent_timeout_seconds
        return self.default_timeout_seconds

    def get_visibility_timeout_for_classification(self, classification: str = None) -> int:
        """Get visibility timeout based on classification.

        Args:
            classification: Request classification (e.g., "IMAGE", "CODE", "GENERAL")

        Returns:
            Visibility timeout in seconds.
        """
        if classification == "IMAGE":
            return self.image_visibility_timeout_seconds
        return self.visibility_timeout_seconds


# =============================================================================
# Circuit Breaker Configuration
# =============================================================================

@dataclass
class CircuitBreakerYAMLConfig:
    """Circuit breaker configuration loaded from YAML.

    Note: This is the YAML-loaded config. The actual CircuitBreakerConfig
    used by the CircuitBreaker class is in app/core/circuit_breaker.py.
    """
    # Thresholds
    failure_threshold: int = 10  # Consecutive failures before OPEN
    success_threshold: int = 5   # Successes in HALF_OPEN before CLOSED
    open_timeout_seconds: float = 60.0  # Time in OPEN before HALF_OPEN

    # Rate-based triggering
    failure_rate_threshold: float = 0.5  # 50% failure rate triggers OPEN
    sample_window_seconds: float = 60.0  # Window for rate calculation

    # HALF_OPEN settings
    half_open_max_requests: int = 3  # Max requests to test in HALF_OPEN

    @classmethod
    def from_dict(cls, data: Dict) -> "CircuitBreakerYAMLConfig":
        """Create CircuitBreakerYAMLConfig from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        return cls(
            failure_threshold=data.get("failure_threshold", 10),
            success_threshold=data.get("success_threshold", 5),
            open_timeout_seconds=data.get("open_timeout_seconds", 60.0),
            failure_rate_threshold=data.get("failure_rate_threshold", 0.5),
            sample_window_seconds=data.get("sample_window_seconds", 60.0),
            half_open_max_requests=data.get("half_open_max_requests", 3),
        )


class Config:
    """
    Configuration manager for TROISE AI.

    Loads profile from environment variable or config file.
    Profiles define which models are available and how they map to tasks.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        self._config_path = Path(config_path)
        self._data: Dict = {}
        self._profile: "IConfigProfile" = None
        self._backends: Dict[str, BackendConfig] = {}
        self._rag: RAGConfig = None
        self._session: SessionConfig = None
        self._skills: SkillsConfig = None
        self._tools: ToolsConfig = None
        self._queue: QueueConfig = None
        self._circuit_breaker: CircuitBreakerYAMLConfig = None

        self._load_config()
        self._load_backends()
        self._load_profile()
        self._load_rag_config()
        self._load_session_config()
        self._load_tools_config()
        self._load_skills_config()
        self._load_queue_config()
        self._load_circuit_breaker_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        if self._config_path.exists():
            self._data = yaml.safe_load(self._config_path.read_text())
        else:
            logger.warning(f"Config file not found: {self._config_path}, using defaults")
            self._data = {"active_profile": "balanced"}

    def _load_backends(self):
        """Load backend configurations.

        Environment variables override YAML settings for hosts:
        - OLLAMA_HOST overrides backends.ollama.host
        - SGLANG_ENDPOINT overrides backends.sglang.host
        - VLLM_HOST overrides backends.vllm.host
        - COMFYUI_HOST overrides backends.comfyui.host
        """
        backends_config = self._data.get("backends", {})

        # Environment variable overrides for hosts
        host_overrides = {
            "ollama": os.getenv("OLLAMA_HOST"),
            "sglang": os.getenv("SGLANG_ENDPOINT"),
            "vllm": os.getenv("VLLM_HOST"),
            "comfyui": os.getenv("COMFYUI_HOST"),
        }

        for name, config in backends_config.items():
            # Use env var if set, otherwise use YAML config, otherwise default
            yaml_host = config.get("host", "http://localhost:11434")
            host = host_overrides.get(name) or yaml_host
            if host_overrides.get(name):
                logger.info(f"Backend '{name}' host overridden by env var: {host}")
            self._backends[name] = BackendConfig(
                type=config.get("type", name),
                host=host,
                options=config.get("options", {}),
                dgx_script=config.get("dgx_script")
            )

        # Default Ollama backend if none configured
        if "ollama" not in self._backends:
            self._backends["ollama"] = BackendConfig(
                type="ollama",
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
            )

    def _load_profile(self):
        """Load the active profile."""
        from .profiles import get_profile

        # Priority: env var > config file > default
        name = os.getenv("TROISE_PROFILE") or self._data.get("active_profile", "balanced")
        self._profile = get_profile(name)
        logger.info(f"Loaded profile: {name}")

    def _load_rag_config(self):
        """Load RAG configuration."""
        rag_data = self._data.get("rag", {})
        self._rag = RAGConfig.from_dict(rag_data)
        logger.info(f"Loaded RAG config: chunk_size={self._rag.chunk_size}, encoding={self._rag.tokenizer_encoding}")

    def _load_session_config(self):
        """Load session configuration."""
        session_data = self._data.get("session", {})
        self._session = SessionConfig.from_dict(session_data)
        logger.info(f"Loaded session config: max_history_messages={self._session.max_history_messages}, max_history_turns={self._session.max_history_turns}")

    def _load_tools_config(self):
        """Load tools configuration."""
        tools_data = self._data.get("tools", {})
        self._tools = ToolsConfig.from_dict(tools_data)
        logger.info(f"Loaded tools config: universal_tools={self._tools.universal_tools}")

    def _load_skills_config(self):
        """Load skills configuration."""
        skills_data = self._data.get("skills", {})
        self._skills = SkillsConfig.from_dict(skills_data)
        logger.info(f"Loaded skills config: max_skill_depth={self._skills.max_skill_depth}")

    def _load_queue_config(self):
        """Load queue configuration."""
        queue_data = self._data.get("queue", {})
        self._queue = QueueConfig.from_dict(queue_data)
        logger.info(f"Loaded queue config: workers={self._queue.worker_count}")

    def _load_circuit_breaker_config(self):
        """Load circuit breaker configuration."""
        cb_data = self._data.get("circuit_breaker", {})
        self._circuit_breaker = CircuitBreakerYAMLConfig.from_dict(cb_data)
        logger.info(
            f"Loaded circuit breaker config: "
            f"failure_threshold={self._circuit_breaker.failure_threshold}, "
            f"open_timeout={self._circuit_breaker.open_timeout_seconds}s"
        )

    @property
    def circuit_breaker(self) -> CircuitBreakerYAMLConfig:
        """Get circuit breaker configuration."""
        return self._circuit_breaker

    @property
    def queue(self) -> QueueConfig:
        """Get queue configuration."""
        return self._queue

    @property
    def rag(self) -> RAGConfig:
        """Get RAG (Retrieval-Augmented Generation) configuration."""
        return self._rag

    @property
    def session(self) -> SessionConfig:
        """Get session configuration."""
        return self._session

    @property
    def tools(self) -> ToolsConfig:
        """Get tools configuration."""
        return self._tools

    @property
    def skills(self) -> SkillsConfig:
        """Get skills configuration."""
        return self._skills

    @property
    def profile(self) -> "IConfigProfile":
        """Get the active profile."""
        return self._profile

    @property
    def backends(self) -> Dict[str, BackendConfig]:
        """Get backend configurations."""
        return self._backends

    @property
    def dgx_config(self) -> Dict:
        """Get DGX SSH configuration."""
        return self._data.get("dgx", {})

    @property
    def vault_path(self) -> str:
        """Get Obsidian vault path."""
        return os.getenv("TROISE_VAULT_PATH", self._data.get("vault_path", "/home/trosfy/obsidian-vault"))

    @property
    def execution_timeout(self) -> float:
        """Get execution timeout in seconds (default: 10 minutes)."""
        env_val = os.getenv("TROISE_EXECUTION_TIMEOUT")
        if env_val:
            return float(env_val)
        return float(self._data.get("execution_timeout", 600.0))

    def switch_profile(self, name: str):
        """Switch to a different profile at runtime."""
        from .profiles import get_profile

        self._profile = get_profile(name)
        self._data["active_profile"] = name
        logger.info(f"Switched to profile: {name}")

    def get_model_for_task(self, task: str) -> str:
        """Get the appropriate model for a task type.

        Task types aligned with router classifications:
        - route/routing: Fast model for routing classification
        - general: GENERAL classification - general conversation
        - research: RESEARCH classification - deep research
        - code: CODE classification - code generation/review
        - braindump: BRAINDUMP classification - thought capture
        - vision: Vision/OCR tasks
        - embedding: Embedding generation
        - analysis: File analysis (preprocessing)
        - extraction: Artifact extraction (postprocessing)
        """
        task_map = {
            # Routing
            "route": self._profile.router_model,
            "routing": self._profile.router_model,
            # Agent tasks (aligned with router classifications)
            "general": self._profile.general_model,
            "research": self._profile.research_model,
            "code": self._profile.code_model,
            "braindump": self._profile.braindump_model,
            # Utility tasks
            "vision": self._profile.vision_model,
            "embedding": self._profile.embedding_model,
            # Preprocessing/Postprocessing tasks
            "analysis": self._profile.general_model,
            "extraction": self._profile.general_model,
        }
        model = task_map.get(task, self._profile.general_model)
        logger.debug(f"Model for task '{task}': {model}")
        return model

    def get_backend_for_model(self, model_id: str) -> Optional[BackendConfig]:
        """Get backend configuration for a specific model."""
        # Find model in profile
        for model in self._profile.available_models:
            if model.name == model_id:
                return model.backend
        return self._backends.get("ollama")

    def get_model_capabilities(self, model_id: str) -> Optional[ModelCapabilities]:
        """Get capabilities for a specific model."""
        for model in self._profile.available_models:
            if model.name == model_id:
                return model
        return None
