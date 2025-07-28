"""Utility functions for date manipulation."""

from datetime import datetime, date


def format_datetime_for_db(dt_str: str) -> str | None:
    """Formats an ISO datetime string for MySQL DATETIME."""
    if not dt_str:
        return None
    try:
        # Handle both Z and +00:00 for UTC, or local timezone
        dt_obj = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def format_date_for_db(date_str: str) -> str | None:
    """Formats an ISO date string for MySQL DATE."""
    if not date_str:
        return None
    try:
        date_obj = date.fromisoformat(date_str)
        return date_obj.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None
