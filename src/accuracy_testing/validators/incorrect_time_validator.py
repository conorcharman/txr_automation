"""
Incorrect Time Validator
==========================

Core validation logic for incorrect time checking (Incident Code 7_30).

For each child transaction, the trade datetime of the child allocation is
compared against the trade datetime of the parent block at second precision
(microseconds are ignored). A mismatch is flagged as an error and the
human-readable time difference is recorded.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

from ..models.incorrect_time_record import IncorrectTimeRecord, PARENT_DATETIME_MISSING

logger = logging.getLogger(__name__)

# AS400 TRDDATTIM format: CCYY-MM-DD-HH.MM.SS.ffffff
_DATETIME_FORMAT: str = '%Y-%m-%d-%H.%M.%S.%f'


def _parse_datetime(value: str) -> datetime:
    """
    Parse an AS400 TRDDATTIM string into a datetime object.

    Args:
        value: Timestamp string in the format CCYY-MM-DD-HH.MM.SS.ffffff

    Returns:
        datetime object

    Raises:
        ValueError: If the string does not match the expected format.
    """
    return datetime.strptime(value.strip(), _DATETIME_FORMAT)


def _format_difference(delta: timedelta) -> str:
    """
    Format a timedelta as a human-readable string using the largest applicable
    unit, e.g. '30 seconds', '2 minutes 15 seconds', '1 hour 5 minutes',
    '1 day 3 hours'.

    Args:
        delta: Absolute time difference (must be non-negative).

    Returns:
        Human-readable string describing the time gap.
    """
    total_seconds = int(delta.total_seconds())

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: List[str] = []

    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    elif hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    elif minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    else:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ' '.join(parts)


class IncorrectTimeValidator:
    """
    Validates that each child transaction's trade datetime matches its parent
    block's trade datetime to second precision.

    Processing steps per record:
        1. If parent_datetime is empty/null, set error = 'Y' and
           time_difference = 'parent datetime missing'.
        2. Parse both datetimes with strptime('%Y-%m-%d-%H.%M.%S.%f').
        3. Truncate microseconds via .replace(microsecond=0).
        4. If equal, set error = 'N', time_difference = ''.
        5. If not equal, set error = 'Y', time_difference = formatted delta.

    There is no grouping or deduplication — every input row is checked
    independently and written to the output.

    Usage:
        validator = IncorrectTimeValidator(verbose=True)
        stats = validator.validate_all(records)
    """

    def __init__(self, verbose: bool = False) -> None:
        """
        Initialise the validator.

        Args:
            verbose: Enable verbose debug logging (default False).
        """
        self.verbose = verbose

        if self.verbose:
            logger.info("IncorrectTimeValidator initialised")

    def validate_record(self, record: IncorrectTimeRecord) -> None:
        """
        Validate a single record in place, setting error and time_difference.

        Args:
            record: The IncorrectTimeRecord to validate (mutated in place).
        """
        # Handle missing parent datetime
        if not record.parent_datetime:
            record.error = 'Y'
            record.time_difference = PARENT_DATETIME_MISSING
            if self.verbose:
                logger.debug(
                    f"  {record.child_ref}: parent_datetime missing — error=Y"
                )
            return

        try:
            child_dt = _parse_datetime(record.child_datetime).replace(microsecond=0)
            parent_dt = _parse_datetime(record.parent_datetime).replace(microsecond=0)
        except ValueError as e:
            logger.warning(
                f"  {record.child_ref}: could not parse datetime — {e} — skipping comparison"
            )
            record.error = 'Y'
            record.time_difference = f"parse error: {e}"
            return

        if child_dt == parent_dt:
            record.error = 'N'
            record.time_difference = ''
            if self.verbose:
                logger.debug(f"  {record.child_ref}: match — {child_dt}")
        else:
            delta = abs(child_dt - parent_dt)
            record.error = 'Y'
            record.time_difference = _format_difference(delta)
            if self.verbose:
                logger.debug(
                    f"  {record.child_ref}: mismatch — child={child_dt} "
                    f"parent={parent_dt} diff={record.time_difference}"
                )

    def validate_all(self, records: List[IncorrectTimeRecord]) -> Dict[str, int]:
        """
        Validate all records, mutating each in place.

        Args:
            records: List of IncorrectTimeRecord objects in CSV row order.

        Returns:
            Stats dictionary with keys:
                - total:    total records processed
                - matches:  records where error = 'N'
                - errors:   records where error = 'Y'
                - missing:  records where parent_datetime was absent
                - parse_errors: records where datetime parsing failed

        Example:
            >>> validator = IncorrectTimeValidator()
            >>> stats = validator.validate_all(records)
            >>> print(stats['errors'])
        """
        total = len(records)
        matches = 0
        errors = 0
        missing = 0
        parse_errors = 0

        if self.verbose:
            logger.info(f"Validating {total} records")

        for record in records:
            was_missing = not record.parent_datetime

            self.validate_record(record)

            if record.error == 'N':
                matches += 1
            else:
                errors += 1
                if was_missing:
                    missing += 1
                elif record.time_difference.startswith('parse error'):
                    parse_errors += 1

        if self.verbose:
            logger.info(
                f"Validation complete — total={total} matches={matches} "
                f"errors={errors} missing={missing} parse_errors={parse_errors}"
            )

        return {
            'total': total,
            'matches': matches,
            'errors': errors,
            'missing': missing,
            'parse_errors': parse_errors,
        }
