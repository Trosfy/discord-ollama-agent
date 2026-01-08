"""Discord bot configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class BotSettings(BaseSettings):
    """Bot configuration with environment variable support."""

    DISCORD_TOKEN: str
    FASTAPI_WS_URL: str = "ws://fastapi-service:8000/ws/discord"

    # Admin Service Settings
    ADMIN_SERVICE_URL: str = "http://admin-service:8000"
    BOT_SECRET: str = ""  # For signing Discord admin tokens
    ADMIN_ROLE_IDS: str = ""  # Comma-separated Discord role IDs that have admin access

    # File Upload Settings
    MAX_FILE_SIZE_MB: int = 10  # Maximum upload size in MB
    ALLOWED_FILE_TYPES: List[str] = [
        # Images
        'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
        # Text & Documents
        'text/plain', 'text/markdown', 'text/csv', 'application/pdf',
        # Code files
        'text/x-python', 'application/x-python-code',
        'text/javascript', 'application/javascript',
        'text/x-java', 'text/x-java-source',
        'text/x-c', 'text/x-c++',
        'text/x-rust', 'text/x-go', 'text/typescript',
        'text/html', 'text/css',
        'application/json', 'application/xml',
        'text/x-yaml', 'application/x-yaml',
        'text/x-shellscript', 'application/x-sh'
    ]
    ALLOWED_FILE_EXTENSIONS: List[str] = [
        # Images
        '.png', '.jpg', '.jpeg', '.webp', '.gif',
        # Text & Documents
        '.txt', '.md', '.csv', '.pdf',
        # Code files
        '.py', '.js', '.ts', '.tsx', '.jsx',
        '.java', '.c', '.cpp', '.h', '.hpp',
        '.rs', '.go', '.rb', '.php', '.swift',
        '.html', '.css', '.scss', '.sass',
        '.json', '.yaml', '.yml', '.toml', '.xml',
        '.sh', '.bash', '.zsh', '.fish',
        '.sql', '.graphql', '.proto'
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


# Singleton instance
settings = BotSettings()
