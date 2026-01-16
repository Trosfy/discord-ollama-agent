"""Base DynamoDB client configuration for TROISE AI.

Provides shared client setup and configuration for all DynamoDB adapters.
Uses aioboto3 for async operations.
"""
import os
import logging
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

import aioboto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """
    Shared DynamoDB client configuration.

    Provides async context managers for DynamoDB resource and client.
    Configuration is loaded from environment variables.

    Environment Variables:
        DYNAMODB_ENDPOINT: DynamoDB endpoint URL (default: http://localhost:8000)
        DYNAMODB_REGION: AWS region (default: us-east-1)
        DYNAMODB_ACCESS_KEY: AWS access key (default: test for local)
        DYNAMODB_SECRET_KEY: AWS secret key (default: test for local)

    Example:
        client = DynamoDBClient()

        async with client.resource() as dynamodb:
            table = await dynamodb.Table('troise_main')
            await table.put_item(Item={...})

        async with client.client() as dynamo_client:
            response = await dynamo_client.query(...)
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize DynamoDB client configuration.

        Args:
            endpoint_url: DynamoDB endpoint (overrides env var).
            region_name: AWS region (overrides env var).
            access_key: AWS access key (overrides env var).
            secret_key: AWS secret key (overrides env var).
        """
        self._endpoint_url = endpoint_url or os.getenv(
            'DYNAMODB_ENDPOINT', 'http://localhost:8000'
        )
        self._region_name = region_name or os.getenv(
            'DYNAMODB_REGION', 'us-east-1'
        )
        self._access_key = access_key or os.getenv(
            'DYNAMODB_ACCESS_KEY', 'test'
        )
        self._secret_key = secret_key or os.getenv(
            'DYNAMODB_SECRET_KEY', 'test'
        )
        self._session = aioboto3.Session()

        # Configure retries and timeouts
        self._config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=5,
            read_timeout=30,
        )

        logger.debug(f"DynamoDB client configured for {self._endpoint_url}")

    @property
    def _resource_config(self) -> Dict[str, Any]:
        """Get configuration dict for resource/client creation."""
        return {
            'endpoint_url': self._endpoint_url,
            'region_name': self._region_name,
            'aws_access_key_id': self._access_key,
            'aws_secret_access_key': self._secret_key,
            'config': self._config,
        }

    @asynccontextmanager
    async def resource(self):
        """
        Get async DynamoDB resource context manager.

        Yields:
            DynamoDB resource for table operations.

        Example:
            async with client.resource() as dynamodb:
                table = await dynamodb.Table('troise_main')
        """
        async with self._session.resource('dynamodb', **self._resource_config) as dynamodb:
            yield dynamodb

    @asynccontextmanager
    async def client(self):
        """
        Get async DynamoDB client context manager.

        Yields:
            DynamoDB client for low-level operations.

        Example:
            async with client.client() as dynamo:
                response = await dynamo.query(...)
        """
        async with self._session.client('dynamodb', **self._resource_config) as dynamo:
            yield dynamo

    async def get_table(self, table_name: str):
        """
        Get a table reference (for use within a resource context).

        Note: This creates a new resource context. For multiple operations,
        use the resource() context manager directly.

        Args:
            table_name: Name of the DynamoDB table.

        Returns:
            Table resource.
        """
        async with self.resource() as dynamodb:
            return await dynamodb.Table(table_name)

    async def health_check(self) -> bool:
        """
        Check if DynamoDB is accessible.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            async with self.client() as dynamo:
                await dynamo.list_tables(Limit=1)
            return True
        except Exception as e:
            logger.warning(f"DynamoDB health check failed: {e}")
            return False

    def __repr__(self) -> str:
        return f"DynamoDBClient(endpoint={self._endpoint_url}, region={self._region_name})"
