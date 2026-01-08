"""System logs API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict
from pathlib import Path
import re
import logging

from app.middleware.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/logs", tags=["logs"])

# Base path for logs directory
LOGS_BASE_PATH = Path("/home/trosfy/projects/discord-ollama-agent/logs")


def validate_date_format(date: str) -> bool:
    """
    Validate date string format (YYYY-MM-DD).

    Args:
        date: Date string to validate

    Returns:
        bool: True if valid format, False otherwise
    """
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', date))


def validate_log_type(log_type: str) -> bool:
    """
    Validate log type is one of the allowed types.

    Args:
        log_type: Log type string

    Returns:
        bool: True if valid type, False otherwise
    """
    return log_type in ["app", "debug", "error"]


@router.get("/dates")
async def get_log_dates(
    admin_auth: Dict = Depends(require_admin)
) -> Dict[str, List[str]]:
    """
    Get list of available log dates.

    Returns dates in descending order (most recent first).

    Requires admin authentication.

    Returns:
        dict: {"dates": ["2025-12-29", "2025-12-28", ...]}
    """
    try:
        if not LOGS_BASE_PATH.exists():
            logger.error(f"Logs directory does not exist: {LOGS_BASE_PATH}")
            return {"dates": []}

        # Get all date directories matching YYYY-MM-DD format
        dates = []
        for item in LOGS_BASE_PATH.iterdir():
            if item.is_dir() and validate_date_format(item.name):
                dates.append(item.name)

        # Sort in descending order (most recent first)
        dates.sort(reverse=True)

        logger.info(f"Found {len(dates)} log dates")
        return {"dates": dates}

    except Exception as e:
        logger.error(f"Failed to get log dates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read log dates: {str(e)}")


@router.get("/content")
async def get_log_content(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    log_type: str = Query(..., description="Log type: app, debug, or error"),
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to return (max 1000)"),
    offset: int = Query(0, ge=0, description="Number of lines to skip from start"),
    admin_auth: Dict = Depends(require_admin)
) -> Dict:
    """
    Get log file content with pagination.

    Returns log content with pagination info.

    Requires admin authentication.

    Args:
        date: Date in YYYY-MM-DD format
        log_type: Type of log (app, debug, error)
        lines: Number of lines to return (1-1000)
        offset: Number of lines to skip from start

    Returns:
        dict: {
            "date": "2025-12-29",
            "log_type": "app",
            "content": ["line1", "line2", ...],
            "total_lines": 5000,
            "offset": 0,
            "returned_lines": 100
        }

    Raises:
        HTTPException: If date format invalid, log type invalid, or file not found
    """
    try:
        # Validate date format (prevent path traversal)
        if not validate_date_format(date):
            logger.warning(f"Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Validate log type
        if not validate_log_type(log_type):
            logger.warning(f"Invalid log type: {log_type}")
            raise HTTPException(
                status_code=400,
                detail="Invalid log type. Must be one of: app, debug, error"
            )

        # Build log file path
        log_file = LOGS_BASE_PATH / date / f"{log_type}.log"

        # Check if file exists
        if not log_file.exists():
            logger.warning(f"Log file not found: {log_file}")
            raise HTTPException(
                status_code=404,
                detail=f"Log file not found for date={date}, type={log_type}"
            )

        # Read file content
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed to read log file {log_file}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")

        total_lines = len(all_lines)

        # Apply pagination
        end_offset = min(offset + lines, total_lines)
        content_lines = all_lines[offset:end_offset]

        # Strip newlines and return
        content = [line.rstrip('\n') for line in content_lines]

        logger.info(f"Returned {len(content)} lines from {log_file} (offset={offset}, total={total_lines})")

        return {
            "date": date,
            "log_type": log_type,
            "content": content,
            "total_lines": total_lines,
            "offset": offset,
            "returned_lines": len(content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get log content: {str(e)}")


@router.get("/search")
async def search_logs(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    log_type: str = Query(..., description="Log type: app, debug, or error"),
    query: str = Query(..., min_length=1, description="Search query text"),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
    max_results: int = Query(100, ge=1, le=500, description="Maximum results to return (max 500)"),
    admin_auth: Dict = Depends(require_admin)
) -> Dict:
    """
    Search within log files.

    Returns matching lines with line numbers.

    Requires admin authentication.

    Args:
        date: Date in YYYY-MM-DD format
        log_type: Type of log (app, debug, error)
        query: Text to search for
        case_sensitive: Whether search should be case sensitive
        max_results: Maximum number of results to return (1-500)

    Returns:
        dict: {
            "date": "2025-12-29",
            "log_type": "app",
            "query": "error",
            "case_sensitive": false,
            "matches": [
                {"line_number": 42, "content": "Error occurred..."},
                {"line_number": 156, "content": "Another error..."}
            ],
            "total_matches": 2,
            "truncated": false
        }

    Raises:
        HTTPException: If date format invalid, log type invalid, or file not found
    """
    try:
        # Validate date format (prevent path traversal)
        if not validate_date_format(date):
            logger.warning(f"Invalid date format: {date}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Validate log type
        if not validate_log_type(log_type):
            logger.warning(f"Invalid log type: {log_type}")
            raise HTTPException(
                status_code=400,
                detail="Invalid log type. Must be one of: app, debug, error"
            )

        # Build log file path
        log_file = LOGS_BASE_PATH / date / f"{log_type}.log"

        # Check if file exists
        if not log_file.exists():
            logger.warning(f"Log file not found: {log_file}")
            raise HTTPException(
                status_code=404,
                detail=f"Log file not found for date={date}, type={log_type}"
            )

        # Read file and search
        matches = []
        search_query = query if case_sensitive else query.lower()

        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line_number, line in enumerate(f, start=1):
                    line_content = line.rstrip('\n')
                    search_content = line_content if case_sensitive else line_content.lower()

                    if search_query in search_content:
                        matches.append({
                            "line_number": line_number,
                            "content": line_content
                        })

                        # Stop if we've hit max results
                        if len(matches) >= max_results:
                            break
        except Exception as e:
            logger.error(f"Failed to search log file {log_file}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to search log file: {str(e)}")

        total_matches = len(matches)
        truncated = total_matches >= max_results

        logger.info(f"Search in {log_file} for '{query}': found {total_matches} matches (truncated={truncated})")

        return {
            "date": date,
            "log_type": log_type,
            "query": query,
            "case_sensitive": case_sensitive,
            "matches": matches,
            "total_matches": total_matches,
            "truncated": truncated
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search logs: {str(e)}")
