"""
Metrics Aggregator

Handles aggregation of time-series metric data with support for:
- Simple (raw) data points
- Statistical aggregations: max, min, sum, avg
- Percentiles: p95, p99

Implements granularity bucketing to downsample 5s data to larger intervals.
"""

import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates time-series metrics data with configurable granularity."""

    @staticmethod
    def extract_field_value(data_point: dict, field: str) -> Optional[float]:
        """
        Extract a numeric field from nested data structure.

        Args:
            data_point: DynamoDB item with nested 'data' attribute
            field: Field path, supports dot notation (e.g., "psi.cpu")

        Returns:
            Float value or None if field doesn't exist or is non-numeric

        Example:
            data_point = {
                "PK": "vram#2025-01-25T10",
                "SK": "2025-01-25T10:30:45Z",
                "data": {
                    "used_gb": 18.5,
                    "total_gb": 24.0
                }
            }
            value = extract_field_value(data_point, "used_gb")  # Returns 18.5
        """
        try:
            data = data_point.get("data", {})

            # Support dot notation for nested fields (e.g., "psi.cpu")
            field_parts = field.split(".")
            value = data

            for part in field_parts:
                value = value.get(part)
                if value is None:
                    return None

            # Handle numeric types (int, float, Decimal from DynamoDB)
            if isinstance(value, (int, float, Decimal)):
                return float(value)

            # Handle boolean values (convert True->1.0, False->0.0)
            if isinstance(value, bool):
                return float(value)

            return None

        except (KeyError, TypeError, AttributeError):
            return None

    @staticmethod
    def extract_field_values(data_points: List[dict], field: str) -> List[float]:
        """
        Extract numeric field from multiple data points.

        Args:
            data_points: List of DynamoDB items
            field: Field path to extract

        Returns:
            List of numeric values (skips invalid/missing data)

        Example:
            points = [
                {"SK": "10:00:00Z", "data": {"used_gb": 18.5}},
                {"SK": "10:00:05Z", "data": {"used_gb": 18.6}},
            ]
            values = extract_field_values(points, "used_gb")  # [18.5, 18.6]
        """
        values = []

        for point in data_points:
            value = MetricsAggregator.extract_field_value(point, field)
            if value is not None:
                values.append(value)

        return values

    @staticmethod
    def bucket_by_granularity(
        data_points: List[dict],
        field: str,
        granularity: int
    ) -> List[Tuple[datetime, List[float]]]:
        """
        Group data points into time buckets based on granularity.

        Args:
            data_points: List of DynamoDB items with SK (timestamp)
            field: Field to extract from each point
            granularity: Bucket size in seconds (e.g., 60 for 1 minute)

        Returns:
            List of (bucket_timestamp, values_in_bucket) tuples

        Example:
            granularity = 60 (1 minute)
            Raw points (5s intervals):
                - 10:00:00 -> 18.5
                - 10:00:05 -> 18.6
                - ...
                - 10:00:55 -> 19.0

            Bucketed output:
                - (10:00:00, [18.5, 18.6, 18.7, ..., 19.0])  # 12 values
                - (10:01:00, [19.1, 19.2, ...])              # 12 values
        """
        if granularity <= 5:
            # No bucketing needed for 5s granularity (raw data)
            result = []
            for point in data_points:
                timestamp = datetime.fromisoformat(
                    point["SK"].replace("Z", "+00:00")
                )
                value = MetricsAggregator.extract_field_value(point, field)
                if value is not None:
                    result.append((timestamp, [value]))
            return result

        buckets = {}

        for point in data_points:
            # Parse timestamp from sort key
            timestamp = datetime.fromisoformat(
                point["SK"].replace("Z", "+00:00")
            )
            value = MetricsAggregator.extract_field_value(point, field)

            if value is None:
                continue

            # Round timestamp down to nearest granularity interval
            bucket_time = timestamp.replace(microsecond=0)
            bucket_seconds = (bucket_time.minute * 60 + bucket_time.second)
            rounded_seconds = (bucket_seconds // granularity) * granularity

            bucket_time = bucket_time.replace(
                minute=rounded_seconds // 60,
                second=rounded_seconds % 60
            )

            if bucket_time not in buckets:
                buckets[bucket_time] = []

            buckets[bucket_time].append(value)

        # Sort by timestamp
        return sorted(buckets.items(), key=lambda x: x[0])

    @staticmethod
    def calculate_percentile(values: List[float], percentile: int) -> float:
        """
        Calculate percentile using nearest-rank method.

        Args:
            values: List of numeric values
            percentile: Percentile to calculate (e.g., 95 for p95)

        Returns:
            Percentile value

        Example:
            values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
            p95 = calculate_percentile(values, 95)  # Returns 10
            p99 = calculate_percentile(values, 99)  # Returns 10
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)

        # Calculate index using nearest-rank method
        index = (percentile / 100) * len(sorted_values)

        # Use ceiling for nearest-rank
        index = int(math.ceil(index)) - 1

        # Clamp to valid range
        index = max(0, min(index, len(sorted_values) - 1))

        return sorted_values[index]

    @staticmethod
    def aggregate_values(values: List[float], aggregation: str) -> Optional[float]:
        """
        Apply aggregation function to a list of values.

        Args:
            values: List of numeric values
            aggregation: Type of aggregation (simple, max, min, sum, avg, p95, p99)

        Returns:
            Aggregated value or None if values list is empty

        Raises:
            ValueError: If aggregation type is unknown

        Example:
            values = [10, 20, 30, 40, 50]

            aggregate_values(values, "max")    # 50
            aggregate_values(values, "min")    # 10
            aggregate_values(values, "avg")    # 30
            aggregate_values(values, "sum")    # 150
            aggregate_values(values, "p95")    # 50
        """
        if not values:
            return None

        if aggregation == "simple":
            # For simple, return first value
            return values[0]

        elif aggregation == "max":
            return max(values)

        elif aggregation == "min":
            return min(values)

        elif aggregation == "sum":
            return sum(values)

        elif aggregation == "avg":
            return sum(values) / len(values)

        elif aggregation == "p95":
            return MetricsAggregator.calculate_percentile(values, 95)

        elif aggregation == "p99":
            return MetricsAggregator.calculate_percentile(values, 99)

        else:
            raise ValueError(f"Unknown aggregation type: {aggregation}")

    @staticmethod
    def calculate_summary_stats(values: List[float]) -> Dict[str, Optional[float]]:
        """
        Calculate comprehensive summary statistics.

        Args:
            values: List of numeric values

        Returns:
            Dictionary with count, min, max, avg, p95, p99

        Example:
            values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
            summary = calculate_summary_stats(values)

            # Returns:
            # {
            #     "count": 10,
            #     "min": 10,
            #     "max": 100,
            #     "avg": 55.0,
            #     "p95": 95,
            #     "p99": 99
            # }
        """
        if not values:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "p95": None,
                "p99": None
            }

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p95": MetricsAggregator.calculate_percentile(values, 95),
            "p99": MetricsAggregator.calculate_percentile(values, 99)
        }

    @staticmethod
    def aggregate_time_series(
        data_points: List[dict],
        field: str,
        granularity: int,
        aggregation: str
    ) -> Tuple[List[dict], Dict[str, Optional[float]]]:
        """
        Complete time-series aggregation pipeline.

        Args:
            data_points: Raw DynamoDB metric items
            field: Field to extract and aggregate
            granularity: Bucket size in seconds
            aggregation: Aggregation type

        Returns:
            Tuple of (aggregated_data_points, summary_stats)

            aggregated_data_points: List of {timestamp, value} dicts
            summary_stats: Overall statistics for entire time range

        Example:
            points = await storage.query_metrics("vram", start, end)

            data, summary = MetricsAggregator.aggregate_time_series(
                points,
                field="used_gb",
                granularity=60,
                aggregation="avg"
            )

            # data = [
            #     {"timestamp": "2025-01-25T10:00:00Z", "value": 18.5},
            #     {"timestamp": "2025-01-25T10:01:00Z", "value": 18.7},
            #     ...
            # ]
            #
            # summary = {
            #     "count": 1440,
            #     "min": 15.2,
            #     "max": 22.5,
            #     "avg": 18.6,
            #     "p95": 21.2,
            #     "p99": 22.1
            # }
        """
        try:
            # Extract all values for summary stats
            all_values = MetricsAggregator.extract_field_values(data_points, field)

            # Bucket by granularity
            bucketed_data = MetricsAggregator.bucket_by_granularity(
                data_points, field, granularity
            )

            # Apply aggregation to each bucket
            aggregated_points = []
            for timestamp, bucket_values in bucketed_data:
                aggregated_value = MetricsAggregator.aggregate_values(
                    bucket_values, aggregation
                )

                if aggregated_value is not None:
                    aggregated_points.append({
                        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                        "value": aggregated_value
                    })

            # Calculate summary statistics
            summary = MetricsAggregator.calculate_summary_stats(all_values)

            logger.debug(
                f"Aggregated {len(all_values)} raw values into "
                f"{len(aggregated_points)} {aggregation} data points "
                f"at {granularity}s granularity"
            )

            return aggregated_points, summary

        except Exception as e:
            logger.error(f"Error aggregating time series: {e}", exc_info=True)
            return [], {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "p95": None,
                "p99": None
            }
