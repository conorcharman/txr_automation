"""
Validation Rules - Indicators
==============================

Rules for indicator field validation: Y/N indicators.
"""

from ...columns import INDICATOR_COLUMNS
from ..base import RuleResult
from ..registry import rule_registry


class IndicatorRule:
    """Rule: indicator field (Y/N) must be Y or N."""

    rule_id = "indicator_valid"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check indicator is Y or N.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the indicator is valid (Y, N, or empty).
        """
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
# Auto-register rule against indicator columns
# ────────────────────────────────────────────────────────────────────────────

_indicator = IndicatorRule()

# Register all indicator columns
rule_registry.register(*INDICATOR_COLUMNS)(_indicator)

