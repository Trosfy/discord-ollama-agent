"""IConfigProfile interface - configuration profiles for different VRAM setups."""
from typing import Protocol, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import ModelCapabilities


class IConfigProfile(Protocol):
    """
    Configuration profile interface (SOLID compliance).

    Enables dependency inversion and easy extensibility.
    Profiles define which models are available and how they map to tasks.

    VRAM limits are NOT part of the profile - VRAMOrchestrator auto-detects.
    """

    @property
    def profile_name(self) -> str:
        """Profile identifier: 'conservative', 'balanced', 'performance'."""
        ...

    @property
    def available_models(self) -> List["ModelCapabilities"]:
        """Models available in this profile."""
        ...

    # Model assignments by task type (aligned with router classifications)
    @property
    def router_model(self) -> str:
        """Fast model for request classification."""
        ...

    @property
    def general_model(self) -> str:
        """Model for GENERAL classification - general conversation agent."""
        ...

    @property
    def research_model(self) -> str:
        """Model for RESEARCH classification - deep research agent."""
        ...

    @property
    def code_model(self) -> str:
        """Model for CODE classification - agentic code agent."""
        ...

    @property
    def braindump_model(self) -> str:
        """Model for BRAINDUMP classification - braindump agent."""
        ...

    @property
    def vision_model(self) -> str:
        """Model for OCR and vision tasks."""
        ...

    @property
    def embedding_model(self) -> str:
        """Model for text embeddings and RAG."""
        ...

    def validate(self) -> None:
        """Validate all assigned models exist in available_models."""
        ...
