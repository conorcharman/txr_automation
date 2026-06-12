"""
Validation Rules - ID Fields
=============================

Rules for ID field validation: not empty, format checks.
"""

import re

from ...columns import ID_COLUMNS
from ..base import RuleResult
from ..registry import rule_registry


class IdNotEmptyRule:
    """Rule: ID fields (BUYER_ID, SELLER_ID, etc.) must not be empty."""

    rule_id = "id_not_empty"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check that ID is not empty.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the ID is non-empty.
        """
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
        """Check ID format.

        IDs must contain 2–50 alphanumeric characters, hyphens, underscores, or dots.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the ID format is valid.
        """
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
# Auto-register rules against ID columns
# ────────────────────────────────────────────────────────────────────────────

_id_not_empty = IdNotEmptyRule()
_id_format = IdFormatRule()

# Register against all ID columns from columns.py
rule_registry.register(*ID_COLUMNS)(_id_not_empty)
rule_registry.register(*ID_COLUMNS)(_id_format)

