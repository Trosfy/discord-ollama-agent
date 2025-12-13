"""Global application settings."""
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class ModelCapabilities(BaseModel):
    """Model capability flags."""
    name: str
    supports_vision: bool = False
    supports_thinking: bool = False
    supports_tools: bool = True  # Most models support tools
    context_window: Optional[int] = None  # For future use
    thinking_format: str = "boolean"  # "boolean" (think=True) or "level" (ThinkLevel="high")
    default_thinking_level: str = "high"  # For models with thinking_format="level"


# Available Models with Capabilities (module-level constant)
_AVAILABLE_MODELS: List[ModelCapabilities] = [
    ModelCapabilities(
        name="gpt-oss:20b",
        supports_tools=True,
        supports_thinking=True,
        thinking_format="level",
        default_thinking_level="high"
    ),
    ModelCapabilities(name="magistral:24b", supports_tools=True, supports_thinking=True),
    ModelCapabilities(name="deepcoder:14b", supports_tools=False),
    # ModelCapabilities(name="gpt-oss:120b", supports_tools=True, supports_thinking=True),
    # ModelCapabilities(name="deepseek-r1:32b", supports_tools=False, supports_thinking=True),
    ModelCapabilities(name="deepseek-r1:14b", supports_tools=False, supports_thinking=True),
    # ModelCapabilities(name="deepseek-r1:8b", supports_tools=False, supports_thinking=True),
    ModelCapabilities(name="devstral:24b", supports_tools=True),
    ModelCapabilities(name="qwen2.5-coder:7b", supports_tools=True),
    ModelCapabilities(name="qwen3-coder:30b", supports_tools=True),
    ModelCapabilities(name="ministral-3:14b", supports_vision=True, supports_tools=True),
    ModelCapabilities(name="qwen3-vl:8b", supports_vision=True, supports_tools=True, supports_thinking=True),
    ModelCapabilities(
        name="rnj-1:8b",
        supports_tools=True,
        supports_thinking=False,
        supports_vision=False,
        thinking_format="boolean",
        default_thinking_level="high"
    ),
]


def get_model_capabilities(model_name: str) -> Optional[ModelCapabilities]:
    """Get capabilities for a model by name."""
    for model in _AVAILABLE_MODELS:
        if model.name == model_name:
            return model
    return None


def get_available_model_names() -> List[str]:
    """Get list of all available model names."""
    return [model.name for model in _AVAILABLE_MODELS]


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
    OLLAMA_SUMMARIZATION_MODEL: str = "gpt-oss:20b"
    OLLAMA_REQUEST_TIMEOUT: int = 300  # 5 minutes
    OLLAMA_KEEP_ALIVE: int = 0  # Immediately unload models after use (memory management)

    # Router Settings
    ROUTER_MODEL: str = "gpt-oss:20b"
    CODER_MODEL: str = "deepcoder:14b"
    REASONING_MODEL: str = "magistral:24b"  # Use magistral:24b for reasoning with web tools (best for <40K tokens)
    RESEARCH_MODEL: str = "magistral:24b"  # Use magistral:24b with think=True for deep research with web tools
    MATH_MODEL: str = "rnj-1:8b"  # Math problem solving model
    POST_PROCESSING_OUTPUT_ARTIFACT_MODEL: str = "gpt-oss:20b"  # Faster thinking model for intelligent artifact extraction (was: magistral:24b - too slow)
    DEFAULT_TEMPERATURE: float = 0.2  # Default temperature for LLM generation (lower = more deterministic)

    # Queue Settings
    MAX_QUEUE_SIZE: int = 50
    QUEUE_TIMEOUT_SECONDS: int = 300
    VISIBILITY_TIMEOUT: int = 900  # 15 minutes (handles long-running requests like chart analysis)
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
    OCR_MODEL: str = "qwen3-vl:8b"  # Ollama model for OCR/vision tasks
    ARTIFACT_TTL_HOURS: int = 12  # Artifact storage time (hours)
    UPLOAD_CLEANUP_HOURS: int = 1  # Temp upload file cleanup time (hours)
    TEMP_UPLOAD_DIR: str = "/tmp/discord-bot-uploads"
    TEMP_ARTIFACT_DIR: str = "/tmp/discord-bot-artifacts"

    # Maintenance
    MAINTENANCE_MODE: bool = False  # Soft maintenance (still queue)
    MAINTENANCE_MODE_HARD: bool = False  # Hard maintenance (reject new)
    MAINTENANCE_MESSAGE: str = "🔧 Bot is under maintenance. Your request has been queued."
    MAINTENANCE_MESSAGE_HARD: str = "🚫 Bot is under emergency maintenance. Please try again later."

    # Available Models (reference to module-level constant)
    AVAILABLE_MODELS: List[ModelCapabilities] = _AVAILABLE_MODELS

    # Health Check
    HEALTH_CHECK_INTERVAL: int = 30  # seconds

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )

    def model_post_init(self, __context) -> None:
        """Validate settings after initialization (Pydantic v2)."""
        model_names = get_available_model_names()

        # Validate router models
        models_to_check = {
            'ROUTER_MODEL': self.ROUTER_MODEL,
            'CODER_MODEL': self.CODER_MODEL,
            'REASONING_MODEL': self.REASONING_MODEL,
            'RESEARCH_MODEL': self.RESEARCH_MODEL,
            'MATH_MODEL': self.MATH_MODEL,
            'OLLAMA_DEFAULT_MODEL': self.OLLAMA_DEFAULT_MODEL,
            'OLLAMA_SUMMARIZATION_MODEL': self.OLLAMA_SUMMARIZATION_MODEL,
            'OCR_MODEL': self.OCR_MODEL,
        }

        for setting_name, model_name in models_to_check.items():
            if model_name not in model_names:
                raise ValueError(
                    f"{setting_name} '{model_name}' is not in AVAILABLE_MODELS. "
                    f"Available: {', '.join(model_names)}"
                )


settings = Settings()
