"""Processing strategy interface (Open/Closed Principle)."""
from abc import ABC, abstractmethod
from typing import Dict, List


class ProcessingStrategy(ABC):
    """Base interface for processing strategies (Open/Closed Principle)."""

    @abstractmethod
    async def process(self, context: Dict) -> List[Dict]:
        """
        Execute processing strategy.

        Args:
            context: Processing context with required data

        Returns:
            List of processing results (e.g., artifact metadata)
        """
        pass
