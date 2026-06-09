"""
Date Parser Module
==================

Date parsing utilities with caching for performance.

This is the canonical location for date parsing.
For backward compatibility, this is also re-exported from:
- common.utils
- txr_replay_core.utils
"""

from datetime import datetime
from typing import Optional


class DateParser:
    """
    Handles various date format parsing with caching.

    This unified implementation includes support for:
    - Multiple date formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
    - Timestamp handling (strips time portions)
    - Caching for performance

    Example:
        >>> DateParser.parse_date("01/12/2023")
        '2023-12-01'
        >>> DateParser.parse_date("2023-12-01 14:30:00")
        '2023-12-01'
    """

    _date_cache: dict = {}  # Cache parsed dates for performance

    @classmethod
    def parse_date(cls, date_str: str) -> Optional[str]:
        """
        Parse date with caching for performance.

        Args:
            date_str: Date string in various formats

        Returns:
            Standardized date string (YYYY-MM-DD) or None if parsing fails

        Examples:
            >>> DateParser.parse_date("01/12/2023")
            '2023-12-01'
            >>> DateParser.parse_date("2023-12-01")
            '2023-12-01'
            >>> DateParser.parse_date("01/12/2023 14:30:00")
            '2023-12-01'
        """
        if not date_str or date_str.strip() == "":
            return None

        date_str = date_str.strip()

        # Check cache first
        if date_str in cls._date_cache:
            return cls._date_cache[date_str]

        # Strip time portion if present (e.g., "08/09/1984 00:00:00" -> "08/09/1984")
        if " " in date_str:
            parts = date_str.split(" ", 1)
            time_part = parts[1].strip()
            # Check if second part looks like time (contains : or is all digits)
            if ":" in time_part or time_part.replace(":", "").isdigit():
                date_str = parts[0]  # Use only the date portion

        # Common date formats to try
        date_formats = [
            "%Y-%m-%d",  # YYYY-MM-DD (ISO format)
            "%d/%m/%Y",  # DD/MM/YYYY (UK format)
            "%m/%d/%Y",  # MM/DD/YYYY (US format)
            "%d-%m-%Y",  # DD-MM-YYYY
            "%m-%d-%Y",  # MM-DD-YYYY
            "%Y/%m/%d",  # YYYY/MM/DD
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                result = parsed_date.strftime("%Y-%m-%d")
                cls._date_cache[date_str] = result
                return result
            except ValueError:
                continue

        # Cache miss result too (avoid repeated parsing attempts)
        cls._date_cache[date_str] = None
        return None

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the date parsing cache."""
        cls._date_cache.clear()

    @classmethod
    def cache_size(cls) -> int:
        """Get current cache size."""
        return len(cls._date_cache)
