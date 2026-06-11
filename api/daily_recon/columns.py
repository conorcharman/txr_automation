"""
Column Registry
===============

Single source of truth for the 50-column reconciliation report schema.
Every layer — SQL projection, Python model, validation, storage, API, CSV —
derives from this registry, guaranteeing name consistency end-to-end.
"""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ReconColumn:
    """Immutable definition of one reconciliation report column."""

    name: str
    """Canonical column name (matches source DB and all layers)."""

    py_type: type
    """Python type for typed model: str, int, float, Decimal, date, datetime."""

    nullable: bool = True
    """Whether the source allows NULL."""

    sql_alias: str | None = None
    """Optional alias for external query (if different from name)."""

    def __post_init__(self) -> None:
        """Validate type is sensible."""
        allowed_types = (str, int, float, bool)
        # Also allow type objects from decimal, datetime, etc.
        type_name = getattr(self.py_type, "__name__", str(self.py_type))
        if self.py_type not in allowed_types and type_name not in (
            "Decimal",
            "date",
            "datetime",
        ):
            msg = f"Unsupported py_type: {self.py_type}"
            raise TypeError(msg)


# ── Fixed 50-column schema ──────────────────────────────────────────────────

COLUMNS = (
    # Transaction header
    ReconColumn("REPSTS", str),
    ReconColumn("TRADEREF", str),
    ReconColumn("VENUETXNID", str),
    ReconColumn("EXENTITYID", str),
    ReconColumn("FRMDIRIND", str),
    ReconColumn("SUBMITID", str),
    # Buyer identity
    ReconColumn("BUYER_ID", str),
    ReconColumn("BUYER_BRANCH_COUNTRY", str),
    ReconColumn("BUYER_FIRST_NAME", str),
    ReconColumn("BUYER_SURNAME", str),
    ReconColumn("BUYER_DOB", str),  # Will parse as date in model
    # Buyer decision maker
    ReconColumn("BUY_DECISION_MAKER", str),
    ReconColumn("BUYDECFORE", str),
    ReconColumn("BUYDEC_SURNAME", str),
    ReconColumn("BUYDECDOB", str),  # Will parse as date in model
    # Seller identity
    ReconColumn("SELLER_ID", str),
    ReconColumn("SELLER_BRANCH_COUNTRY", str),
    ReconColumn("SELLER_FIRST_NAME", str),
    ReconColumn("SELLER_SURNAME", str),
    ReconColumn("SELLER_DOB", str),  # Will parse as date in model
    # Seller decision maker
    ReconColumn("SELL_DECISION_MAKER", str),
    ReconColumn("SELLDEC_FIRST_NAME", str),
    ReconColumn("SELLDEC_SURNAME", str),
    ReconColumn("SELLDEC_DOB", str),  # Will parse as date in model
    # Transaction indicators
    ReconColumn("TRANSIND", str),
    ReconColumn("TRANSIDBUY", str),
    ReconColumn("TRANSIDSEL", str),
    ReconColumn("TRDDATTIM", str),  # Will parse as datetime in model
    ReconColumn("TRADING_CAPACITY", str),
    # Quantity & pricing
    ReconColumn("QUANTITY", str),  # Stored as str, parsed to Decimal
    ReconColumn("QUANCUR", str),
    ReconColumn("DERIVATIVE_NOTIONAL_INCREASE_DECREASE", str),  # Decimal
    ReconColumn("PRICE", str),  # Decimal
    ReconColumn("PRICUR", str),
    ReconColumn("NETAMT", str),  # Decimal
    # Venue & routing
    ReconColumn("VENUE", str),
    ReconColumn("CNTBRCHMEM", str),
    ReconColumn("INVDECFIRM", str),
    ReconColumn("CNTBRCHDEC", str),
    ReconColumn("EXINFIRM", str),
    ReconColumn("CNTBRCHEX", str),
    # Indicators
    ReconColumn("SHRTSELIND", str),
    ReconColumn("OTCPSTIND", str),
    ReconColumn("COMDERIND", str),
    ReconColumn("SECFININD", str),
)

#: Ordered mapping for external query projection and CSV export.
COLUMN_NAMES = tuple(c.name for c in COLUMNS)

#: For validation framework — group columns by type.
NUMERIC_COLUMNS = {
    "QUANTITY",
    "PRICE",
    "NETAMT",
    "DERIVATIVE_NOTIONAL_INCREASE_DECREASE",
}

DATE_COLUMNS = {
    "BUYER_DOB",
    "SELLER_DOB",
    "BUYDECDOB",
    "SELLDEC_DOB",
}

DATETIME_COLUMNS = {"TRDDATTIM"}

ID_COLUMNS = {
    "BUYER_ID",
    "SELLER_ID",
    "EXENTITYID",
    "VENUETXNID",
    "TRADEREF",
}

COUNTRY_CODE_COLUMNS = {
    "BUYER_BRANCH_COUNTRY",
    "SELLER_BRANCH_COUNTRY",
}

INDICATOR_COLUMNS = {
    "FRMDIRIND",
    "TRANSIND",
    "SHRTSELIND",
    "OTCPSTIND",
    "COMDERIND",
    "SECFININD",
}


def get_column(name: str) -> ReconColumn | None:
    """Look up a column by name.

    Args:
        name: Column name (case-sensitive).

    Returns:
        The ReconColumn object, or None if not found.
    """
    for col in COLUMNS:
        if col.name == name:
            return col
    return None

