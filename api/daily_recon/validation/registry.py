"""
Validation Framework - Registry
================================

Extensible rule registry: column_name -> tuple[Rule, ...].
Add/remove rules via decorator; registry frozen at import; zero hardcode.
"""

from typing import Callable

from .base import Rule


class RuleRegistry:
    """Immutable registry mapping column names to validation rules."""

    def __init__(self) -> None:
        """Initialize empty registry (frozen after loading rules)."""
        self._registry: dict[str, tuple[Rule, ...]] = {}
        self._locked = False

    def register(self, *column_names: str) -> Callable[[Rule], Rule]:
        """Decorator to register a rule for one or more columns.

        Example:
            @rule_registry.register("BUYER_ID", "SELLER_ID")
            class IdNotEmptyRule:
                rule_id = "id_not_empty"
                def validate(self, value, record):
                    ...

        Args:
            column_names: One or more column names.

        Returns:
            A decorator function.
        """
        if self._locked:
            msg = "Registry is frozen; cannot add more rules."
            raise RuntimeError(msg)

        def decorator(rule: Rule) -> Rule:
            for col in column_names:
                existing = self._registry.get(col, ())
                self._registry[col] = existing + (rule,)
            return rule

        return decorator

    def get_rules(self, column_name: str) -> tuple[Rule, ...]:
        """Retrieve rules for a column (empty tuple if none).

        Args:
            column_name: The column name.

        Returns:
            Tuple of Rule instances (possibly empty).
        """
        return self._registry.get(column_name, ())

    def freeze(self) -> None:
        """Prevent further rule registration (called after module load)."""
        self._locked = True

    def all_rules(self) -> dict[str, tuple[Rule, ...]]:
        """Return the complete rule mapping (for debugging/introspection)."""
        return dict(self._registry)


#: Module-level singleton, frozen after import of rules modules.
rule_registry = RuleRegistry()

