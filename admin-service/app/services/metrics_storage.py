"""
MetricsStorage Service

Handles DynamoDB operations for metrics storage with hourly bucketing strategy.
Supports 2-day TTL retention and efficient querying across time ranges.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aioboto3
from app.config import settings

logger = logging.getLogger(__name__)


class MetricsStorage:
    """DynamoDB storage service for admin metrics with hourly bucketing."""

    def __init__(self):
        self.session = aioboto3.Session()
        self.table_name = "admin_metrics"

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    async def _get_dynamodb_client(self):
        """Get DynamoDB client with configured credentials."""
        return self.session.resource(
            "dynamodb",
            region_name=settings.DYNAMODB_REGION,
            endpoint_url=settings.DYNAMODB_ENDPOINT,
            aws_access_key_id=settings.DYNAMODB_ACCESS_KEY,
            aws_secret_access_key=settings.DYNAMODB_SECRET_KEY,
        )

    def _get_partition_key(self, metric_type: str, timestamp: datetime) -> str:
        """
        Generate partition key with hourly bucketing.

        Args:
            metric_type: Type of metric (vram, health, psi, queue)
            timestamp: Timestamp for the metric

        Returns:
            Partition key in format: {metric_type}#{YYYY-MM-DDTHH}

        Example:
            vram#2025-01-25T10
        """
        hour_bucket = timestamp.strftime("%Y-%m-%dT%H")
        return f"{metric_type}#{hour_bucket}"

    def _get_sort_key(self, timestamp: datetime) -> str:
        """
        Generate sort key from timestamp.

        Args:
            timestamp: Timestamp for the metric

        Returns:
            ISO format timestamp with milliseconds

        Example:
            2025-01-25T10:30:45.123Z
        """
        return timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    async def write_metric(
        self,
        metric_type: str,
        timestamp: datetime,
        data: dict,
        ttl: int
    ) -> bool:
        """
        Write a single metric to DynamoDB.

        Args:
            metric_type: Type of metric (vram, health, psi, queue)
            timestamp: When the metric was collected
            data: The metric payload
            ttl: TTL as Unix timestamp (should be timestamp + 2 days)

        Returns:
            True if write was successful, False otherwise

        Example:
            await storage.write_metric(
                "vram",
                datetime.utcnow(),
                {"used_gb": 18.5, "total_gb": 24.0},
                int((datetime.utcnow() + timedelta(days=2)).timestamp())
            )
        """
        try:
            async with await self._get_dynamodb_client() as dynamodb:
                table = await dynamodb.Table(self.table_name)

                item = {
                    "PK": self._get_partition_key(metric_type, timestamp),
                    "SK": self._get_sort_key(timestamp),
                    "ttl": ttl,
                    "entity_type": "metric",
                    "metric_type": metric_type,
                    "data": data
                }

                await table.put_item(Item=item)
                logger.debug(f"Wrote metric {metric_type} at {timestamp}")
                return True

        except Exception as e:
            logger.error(f"Failed to write metric {metric_type}: {e}", exc_info=True)
            return False

    async def write_metrics_batch(
        self,
        metrics: List[Dict[str, any]],
        ttl: int
    ) -> int:
        """
        Write multiple metrics in a single batch operation.

        Args:
            metrics: List of metric dictionaries with keys: metric_type, timestamp, data
            ttl: TTL as Unix timestamp (same for all metrics in batch)

        Returns:
            Number of successfully written metrics

        Example:
            metrics = [
                {"metric_type": "vram", "timestamp": now, "data": {...}},
                {"metric_type": "health", "timestamp": now, "data": {...}},
            ]
            count = await storage.write_metrics_batch(metrics, ttl)
        """
        try:
            async with await self._get_dynamodb_client() as dynamodb:
                table = await dynamodb.Table(self.table_name)

                # DynamoDB batch write supports max 25 items per batch
                success_count = 0

                for i in range(0, len(metrics), 25):
                    batch = metrics[i:i+25]

                    async with table.batch_writer() as writer:
                        for metric in batch:
                            item = {
                                "PK": self._get_partition_key(
                                    metric["metric_type"],
                                    metric["timestamp"]
                                ),
                                "SK": self._get_sort_key(metric["timestamp"]),
                                "ttl": ttl,
                                "entity_type": "metric",
                                "metric_type": metric["metric_type"],
                                "data": metric["data"]
                            }
                            await writer.put_item(Item=item)
                            success_count += 1

                logger.debug(f"Wrote {success_count} metrics in batch")
                return success_count

        except Exception as e:
            logger.error(f"Failed to write metrics batch: {e}", exc_info=True)
            return success_count

    def _get_hourly_buckets(
        self,
        start_time: datetime,
        end_time: datetime,
        metric_type: str
    ) -> List[str]:
        """
        Generate list of hourly partition keys to query.

        Args:
            start_time: Start of time range
            end_time: End of time range
            metric_type: Type of metric

        Returns:
            List of partition keys

        Example:
            Input: 2025-01-25T10:30:00Z to 2025-01-25T12:15:00Z, metric_type="vram"
            Output: ["vram#2025-01-25T10", "vram#2025-01-25T11", "vram#2025-01-25T12"]
        """
        buckets = []
        current = start_time.replace(minute=0, second=0, microsecond=0)

        while current <= end_time:
            bucket_key = self._get_partition_key(metric_type, current)
            buckets.append(bucket_key)
            current += timedelta(hours=1)

        return buckets

    async def _query_single_bucket(
        self,
        partition_key: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[dict]:
        """
        Query a single hourly bucket with time range filter.

        Args:
            partition_key: The partition key to query
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of metric items from DynamoDB
        """
        try:
            async with await self._get_dynamodb_client() as dynamodb:
                table = await dynamodb.Table(self.table_name)

                response = await table.query(
                    KeyConditionExpression=(
                        "#pk = :pk AND #sk BETWEEN :start AND :end"
                    ),
                    ExpressionAttributeNames={
                        "#pk": "PK",
                        "#sk": "SK"
                    },
                    ExpressionAttributeValues={
                        ":pk": partition_key,
                        ":start": self._get_sort_key(start_time),
                        ":end": self._get_sort_key(end_time)
                    }
                )

                return response.get("Items", [])

        except Exception as e:
            logger.error(
                f"Failed to query bucket {partition_key}: {e}",
                exc_info=True
            )
            return []

    async def query_metrics(
        self,
        metric_type: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[dict]:
        """
        Query metrics across multiple hourly buckets in parallel.

        Args:
            metric_type: Type of metric to query
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of all metric items, sorted by timestamp

        Example:
            points = await storage.query_metrics(
                "vram",
                datetime.utcnow() - timedelta(hours=2),
                datetime.utcnow()
            )
        """
        try:
            # Get all hourly buckets to query
            buckets = self._get_hourly_buckets(start_time, end_time, metric_type)

            # Query all buckets in parallel for performance
            tasks = [
                self._query_single_bucket(bucket, start_time, end_time)
                for bucket in buckets
            ]

            results = await asyncio.gather(*tasks)

            # Flatten and sort by timestamp
            all_points = []
            for bucket_points in results:
                all_points.extend(bucket_points)

            all_points.sort(key=lambda x: x["SK"])

            logger.debug(
                f"Queried {len(all_points)} {metric_type} metrics "
                f"from {len(buckets)} buckets"
            )

            return all_points

        except Exception as e:
            logger.error(
                f"Failed to query metrics {metric_type}: {e}",
                exc_info=True
            )
            return []

    async def create_table(self) -> bool:
        """
        Create the admin_metrics table if it doesn't exist.

        Returns:
            True if table was created or already exists, False on error

        Note:
            This should be called during service startup or via setup script.
        """
        try:
            async with await self._get_dynamodb_client() as dynamodb:
                try:
                    # Check if table exists
                    table = await dynamodb.Table(self.table_name)
                    await table.load()
                    logger.info(f"Table {self.table_name} already exists")
                    return True

                except dynamodb.meta.client.exceptions.ResourceNotFoundException:
                    # Create table
                    table = await dynamodb.create_table(
                        TableName=self.table_name,
                        KeySchema=[
                            {"AttributeName": "PK", "KeyType": "HASH"},  # Partition key
                            {"AttributeName": "SK", "KeyType": "RANGE"}  # Sort key
                        ],
                        AttributeDefinitions=[
                            {"AttributeName": "PK", "AttributeType": "S"},
                            {"AttributeName": "SK", "AttributeType": "S"}
                        ],
                        BillingMode="PAY_PER_REQUEST",  # On-demand pricing
                        TimeToLiveSpecification={
                            "AttributeName": "ttl",
                            "Enabled": True
                        }
                    )

                    # Wait for table to be created
                    await table.meta.client.get_waiter("table_exists").wait(
                        TableName=self.table_name
                    )

                    logger.info(f"Created table {self.table_name} with TTL enabled")
                    return True

        except Exception as e:
            logger.error(f"Failed to create table {self.table_name}: {e}", exc_info=True)
            return False
