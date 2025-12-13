"""Global application settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    # Service Info
    APP_NAME: str = "Discord-Ollama Agent"
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
    CODER_MODEL: str = "qwen2.5-coder:7b"
    REASONING_MODEL: str = "gpt-oss:20b"  # Use gpt-oss:20b for reasoning with web tools

    # Multi-Agent Settings (deprecated - keeping for backward compatibility)
    ENABLE_MULTI_AGENT: bool = False  # Disabled in favor of router
    PLANNER_MODEL: str = "deepseek-r1:8b"
    EXECUTOR_MODEL: str = "gpt-oss:20b"
    PLANNER_TEMPERATURE: float = 0.3

    # Queue Settings
    MAX_QUEUE_SIZE: int = 50
    QUEUE_TIMEOUT_SECONDS: int = 300
    VISIBILITY_TIMEOUT: int = 300  # 5 minutes
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # seconds

    # Token Settings
    MAX_CONTEXT_TOKENS: int = 10000
    DEFAULT_SUMMARIZATION_THRESHOLD: int = 9000
    FREE_TIER_WEEKLY_BUDGET: int = 100000
    ADMIN_TIER_WEEKLY_BUDGET: int = 500000

    # Discord
    DISCORD_MESSAGE_MAX_LENGTH: int = 2000
    DISCORD_SPLIT_MESSAGE_INDICATOR: bool = True

    # Maintenance
    MAINTENANCE_MODE: bool = False  # Soft maintenance (still queue)
    MAINTENANCE_MODE_HARD: bool = False  # Hard maintenance (reject new)
    MAINTENANCE_MESSAGE: str = "🔧 Bot is under maintenance. Your request has been queued."
    MAINTENANCE_MESSAGE_HARD: str = "🚫 Bot is under emergency maintenance. Please try again later."

    # Available Models
    AVAILABLE_MODELS: List[str] = [
        "gpt-oss:20b",
        "gpt-oss:120b",
        "deepseek-r1:32b",
        "deepseek-r1:8b",
        "qwen2.5-coder:7b"
    ]

    # Health Check
    HEALTH_CHECK_INTERVAL: int = 30  # seconds

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
