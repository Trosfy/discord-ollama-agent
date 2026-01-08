"""
JSON Encoder Utilities

Provides custom JSON encoders for handling types that aren't natively JSON serializable:
- Decimal (from DynamoDB)
- datetime objects
- Other custom types
"""

import json
from decimal import Decimal
from datetime import datetime, date
from typing import Any


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles:
    - Decimal → float
    - datetime → ISO 8601 string
    - date → ISO 8601 string
    - Other types → default behavior
    """
    
    def default(self, obj: Any) -> Any:
        """Convert non-JSON-serializable types to JSON-compatible formats."""
        if isinstance(obj, Decimal):
            # Convert Decimal to float
            return float(obj)
        elif isinstance(obj, datetime):
            # Convert datetime to ISO 8601 string
            return obj.isoformat()
        elif isinstance(obj, date):
            # Convert date to ISO 8601 string
            return obj.isoformat()
        
        # Let the base class raise TypeError for unsupported types
        return super().default(obj)


def json_dumps(obj: Any, **kwargs) -> str:
    """
    JSON dumps with custom encoder.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        JSON string
        
    Example:
        >>> from decimal import Decimal
        >>> from datetime import datetime
        >>> data = {
        ...     "value": Decimal("123.45"),
        ...     "timestamp": datetime(2025, 1, 1)
        ... }
        >>> json_dumps(data)
        '{"value": 123.45, "timestamp": "2025-01-01T00:00:00"}'
    """
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)
