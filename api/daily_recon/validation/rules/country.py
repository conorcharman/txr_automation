"""
Validation Rules - Country Codes
==================================

Rule for country code validation, delegating to the authoritative country_manager.
"""

from core.data import country_manager

from ...columns import COUNTRY_CODE_COLUMNS
from ..base import RuleResult
from ..registry import rule_registry


class CountryCodeRule:
    """Rule: country code must be a valid ISO 3166-1 alpha-2 code.

    Uses the authoritative country_manager from src.core.data, ensuring consistency
    with all other parts of the application.
    """

    rule_id = "country_code_valid"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check country code is valid.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the country code is valid.
        """
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        val = value.strip().upper()
        if not country_manager.validate_code(val):
            return RuleResult(
                is_valid=False,
                message=f"Invalid country code: {val}. Must be ISO 3166-1 alpha-2 or alpha-3.",
            )
        return RuleResult(is_valid=True)


# ────────────────────────────────────────────────────────────────────────────
# Auto-register rule against country code columns
# ────────────────────────────────────────────────────────────────────────────

_country_code = CountryCodeRule()

# Register against all country code columns from columns.py
rule_registry.register(*COUNTRY_CODE_COLUMNS)(_country_code)

