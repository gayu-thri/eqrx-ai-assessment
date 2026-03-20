"""
Input validation for MCP tool parameters.
"""

from datetime import datetime, timezone


def parse_iso_time(value):
    """Parse ISO 8601 string to timezone-aware datetime."""
    # Handle 'Z' suffix (common in ISO 8601)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(value)

    # If no timezone provided, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def validate_time_range(start_time, end_time):
    """Validate and return parsed (start, end). Raises ValueError if start>=end and invalid."""
    start = parse_iso_time(start_time)
    end = parse_iso_time(end_time)

    if start >= end:
        raise ValueError("start_time must be before end_time")

    return start, end
