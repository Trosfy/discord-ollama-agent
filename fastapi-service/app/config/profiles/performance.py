"""Performance Profile for 128GB VRAM systems using Ollama."""
from typing import List
from app.config import ModelCapabilities, BackendConfig


class PerformanceProfile:
    """
    Configuration profile for 128GB VRAM systems optimized for maximum speed.

    Uses gpt-oss:120b from Ollama for ALL text tasks.
    Minimal Ollama models only for vision and embedding tasks.

    Characteristics:
    - Single powerful model (gpt-oss:120b) for all text/code/reasoning
    - Minimal orchestration overhead (fewer model switches)
    - Ollama only for all tasks
    - ~65GB gpt-oss:120b + 12GB other models = 77GB total, 42GB free

    Following SOLID Principles:
    - Single Responsibility: Performance-optimized 128GB configuration
    - Liskov Substitution: Can replace any IConfigProfile implementation
    """

    @property
    def profile_name(self) -> str:
        return "performance"

    @property
    def available_models(self) -> List[ModelCapabilities]:
        return [
            # Primary model: gpt-oss:120b for ALL text tasks
            ModelCapabilities(
                name="gpt-oss:120b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "15m"}),
                supports_tools=True,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="high",
                vram_size_gb=65.0,
                priority="CRITICAL"  # Never evict - this is our only text model
            ),

            # SGLang model (commented out for performance)
            # ModelCapabilities(
            #     name="gpt-oss-120b-eagle3",
            #     backend=BackendConfig(
            #         type="sglang",
            #         endpoint="http://sglang-server:30000",
            #         options={}
            #     ),
            #     supports_tools=True,
            #     supports_thinking=False,
            #     thinking_format="boolean",
            #     context_window=40960,
            #     vram_size_gb=84.0,
            #     priority="CRITICAL"
            # ),

            # Specialized models (Ollama only)
            ModelCapabilities(
                name="ministral-3:14b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_vision=True,
                supports_tools=True,
                vram_size_gb=9.1,
                priority="HIGH"  # Vision tasks need this
            ),
            ModelCapabilities(
                name="qwen3-embedding:4b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "60m"}),
                supports_tools=False,
                vram_size_gb=2.5,
                priority="HIGH"  # Embeddings/RAG need this
            ),
        ]

    @property
    def vram_soft_limit_gb(self) -> float:
        return 100.0  # 119.7GB total - 10GB buffer

    @property
    def vram_hard_limit_gb(self) -> float:
        return 110.0  # 119.7GB total - 10GB buffer (above earlyoom threshold)

    # All text routes use gpt-oss:120b
    @property
    def router_model(self) -> str:
        return "gpt-oss:120b"

    @property
    def simple_coder_model(self) -> str:
        return "gpt-oss:120b"

    @property
    def complex_coder_model(self) -> str:
        return "gpt-oss:120b"

    @property
    def reasoning_model(self) -> str:
        return "gpt-oss:120b"

    @property
    def research_model(self) -> str:
        return "gpt-oss:120b"

    @property
    def math_model(self) -> str:
        return "gpt-oss:120b"

    # Specialized model assignments
    @property
    def vision_model(self) -> str:
        return "ministral-3:14b"

    @property
    def embedding_model(self) -> str:
        return "qwen3-embedding:4b"

    @property
    def summarization_model(self) -> str:
        return "gpt-oss:120b"  # Use 120b for all text tasks

    # NOTE: post_processing_model removed - migrated to artifact_extraction_model

    @property
    def artifact_detection_model(self) -> str:
        """Detection: Does user want file output? (preprocessing)"""
        return "gpt-oss:120b"

    @property
    def artifact_extraction_model(self) -> str:
        """Extraction: Parse response to create file (postprocessing)"""
        return "gpt-oss:120b"

    @property
    def fetch_limits(self) -> dict:
        """Performance fetch limits (large models can process more data)."""
        return {
            'REASONING': 5,   # 5 × 7K = 35K tokens (within 40K context budget)
            'RESEARCH': 5,    # 5 × 7K = 35K tokens (within 40K context budget)
            'default': 5      # Default for other routes
        }

    def validate(self) -> None:
        """Validate all router models exist in available_models."""
        available_names = {m.name for m in self.available_models}
        router_models = {
            self.router_model,
            self.simple_coder_model,
            self.complex_coder_model,
            self.reasoning_model,
            self.research_model,
            self.math_model,
        }

        missing = router_models - available_names
        if missing:
            raise ValueError(f"Performance profile: Models not in roster: {missing}")
