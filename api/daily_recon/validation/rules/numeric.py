"""
Validation Rules - Numeric
===========================

Rules for numeric field validation: valid numbers, positive numbers.
"""

from decimal import Decimal, InvalidOperation

from ...columns import NUMERIC_COLUMNS
from ..base import RuleResult
from ..registry import rule_registry


class NumericRule:
    """Rule: value must be a valid number."""

    rule_id = "numeric"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check numeric validity.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the value is a valid number.
        """
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
        """Check that value is non-negative.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the value is non-negative.
        """
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
# Auto-register rules against numeric columns
# ────────────────────────────────────────────────────────────────────────────

_numeric = NumericRule()
_positive_number = PositiveNumberRule()

# Register all numeric columns as valid numbers
rule_registry.register(*NUMERIC_COLUMNS)(_numeric)

# Register quantity/notional columns as positive-only
positive_columns = {
    "QUANTITY",
    "DERIVATIVE_NOTIONAL_INCREASE_DECREASE",
}
rule_registry.register(*positive_columns)(_positive_number)
