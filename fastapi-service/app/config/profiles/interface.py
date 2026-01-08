"""IConfigProfile interface (Dependency Inversion Principle)."""
from typing import Protocol, List


class IConfigProfile(Protocol):
    """
    Configuration profile interface (SOLID compliance).

    This interface defines the contract for all configuration profiles,
    enabling dependency inversion and easy extensibility.

    Following SOLID Principles:
    - Single Responsibility: Defines profile contract only
    - Interface Segregation: Only exposes needed properties
    - Dependency Inversion: Settings depends on this abstraction
    """

    @property
    def profile_name(self) -> str:
        """Profile identifier (e.g., 'conservative', 'performance', 'balanced')."""
        ...

    @property
    def available_models(self) -> List['ModelCapabilities']:  # noqa: F821
        """Models available in this profile."""
        ...

    @property
    def vram_soft_limit_gb(self) -> float:
        """Soft VRAM limit for this profile."""
        ...

    @property
    def vram_hard_limit_gb(self) -> float:
        """Hard VRAM limit for this profile."""
        ...

    @property
    def router_model(self) -> str:
        """Router model for classification."""
        ...

    @property
    def simple_coder_model(self) -> str:
        """Model for simple code tasks."""
        ...

    @property
    def complex_coder_model(self) -> str:
        """Model for complex system design."""
        ...

    @property
    def reasoning_model(self) -> str:
        """Model for reasoning tasks."""
        ...

    @property
    def research_model(self) -> str:
        """Model for research tasks."""
        ...

    @property
    def math_model(self) -> str:
        """Model for math tasks."""
        ...

    @property
    def vision_model(self) -> str:
        """Model for OCR and vision tasks."""
        ...

    @property
    def embedding_model(self) -> str:
        """Model for text embeddings and RAG."""
        ...

    @property
    def summarization_model(self) -> str:
        """Model for text summarization."""
        ...

    # NOTE: post_processing_model DEPRECATED - migrated to artifact_extraction_model
    # @property
    # def post_processing_model(self) -> str:
    #     """DEPRECATED: Use artifact_extraction_model instead."""
    #     ...

    @property
    def artifact_detection_model(self) -> str:
        """Model for output artifact DETECTION (binary YES/NO classification).

        Used in preprocessing to determine if user wants file output.
        Recommended: Small fast model (qwen2.5:3b) for quick classification.
        """
        ...

    @property
    def artifact_extraction_model(self) -> str:
        """Model for output artifact EXTRACTION (parsing response to create file).

        Used in postprocessing to extract file content from LLM response.
        Can be same as detection model or larger for better parsing accuracy.
        """
        ...

    @property
    def fetch_limits(self) -> dict:
        """Fetch limits per route (e.g., {'REASONING': 3, 'RESEARCH': 5})."""
        ...

    def validate(self) -> None:
        """Validate profile consistency (all router models exist in roster)."""
        ...
