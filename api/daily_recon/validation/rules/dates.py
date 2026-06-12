"""
Validation Rules - Dates
=========================

Rules for date field validation: date format, reasonable date ranges.
"""

from datetime import datetime

from ...columns import DATE_COLUMNS
from ..base import RuleResult
from ..registry import rule_registry


class DateFormatRule:
    """Rule: date must parse to a valid date."""

    rule_id = "date_format"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Try parsing as date.

        Accepts multiple common date formats:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - MM/DD/YYYY
        - DD-MM-YYYY

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the date format is valid.
        """
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
        """Check date is within a reasonable range.

        Dates before 1900 or after 2050 are considered unreasonable for modern transaction data.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the date is within a reasonable range.
        """
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
# Auto-register rules against date columns
# ────────────────────────────────────────────────────────────────────────────

_date_format = DateFormatRule()
_reasonable_date = ReasonableDateRule()

# Register all date columns
rule_registry.register(*DATE_COLUMNS)(_date_format)
rule_registry.register(*DATE_COLUMNS)(_reasonable_date)

