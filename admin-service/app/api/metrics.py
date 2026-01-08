"""
Metrics API - Historical Time-Series Data

Provides endpoints for querying historical metrics with:
- Configurable time ranges
- Multiple aggregation types (simple, max, min, avg, sum, p95, p99)
- Adjustable granularity (5s, 1m, 5m, 1h, etc.)
- Summary statistics
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.middleware.auth import require_admin
from app.services.metrics_storage import MetricsStorage
from app.services.metrics_aggregator import MetricsAggregator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/metrics", tags=["metrics"])


# Valid metric types
VALID_METRIC_TYPES = ["vram", "health", "psi", "queue"]

# Valid aggregation types
VALID_AGGREGATIONS = ["simple", "max", "min", "sum", "avg", "p95", "p99"]

# Valid granularity values (in seconds)
VALID_GRANULARITIES = [5, 60, 300, 900, 1800, 3600]  # 5s, 1m, 5m, 15m, 30m, 1h


@router.get("/history")
async def get_metrics_history(
    metric_type: str = Query(..., description="Metric type (vram, health, psi, queue)"),
    field: str = Query(..., description="Field to extract (e.g., used_gb, cpu, memory)"),
    start_time: str = Query(..., description="Start time (ISO 8601 format)"),
    end_time: str = Query(..., description="End time (ISO 8601 format)"),
    granularity: int = Query(5, description="Granularity in seconds (5, 60, 300, 3600)"),
    aggregation: str = Query("simple", description="Aggregation type"),
    admin_auth: Dict = Depends(require_admin)
) -> Dict:
    """
    Query historical metrics data with aggregation.

    Args:
        metric_type: Type of metric (vram, health, psi, queue)
        field: Field to extract (supports dot notation, e.g., "psi.cpu")
        start_time: Start of time range (ISO 8601 format)
        end_time: End of time range (ISO 8601 format)
        granularity: Time bucket size in seconds
        aggregation: How to aggregate values (simple, max, min, sum, avg, p95, p99)
        admin_auth: Admin authentication (injected by middleware)

    Returns:
        Dictionary with:
            - metric_type: The queried metric type
            - field: The queried field
            - start_time: Query start time
            - end_time: Query end time
            - granularity: Bucket size used
            - aggregation: Aggregation type used
            - data_points: List of {timestamp, value} objects
            - summary: Overall statistics {count, min, max, avg, p95, p99}

    Example:
        GET /admin/metrics/history?
            metric_type=vram&
            field=usage_percentage&
            start_time=2025-01-25T10:00:00Z&
            end_time=2025-01-25T12:00:00Z&
            granularity=60&
            aggregation=avg

        Response:
        {
            "metric_type": "vram",
            "field": "usage_percentage",
            "start_time": "2025-01-25T10:00:00Z",
            "end_time": "2025-01-25T12:00:00Z",
            "granularity": 60,
            "aggregation": "avg",
            "data_points": [
                {"timestamp": "2025-01-25T10:00:00Z", "value": 77.5},
                {"timestamp": "2025-01-25T10:01:00Z", "value": 78.2},
                ...
            ],
            "summary": {
                "count": 120,
                "min": 75.0,
                "max": 85.0,
                "avg": 77.8,
                "p95": 82.5,
                "p99": 84.2
            }
        }
    """
    try:
        # Validate inputs
        if metric_type not in VALID_METRIC_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric_type. Must be one of: {VALID_METRIC_TYPES}"
            )

        if aggregation not in VALID_AGGREGATIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid aggregation. Must be one of: {VALID_AGGREGATIONS}"
            )

        if granularity not in VALID_GRANULARITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid granularity. Must be one of: {VALID_GRANULARITIES}"
            )

        # Parse timestamps
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timestamp format. Use ISO 8601 format: {e}"
            )

        # Validate time range
        if start_dt >= end_dt:
            raise HTTPException(
                status_code=400,
                detail="start_time must be before end_time"
            )

        time_range = end_dt - start_dt
        if time_range > timedelta(days=2):
            raise HTTPException(
                status_code=400,
                detail="Time range cannot exceed 2 days (data retention limit)"
            )

        # Query metrics from DynamoDB
        storage = MetricsStorage()
        raw_points = await storage.query_metrics(metric_type, start_dt, end_dt)

        if not raw_points:
            logger.warning(
                f"No data found for {metric_type}.{field} "
                f"in range {start_time} to {end_time}"
            )
            return {
                "metric_type": metric_type,
                "field": field,
                "start_time": start_time,
                "end_time": end_time,
                "granularity": granularity,
                "aggregation": aggregation,
                "data_points": [],
                "summary": {
                    "count": 0,
                    "min": None,
                    "max": None,
                    "avg": None,
                    "p95": None,
                    "p99": None
                }
            }

        # Aggregate data
        aggregated_points, summary = MetricsAggregator.aggregate_time_series(
            raw_points,
            field,
            granularity,
            aggregation
        )

        logger.info(
            f"Returned {len(aggregated_points)} {metric_type}.{field} data points "
            f"for user {admin_auth.get('user_id')} "
            f"({aggregation} @ {granularity}s granularity)"
        )

        return {
            "metric_type": metric_type,
            "field": field,
            "start_time": start_time,
            "end_time": end_time,
            "granularity": granularity,
            "aggregation": aggregation,
            "data_points": aggregated_points,
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying metrics history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query metrics: {str(e)}"
        )


@router.get("/summary")
async def get_metrics_summary(
    metric_type: str = Query(..., description="Metric type (vram, health, psi, queue)"),
    field: str = Query(..., description="Field to extract (e.g., used_gb, cpu)"),
    start_time: str = Query(..., description="Start time (ISO 8601 format)"),
    end_time: str = Query(..., description="End time (ISO 8601 format)"),
    admin_auth: Dict = Depends(require_admin)
) -> Dict:
    """
    Get summary statistics for a metric over a time range.

    Faster than /history endpoint since it doesn't return data points,
    only overall statistics.

    Args:
        metric_type: Type of metric (vram, health, psi, queue)
        field: Field to extract
        start_time: Start of time range (ISO 8601 format)
        end_time: End of time range (ISO 8601 format)
        admin_auth: Admin authentication (injected by middleware)

    Returns:
        Dictionary with:
            - metric_type: The queried metric type
            - field: The queried field
            - time_range: {start, end}
            - statistics: {count, min, max, avg, p95, p99}

    Example:
        GET /admin/metrics/summary?
            metric_type=vram&
            field=used_gb&
            start_time=2025-01-25T00:00:00Z&
            end_time=2025-01-25T23:59:59Z

        Response:
        {
            "metric_type": "vram",
            "field": "used_gb",
            "time_range": {
                "start": "2025-01-25T00:00:00Z",
                "end": "2025-01-25T23:59:59Z"
            },
            "statistics": {
                "count": 17280,
                "min": 15.2,
                "max": 22.8,
                "avg": 18.6,
                "p95": 21.5,
                "p99": 22.3
            }
        }
    """
    try:
        # Validate inputs
        if metric_type not in VALID_METRIC_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric_type. Must be one of: {VALID_METRIC_TYPES}"
            )

        # Parse timestamps
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timestamp format. Use ISO 8601 format: {e}"
            )

        # Validate time range
        if start_dt >= end_dt:
            raise HTTPException(
                status_code=400,
                detail="start_time must be before end_time"
            )

        # Query metrics
        storage = MetricsStorage()
        raw_points = await storage.query_metrics(metric_type, start_dt, end_dt)

        # Extract values and calculate summary
        values = MetricsAggregator.extract_field_values(raw_points, field)
        summary = MetricsAggregator.calculate_summary_stats(values)

        logger.info(
            f"Returned summary for {metric_type}.{field} "
            f"({summary['count']} data points) "
            f"for user {admin_auth.get('user_id')}"
        )

        return {
            "metric_type": metric_type,
            "field": field,
            "time_range": {
                "start": start_time,
                "end": end_time
            },
            "statistics": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating metrics summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate summary: {str(e)}"
        )
