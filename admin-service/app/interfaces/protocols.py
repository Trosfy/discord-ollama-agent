"""
Interface Protocols for Dependency Inversion Principle

Defines abstract interfaces that services depend on, allowing for easy testing
and swapping of implementations. Follows Dependency Inversion Principle:
- High-level modules depend on abstractions (interfaces)
- Low-level modules implement abstractions
"""

from typing import Protocol, Dict, List, Optional, Any
from datetime import datetime


class IVRAMClient(Protocol):
    """
    Interface for VRAM/GPU model management client.

    Implementations:
    - VRAMClient (HTTP client to fastapi-service)
    - MockVRAMClient (for testing)
    """

    async def get_loaded_models(self) -> List[Dict]:
        """Get list of currently loaded models."""
        ...

    async def load_model(
        self,
        model_id: str,
        priority: str,
        admin_user: str
    ) -> Dict:
        """Load a model into VRAM."""
        ...

    async def unload_model(
        self,
        model_id: str,
        admin_user: str
    ) -> Dict:
        """Unload a model from VRAM."""
        ...

    async def emergency_evict(
        self,
        priority: str,
        admin_user: str
    ) -> Dict:
        """Emergency evict lowest priority model."""
        ...


class INotificationService(Protocol):
    """
    Interface for notification/webhook service.

    Implementations:
    - WebhookService (Discord webhooks)
    - MockNotificationService (for testing)
    - SlackNotificationService (future)
    """

    async def send_event(
        self,
        event_type: str,
        data: Dict,
        color: Optional[int] = None
    ) -> bool:
        """Send event notification."""
        ...


class IMetricsStorage(Protocol):
    """
    Interface for metrics storage.

    Implementations:
    - MetricsStorage (DynamoDB)
    - MockMetricsStorage (for testing)
    - PostgresMetricsStorage (future)
    """

    async def create_table(self) -> bool:
        """Create/verify metrics table exists."""
        ...

    async def write_metric(
        self,
        metric_type: str,
        timestamp: datetime,
        data: Dict,
        ttl: int
    ) -> bool:
        """Write a metric to storage."""
        ...

    async def store_metric(
        self,
        metric_type: str,
        data: Dict
    ) -> bool:
        """Store a metric (simplified interface)."""
        ...

    async def query_metrics(
        self,
        metric_type: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Query metrics within time range."""
        ...


class IUserRepository(Protocol):
    """
    Interface for user data repository.

    Implementations:
    - DynamoDBUserRepository
    - MockUserRepository (for testing)
    - PostgresUserRepository (future)
    """

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        ...

    async def create_user(self, user_id: str, user_data: Dict) -> bool:
        """Create new user."""
        ...

    async def update_user(self, user_id: str, updates: Dict) -> bool:
        """Update user data."""
        ...

    async def delete_user(self, user_id: str) -> bool:
        """Delete user."""
        ...

    async def ban_user(self, user_id: str, reason: str, admin_user: str) -> bool:
        """Ban a user."""
        ...

    async def unban_user(self, user_id: str, admin_user: str) -> bool:
        """Unban a user."""
        ...

    async def grant_tokens(
        self,
        user_id: str,
        amount: int,
        reason: str,
        admin_user: str
    ) -> bool:
        """Grant bonus tokens to user."""
        ...

    async def list_users(
        self,
        limit: int = 100,
        last_key: Optional[str] = None
    ) -> Dict:
        """List users with pagination."""
        ...


class IDockerClient(Protocol):
    """
    Interface for Docker container management.

    Implementations:
    - DockerClient (subprocess-based)
    - MockDockerClient (for testing)
    - DockerAPIClient (future - using docker-py)
    """

    def list_containers(
        self,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None
    ) -> List[Dict]:
        """List Docker containers."""
        ...

    def get_container_status(self, container_name: str) -> Dict:
        """Get detailed status of a container."""
        ...

    def restart_container(self, container_name: str, timeout: int = 10) -> bool:
        """Restart a Docker container."""
        ...

    def get_container_logs(
        self,
        container_name: str,
        tail: int = 100,
        since: Optional[str] = None
    ) -> str:
        """Get logs from a container."""
        ...

    def get_container_stats(self, container_name: str) -> Dict:
        """Get resource usage stats for a container."""
        ...


class IHealthChecker(Protocol):
    """
    Interface for service health checking.

    Implementations:
    - HealthCheckerService
    - MockHealthChecker (for testing)
    """

    async def check_service(self, name: str, config: dict) -> dict:
        """Check health of a single service."""
        ...

    def get_health_snapshot(self) -> dict:
        """Get current health status snapshot."""
        ...

    def get_current_status(self) -> dict:
        """Get current status with history and uptime."""
        ...

    async def start(self) -> None:
        """Start the health checker."""
        ...

    async def stop(self) -> None:
        """Stop the health checker."""
        ...


class ISystemMetrics(Protocol):
    """
    Interface for system metrics collection.

    Implementations:
    - SystemMetricsService
    - MockSystemMetrics (for testing)
    """

    async def get_system_snapshot(self) -> dict:
        """Get current system metrics snapshot."""
        ...

    async def fetch_vram_stats(self) -> dict:
        """Fetch VRAM/memory stats."""
        ...

    async def fetch_queue_stats(self) -> dict:
        """Fetch queue statistics."""
        ...

    async def fetch_psi_metrics(self) -> dict:
        """Fetch PSI metrics."""
        ...

    async def start(self) -> None:
        """Start background tasks."""
        ...

    async def stop(self) -> None:
        """Stop background tasks."""
        ...


class IMetricsWriter(Protocol):
    """
    Interface for metrics writer service.

    Implementations:
    - MetricsWriter
    - MockMetricsWriter (for testing)
    """

    async def start(
        self,
        system_metrics_service: ISystemMetrics,
        health_checker_service: IHealthChecker
    ) -> None:
        """Start the metrics writer."""
        ...

    async def stop(self) -> None:
        """Stop the metrics writer."""
        ...

    async def write_now(self) -> dict:
        """Manually trigger an immediate write."""
        ...
