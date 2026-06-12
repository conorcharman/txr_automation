"""
Validation Framework - Built-in Rules
======================================

Common validation rules for ID, date, numeric, indicator fields, etc.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .base import Rule, RuleResult
from .registry import rule_registry


# ────────────────────────────────────────────────────────────────────────────
# Generic Rules
# ────────────────────────────────────────────────────────────────────────────


class NotEmptyRule:
    """Rule: cell must not be empty/NULL."""

    rule_id = "not_empty"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check that value is not empty."""
        if value is None or value.strip() == "":
            return RuleResult(
                is_valid=False,
                message="Value cannot be empty.",
            )
        return RuleResult(is_valid=True)


class MaxLengthRule:
    """Rule: string must not exceed max length."""

    rule_id = "max_length"

    def __init__(self, max_length: int):
        """Initialize with max allowed length.

        Args:
            max_length: Maximum string length.
        """
        self.max_length = max_length

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check length."""
        if value is None:
            return RuleResult(is_valid=True)
        if len(value) > self.max_length:
            return RuleResult(
                is_valid=False,
                message=f"Value exceeds {self.max_length} characters.",
            )
        return RuleResult(is_valid=True)


class RegexRule:
    """Rule: value must match a regex pattern."""

    rule_id = "regex_match"

    def __init__(self, pattern: str, description: str = ""):
        """Initialize with pattern and optional description.

        Args:
            pattern: Compiled regex pattern.
            description: Human-readable pattern description.
        """
        self.pattern = re.compile(pattern)
        self.description = description or pattern

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check regex match."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        if not self.pattern.match(value.strip()):
            return RuleResult(
                is_valid=False,
                message=f"Value does not match expected format: {self.description}",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# ID Field Rules
# ────────────────────────────────────────────────────────────────────────────


class IdNotEmptyRule:
    """Rule: ID fields (BUYER_ID, SELLER_ID, etc.) must not be empty."""

    rule_id = "id_not_empty"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check that ID is not empty."""
        if value is None or value.strip() == "":
            return RuleResult(
                is_valid=False,
                message="ID cannot be empty.",
            )
        return RuleResult(is_valid=True)


class IdFormatRule:
    """Rule: ID must follow a reasonable format (alphanumeric, no special chars)."""

    rule_id = "id_format"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check ID format."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip()
        # Allow letters, digits, hyphen, underscore, dot
        if not re.match(r"^[A-Za-z0-9\-_.]+$", val):
            return RuleResult(
                is_valid=False,
                message="ID contains invalid characters (only alphanumeric, hyphen, underscore, dot allowed).",
            )
        if len(val) < 2:
            return RuleResult(
                is_valid=False,
                message="ID is too short (minimum 2 characters).",
            )
        if len(val) > 50:
            return RuleResult(
                is_valid=False,
                message="ID is too long (maximum 50 characters).",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# Country Code Rules
# ────────────────────────────────────────────────────────────────────────────


class CountryCodeRule:
    """Rule: country code must be ISO 3166-1 alpha-2 (2-letter code)."""

    # A minimal set of valid country codes (curated; can extend as needed)
    VALID_CODES = frozenset(
        {
            "GB",
            "US",
            "DE",
            "FR",
            "IT",
            "ES",
            "NL",
            "BE",
            "AT",
            "CH",
            "SE",
            "NO",
            "DK",
            "FI",
            "PL",
            "CZ",
            "HU",
            "RO",
            "GR",
            "PT",
            "IE",
            "LU",
            "CY",
            "MT",
            "SI",
            "SK",
            "BG",
            "HR",
            "LV",
            "LT",
            "EE",
            "CA",
            "MX",
            "BR",
            "AR",
            "AU",
            "NZ",
            "JP",
            "CN",
            "IN",
            "SG",
            "HK",
            "AE",
            "SA",
            "ZA",
        }
    )

    rule_id = "country_code_valid"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check country code validity."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip().upper()
        if val not in self.VALID_CODES:
            return RuleResult(
                is_valid=False,
                message=f"Invalid country code: {val}. Must be ISO 3166-1 alpha-2.",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# Numeric Rules
# ────────────────────────────────────────────────────────────────────────────


class NumericRule:
    """Rule: value must be a valid number."""

    rule_id = "numeric"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check numeric validity."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        try:
            Decimal(value.strip())
            return RuleResult(is_valid=True)
        except (InvalidOperation, ValueError):
            return RuleResult(
                is_valid=False,
                message=f"Value '{value}' is not a valid number.",
            )


class PositiveNumberRule:
    """Rule: numeric value must be >= 0."""

    rule_id = "positive_number"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check that value is non-negative."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        try:
            num = Decimal(value.strip())
            if num < 0:
                return RuleResult(
                    is_valid=False,
                    message=f"Value must be non-negative, got: {num}",
                )
            return RuleResult(is_valid=True)
        except (InvalidOperation, ValueError):
            return RuleResult(
                is_valid=False,
                message=f"Value '{value}' is not a valid number.",
            )


# ────────────────────────────────────────────────────────────────────────────
# Date Rules
# ────────────────────────────────────────────────────────────────────────────


class DateFormatRule:
    """Rule: date must parse to a valid date."""

    rule_id = "date_format"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Try parsing as date."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                datetime.strptime(val, fmt)
                return RuleResult(is_valid=True)
            except ValueError:
                continue
        return RuleResult(
            is_valid=False,
            message=f"Invalid date format: {val}. Expected YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY.",
        )


class ReasonableDateRule:
    """Rule: date should be within a reasonable historical range (e.g., 1900-today)."""

    rule_id = "reasonable_date"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check date is within a reasonable range."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip()
        parsed = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(val, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            return RuleResult(is_valid=True)  # Format rule already checked this
        if parsed.year < 1900:
            return RuleResult(
                is_valid=False,
                message=f"Date {parsed} is before 1900 (unreasonable for modern data).",
            )
        if parsed.year > 2050:
            return RuleResult(
                is_valid=False,
                message=f"Date {parsed} is after 2050 (unreasonable for modern data).",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# Indicator Rules
# ────────────────────────────────────────────────────────────────────────────


class IndicatorRule:
    """Rule: indicator field (Y/N) must be Y or N."""

    rule_id = "indicator_valid"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check indicator is Y or N."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip().upper()
        if val not in ("Y", "N"):
            return RuleResult(
                is_valid=False,
                message=f"Indicator must be 'Y' or 'N', got: {val}",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# Register module-level rule instances
# ────────────────────────────────────────────────────────────────────────────

_not_empty = NotEmptyRule()
_id_not_empty = IdNotEmptyRule()
_id_format = IdFormatRule()
_country_code = CountryCodeRule()
_numeric = NumericRule()
_positive_number = PositiveNumberRule()
_date_format = DateFormatRule()
_reasonable_date = ReasonableDateRule()
_indicator = IndicatorRule()

# Register ID columns
rule_registry.register("BUYER_ID", "SELLER_ID", "EXENTITYID")(
    _id_not_empty
)
rule_registry.register("BUYER_ID", "SELLER_ID", "EXENTITYID")(_id_format)

# Register country code columns
rule_registry.register("BUYER_BRANCH_COUNTRY", "SELLER_BRANCH_COUNTRY")(
    _country_code
)

# Register numeric columns
rule_registry.register(
    "QUANTITY",
    "DERIVATIVE_NOTIONAL_INCREASE_DECREASE",
    "PRICE",
    "NETAMT",
)(_numeric)
rule_registry.register(
    "QUANTITY",
    "DERIVATIVE_NOTIONAL_INCREASE_DECREASE",
)(_positive_number)

# Register date columns
rule_registry.register(
    "BUYER_DOB",
    "SELLER_DOB",
    "BUYDECDOB",
    "SELLDEC_DOB",
)(_date_format)
rule_registry.register(
    "BUYER_DOB",
    "SELLER_DOB",
    "BUYDECDOB",
    "SELLDEC_DOB",
)(_reasonable_date)

# Register indicator columns
rule_registry.register(
    "FRMDIRIND",
    "TRANSIND",
    "SHRTSELIND",
    "OTCPSTIND",
    "COMDERIND",
    "SECFININD",
)(_indicator)

# Freeze the registry at module load (no more rule registration allowed)
rule_registry.freeze()

