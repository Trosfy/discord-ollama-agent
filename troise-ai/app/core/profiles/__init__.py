"""Configuration profiles for different VRAM setups."""
from typing import Dict, Type

from ..interfaces import IConfigProfile
from ..exceptions import ProfileNotFoundError

from .conservative import ConservativeProfile
from .balanced import BalancedProfile
from .performance import PerformanceProfile

PROFILES: Dict[str, Type[IConfigProfile]] = {
    "conservative": ConservativeProfile,
    "balanced": BalancedProfile,
    "performance": PerformanceProfile,
}


def get_profile(name: str) -> IConfigProfile:
    """
    Factory function to get profile by name.

    Args:
        name: Profile name ('conservative', 'balanced', 'performance')

    Returns:
        Profile instance

    Raises:
        ProfileNotFoundError: If profile name is not found
    """
    if name not in PROFILES:
        raise ProfileNotFoundError(
            f"Unknown profile: {name}. Available: {list(PROFILES.keys())}"
        )
    profile = PROFILES[name]()
    profile.validate()
    return profile


__all__ = [
    "get_profile",
    "ConservativeProfile",
    "BalancedProfile",
    "PerformanceProfile",
    "PROFILES",
]
