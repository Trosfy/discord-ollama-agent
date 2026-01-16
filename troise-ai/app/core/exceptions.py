"""Custom exceptions for TROISE AI."""


class TroiseError(Exception):
    """Base exception for TROISE AI."""
    pass


class AgentCancelled(TroiseError):
    """Raised when an agent execution is cancelled by user."""
    pass


class RoutingError(TroiseError):
    """Raised when routing fails to find a skill or agent."""
    pass


class PluginError(TroiseError):
    """Raised when a plugin fails to load or execute."""
    pass


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found."""
    pass


class BackendError(TroiseError):
    """Raised when a backend operation fails."""
    pass


class BackendNotAvailableError(BackendError):
    """Raised when a backend is not available."""
    pass


class ModelNotFoundError(TroiseError):
    """Raised when a requested model is not found in the profile."""
    pass


class VRAMError(TroiseError):
    """Raised when VRAM operations fail."""
    pass


class InsufficientVRAMError(VRAMError):
    """Raised when there's not enough VRAM to load a model."""
    pass


class ProfileError(TroiseError):
    """Raised when profile operations fail."""
    pass


class ProfileNotFoundError(ProfileError):
    """Raised when a requested profile is not found."""
    pass


class BrainServiceError(TroiseError):
    """Raised when brain service operations fail."""
    pass


class VaultError(TroiseError):
    """Raised when vault operations fail."""
    pass
