"""
Fiscal Date Utilities
=====================

Shared utilities for fiscal year/quarter calculations used by the pipeline
service and reconciliation service.

Fiscal year convention: FY{N} runs from April of calendar year (N-1) to
March of calendar year N.

    - Q1 = 1 Apr – 30 Jun
    - Q2 = 1 Jul – 30 Sep
    - Q3 = 1 Oct – 31 Dec
    - Q4 = 1 Jan – 31 Mar
"""

from datetime import datetime, timezone


def get_completed_quarter(reference_date: datetime) -> tuple[str, str]:
    """Return the most recently completed fiscal quarter.

    Args:
        reference_date: The date to calculate from (typically ``utcnow()``).

    Returns:
        A ``(fiscal_year, quarter)`` tuple, e.g. ``("FY26", "Q4")``.

    Examples:
        >>> from datetime import datetime, timezone
        >>> get_completed_quarter(datetime(2026, 4, 15, tzinfo=timezone.utc))
        ('FY26', 'Q4')
        >>> get_completed_quarter(datetime(2025, 7, 1, tzinfo=timezone.utc))
        ('FY26', 'Q1')
        >>> get_completed_quarter(datetime(2026, 1, 15, tzinfo=timezone.utc))
        ('FY26', 'Q3')
        >>> get_completed_quarter(datetime(2025, 4, 1, tzinfo=timezone.utc))
        ('FY25', 'Q4')
    """
    month = reference_date.month
    year = reference_date.year

    # Map calendar month to the most recently completed fiscal quarter.
    # Apr-Jun → previous Q4 ended 31 Mar
    # Jul-Sep → Q1 ended 30 Jun
    # Oct-Dec → Q2 ended 30 Sep
    # Jan-Mar → Q3 ended 31 Dec (of the previous calendar year)
    if 4 <= month <= 6:
        # Q4 of the FY that ended on 31 Mar of this calendar year
        fy_num = year % 100
        return (f"FY{fy_num:02d}", "Q4")
    elif 7 <= month <= 9:
        # Q1 of the current FY ended 30 Jun
        fy_num = (year + 1) % 100
        return (f"FY{fy_num:02d}", "Q1")
    elif 10 <= month <= 12:
        # Q2 of the current FY ended 30 Sep
        fy_num = (year + 1) % 100
        return (f"FY{fy_num:02d}", "Q2")
    else:
        # Jan-Mar: Q3 of the current FY ended 31 Dec of previous year
        fy_num = year % 100
        return (f"FY{fy_num:02d}", "Q3")


def calculate_quarterly_next_run(from_date: datetime) -> datetime:
    """Return the start of the next fiscal quarter after ``from_date``.

    Quarter start dates:
        - Q1: 1 April
        - Q2: 1 July
        - Q3: 1 October
        - Q4: 1 January

    Args:
        from_date: The reference datetime.

    Returns:
        A timezone-aware UTC ``datetime`` at midnight on the next quarter start.

    Examples:
        >>> from datetime import datetime, timezone
        >>> calculate_quarterly_next_run(datetime(2026, 4, 15, tzinfo=timezone.utc))
        datetime.datetime(2026, 7, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> calculate_quarterly_next_run(datetime(2026, 12, 31, tzinfo=timezone.utc))
        datetime.datetime(2027, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> calculate_quarterly_next_run(datetime(2026, 1, 1, tzinfo=timezone.utc))
        datetime.datetime(2026, 4, 1, 0, 0, tzinfo=datetime.timezone.utc)
    """
    month = from_date.month
    year = from_date.year

    # Fiscal quarter boundaries: Apr 1, Jul 1, Oct 1, Jan 1
    if month < 4:
        return datetime(year, 4, 1, tzinfo=timezone.utc)
    elif month < 7:
        return datetime(year, 7, 1, tzinfo=timezone.utc)
    elif month < 10:
        return datetime(year, 10, 1, tzinfo=timezone.utc)
    else:
        return datetime(year + 1, 1, 1, tzinfo=timezone.utc)
