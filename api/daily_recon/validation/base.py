"""
Validation Framework - Base
===========================

Core protocols and data structures for the validation engine.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RuleResult:
    """Result of a single validation rule.

    Attributes:
        is_valid: True if the value passes validation.
        message: Human-readable error message if not valid.
        suggested_fix: Optional suggested correction (do not auto-apply).
    """

    is_valid: bool
    message: str | None = None
    suggested_fix: str | None = None


class Rule(Protocol):
    """Protocol for a validation rule."""

    rule_id: str

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Validate a cell value.

        Args:
            value: The cell value to validate (original_value as string).
            record: The entire row as raw string dict (for cross-field rules).

        Returns:
            A RuleResult with is_valid, message, and optional suggested_fix.
        """
        ...

