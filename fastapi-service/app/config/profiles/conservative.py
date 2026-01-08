"""Conservative Profile for 16GB VRAM systems."""
from typing import List
from app.config import ModelCapabilities, BackendConfig


class ConservativeProfile:
    """
    Configuration profile for 16GB VRAM systems.

    Characteristics:
    - Small model roster (excludes models > 20GB)
    - Tight VRAM limits (14GB hard limit)
    - CRITICAL priority for router (must stay loaded)
    - Graceful degradation (uses best available for each task)

    Following SOLID Principles:
    - Single Responsibility: 16GB system configuration only
    - Liskov Substitution: Can replace any IConfigProfile implementation
    """

    @property
    def profile_name(self) -> str:
        return "conservative"

    @property
    def available_models(self) -> List[ModelCapabilities]:
        return [
            # Router model (CRITICAL - keep loaded)
            ModelCapabilities(
                name="gpt-oss:20b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "60m"}),
                supports_tools=True,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="high",
                vram_size_gb=13.0,
                priority="CRITICAL"  # Never evict router
            ),

            # Fast code model (HIGH priority)
            ModelCapabilities(
                name="rnj-1:8b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_tools=True,
                vram_size_gb=5.1,
                priority="HIGH"
            ),

            # Vision + tools model (NORMAL priority)
            ModelCapabilities(
                name="ministral-3:14b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "15m"}),
                supports_vision=True,
                supports_tools=True,
                vram_size_gb=9.1,
                priority="NORMAL"
            ),

            # OCR model (LOW priority)
            ModelCapabilities(
                name="deepseek-ocr:3b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "20m"}),
                supports_vision=True,
                supports_tools=False,
                vram_size_gb=6.7,
                priority="LOW"
            ),

            # Embedding model (LOW priority)
            ModelCapabilities(
                name="qwen3-embedding:4b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_tools=False,
                vram_size_gb=2.5,
                priority="LOW"
            ),

            # Artifact detection model (LOW priority, small and fast)
            ModelCapabilities(
                name="qwen3:4b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "5s"}),
                supports_tools=True,  # qwen3 supports tools
                supports_thinking=True,  # qwen3 supports thinking
                thinking_format="boolean",
                context_window=262144,
                vram_size_gb=2.5,
                priority="LOW"  # Short-lived, evict quickly
            ),
        ]

    @property
    def vram_soft_limit_gb(self) -> float:
        return 12.0  # 16GB - 4GB overhead

    @property
    def vram_hard_limit_gb(self) -> float:
        return 14.0  # 16GB - 2GB overhead (tight)

    # Router models (graceful degradation)
    @property
    def router_model(self) -> str:
        return "gpt-oss:20b"

    @property
    def simple_coder_model(self) -> str:
        return "rnj-1:8b"

    @property
    def complex_coder_model(self) -> str:
        return "ministral-3:14b"  # Best available (no 120B)

    @property
    def reasoning_model(self) -> str:
        return "gpt-oss:20b"  # Fallback to router

    @property
    def research_model(self) -> str:
        return "gpt-oss:20b"  # Fallback to router

    @property
    def math_model(self) -> str:
        return "rnj-1:8b"

    # Specialized model assignments
    @property
    def vision_model(self) -> str:
        return "ministral-3:14b"

    @property
    def embedding_model(self) -> str:
        return "qwen3-embedding:4b"

    @property
    def summarization_model(self) -> str:
        return "gpt-oss:20b"

    # NOTE: post_processing_model removed - migrated to artifact_extraction_model

    @property
    def artifact_detection_model(self) -> str:
        """Detection: Does user want file output? (preprocessing)"""
        return "qwen3:4b"  # ~2.5GB, fast for YES/NO classification, supports tools

    @property
    def artifact_extraction_model(self) -> str:
        """Extraction: Parse response to create file (postprocessing)"""
        return "qwen3:4b"  # Same model - already loaded, efficient

    @property
    def fetch_limits(self) -> dict:
        """Conservative fetch limits (smaller models need less data)."""
        return {
            'REASONING': 3,  # 3 × 2K = 6K tokens for factual lookup
            'RESEARCH': 5,   # 5 × 2K = 10K tokens for deep research
            'default': 3     # Default for other routes
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
            raise ValueError(f"Conservative profile: Models not in roster: {missing}")
