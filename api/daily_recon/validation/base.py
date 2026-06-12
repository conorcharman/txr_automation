"""
Validation Framework - Base
===========================

Core protocols and data structures for the validation engine.
"""

from abc import ABC, abstractmethod
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
    """Protocol for a validation rule (structural typing)."""

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


class BaseRule(ABC):
    """Abstract base class for validation rules (optional; enables runtime enforcement).

    Subclass this to get automatic type checking at class definition time.
    Alternatively, just implement the Rule protocol for structural typing.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        ...

    @abstractmethod
    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Validate a cell value.

        Args:
            value: The cell value to validate (original_value as string).
            record: The entire row as raw string dict (for cross-field rules).

        Returns:
            A RuleResult with is_valid, message, and optional suggested_fix.
        """
        ...


class AsyncRule(Protocol):
    """Protocol for an asynchronous validation rule (for future GLEIF/FIRDS lookups)."""

    rule_id: str

    async def validate_async(
        self, value: str | None, record: dict[str, str | None]
    ) -> RuleResult:
        """Asynchronously validate a cell value.

        Args:
            value: The cell value to validate (original_value as string).
            record: The entire row as raw string dict (for cross-field rules).

        Returns:
            A RuleResult with is_valid, message, and optional suggested_fix.
        """
        ...
