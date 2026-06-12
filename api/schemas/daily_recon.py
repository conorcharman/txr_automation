"""
Daily Reconciliation Schemas
=============================

Pydantic v2 schemas for daily_recon API endpoints.
camelCase JSON serialization (React convention).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from api.schemas.common import _CamelModel


# ────────────────────────────────────────────────────────────────────────────
# Request Schemas
# ────────────────────────────────────────────────────────────────────────────


class DailyReconTriggerRequest(_CamelModel):
    """Request body to trigger a new daily reconciliation run."""

    source_query: str | None = None
    """Optional SQL override. If omitted, the stored query is used."""

    job_id: UUID | None = None
    """Optional Celery job ID for tracking."""


class CellCorrectionRequest(_CamelModel):
    """Request body to apply a correction to a cell."""

    corrected_value: str
    """The manually-corrected value."""


# ────────────────────────────────────────────────────────────────────────────
# Response Schemas
# ────────────────────────────────────────────────────────────────────────────


class CellIssueResponse(_CamelModel):
    """A single validation issue for a cell."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    rule_id: str
    """Identifier of the failed validation rule."""

    message: str
    """Human-readable error message."""

    suggested_fix: str | None = None
    """Optional suggested fix from the rule."""


class CellResponse(_CamelModel):
    """Response for a single cell (one column of one row)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: int
    """Cell ID (bigint)."""

    column_name: str
    """Column name (e.g., BUYER_ID)."""

    original_value: str | None = None
    """Original value from source."""

    suggested_fix: str | None = None
    """Suggested fix (if errored)."""

    corrected_value: str | None = None
    """User-applied correction."""

    is_errored: bool
    """Whether this cell has validation errors."""

    issues: list[CellIssueResponse] = []
    """List of validation rule failures (if any)."""


class RowResponse(_CamelModel):
    """Response for a single row (all columns)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    """Row ID."""

    row_index: int
    """Ordinal in the run (0-based)."""

    trade_ref: str | None = None
    """Denorm'd TRADEREF for lookup."""

    has_error: bool
    """Aggregate error flag."""

    approved: bool
    """User approval flag."""

    approved_at: datetime | None = None
    """When user approved (if approved=True)."""

    cells: list[CellResponse] = []
    """All cells in this row."""


class RunResponse(_CamelModel):
    """Response for a single reconciliation run."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: UUID
    """Run ID."""

    job_id: UUID | None = None
    """Celery job ID (if any)."""

    source_query: str
    """SQL query executed."""

    row_count: int
    """Total rows extracted."""

    error_row_count: int
    """Rows with at least one error."""

    status: str
    """pending|running|validated|exported|failed."""

    created_at: datetime | None = None
    """Creation timestamp."""

    updated_at: datetime | None = None
    """Last update timestamp."""

    # Avoid circular: don't include nested rows by default
    # Fetch via separate GET /runs/{id}/rows endpoint


class RunDetailResponse(RunResponse):
    """Run response with nested rows (for detail view)."""

    rows: list[RowResponse] = []
    """All rows in the run."""


# ────────────────────────────────────────────────────────────────────────────
# Pagination Response
# ────────────────────────────────────────────────────────────────────────────


class PaginatedRunsResponse(_CamelModel):
    """Paginated list of runs."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    data: list[RunResponse]
    """List of runs."""

    total: int
    """Total count (unfettered)."""

    limit: int = 50
    """Pagination limit."""

    offset: int = 0
    """Pagination offset."""


class PaginatedRowsResponse(_CamelModel):
    """Paginated list of rows."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    data: list[RowResponse]
    """List of rows."""

    total: int
    """Total count (unfettered)."""

    limit: int = 50
    """Pagination limit."""

    offset: int = 0
    """Pagination offset."""


