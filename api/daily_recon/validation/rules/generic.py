"""
Validation Rules - Generic
===========================

Reusable generic validation rules: not empty, max length, regex, allowed values.
"""

import re
from typing import Optional

from ..base import RuleResult
from ..registry import rule_registry


class NotEmptyRule:
    """Rule: cell must not be empty/NULL."""

    rule_id = "not_empty"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check that value is not empty.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the cell is non-empty.
        """
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
        """Check length.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the cell length is valid.
        """
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
            pattern: Regex pattern string.
            description: Human-readable pattern description.
        """
        self.pattern = re.compile(pattern)
        self.description = description or pattern

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check regex match.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the cell matches the regex.
        """
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        if not self.pattern.match(value.strip()):
            return RuleResult(
                is_valid=False,
                message=f"Value does not match expected format: {self.description}",
            )
        return RuleResult(is_valid=True)


class AllowedValuesRule:
    """Rule: value must be one of an allowed set."""

    rule_id = "allowed_values"

    def __init__(self, allowed: set[str], case_sensitive: bool = False):
        """Initialize with allowed values.

        Args:
            allowed: Set of allowed values.
            case_sensitive: Whether comparison is case-sensitive.
        """
        self.allowed = allowed if case_sensitive else {v.upper() for v in allowed}
        self.case_sensitive = case_sensitive

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check value is in allowed set.

        Args:
            value: The cell value to validate.
            record: The entire row dict (unused).

        Returns:
            A RuleResult indicating whether the value is allowed.
        """
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        check = value.strip() if self.case_sensitive else value.strip().upper()
        if check not in self.allowed:
            return RuleResult(
                is_valid=False,
                message=f"'{value}' is not an allowed value. Expected one of: {sorted(self.allowed)}",
            )
        return RuleResult(is_valid=True)

