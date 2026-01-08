"""Configuration profiles for different VRAM environments."""
from app.config.profiles.interface import IConfigProfile
from app.config.profiles.factory import ProfileFactory
from app.config.profiles.conservative import ConservativeProfile
from app.config.profiles.performance import PerformanceProfile
from app.config.profiles.balanced import BalancedProfile

__all__ = [
    'IConfigProfile',
    'ProfileFactory',
    'ConservativeProfile',
    'PerformanceProfile',
    'BalancedProfile',
]
