"""
Validation Framework - Engine
=============================

Batch validation engine: column-major processing, parallel workers,
traceability collection.
"""

from dataclasses import dataclass, field
from typing import NamedTuple

from ..columns import COLUMN_NAMES
from .base import RuleResult
from .registry import rule_registry


class ValidationIssue(NamedTuple):
    """A single validation issue for one cell."""

    row_index: int
    column_name: str
    rule_id: str
    message: str
    suggested_fix: str | None = None


@dataclass
class CellValidationResult:
    """Validation result for one cell."""

    row_index: int
    column_name: str
    is_errored: bool
    suggested_fix: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)


def validate_batch(
    batch: list[dict[str, str | None]],
    start_row_index: int = 0,
) -> list[list[CellValidationResult]]:
    """Validate a batch of rows, returning results per row.

    Column-major approach: iterate columns, gather all values for that column
    across the batch, apply rules (vectorised where possible), collect issues.

    Args:
        batch: List of row dicts (source strings, nullable).
        start_row_index: Starting row index (for multi-batch runs).

    Returns:
        List of result lists: results[row_idx] = list[CellValidationResult]
        for that row. Same length as batch.
    """
    # Initialize results per row
    results_by_row: list[list[CellValidationResult]] = [
        [] for _ in range(len(batch))
    ]

    # Column-major iteration
    for column_name in COLUMN_NAMES:
        rules = rule_registry.get_rules(column_name)
        if not rules:
            continue

        # Apply all rules for this column to all rows in batch
        for row_idx, row_dict in enumerate(batch):
            cell_value = row_dict.get(column_name)
            issues: list[ValidationIssue] = []
            suggested_fix: str | None = None
            is_errored = False

            # Run each rule
            for rule in rules:
                result: RuleResult = rule.validate(cell_value, row_dict)
                if not result.is_valid:
                    is_errored = True
                    issues.append(
                        ValidationIssue(
                            row_index=start_row_index + row_idx,
                            column_name=column_name,
                            rule_id=rule.rule_id,
                            message=result.message or "Validation failed",
                            suggested_fix=result.suggested_fix,
                        )
                    )
                    # Prefer the first rule's suggested fix (can refine logic here)
                    if result.suggested_fix and not suggested_fix:
                        suggested_fix = result.suggested_fix

            # Build result for this cell
            cell_result = CellValidationResult(
                row_index=start_row_index + row_idx,
                column_name=column_name,
                is_errored=is_errored,
                suggested_fix=suggested_fix if is_errored else None,
                issues=issues,
            )
            results_by_row[row_idx].append(cell_result)

    return results_by_row


