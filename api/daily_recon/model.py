"""
Data Model
==========

Python representation of a reconciliation report row.
Strong typing + raw string preservation for audit.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .columns import (
    DATE_COLUMNS,
    DATETIME_COLUMNS,
    NUMERIC_COLUMNS,
    COLUMNS,
    get_column,
)


@dataclass
class ReconRecord:
    """Strongly-typed representation of one reconciliation report row.

    Attributes:
        Contains attributes for each column in COLUMNS (e.g., BUYER_ID, PRICE).
        Types are coerced per column definition (str, Decimal, date, etc.).

    Stores raw source strings to preserve original values for persistence
    and audit when validation fails.
    """

    # Basic header
    REPSTS: str | None = None
    TRADEREF: str | None = None
    VENUETXNID: str | None = None
    EXENTITYID: str | None = None
    FRMDIRIND: str | None = None
    SUBMITID: str | None = None

    # Buyer identity
    BUYER_ID: str | None = None
    BUYER_BRANCH_COUNTRY: str | None = None
    BUYER_FIRST_NAME: str | None = None
    BUYER_SURNAME: str | None = None
    BUYER_DOB: date | None = None

    # Buyer decision maker
    BUY_DECISION_MAKER: str | None = None
    BUYDECFORE: str | None = None
    BUYDEC_SURNAME: str | None = None
    BUYDECDOB: date | None = None

    # Seller identity
    SELLER_ID: str | None = None
    SELLER_BRANCH_COUNTRY: str | None = None
    SELLER_FIRST_NAME: str | None = None
    SELLER_SURNAME: str | None = None
    SELLER_DOB: date | None = None

    # Seller decision maker
    SELL_DECISION_MAKER: str | None = None
    SELLDEC_FIRST_NAME: str | None = None
    SELLDEC_SURNAME: str | None = None
    SELLDEC_DOB: date | None = None

    # Transaction indicators
    TRANSIND: str | None = None
    TRANSIDBUY: str | None = None
    TRANSIDSEL: str | None = None
    TRDDATTIM: datetime | None = None
    TRADING_CAPACITY: str | None = None

    # Quantity & pricing
    QUANTITY: Decimal | None = None
    QUANCUR: str | None = None
    DERIVATIVE_NOTIONAL_INCREASE_DECREASE: Decimal | None = None
    PRICE: Decimal | None = None
    PRICUR: str | None = None
    NETAMT: Decimal | None = None

    # Venue & routing
    VENUE: str | None = None
    CNTBRCHMEM: str | None = None
    INVDECFIRM: str | None = None
    CNTBRCHDEC: str | None = None
    EXINFIRM: str | None = None
    CNTBRCHEX: str | None = None

    # Indicators
    SHRTSELIND: str | None = None
    OTCPSTIND: str | None = None
    COMDERIND: str | None = None
    SECFININD: str | None = None

    # Raw source strings (for persistence as-is)
    raw: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_row(cls, mapping: dict[str, Any]) -> "ReconRecord":
        """Construct a ReconRecord from a row mapping (e.g. from SQL result).

        Coerces values to their declared types; keeps raw strings in self.raw.
        Failures on coercion (e.g., bad date) are flagged during validation,
        not here — the record is built with the original value preserved.

        Args:
            mapping: Dict with column names as keys, values as strings/objects.

        Returns:
            A new ReconRecord instance.
        """
        raw: dict[str, str | None] = {}
        typed_data: dict[str, Any] = {}

        for column in COLUMNS:
            col_name = column.name
            raw_val = mapping.get(col_name)

            # Preserve raw as string for audit
            if raw_val is not None:
                raw[col_name] = str(raw_val).strip() if isinstance(raw_val, str) else str(
                    raw_val
                )
            else:
                raw[col_name] = None

            # Attempt type coercion
            typed_val = None
            if raw_val is not None and raw_val != "":
                try:
                    if col_name in DATE_COLUMNS:
                        typed_val = _parse_date(raw_val)
                    elif col_name in DATETIME_COLUMNS:
                        typed_val = _parse_datetime(raw_val)
                    elif col_name in NUMERIC_COLUMNS:
                        typed_val = Decimal(str(raw_val).strip())
                    else:
                        typed_val = str(raw_val).strip()
                except (ValueError, TypeError) as exc:
                    # Parsing failed — keep None, validation will catch it.
                    # Log if needed; caller may inspect raw[col_name] vs typed_val=None.
                    pass

            typed_data[col_name] = typed_val

        record = cls(**typed_data)
        record.raw = raw
        return record


def _parse_date(val: Any) -> date:
    """Parse a date from string or date object.

    Tries common formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY.
    Caller should catch ValueError on failure.
    """
    if isinstance(val, date):
        return val

    val_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date: {val_str}")


def _parse_datetime(val: Any) -> datetime:
    """Parse a datetime from string or datetime object.

    Tries common formats: ISO 8601 with/without Z, SQL datetime formats.
    Caller should catch ValueError on failure.
    """
    if isinstance(val, datetime):
        return val

    val_str = str(val).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse datetime: {val_str}")

