"""
Inconsistent Type Record Model
================================

Data structure for inconsistent quantity type (Incident Code 7_38) and
inconsistent price type (Incident Code 7_50) validation.

Both incidents are driven by the same source field — STOCK.F11 — which
determines the quantity type tag and price type tag simultaneously:

    F11 value   Qty tag       Price tag
    ---------   -----------   ---------------
    A, D or E   NmnlVal       Pctg
    F or blank  Unit          MntryVal

The SQL extract returns raw F11 values for the child and parent records.
The validator flags a group as inconsistent when child_f11 and parent_f11
differ. The script layer translates F11 values to human-readable tags for
the output columns (qty_type / price_type).
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

# F11 values that map to NmnlVal / Pctg
F11_PERCENTAGE_MARKERS: frozenset = frozenset({'A', 'D', 'E'})

# Human-readable quantity type tags keyed by F11 classification
QTY_TYPE_LABELS: Dict[str, str] = {
    'percentage': 'NmnlVal',
    'unit': 'Unit',
}

# Human-readable price type tags keyed by F11 classification
PRICE_TYPE_LABELS: Dict[str, str] = {
    'percentage': 'Pctg',
    'unit': 'MntryVal',
}

# Number of characters used to derive the bulk reference from parent_ref.
BULK_REF_LENGTH: int = 11


def classify_f11(f11: str) -> str:
    """
    Classify an F11 value as 'percentage' or 'unit'.

    Args:
        f11: Raw F11 field value from STOCK table.

    Returns:
        'percentage' if F11 is A, D or E; 'unit' otherwise (F or blank).
    """
    return 'percentage' if f11.strip().upper() in F11_PERCENTAGE_MARKERS else 'unit'


@dataclass
class InconsistentTypeRecord:
    """
    Validation record representing a single child transaction row for
    inconsistent quantity/price type checking.

    Each record corresponds to one child row from the SQL extract.
    Records are grouped by bulk_ref during validation.

    Input Fields (from database/CSV):
        - child_ref: Child transaction reference
        - child_f11: Raw F11 value from STOCK for the child contract
        - parent_ref: Full parent order reference
        - parent_f11: Raw F11 value from STOCK for the parent contract
        - trade_date_time: Trade date and time string

    Derived Fields (set automatically on construction):
        - bulk_ref: First 11 characters of parent_ref
        - child_type: F11 classification for child ('percentage' or 'unit')
        - parent_type: F11 classification for parent ('percentage' or 'unit')

    Output Fields (set by validator):
        - error: 'N' (consistent) or 'Y' (inconsistent within bulk group)
    """

    # Input fields (from database/CSV)
    child_ref: str
    child_f11: str
    parent_ref: str
    parent_f11: str
    trade_date_time: str

    # Derived fields — set automatically in __post_init__
    bulk_ref: str = field(default='', init=False)
    child_type: str = field(default='', init=False)
    parent_type: str = field(default='', init=False)

    # Output field (set by validator)
    error: str = field(default='N')

    def __post_init__(self) -> None:
        """Derive bulk_ref and type classifications from input fields."""
        self.bulk_ref = self.parent_ref[:BULK_REF_LENGTH]
        self.child_type = classify_f11(self.child_f11)
        self.parent_type = classify_f11(self.parent_f11)

    @property
    def child_qty_type(self) -> str:
        """Human-readable quantity type tag for the child record."""
        return QTY_TYPE_LABELS[self.child_type]

    @property
    def parent_qty_type(self) -> str:
        """Human-readable quantity type tag for the parent record."""
        return QTY_TYPE_LABELS[self.parent_type]

    @property
    def child_price_type(self) -> str:
        """Human-readable price type tag for the child record."""
        return PRICE_TYPE_LABELS[self.child_type]

    @property
    def parent_price_type(self) -> str:
        """Human-readable price type tag for the parent record."""
        return PRICE_TYPE_LABELS[self.parent_type]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InconsistentTypeRecord':
        """
        Create an InconsistentTypeRecord from a dictionary (e.g. a CSV row dict).

        Supports both SQL column names (uppercase) and Python field names.

        Args:
            data: Dictionary with the following keys (SQL or Python names):
                - child_ref / CHILD_REF
                - child_f11 / CHILD_F11
                - parent_ref / PARENT_REF
                - parent_f11 / PARENT_F11
                - trade_date_time / TRADE_DATE_TIME

        Returns:
            InconsistentTypeRecord instance

        Example:
            >>> row = {
            ...     'child_ref': 'AA2024000001',
            ...     'child_f11': 'F',
            ...     'parent_ref': 'AA2024000010',
            ...     'parent_f11': 'A',
            ...     'trade_date_time': '2024-01-15 09:30:00',
            ... }
            >>> record = InconsistentTypeRecord.from_dict(row)
        """
        return cls(
            child_ref=str(data.get('child_ref') or data.get('CHILD_REF', '')).strip(),
            child_f11=str(data.get('child_f11') or data.get('CHILD_F11', '')).strip(),
            parent_ref=str(data.get('parent_ref') or data.get('PARENT_REF', '')).strip(),
            parent_f11=str(data.get('parent_f11') or data.get('PARENT_F11', '')).strip(),
            trade_date_time=str(data.get('trade_date_time') or data.get('TRADE_DATE_TIME', '')).strip(),
        )

    @classmethod
    def from_row(cls, row: list, row_index: int = 0) -> 'InconsistentTypeRecord':
        """
        Create an InconsistentTypeRecord from a positional CSV row.

        Expected column order (matches SQL extract output):
            0: child_ref
            1: child_f11
            2: parent_ref
            3: parent_f11
            4: trade_date_time

        Args:
            row: List of string values from csv.reader.
            row_index: 1-based row number for error reporting.

        Returns:
            InconsistentTypeRecord instance

        Raises:
            ValueError: If the row has fewer than 5 columns.
        """
        if len(row) < 5:
            raise ValueError(
                f"Row {row_index} has {len(row)} column(s); expected at least 5. "
                f"Columns: child_ref, child_f11, parent_ref, parent_f11, trade_date_time"
            )
        return cls(
            child_ref=str(row[0]).strip(),
            child_f11=str(row[1]).strip(),
            parent_ref=str(row[2]).strip(),
            parent_f11=str(row[3]).strip(),
            trade_date_time=str(row[4]).strip(),
        )

    def to_dict(self) -> Dict[str, str]:
        """
        Serialise the record to a flat dictionary for CSV output.

        Returns:
            Ordered dictionary containing all input, derived, and output fields.
        """
        return {
            'child_ref': self.child_ref,
            'child_f11': self.child_f11,
            'parent_ref': self.parent_ref,
            'parent_f11': self.parent_f11,
            'trade_date_time': self.trade_date_time,
            'bulk_ref': self.bulk_ref,
            'child_type': self.child_type,
            'parent_type': self.parent_type,
            'error': self.error,
        }
