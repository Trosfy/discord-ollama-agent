"""Balanced Profile for 128GB VRAM systems."""
from typing import List
from app.config import ModelCapabilities, BackendConfig


class BalancedProfile:
    """
    Configuration profile for 128GB VRAM systems with model variety.

    Strategy: Full Ollama model zoo including gpt-oss:120b.
    No SGLang dependency - pure Ollama orchestration for maximum flexibility.

    Characteristics:
    - Full model zoo (10+ models, no SGLang)
    - gpt-oss:120b from Ollama for heavy text tasks
    - VRAM limits: 100GB soft, 110GB hard (119GB - 9GB buffer)
    - Model variety over speed (no EAGLE3 speedup, but more diverse capabilities)
    - Suitable for workloads requiring different specialized models

    Following SOLID Principles:
    - Single Responsibility: 128GB system with Ollama-only configuration
    - Liskov Substitution: Can replace any IConfigProfile implementation
    """

    @property
    def profile_name(self) -> str:
        return "balanced"

    @property
    def available_models(self) -> List[ModelCapabilities]:
        return [
            # Router models
            ModelCapabilities(
                name="gpt-oss:20b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_tools=True,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="high",
                vram_size_gb=13.0,
                priority="HIGH"
            ),
            ModelCapabilities(
                name="gpt-oss:120b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "15m"}),
                supports_tools=True,
                supports_thinking=True,
                thinking_format="level",
                default_thinking_level="high",
                vram_size_gb=76.0,  # Ollama GGUF version
                priority="HIGH"  # Primary large model for complex tasks
            ),

            # Code models
            ModelCapabilities(
                name="rnj-1:8b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_tools=True,
                vram_size_gb=5.1,
                priority="HIGH"
            ),
            ModelCapabilities(
                name="ministral-3:14b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "20m"}),
                supports_vision=True,
                supports_tools=True,
                vram_size_gb=9.1,
                priority="NORMAL"
            ),
            ModelCapabilities(
                name="devstral-small-2:24b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "20m"}),
                supports_tools=True,
                vram_size_gb=15.0,
                priority="NORMAL"
            ),
            ModelCapabilities(
                name="devstral-2:123b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "5m"}),
                supports_tools=True,
                vram_size_gb=74.0,
                priority="LOW"  # Huge model, evict aggressively
            ),

            # Reasoning models
            ModelCapabilities(
                name="deepseek-r1:70b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "10m"}),
                supports_tools=False,
                supports_thinking=True,
                thinking_format="boolean",
                vram_size_gb=42.0,
                priority="LOW"
            ),
            ModelCapabilities(
                name="nemotron-3-nano:30b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "15m"}),
                supports_tools=False,
                vram_size_gb=24.0,
                priority="NORMAL"
            ),

            # Specialized models
            ModelCapabilities(
                name="deepseek-ocr:3b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "30m"}),
                supports_vision=True,
                supports_tools=False,
                vram_size_gb=6.7,
                priority="LOW"
            ),
            ModelCapabilities(
                name="qwen3-embedding:4b",
                backend=BackendConfig(type="ollama", options={"keep_alive": "60m"}),
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
        return 100.0  # 119GB total - 19GB buffer (safe zone)

    @property
    def vram_hard_limit_gb(self) -> float:
        return 110.0  # 119GB total - 9GB buffer (3% + margin)

    # Router models (balanced approach)
    @property
    def router_model(self) -> str:
        return "gpt-oss:20b"

    @property
    def simple_coder_model(self) -> str:
        return "rnj-1:8b"

    @property
    def complex_coder_model(self) -> str:
        return "gpt-oss:120b"  # Use 120B for complex tasks

    @property
    def reasoning_model(self) -> str:
        return "gpt-oss:120b"  # Use 120B for reasoning

    @property
    def research_model(self) -> str:
        return "gpt-oss:120b"  # Use 120B for research

    @property
    def math_model(self) -> str:
        return "gpt-oss:120b"  # Use 120B for math

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
        return "qwen3:4b"  # Same model - efficient

    @property
    def fetch_limits(self) -> dict:
        """Balanced fetch limits (moderate models, moderate data needs)."""
        return {
            'REASONING': 4,  # 4 × 2K = 8K tokens for balanced analysis
            'RESEARCH': 5,   # 5 × 2K = 10K tokens for research
            'default': 4     # Default for other routes
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
            raise ValueError(f"Balanced profile: Models not in roster: {missing}")
