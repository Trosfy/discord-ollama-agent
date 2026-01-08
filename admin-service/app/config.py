"""Configuration settings for admin-service."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Admin service configuration."""

    # FastAPI Service URLs
    FASTAPI_URL: str = os.getenv("FASTAPI_URL", "http://fastapi-service:8000")

    # JWT Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-me")
    JWT_ALGORITHM: str = "HS256"

    # Discord Bot Authentication
    BOT_SECRET: str = os.getenv("BOT_SECRET", "")  # For Discord bot token verification
    DISCORD_TOKEN_EXPIRY_SECONDS: int = 300  # 5 minutes

    # Internal Service Communication
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "change-this-in-production")

    # Discord Webhook
    DISCORD_ADMIN_WEBHOOK_URL: str = os.getenv("DISCORD_ADMIN_WEBHOOK_URL", "")
    WEBHOOK_RATE_LIMIT: int = 10  # Max 10 webhooks per minute

    # DynamoDB (for user management and audit logs)
    DYNAMODB_ENDPOINT: str = os.getenv("DYNAMODB_ENDPOINT", "http://dynamodb-local:8000")
    DYNAMODB_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")  # Alias for compatibility
    DYNAMODB_ACCESS_KEY: str = os.getenv("AWS_ACCESS_KEY_ID", "dummy")
    DYNAMODB_SECRET_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "dummy")
    USERS_TABLE_NAME: str = "users"
    ADMIN_AUDIT_LOG_TABLE: str = "admin_audit_logs"

    # Service Configuration
    SERVICE_NAME: str = "admin-service"
    SERVICE_VERSION: str = "1.0.0"
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://dgx-spark.netbird.cloud:3000",
        "http://dgx-spark.netbird.cloud:8080",
        "http://192.168.1.19:3000",
        "http://192.168.1.19:8080"
    ]

    # Monitoring Configuration
    HEALTH_CHECK_INTERVAL_SECONDS: int = int(os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "5"))
    HEALTH_CHECK_ALERT_THRESHOLD: int = int(os.getenv("HEALTH_CHECK_ALERT_THRESHOLD", "3"))
    HEALTH_CHECK_ALERT_COOLDOWN_SECONDS: int = int(os.getenv("HEALTH_CHECK_ALERT_COOLDOWN_SECONDS", "300"))

    # Metrics Configuration
    METRICS_WRITE_INTERVAL_SECONDS: int = int(os.getenv("METRICS_WRITE_INTERVAL_SECONDS", "5"))
    METRICS_RETENTION_DAYS: int = int(os.getenv("METRICS_RETENTION_DAYS", "2"))

    # Log Cleanup Configuration
    LOG_CLEANUP_INTERVAL_HOURS: int = int(os.getenv("LOG_CLEANUP_INTERVAL_HOURS", "6"))
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "2"))
    LOG_BASE_DIR: str = os.getenv("LOG_BASE_DIR", "/app/logs")

    class Config:
        case_sensitive = True


# Global settings instance
settings = Settings()
