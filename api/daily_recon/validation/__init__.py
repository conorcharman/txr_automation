"""
Daily Reconciliation Validation Framework
===========================================

Extensible, traceable validation system:
- Rule registry (add/remove rules via decorator)
- Built-in rules (ID, country, numeric, date, indicator)
- Batch engine (column-major, parallel-ready)
- Traceability (per-rule failure recording)
"""

from .base import Rule, RuleResult
from .engine import CellValidationResult, ValidationIssue, validate_batch
from .registry import rule_registry

__all__ = [
    "Rule",
    "RuleResult",
    "validate_batch",
    "CellValidationResult",
    "ValidationIssue",
    "rule_registry",
]

