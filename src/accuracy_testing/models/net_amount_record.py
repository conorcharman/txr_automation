"""
Non-Zero Net Amount Record Model
=================================

Data structure for non-zero net amount validation (Incident Code 7_42).

Validates that the sum of all child transaction net amounts matches the
parent order net amount.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

# Number of characters used to derive the bulk reference from parent_ref.
# e.g. parent_ref "44625CPNJMN1G01" → bulk_ref "44625CPNJMN" (first 11 chars)
BULK_REF_LENGTH: int = 11


@dataclass
class NetAmountRecord:
    """
    Net amount validation record representing a single child transaction.

    Each record corresponds to one child transaction row from the SQL extract.
    Records are grouped by bulk_ref (the first 11 characters of parent_ref)
    during validation; the sum of child_netamt across all children within that
    bulk group (after deduplication) is compared against the total bulk net
    amount.

    A parent reference such as "44625CPNJMN1G01" belongs to the bulk group
    "44625CPNJMN". All sub-parent references sharing that prefix are treated
    as part of the same contract for net amount netting purposes.

    Input Fields (from database/CSV):
        - child_ref: Child transaction reference (12-character composite key)
        - child_netamt: Net amount reported on this child transaction
        - parent_ref: Full parent order reference (e.g. "44625CPNJMN1G01")
        - parent_netamt: Net amount on the parent order
        - report_status: Transaction report status code
        - trade_date_time: Trade date and time string

    Derived Fields (set automatically on construction):
        - bulk_ref: First 11 characters of parent_ref (e.g. "44625CPNJMN")

    Output Fields (calculated by validator):
        - bulk_netamt: Sum of one parent_netamt per unique parent_ref in the bulk group
        - net_amt: Sum of all child_netamt values for the bulk group (after dedup)
        - difference: net_amt - bulk_netamt
        - error: "N" (match) or "Y" (mismatch)
    """

    # Input fields (from database/CSV)
    child_ref: str
    child_netamt: Decimal
    parent_ref: str
    parent_netamt: Decimal
    report_status: str
    trade_date_time: str

    # Derived field — set automatically from parent_ref in __post_init__
    bulk_ref: str = field(default='', init=False)

    # Output fields (calculated by validator — initialised to defaults)
    bulk_netamt: Decimal = field(default_factory=lambda: Decimal('0'))
    net_amt: Decimal = field(default_factory=lambda: Decimal('0'))
    difference: Decimal = field(default_factory=lambda: Decimal('0'))
    error: str = field(default="N")

    def __post_init__(self) -> None:
        """Derive bulk_ref from the first BULK_REF_LENGTH characters of parent_ref."""
        self.bulk_ref = self.parent_ref[:BULK_REF_LENGTH]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetAmountRecord':
        """
        Create a NetAmountRecord from a dictionary (e.g. a CSV row dict).

        Supports both SQL column names (uppercase) and Python field names.

        Args:
            data: Dictionary with the following keys (SQL or Python names):
                - child_ref / CHILD_REF
                - child_netamt / CHILD_NETAMT
                - parent_ref / PARENT_REF
                - parent_netamt / PARENT_NETAMT
                - report_status / REPORT_STATUS
                - trade_date_time / TRADE_DATE_TIME

        Returns:
            NetAmountRecord instance

        Example:
            >>> row = {
            ...     'child_ref': 'AA2024000001',
            ...     'child_netamt': '1000.00',
            ...     'parent_ref': 'AA2024000010',
            ...     'parent_netamt': '3000.00',
            ...     'report_status': 'ACCEPTED',
            ...     'trade_date_time': '2024-01-15 09:30:00',
            ... }
            >>> record = NetAmountRecord.from_dict(row)
        """
        def _decimal(value: Any) -> Decimal:
            if value is None or str(value).strip() == '':
                return Decimal('0')
            try:
                return Decimal(str(value).strip())
            except InvalidOperation:
                return Decimal('0')

        return cls(
            child_ref=str(data.get('child_ref') or data.get('CHILD_REF', '')).strip(),
            child_netamt=_decimal(data.get('child_netamt') or data.get('CHILD_NETAMT')),
            parent_ref=str(data.get('parent_ref') or data.get('PARENT_REF', '')).strip(),
            parent_netamt=_decimal(data.get('parent_netamt') or data.get('PARENT_NETAMT')),
            report_status=str(data.get('report_status') or data.get('REPORT_STATUS', '')).strip(),
            trade_date_time=str(data.get('trade_date_time') or data.get('TRADE_DATE_TIME', '')).strip(),
        )

    @classmethod
    def from_row(cls, row: list, row_index: int = 0) -> 'NetAmountRecord':
        """
        Create a NetAmountRecord from a positional CSV row.

        Expected column order (matches SQL extract output):
            0: child_ref
            1: child_netamt
            2: parent_ref
            3: parent_netamt
            4: report_status
            5: trade_date_time

        Args:
            row: List of string values from csv.reader
            row_index: 1-based row number for error reporting

        Returns:
            NetAmountRecord instance

        Raises:
            ValueError: If the row has fewer than 6 columns
        """
        if len(row) < 6:
            raise ValueError(
                f"Row {row_index} has {len(row)} column(s); expected at least 6. "
                f"Columns: child_ref, child_netamt, parent_ref, parent_netamt, "
                f"report_status, trade_date_time"
            )

        def _decimal(value: str) -> Decimal:
            stripped = value.strip() if value else ''
            if not stripped:
                return Decimal('0')
            try:
                return Decimal(stripped)
            except InvalidOperation:
                return Decimal('0')

        return cls(
            child_ref=row[0].strip() if row[0] else '',
            child_netamt=_decimal(row[1]),
            parent_ref=row[2].strip() if row[2] else '',
            parent_netamt=_decimal(row[3]),
            report_status=row[4].strip() if row[4] else '',
            trade_date_time=row[5].strip() if row[5] else '',
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise the record to a dictionary for CSV output.

        Returns all input columns followed by the three output columns
        (net_amt, difference, error).

        Returns:
            Ordered dictionary of field name → value
        """
        return {
            'child_ref': self.child_ref,
            'child_netamt': str(self.child_netamt),
            'parent_ref': self.parent_ref,
            'parent_netamt': str(self.parent_netamt),
            'bulk_ref': self.bulk_ref,
            'bulk_netamt': str(self.bulk_netamt),
            'report_status': self.report_status,
            'trade_date_time': self.trade_date_time,
            'net_amt': str(self.net_amt),
            'difference': str(self.difference),
            'error': self.error,
        }
