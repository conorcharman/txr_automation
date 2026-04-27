"""
Incorrect Time Record Model
==============================

Data structure for incorrect time validation (Incident Code 7_30).

Validates that the trade datetime of a child allocation matches the
trade datetime of its parent block transaction to second precision.
Microseconds are ignored in the comparison.

The AS400 TRDDATTIM format is: CCYY-MM-DD-HH.MM.SS.ffffff
"""

from dataclasses import dataclass, field
from typing import Dict, Any

# Number of characters used to derive the bulk reference from parent_ref.
BULK_REF_LENGTH: int = 11

# Sentinel value written to time_difference when the parent has no
# TXNREPESMA row (LEFT JOIN returned NULL).
PARENT_DATETIME_MISSING: str = "parent datetime missing"


@dataclass
class IncorrectTimeRecord:
    """
    Validation record representing a single child transaction row for
    incorrect time checking.

    Each record corresponds to one child row from the SQL extract.
    The validator compares child_datetime and parent_datetime at second
    precision (microseconds stripped). A mismatch sets error = 'Y' and
    populates time_difference with a human-readable gap description.

    Input Fields (from database/CSV):
        - child_ref: Child transaction reference
        - child_datetime: TRDDATTIM from TXNREPESMA for the child record
        - parent_ref: Full parent order reference
        - parent_datetime: TRDDATTIM from TXNREPESMA for the parent block
                          (may be empty/null if no parent row exists)

    Derived Fields (set automatically on construction):
        - bulk_ref: First 11 characters of parent_ref

    Output Fields (set by validator):
        - time_difference: Human-readable time gap on mismatch, empty on match,
                           or PARENT_DATETIME_MISSING if parent_datetime is absent
        - error: 'N' (datetimes match to the second) or 'Y' (mismatch or missing)
    """

    # Input fields (from database/CSV)
    child_ref: str
    child_datetime: str
    parent_ref: str
    parent_datetime: str

    # Derived field — set automatically in __post_init__
    bulk_ref: str = field(default='', init=False)

    # Output fields (set by validator)
    time_difference: str = field(default='')
    error: str = field(default='N')

    def __post_init__(self) -> None:
        """Derive bulk_ref from the first BULK_REF_LENGTH characters of parent_ref."""
        self.bulk_ref = self.parent_ref[:BULK_REF_LENGTH]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IncorrectTimeRecord':
        """
        Create an IncorrectTimeRecord from a dictionary (e.g. a CSV row dict).

        Supports both SQL column names (uppercase) and Python field names.

        Args:
            data: Dictionary with the following keys (SQL or Python names):
                - child_ref / CHILD_REF
                - child_datetime / CHILD_DATETIME
                - parent_ref / PARENT_REF
                - parent_datetime / PARENT_DATETIME

        Returns:
            IncorrectTimeRecord instance

        Example:
            >>> row = {
            ...     'child_ref': 'AA2024000001',
            ...     'child_datetime': '2024-01-15-09.30.00.000000',
            ...     'parent_ref': 'AA2024000010',
            ...     'parent_datetime': '2024-01-15-10.00.00.000000',
            ... }
            >>> record = IncorrectTimeRecord.from_dict(row)
        """
        return cls(
            child_ref=str(data.get('child_ref') or data.get('CHILD_REF', '')).strip(),
            child_datetime=str(data.get('child_datetime') or data.get('CHILD_DATETIME', '')).strip(),
            parent_ref=str(data.get('parent_ref') or data.get('PARENT_REF', '')).strip(),
            parent_datetime=str(data.get('parent_datetime') or data.get('PARENT_DATETIME', '')).strip(),
        )

    @classmethod
    def from_row(cls, row: list, row_index: int = 0) -> 'IncorrectTimeRecord':
        """
        Create an IncorrectTimeRecord from a positional CSV row.

        Expected column order (matches SQL extract output):
            0: child_ref
            1: child_datetime
            2: parent_ref
            3: parent_datetime

        Args:
            row: List of string values from csv.reader.
            row_index: 1-based row number for error reporting.

        Returns:
            IncorrectTimeRecord instance

        Raises:
            ValueError: If the row has fewer than 4 columns.
        """
        if len(row) < 4:
            raise ValueError(
                f"Row {row_index} has {len(row)} column(s); expected at least 4. "
                f"Columns: child_ref, child_datetime, parent_ref, parent_datetime"
            )
        return cls(
            child_ref=str(row[0]).strip(),
            child_datetime=str(row[1]).strip(),
            parent_ref=str(row[2]).strip(),
            parent_datetime=str(row[3]).strip(),
        )

    def to_dict(self) -> Dict[str, str]:
        """
        Serialise the record to a flat dictionary for CSV output.

        Returns:
            Ordered dictionary containing all input, derived, and output fields.
        """
        return {
            'child_ref': self.child_ref,
            'child_datetime': self.child_datetime,
            'parent_ref': self.parent_ref,
            'parent_datetime': self.parent_datetime,
            'bulk_ref': self.bulk_ref,
            'time_difference': self.time_difference,
            'error': self.error,
        }
