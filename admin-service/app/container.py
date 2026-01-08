"""
Dependency Injection Container

Central container for dependency injection using dependency-injector library.
Wires all services, repositories, and clients together following DIP.
"""

from dependency_injector import containers, providers

from app.config import settings
from app.clients.vram_client import VRAMClient
from app.clients.docker_client import DockerClient
from app.repositories.dynamodb_user_repository import DynamoDBUserRepository
from app.services.webhook_service import WebhookService
from app.services.webhook.registry import get_default_registry
from app.services.health_checker_service import HealthCheckerService
from app.services.system_metrics_service import SystemMetricsService
from app.services.metrics_writer import MetricsWriter
from app.services.metrics_storage import MetricsStorage
from app.services.log_cleanup_service import LogCleanupService


class Container(containers.DeclarativeContainer):
    """
    Application dependency injection container.

    Defines how all services, repositories, and clients are created and wired together.
    This centralized configuration makes dependencies explicit and testable.

    Usage:
        # Create container
        container = Container()

        # Get service instance
        vram_client = container.vram_client()
        user_repo = container.user_repository()

        # Override for testing
        container.user_repository.override(MockUserRepository())
    """

    # Configuration
    config = providers.Configuration()

    # ========== Clients ==========

    vram_client = providers.Singleton(
        VRAMClient,
        base_url=settings.FASTAPI_URL,
        api_key=settings.INTERNAL_API_KEY
    )

    docker_client = providers.Singleton(
        DockerClient
    )

    # ========== Repositories ==========

    user_repository = providers.Singleton(
        DynamoDBUserRepository
    )

    metrics_storage = providers.Singleton(
        MetricsStorage
    )

    # ========== Services ==========

    webhook_service = providers.Singleton(
        WebhookService,
        webhook_url=settings.DISCORD_ADMIN_WEBHOOK_URL,
        formatter_registry=get_default_registry()
    )

    health_checker_service = providers.Singleton(
        HealthCheckerService,
        webhook_service=webhook_service
    )

    system_metrics_service = providers.Singleton(
        SystemMetricsService
    )

    metrics_writer = providers.Singleton(
        MetricsWriter
    )

    log_cleanup_service = providers.Singleton(
        LogCleanupService
    )

    # ========== Background Services Factory ==========

    @providers.Factory
    def background_services():
        """
        Factory for getting all background services that need to be started.

        Returns:
            dict: Dictionary of service name -> service instance
        """
        return {
            "health_checker": health_checker_service(),
            "system_metrics": system_metrics_service(),
            "metrics_writer": metrics_writer(),
            "log_cleanup": log_cleanup_service()
        }


# Global container instance
container = Container()


def get_container() -> Container:
    """
    Get the global container instance.

    Returns:
        Container: Global DI container

    Example:
        from app.container import get_container

        container = get_container()
        vram_client = container.vram_client()
    """
    return container


def init_container() -> Container:
    """
    Initialize and wire the container.

    Returns:
        Container: Initialized container

    Example:
        container = init_container()
        # Container is now ready to use
    """
    container.config.from_dict({
        "fastapi_url": settings.FASTAPI_URL,
        "internal_api_key": settings.INTERNAL_API_KEY,
        "webhook_url": settings.DISCORD_ADMIN_WEBHOOK_URL
    })
    return container
