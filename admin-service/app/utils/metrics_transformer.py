"""
Metrics Transformer Utility

Provides utilities for transforming metrics data between different formats.
Follows Single Responsibility Principle by isolating data transformation logic.
"""

from typing import Any
from decimal import Decimal
from datetime import datetime


class MetricsTransformer:
    """
    Utility class for transforming metrics data.

    Responsibilities:
    - Convert data types for storage compatibility (e.g., float → Decimal for DynamoDB)
    - Transform metric formats
    - Validate metric data structures

    This class isolates data transformation logic from business services,
    making transformations reusable and testable.
    """

    @staticmethod
    def convert_floats_to_decimal(obj: Any) -> Any:
        """
        Recursively convert all float values to Decimal and datetime to ISO strings
        for DynamoDB compatibility.

        DynamoDB requires:
        - Decimal type instead of float for numeric values
        - String representation for datetime objects

        Args:
            obj: Object to convert (dict, list, float, datetime, or other)

        Returns:
            Object with all floats converted to Decimal and datetime to ISO strings

        Example:
            >>> from datetime import datetime
            >>> data = {"usage": 45.5, "stats": [1.2, 3.4], "timestamp": datetime(2025, 1, 1)}
            >>> MetricsTransformer.convert_floats_to_decimal(data)
            {'usage': Decimal('45.5'), 'stats': [Decimal('1.2'), Decimal('3.4')],
             'timestamp': '2025-01-01T00:00:00'}
        """
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: MetricsTransformer.convert_floats_to_decimal(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [MetricsTransformer.convert_floats_to_decimal(item) for item in obj]
        else:
            return obj

    @staticmethod
    def convert_decimal_to_float(obj: Any) -> Any:
        """
        Recursively convert all Decimal values to float for JSON compatibility.

        Useful when reading from DynamoDB and need to serialize to JSON.

        Args:
            obj: Object to convert (dict, list, Decimal, or other)

        Returns:
            Object with all Decimals converted to float

        Example:
            >>> from decimal import Decimal
            >>> data = {"usage": Decimal("45.5"), "stats": [Decimal("1.2")]}
            >>> MetricsTransformer.convert_decimal_to_float(data)
            {'usage': 45.5, 'stats': [1.2]}
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: MetricsTransformer.convert_decimal_to_float(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [MetricsTransformer.convert_decimal_to_float(item) for item in obj]
        else:
            return obj

    @staticmethod
    def sanitize_metric_name(name: str) -> str:
        """
        Sanitize metric name for storage.

        Replaces invalid characters with underscores.

        Args:
            name: Metric name to sanitize

        Returns:
            Sanitized metric name

        Example:
            >>> MetricsTransformer.sanitize_metric_name("cpu-usage.percent")
            'cpu_usage_percent'
        """
        return name.replace("-", "_").replace(".", "_").lower()

    @staticmethod
    def validate_metric_structure(metric: dict, required_fields: list) -> bool:
        """
        Validate that a metric dict contains all required fields.

        Args:
            metric: Metric dictionary to validate
            required_fields: List of required field names

        Returns:
            bool: True if all required fields present

        Example:
            >>> metric = {"timestamp": "2024-01-01", "value": 42}
            >>> MetricsTransformer.validate_metric_structure(metric, ["timestamp", "value"])
            True
        """
        return all(field in metric for field in required_fields)

    @staticmethod
    def normalize_percentage(value: Any) -> float:
        """
        Normalize percentage value to 0-100 range.

        Handles various input formats:
        - String with "%" suffix: "45.5%" → 45.5
        - Float/int between 0-1: 0.455 → 45.5
        - Float/int between 0-100: 45.5 → 45.5

        Args:
            value: Percentage value in various formats

        Returns:
            float: Normalized percentage (0-100)

        Example:
            >>> MetricsTransformer.normalize_percentage("45.5%")
            45.5
            >>> MetricsTransformer.normalize_percentage(0.455)
            45.5
        """
        if isinstance(value, str):
            # Remove % and convert
            value = value.rstrip("%")
            return float(value)
        elif isinstance(value, (int, float)):
            # If value is between 0-1, assume it's a fraction
            if 0 <= value <= 1:
                return value * 100
            # Otherwise assume it's already 0-100
            return float(value)
        else:
            return 0.0
