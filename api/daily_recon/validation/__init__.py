"""
Daily Reconciliation Validation Framework
===========================================

Extensible, traceable validation system:
- Rule registry with decorator-based registration
- Built-in rules (ID, country, numeric, date, indicator)
- Batch engine (column-major, parallel-ready)
- Traceability (per-rule failure recording)

Rule modules are auto-discovered and loaded here, then the registry is frozen.
"""

# ────────────────────────────────────────────────────────────────────────────
# Import rule modules (each self-registers via @rule_registry.register)
# ────────────────────────────────────────────────────────────────────────────
# When adding a new rule module, add its import here.

from . import rules  # noqa: F401 — triggers package __init__ (empty but valid)
from .rules import (  # noqa: F401
    country,
    dates,
    generic,
    id_rules,
    indicators,
    numeric,
)

# ────────────────────────────────────────────────────────────────────────────
# Freeze the registry after all rules are loaded
# ────────────────────────────────────────────────────────────────────────────

from .base import AsyncRule, BaseRule, Rule, RuleResult
from .engine import CellValidationResult, ValidationIssue, validate_batch
from .registry import rule_registry

# Freeze after all imports complete
rule_registry.freeze()

__all__ = [
    "Rule",
    "BaseRule",
    "AsyncRule",
    "RuleResult",
    "validate_batch",
    "CellValidationResult",
    "ValidationIssue",
    "rule_registry",
]
