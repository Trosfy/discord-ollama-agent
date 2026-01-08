"""Profile Factory (Open/Closed Principle)."""
from typing import Dict, Type
import logging_client

logger = logging_client.setup_logger('config')


class ProfileFactory:
    """
    Factory for loading configuration profiles (Open/Closed Principle).

    Adding new profiles:
    1. Create new profile class implementing IConfigProfile
    2. Register in _PROFILES dict
    3. No changes to Settings or other components needed

    Following SOLID Principles:
    - Single Responsibility: Profile loading/validation only
    - Open/Closed: New profiles added without modifying existing code
    """

    _PROFILES: Dict[str, Type['IConfigProfile']] = {}  # noqa: F821

    @staticmethod
    def load_profile(profile_name: str) -> 'IConfigProfile':  # noqa: F821
        """
        Load configuration profile by name.

        Args:
            profile_name: Profile identifier ("conservative", "performance", "balanced")

        Returns:
            Profile instance implementing IConfigProfile

        Raises:
            ValueError: If profile not found or validation fails
        """
        # Lazy import to avoid circular dependency
        if not ProfileFactory._PROFILES:
            from app.config.profiles.conservative import ConservativeProfile
            from app.config.profiles.performance import PerformanceProfile
            from app.config.profiles.balanced import BalancedProfile

            ProfileFactory._PROFILES = {
                "conservative": ConservativeProfile,
                "performance": PerformanceProfile,
                "balanced": BalancedProfile,
            }

        if profile_name not in ProfileFactory._PROFILES:
            available = ", ".join(ProfileFactory._PROFILES.keys())
            raise ValueError(
                f"Unknown profile: '{profile_name}'. Available: {available}"
            )

        profile_class = ProfileFactory._PROFILES[profile_name]
        profile = profile_class()

        # Validate profile consistency
        profile.validate()

        logger.info(f"✅ Loaded '{profile_name}' profile")
        logger.info(f"   Models: {len(profile.available_models)}")
        logger.info(f"   VRAM limit: {profile.vram_hard_limit_gb}GB")

        return profile

    @staticmethod
    def get_default_profile() -> str:
        """Get default profile name."""
        return "performance"
