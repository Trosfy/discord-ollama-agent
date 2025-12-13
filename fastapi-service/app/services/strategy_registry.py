"""Strategy registry for preprocessing/postprocessing (Open/Closed Principle)."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, List
from app.interfaces.processing_strategy import ProcessingStrategy
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class StrategyRegistry:
    """Registry for preprocessing/postprocessing strategies (Open/Closed)."""

    def __init__(self):
        """Initialize empty strategy registry."""
        self._strategies: Dict[str, ProcessingStrategy] = {}
        logger.info("✅ StrategyRegistry initialized")

    def register(self, name: str, strategy: ProcessingStrategy):
        """
        Register a processing strategy.

        Args:
            name: Strategy name (e.g., 'OUTPUT_ARTIFACT')
            strategy: Strategy instance implementing ProcessingStrategy interface
        """
        self._strategies[name] = strategy
        logger.info(f"📝 Registered strategy: {name}")

    def get(self, name: str) -> ProcessingStrategy:
        """
        Get a processing strategy by name.

        Args:
            name: Strategy name

        Returns:
            Strategy instance or None if not found
        """
        return self._strategies.get(name)

    async def execute(self, name: str, context: Dict) -> List[Dict]:
        """
        Execute a strategy by name.

        Args:
            name: Strategy name
            context: Processing context

        Returns:
            List of processing results (empty list if strategy not found)
        """
        strategy = self.get(name)
        if strategy:
            logger.info(f"▶️  Executing strategy: {name}")
            return await strategy.process(context)

        logger.warning(f"⚠️  Strategy not found: {name}")
        return []

    def list_strategies(self) -> List[str]:
        """Get list of registered strategy names."""
        return list(self._strategies.keys())
