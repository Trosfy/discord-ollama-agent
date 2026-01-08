"""Dependency injection for admin service using DI container.

Replaced manual singleton management with dependency-injector container.
All services are now provided by the container, which handles:
- Singleton lifecycle management
- Dependency resolution
- Easy testing with mock overrides
- Explicit dependency declarations
"""

from app.container import get_container
from app.interfaces.protocols import IVRAMClient, INotificationService, IUserRepository
from app.services.model_service import ModelService
from app.services.user_service import UserService
from app.services.ollama_service import OllamaService
from app.services.vram_validator import VRAMValidator


def get_vram_client() -> IVRAMClient:
    """
    Get VRAM client from container.

    Returns:
        IVRAMClient: VRAM client interface implementation
    """
    container = get_container()
    return container.vram_client()


def get_user_repository() -> IUserRepository:
    """
    Get user repository from container.

    Returns:
        IUserRepository: User repository interface implementation
    """
    container = get_container()
    return container.user_repository()


def get_webhook_service() -> INotificationService:
    """
    Get webhook/notification service from container.

    Returns:
        INotificationService: Notification service interface implementation
    """
    container = get_container()
    return container.webhook_service()


def get_model_service() -> ModelService:
    """
    Get model service from container.

    Model service is automatically wired with:
    - VRAM client (IVRAMClient)
    - Webhook service (INotificationService)

    Returns:
        ModelService: Model management service
    """
    container = get_container()
    return ModelService(
        vram_client=container.vram_client(),
        webhook=container.webhook_service()
    )


def get_user_service() -> UserService:
    """
    Get user service from container.

    User service is automatically wired with:
    - User repository (IUserRepository)
    - Webhook service (INotificationService)

    Returns:
        UserService: User management service
    """
    container = get_container()
    return UserService(
        user_repository=container.user_repository(),
        webhook=container.webhook_service()
    )


# Singleton instance for OllamaService (shared state for prewarm tracking)
_ollama_service: OllamaService | None = None


def get_ollama_service() -> OllamaService:
    """
    Get Ollama service singleton.

    OllamaService tracks prewarmed model state in memory.
    Must be singleton to maintain consistent state across requests.

    Returns:
        OllamaService: Ollama model management service
    """
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service


# Singleton instance for VRAMValidator
_vram_validator: VRAMValidator | None = None


def get_vram_validator() -> VRAMValidator:
    """
    Get VRAM validator singleton.

    VRAMValidator queries system memory and Ollama for capacity checks.
    Must be singleton to reuse HTTP client.

    Returns:
        VRAMValidator: VRAM validation service
    """
    global _vram_validator
    if _vram_validator is None:
        _vram_validator = VRAMValidator()
    return _vram_validator
