"""
Interface protocols for dependency inversion.

These protocols define abstract interfaces that services depend on,
enabling easy testing and swapping of implementations.
"""

from .protocols import (
    IVRAMClient,
    INotificationService,
    IMetricsStorage,
    IUserRepository,
    IDockerClient,
    IHealthChecker,
    ISystemMetrics,
    IMetricsWriter
)

__all__ = [
    "IVRAMClient",
    "INotificationService",
    "IMetricsStorage",
    "IUserRepository",
    "IDockerClient",
    "IHealthChecker",
    "ISystemMetrics",
    "IMetricsWriter"
]
