"""
Validation Framework - Registry
================================

Extensible rule registry: column_name -> tuple[Rule, ...].
Add/remove rules via decorator; zero hardcode; discover and freeze via __init__.
"""

import importlib
import pkgutil
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

        Raises:
            RuntimeError: If registry is frozen.
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

    def is_frozen(self) -> bool:
        """Return True if registry is frozen.

        Returns:
            True if no new rules can be registered.
        """
        return self._locked

    def all_rules(self) -> dict[str, tuple[Rule, ...]]:
        """Return the complete rule mapping (for debugging/introspection).

        Returns:
            Dictionary of column_name -> tuple[Rule, ...].
        """
        return dict(self._registry)

    def auto_discover(self, package_path: str) -> None:
        """Automatically discover and import all rule modules in a package.

        This enables plugins: place rule modules in the package directory,
        and they will be imported and auto-registered via their module-level code.

        Args:
            package_path: Full Python dotted path to the package (e.g. "api.daily_recon.validation.rules").

        Raises:
            RuntimeError: If registry is frozen.
            ImportError: If the package cannot be imported.

        Example:
            rule_registry.auto_discover("api.daily_recon.validation.rules")
            rule_registry.freeze()
        """
        if self._locked:
            msg = "Registry is frozen; cannot discover more rules."
            raise RuntimeError(msg)

        try:
            package = importlib.import_module(package_path)
        except ImportError as e:
            msg = f"Cannot import package {package_path}: {e}"
            raise ImportError(msg) from e

        # Import all modules in the package
        if not hasattr(package, "__path__"):
            msg = f"{package_path} is not a package."
            raise ImportError(msg)

        for importer, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_path}.{module_name}"
            try:
                importlib.import_module(full_name)
            except ImportError as e:
                # Log but do not fail — allow other modules to load
                # In production, consider a logger; for now, silently skip
                pass


#: Module-level singleton, frozen after import of rules modules.
rule_registry = RuleRegistry()
