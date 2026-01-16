"""Dependency Injection Container for TROISE AI.

Provides a simple DI container for service resolution.
No magic - explicit registration, explicit resolution.

Example:
    container = Container()

    # Register singleton instance
    container.register(Config, config_instance)

    # Register factory for lazy instantiation
    container.register_factory(
        IBrainService,
        lambda c: BrainService(storage=c.resolve(IBrainStorage))
    )

    # Resolve service
    brain_service = container.resolve(IBrainService)
"""
import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ContainerError(Exception):
    """Raised when container operations fail."""
    pass


class ServiceNotFoundError(ContainerError):
    """Raised when a requested service is not registered."""
    pass


class Container:
    """
    Simple DI container for service resolution.

    Features:
    - Singleton registration: Store pre-created instances
    - Factory registration: Lazy instantiation on first resolve
    - Type-safe resolution with generics
    - Hierarchical containers (optional parent)

    Thread Safety:
    - This container is NOT thread-safe. For concurrent access,
      either use per-request containers or add locking.
    """

    def __init__(self, parent: Optional["Container"] = None):
        """
        Initialize the container.

        Args:
            parent: Optional parent container for hierarchical resolution.
        """
        self._services: Dict[type, Any] = {}
        self._factories: Dict[type, Callable[["Container"], Any]] = {}
        self._parent = parent

    def register(self, interface: Type[T], implementation: T) -> None:
        """
        Register a singleton instance.

        The same instance will be returned for all resolve() calls.

        Args:
            interface: The type/interface to register.
            implementation: The instance to return when resolving.

        Example:
            container.register(Config, Config())
            container.register(IBackendManager, BackendManager(config))
        """
        self._services[interface] = implementation
        logger.debug(f"Registered singleton: {interface.__name__}")

    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[["Container"], T]
    ) -> None:
        """
        Register a factory for lazy instantiation.

        The factory is called on first resolve(), and the result
        is cached as a singleton for subsequent calls.

        Args:
            interface: The type/interface to register.
            factory: Callable that takes the container and returns an instance.

        Example:
            container.register_factory(
                IBrainService,
                lambda c: BrainService(
                    storage=c.resolve(IBrainStorage),
                    embeddings=c.resolve(IEmbeddingService)
                )
            )
        """
        self._factories[interface] = factory
        logger.debug(f"Registered factory: {interface.__name__}")

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a service by interface.

        Resolution order:
        1. Check for existing singleton
        2. Check for factory (create singleton on first call)
        3. Check parent container (if exists)
        4. Raise ServiceNotFoundError

        Args:
            interface: The type/interface to resolve.

        Returns:
            The resolved service instance.

        Raises:
            ServiceNotFoundError: If no registration exists.
        """
        # Check existing singleton
        if interface in self._services:
            return self._services[interface]

        # Check factory (lazy instantiation)
        if interface in self._factories:
            instance = self._factories[interface](self)
            self._services[interface] = instance  # Cache as singleton
            logger.debug(f"Created instance from factory: {interface.__name__}")
            return instance

        # Check parent container
        if self._parent:
            return self._parent.resolve(interface)

        raise ServiceNotFoundError(
            f"No registration for {interface.__name__}. "
            f"Available: {list(s.__name__ for s in self._services.keys())}"
        )

    def try_resolve(self, interface: Type[T]) -> Optional[T]:
        """
        Try to resolve a service, returning None if not found.

        Args:
            interface: The type/interface to resolve.

        Returns:
            The resolved service instance, or None if not found.
        """
        try:
            return self.resolve(interface)
        except ServiceNotFoundError:
            return None

    def is_registered(self, interface: type) -> bool:
        """
        Check if a type is registered.

        Args:
            interface: The type/interface to check.

        Returns:
            True if registered (as singleton or factory).
        """
        if interface in self._services or interface in self._factories:
            return True
        if self._parent:
            return self._parent.is_registered(interface)
        return False

    def create_child(self) -> "Container":
        """
        Create a child container.

        Child containers inherit registrations from parent but can
        override with their own. Useful for request-scoped services.

        Returns:
            A new Container with this container as parent.
        """
        return Container(parent=self)

    def unregister(self, interface: type) -> bool:
        """
        Remove a registration.

        Args:
            interface: The type/interface to unregister.

        Returns:
            True if something was removed, False if not found.
        """
        removed = False

        if interface in self._services:
            del self._services[interface]
            removed = True

        if interface in self._factories:
            del self._factories[interface]
            removed = True

        return removed

    def list_registrations(self) -> Dict[str, str]:
        """
        List all registrations for debugging.

        Returns:
            Dictionary of interface name -> registration type.
        """
        result = {}

        for interface in self._services:
            result[interface.__name__] = "singleton"

        for interface in self._factories:
            if interface not in self._services:  # Factory not yet resolved
                result[interface.__name__] = "factory (pending)"

        return result


def create_container() -> Container:
    """
    Create and configure the application container.

    This is the composition root where all services are wired together.
    Call this once at application startup.

    Returns:
        Configured Container with all services registered.
    """
    from .config import Config
    from .registry import PluginRegistry
    from .interfaces.storage import IFileStorage
    from ..services.backend_manager import BackendManager
    from ..services.profile_manager import ProfileManager
    from ..services.vram_orchestrator import VRAMOrchestrator
    from ..services.embedding_service import EmbeddingService
    from ..adapters.dynamodb import DynamoDBClient
    from ..adapters.minio import MinIOAdapter
    from ..prompts import PromptRegistry, PromptComposer, prompt_registry

    container = Container()

    # Register Config first (other services depend on it)
    container.register_factory(Config, lambda c: Config())

    # Register Prompt System (depends on Config)
    container.register(PromptRegistry, prompt_registry)
    container.register_factory(
        PromptComposer,
        lambda c: PromptComposer(
            registry=c.resolve(PromptRegistry),
            config=c.resolve(Config),
        )
    )

    # Register PluginRegistry (with config for universal_tools)
    container.register_factory(PluginRegistry, lambda c: PluginRegistry(c.resolve(Config)))

    # Register DynamoDBClient (no dependencies, uses environment variables)
    container.register_factory(DynamoDBClient, lambda c: DynamoDBClient())

    # Register MinIOAdapter (no dependencies, uses environment variables)
    # Register both concrete type and interface for flexibility
    container.register_factory(MinIOAdapter, lambda c: MinIOAdapter())
    container.register_factory(IFileStorage, lambda c: c.resolve(MinIOAdapter))

    # Register ProfileManager (depends on Config)
    container.register_factory(
        ProfileManager,
        lambda c: ProfileManager(c.resolve(Config).profile)
    )

    # Register BackendManager (depends on Config)
    container.register_factory(
        BackendManager,
        lambda c: BackendManager(c.resolve(Config))
    )

    # Register VRAMOrchestrator (depends on Config, BackendManager, ProfileManager)
    container.register_factory(
        VRAMOrchestrator,
        lambda c: VRAMOrchestrator(
            config=c.resolve(Config),
            backend_manager=c.resolve(BackendManager),
            profile_manager=c.resolve(ProfileManager),
        )
    )

    # Register EmbeddingService (depends on Config, DynamoDBClient, ProfileManager)
    container.register_factory(
        EmbeddingService,
        lambda c: EmbeddingService(
            ollama_host=c.resolve(Config).backends.get('ollama').host,
            dynamo_client=c.resolve(DynamoDBClient),
            model=c.resolve(ProfileManager).get_current_profile().embedding_model,
            use_cache=True,
        )
    )

    # ===========================================================================
    # Preprocessing Services
    # ===========================================================================
    from ..preprocessing import (
        PromptSanitizer,
        FileExtractionRouter,
        OutputArtifactDetector,
    )
    from ..preprocessing.extractors import (
        TextExtractor,
        ImageExtractor,
        PDFExtractor,
    )

    # Register PromptSanitizer (uses VRAMOrchestrator for model access)
    container.register_factory(
        PromptSanitizer,
        lambda c: PromptSanitizer(
            config=c.resolve(Config),
            vram_orchestrator=c.resolve(VRAMOrchestrator),
        )
    )

    # Register FileExtractionRouter with extractors
    def create_extraction_router(c: Container) -> FileExtractionRouter:
        router = FileExtractionRouter()
        router.register(TextExtractor())
        router.register(ImageExtractor(
            config=c.resolve(Config),
            vram_orchestrator=c.resolve(VRAMOrchestrator),
        ))
        router.register(PDFExtractor())
        return router

    container.register_factory(FileExtractionRouter, create_extraction_router)

    # Register OutputArtifactDetector (uses VRAMOrchestrator for model access)
    container.register_factory(
        OutputArtifactDetector,
        lambda c: OutputArtifactDetector(
            config=c.resolve(Config),
            vram_orchestrator=c.resolve(VRAMOrchestrator),
        )
    )

    # ===========================================================================
    # Postprocessing Services
    # ===========================================================================
    from ..postprocessing import (
        ArtifactExtractionChain,
        ContentSanitizer,
        ToolArtifactHandler,
        LLMExtractionHandler,
        RegexFallbackHandler,
    )

    # Register ContentSanitizer
    container.register_factory(ContentSanitizer, lambda c: ContentSanitizer())

    # Register ArtifactExtractionChain with handlers
    def create_artifact_chain(c: Container) -> ArtifactExtractionChain:
        sanitizer = c.resolve(ContentSanitizer)

        handlers = [
            ToolArtifactHandler(),
            LLMExtractionHandler(
                config=c.resolve(Config),
                vram_orchestrator=c.resolve(VRAMOrchestrator),
                sanitizer=sanitizer,
            ),
            RegexFallbackHandler(sanitizer=sanitizer),
        ]
        return ArtifactExtractionChain(handlers)

    container.register_factory(ArtifactExtractionChain, create_artifact_chain)

    # ===========================================================================
    # Response Formatters
    # ===========================================================================
    from ..adapters.formatters import (
        DiscordResponseFormatter,
        WebResponseFormatter,
    )

    container.register_factory(DiscordResponseFormatter, lambda c: DiscordResponseFormatter())
    container.register_factory(WebResponseFormatter, lambda c: WebResponseFormatter())

    # ===========================================================================
    # Session Persistence (DynamoDB)
    # ===========================================================================
    from ..adapters.dynamodb.main_adapter import TroiseMainAdapter

    container.register_factory(
        TroiseMainAdapter,
        lambda c: TroiseMainAdapter(c.resolve(DynamoDBClient))
    )

    # ===========================================================================
    # Core Execution Services (Executor, Router, ToolFactory)
    # ===========================================================================
    from .executor import Executor
    from .router import Router
    from .tool_factory import ToolFactory
    from .interfaces.services import IVRAMOrchestrator, IExecutor

    # Register Router (simplified: 4 classifications, no registry needed)
    # Router now uses VRAMOrchestrator.get_model() with Strands models
    container.register_factory(
        Router,
        lambda c: Router(
            config=c.resolve(Config),
            vram_orchestrator=c.resolve(VRAMOrchestrator),
        )
    )

    # Register ToolFactory
    container.register_factory(
        ToolFactory,
        lambda c: ToolFactory(registry=c.resolve(PluginRegistry), container=c)
    )

    # Register Executor
    container.register_factory(
        Executor,
        lambda c: Executor(
            registry=c.resolve(PluginRegistry),
            container=c,
            tool_factory=c.resolve(ToolFactory),
        )
    )

    # Register IExecutor interface (points to Executor)
    container.register_factory(
        IExecutor,
        lambda c: c.resolve(Executor)
    )

    # Register IVRAMOrchestrator interface
    container.register_factory(
        IVRAMOrchestrator,
        lambda c: c.resolve(VRAMOrchestrator)
    )

    # ===========================================================================
    # Queue System
    # ===========================================================================
    from .queue import RequestQueue, HybridPrioritizer
    from .interfaces.queue import (
        IPrioritizer,
        IRequestSubmitter,
        IQueueInternal,
        IQueueMonitor,
    )
    from ..services.queue_manager import QueueManager

    # Register prioritizer (default hybrid scoring)
    container.register_factory(
        IPrioritizer,
        lambda c: HybridPrioritizer()
    )

    # Register RequestQueue (implements all queue interfaces)
    container.register_factory(
        RequestQueue,
        lambda c: RequestQueue(prioritizer=c.resolve(IPrioritizer))
    )

    # Register interface aliases for queue (Interface Segregation)
    container.register_factory(
        IRequestSubmitter,
        lambda c: c.resolve(RequestQueue)
    )
    container.register_factory(
        IQueueInternal,
        lambda c: c.resolve(RequestQueue)
    )
    container.register_factory(
        IQueueMonitor,
        lambda c: c.resolve(RequestQueue)
    )

    # ===========================================================================
    # Circuit Breaker System
    # ===========================================================================
    from ..services.circuit_breaker_registry import CircuitBreakerRegistry
    from ..services.visibility_monitor import VisibilityMonitor

    # Register CircuitBreakerRegistry (depends on ProfileManager and Config)
    container.register_factory(
        CircuitBreakerRegistry,
        lambda c: CircuitBreakerRegistry(
            profile_manager=c.resolve(ProfileManager),
            config=c.resolve(Config),
        )
    )

    # Register VisibilityMonitor (depends on IQueueInternal, Config, CircuitBreakerRegistry)
    container.register_factory(
        VisibilityMonitor,
        lambda c: VisibilityMonitor(
            queue=c.resolve(IQueueInternal),
            config=c.resolve(Config),
            circuit_registry=c.resolve(CircuitBreakerRegistry),
        )
    )

    # Register QueueManager (orchestrates queue and workers with circuit breaker)
    container.register_factory(
        QueueManager,
        lambda c: QueueManager(
            queue=c.resolve(RequestQueue),
            executor=c.resolve(IExecutor),
            config=c.resolve(Config),
            circuit_registry=c.resolve(CircuitBreakerRegistry),
        )
    )

    logger.info("Application container created with all services")
    return container
