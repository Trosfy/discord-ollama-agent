"""Global application settings with profile support."""
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.profiles.interface import IConfigProfile


class BackendConfig(BaseModel):
    """Backend specification with options."""
    type: str  # "ollama", "tensorrt-llm", "vllm"
    endpoint: Optional[str] = None  # Optional custom endpoint
    options: Dict[str, Any] = {}  # Backend-specific options


class ModelCapabilities(BaseModel):
    """Model capability flags."""
    name: str
    backend: BackendConfig  # Backend specification
    supports_vision: bool = False
    supports_thinking: bool = False
    supports_tools: bool = True  # Most models support tools
    context_window: Optional[int] = None  # For future use
    thinking_format: str = "boolean"  # "boolean" (think=True) or "level" (ThinkLevel="high")
    default_thinking_level: str = "high"  # For models with thinking_format="level"
    vram_size_gb: float = 20.0  # Estimated VRAM usage in GB
    priority: str = "NORMAL"  # CRITICAL, HIGH, NORMAL, LOW (for eviction)


# ============================================================================
# Profile Management (Dependency Injection for SOLID compliance)
# ============================================================================

# Global active profile (set at startup in main.py)
_active_profile: Optional['IConfigProfile'] = None  # type: ignore


def set_active_profile(profile: 'IConfigProfile') -> None:  # type: ignore
    """
    Set active configuration profile (called at startup).

    Args:
        profile: Profile instance implementing IConfigProfile
    """
    global _active_profile
    _active_profile = profile


def get_active_profile() -> 'IConfigProfile':  # type: ignore
    """
    Get active configuration profile.

    Returns:
        Active profile instance

    Raises:
        RuntimeError: If no profile has been set
    """
    if _active_profile is None:
        raise RuntimeError(
            "No active profile set. Call set_active_profile() at startup."
        )
    return _active_profile


def switch_profile(profile_name: str) -> None:
    """
    Switch active profile at runtime.

    Low-level operation used by ProfileManager for circuit breaker fallback.

    Args:
        profile_name: Profile to switch to

    Raises:
        ValueError: If profile_name is invalid
    """
    import logging_client
    from app.config.profiles.factory import ProfileFactory

    logger = logging_client.setup_logger('fastapi')

    current_profile = get_active_profile()
    logger.info(f"🔄 Switching profile: {current_profile.profile_name} → {profile_name}")

    new_profile = ProfileFactory.load_profile(profile_name)
    set_active_profile(new_profile)

    # Sync VRAM orchestrator limits with new profile
    try:
        from app.services.vram import get_orchestrator
        orchestrator = get_orchestrator()
        orchestrator.update_limits(
            soft_limit_gb=new_profile.vram_soft_limit_gb,
            hard_limit_gb=new_profile.vram_hard_limit_gb
        )
    except Exception as e:
        logger.warning(f"⚠️  Could not sync orchestrator limits: {e}")

    logger.info(f"✅ Profile switched to: {profile_name}")


# ============================================================================
# Legacy Model List (DEPRECATED - kept for backward compatibility)
# ============================================================================
# NOTE: This list is no longer used. Model roster is now determined by active
# profile. Will be removed in future version.

_AVAILABLE_MODELS: List[ModelCapabilities] = [
    # === GENERAL PURPOSE / ROUTER MODELS ===
    ModelCapabilities(
        name="gpt-oss:20b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
        supports_tools=True,
        supports_thinking=True,
        thinking_format="level",  # Uses ThinkLevel parameter (high/medium/low)
        default_thinking_level="high",
        vram_size_gb=13.0,  # Actual disk size from ollama list
        priority="HIGH"  # Router model, keep loaded
    ),
    ModelCapabilities(
        name="gpt-oss:120b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=True,
        supports_thinking=True,
        thinking_format="level",  # Uses ThinkLevel parameter
        default_thinking_level="high",
        vram_size_gb=65.0,  # Actual disk size from ollama list
        priority="LOW"  # Very large, evict when needed
    ),
    ModelCapabilities(
        name="nemotron-3-nano:30b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "15m"}),
        supports_tools=False,  # Simple template, no tool support
        supports_thinking=False,
        vram_size_gb=24.0,  # Actual disk size from ollama list
        priority="NORMAL"
    ),

    # === CODE GENERATION MODELS ===
    ModelCapabilities(
        name="rnj-1:8b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
        supports_tools=True,  # Llama-3 XML style tool calling
        supports_thinking=False,
        supports_vision=False,
        vram_size_gb=5.1,  # Actual disk size from ollama list
        priority="HIGH"  # Fast code model, keep loaded
    ),
    ModelCapabilities(
        name="ministral-3:14b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "20m"}),
        supports_vision=True,  # Model description indicates vision support
        supports_tools=True,  # Mistral style tool calling
        supports_thinking=False,
        vram_size_gb=9.1,  # Actual disk size from ollama list
        priority="NORMAL"
    ),
    ModelCapabilities(
        name="devstral-small-2:24b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "20m"}),
        supports_tools=True,  # Mistral style tool calling
        supports_thinking=False,
        supports_vision=False,
        vram_size_gb=15.0,  # Actual disk size from ollama list
        priority="NORMAL"
    ),
    ModelCapabilities(
        name="devstral-2:123b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "5m"}),
        supports_tools=True,  # Mistral style tool calling
        supports_thinking=False,
        supports_vision=False,
        vram_size_gb=74.0,  # Actual disk size from ollama list
        priority="LOW"  # Very large model, evict when needed
    ),

    # === REASONING MODELS ===
    ModelCapabilities(
        name="deepseek-r1:70b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
        supports_tools=False,  # No tool support, focused on reasoning
        supports_thinking=True,  # Uses explicit <think> tags
        thinking_format="boolean",  # Boolean think parameter
        vram_size_gb=42.0,  # Actual disk size from ollama list
        priority="LOW"  # Large reasoning model, evict when needed
    ),

    # === SPECIALIZED MODELS ===
    ModelCapabilities(
        name="deepseek-ocr:3b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
        supports_vision=True,
        supports_tools=False,
        supports_thinking=False,
        vram_size_gb=6.7,  # Actual disk size from ollama list
        priority="LOW"  # Small OCR model, can evict easily
    ),
    ModelCapabilities(
        name="qwen3-embedding:4b",
        backend=BackendConfig(type="ollama", options={"keep_alive": "60m"}),
        supports_vision=False,
        supports_tools=False,
        supports_thinking=False,
        vram_size_gb=2.5,  # Actual disk size from ollama list
        priority="LOW"  # Embedding model, can evict easily
    ),
]


def get_model_capabilities(model_name: str) -> Optional[ModelCapabilities]:
    """
    Get capabilities for a model by name.

    Lookup order:
    1. Active profile (performance/balanced/conservative)
    2. Default model registry (common Ollama models)
    3. Generic Ollama capabilities (if no slash in name)
    4. None (for external backends like SGLang)

    Args:
        model_name: Model identifier

    Returns:
        ModelCapabilities if found, None for unknown external backends
    """
    # 1. Check active profile first
    for model in get_active_profile().available_models:
        if model.name == model_name:
            return model

    # 2. Check default model registry
    from app.config.profiles.default import get_default_model_capabilities
    default_caps = get_default_model_capabilities(model_name)
    if default_caps:
        return default_caps

    # 3. Generate generic Ollama capabilities as last resort
    if "/" not in model_name:
        from app.config.profiles.default import get_generic_ollama_capabilities
        return get_generic_ollama_capabilities(model_name)

    # 4. External backend (SGLang) - must be in profile
    return None


def get_available_model_names() -> List[str]:
    """
    Get list of all available model names (reads from active profile).

    Returns:
        List of model names in active profile
    """
    return [model.name for model in get_active_profile().available_models]


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    # Service Info
    APP_NAME: str = "Discord-Trollama Agent"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # DynamoDB
    DYNAMODB_ENDPOINT: str = "http://dynamodb-local:8000"
    DYNAMODB_REGION: str = "us-east-1"
    DYNAMODB_ACCESS_KEY: str = "fake"
    DYNAMODB_SECRET_KEY: str = "fake"

    # Ollama
    OLLAMA_HOST: str = "http://host.docker.internal:11434"
    OLLAMA_DEFAULT_MODEL: str = "gpt-oss:20b"
    OLLAMA_REQUEST_TIMEOUT: int = 300  # 5 minutes
    OLLAMA_KEEP_ALIVE: int = 1800  # Default keep_alive (30 minutes) - overridden by per-model settings

    # Multi-Backend Support
    TENSORRT_HOST: Optional[str] = None  # TensorRT-LLM endpoint (e.g., "http://localhost:8000")
    VLLM_HOST: Optional[str] = None      # vLLM endpoint (e.g., "http://localhost:8001")
    SGLANG_ENDPOINT: Optional[str] = "http://sglang-server:30000"  # SGLang endpoint

    # Router Settings (now dynamic via profile)
    # These are @property methods below - values come from active profile
    DEFAULT_TEMPERATURE: float = 0.2  # Default temperature for LLM generation (lower = more deterministic)

    # Queue Settings
    MAX_QUEUE_SIZE: int = 50
    QUEUE_TIMEOUT_SECONDS: int = 300
    VISIBILITY_TIMEOUT: int = 1200  # 20 minutes (handles long-running requests like chart analysis)
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # seconds

    # Token Settings
    MAX_CONTEXT_TOKENS: int = 10000
    DEFAULT_SUMMARIZATION_THRESHOLD: int = 9000
    FREE_TIER_WEEKLY_BUDGET: int = 100000
    ADMIN_TIER_WEEKLY_BUDGET: int = 500000
    DISABLE_TOKEN_BUDGET: bool = True  # Set to False to enforce token budgets

    # Discord
    DISCORD_MESSAGE_MAX_LENGTH: int = 2000

    # Streaming Settings
    ENABLE_STREAMING: bool = True  # Re-enabled with robust validation
    STREAM_CHUNK_INTERVAL: float = 1.1  # Update interval in seconds (Discord limit: 5 req/5s = 1 req/s, use 1.1s for safety)
    MAX_STREAM_CHUNK_SIZE: int = 1900  # Max Discord message length
    STREAM_BACKOFF_MULTIPLIER: float = 2.0  # Exponential backoff multiplier on rate limit

    # File Handling & OCR
    MAX_FILE_SIZE_MB: int = 10  # Maximum upload size in MB
    ALLOWED_FILE_TYPES: List[str] = [
        # Images
        'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
        # Text & Documents
        'text/plain', 'text/markdown', 'text/csv', 'application/pdf',
        # Code files
        'text/x-python', 'application/x-python-code',  # Python
        'text/javascript', 'application/javascript',    # JavaScript
        'text/x-java', 'text/x-java-source',           # Java
        'text/x-c', 'text/x-c++',                      # C/C++
        'text/x-rust',                                 # Rust
        'text/x-go',                                   # Go
        'text/typescript',                             # TypeScript
        'text/html', 'text/css',                       # HTML/CSS
        'application/json', 'application/xml',         # JSON/XML
        'text/x-yaml', 'application/x-yaml',           # YAML
        'text/x-shellscript', 'application/x-sh'       # Shell scripts
    ]
    ALLOWED_CODE_EXTENSIONS: List[str] = [
        '.py', '.js', '.ts', '.tsx', '.jsx',           # Python, JS, TS, React
        '.java', '.c', '.cpp', '.h', '.hpp',           # Java, C/C++
        '.rs', '.go', '.rb', '.php', '.swift',         # Rust, Go, Ruby, PHP, Swift
        '.html', '.css', '.scss', '.sass',             # Web
        '.json', '.yaml', '.yml', '.toml', '.xml',     # Config/Data
        '.sh', '.bash', '.zsh', '.fish',               # Shell
        '.sql', '.graphql', '.proto'                   # Database/API
    ]
    ARTIFACT_TTL_HOURS: int = 12  # Artifact storage time (hours)
    UPLOAD_CLEANUP_HOURS: int = 1  # Temp upload file cleanup time (hours)
    TEMP_UPLOAD_DIR: str = "/tmp/discord-bot-uploads"
    TEMP_ARTIFACT_DIR: str = "/tmp/discord-bot-artifacts"

    # Embedding & RAG Settings
    EMBEDDING_DIMENSION: int = 1024  # Dimension of embedding vectors (qwen3-embedding:4b)
    VECTOR_CACHE_TTL_HOURS: int = 2  # Cache duration for webpage chunks (hours)
    VECTOR_TOP_K: int = 7  # Number of most similar chunks to retrieve (7 × 1K = ~7K tokens per fetch)
    CHUNK_SIZE: int = 1000  # Tokens per chunk (LangChain)
    CHUNK_OVERLAP: int = 500  # Token overlap between chunks (50% for better context preservation)

    # Maintenance
    MAINTENANCE_MODE: bool = False  # Soft maintenance (still queue)
    MAINTENANCE_MODE_HARD: bool = False  # Hard maintenance (reject new)
    MAINTENANCE_MESSAGE: str = "🔧 Bot is under maintenance. Your request has been queued."
    MAINTENANCE_MESSAGE_HARD: str = "🚫 Bot is under emergency maintenance. Please try again later."

    # Available Models (now dynamic via profile - see @property below)

    # Internal API Security (for service-to-service communication)
    INTERNAL_API_KEY: str = "change-this-in-production"  # Used for /internal/* endpoints

    # Health Check
    HEALTH_CHECK_INTERVAL: int = 30  # seconds

    # VRAM Orchestrator (limits now dynamic via profile - see @property below)
    VRAM_ENABLE_ORCHESTRATOR: bool = True  # Enable VRAM orchestration

    # PSI-based Proactive Eviction (prevents earlyoom kills)
    VRAM_PSI_WARNING_THRESHOLD: float = 10.0   # PSI full_avg10 > 10% - evict LOW priority
    VRAM_PSI_CRITICAL_THRESHOLD: float = 15.0  # PSI full_avg10 > 15% - evict NORMAL priority

    # Circuit Breaker Settings (prevents crash loops)
    VRAM_CIRCUIT_BREAKER_ENABLED: bool = True  # Enable circuit breaker
    VRAM_CRASH_THRESHOLD: int = 2  # Number of crashes to trigger circuit breaker
    VRAM_CRASH_WINDOW_SECONDS: int = 300  # Time window for crash tracking (5 minutes)
    VRAM_CIRCUIT_BREAKER_BUFFER_GB: float = 20.0  # Extra headroom when circuit breaker triggers

    # VRAM Management Strategy
    VRAM_CONSERVATIVE_MODE: bool = False  # Conservative profile (16-32GB): force-unload after each request | Performance/Balanced profiles (128GB): trust keep_alive
    VRAM_PROFILE: str = "performance"  # Profile name: "conservative" (16-32GB) | "performance" (128GB, SGLang) | "balanced" (128GB, Ollama)

    # ========================================================================
    # Dynamic Properties (Read from Active Profile)
    # ========================================================================

    @property
    def AVAILABLE_MODELS(self) -> List[ModelCapabilities]:
        """Get available models from active profile."""
        return get_active_profile().available_models

    @property
    def VRAM_SOFT_LIMIT_GB(self) -> float:
        """Get soft VRAM limit from active profile."""
        return get_active_profile().vram_soft_limit_gb

    @property
    def VRAM_HARD_LIMIT_GB(self) -> float:
        """Get hard VRAM limit from active profile."""
        return get_active_profile().vram_hard_limit_gb

    @property
    def ROUTER_MODEL(self) -> str:
        """Get router model from active profile."""
        return get_active_profile().router_model

    @property
    def SIMPLE_CODER_MODEL(self) -> str:
        """Get simple coder model from active profile."""
        return get_active_profile().simple_coder_model

    @property
    def COMPLEX_CODER_MODEL(self) -> str:
        """Get complex coder model from active profile."""
        return get_active_profile().complex_coder_model

    @property
    def REASONING_MODEL(self) -> str:
        """Get reasoning model from active profile."""
        return get_active_profile().reasoning_model

    @property
    def RESEARCH_MODEL(self) -> str:
        """Get research model from active profile."""
        return get_active_profile().research_model

    @property
    def MATH_MODEL(self) -> str:
        """Get math model from active profile."""
        return get_active_profile().math_model

    @property
    def OCR_MODEL(self) -> str:
        """Get OCR/vision model from active profile."""
        return get_active_profile().vision_model

    @property
    def EMBEDDING_MODEL(self) -> str:
        """Get embedding model from active profile."""
        return get_active_profile().embedding_model

    @property
    def OLLAMA_SUMMARIZATION_MODEL(self) -> str:
        """Get summarization model from active profile."""
        return get_active_profile().summarization_model

    # NOTE: POST_PROCESSING_OUTPUT_ARTIFACT_MODEL removed
    # Now uses profile.artifact_extraction_model via PreferenceResolver
    # @property
    # def POST_PROCESSING_OUTPUT_ARTIFACT_MODEL(self) -> str:
    #     """DEPRECATED: Use profile.artifact_extraction_model instead."""
    #     return get_active_profile().post_processing_model

    # ========================================================================
    # Pydantic Configuration
    # ========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )

    def model_post_init(self, __context) -> None:
        """
        Validate settings after initialization (Pydantic v2).

        NOTE: Profile validation (router models, VRAM limits) is now handled
        by ProfileFactory.load_profile(). This method only validates non-profile
        settings if needed.
        """
        # Profile validation done in ProfileFactory
        pass


settings = Settings()
