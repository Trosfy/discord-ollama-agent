"""Pytest configuration for admin-service tests."""
import sys
import os
from pathlib import Path

# Set test environment variables BEFORE importing app modules
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-for-testing")
os.environ.setdefault("BOT_SECRET", "test-bot-secret-key-for-testing")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-api-key")

# Add shared directory to Python path for logging_client and init_dynamodb
shared_dir = Path(__file__).parent.parent.parent / "shared"
sys.path.insert(0, str(shared_dir))
