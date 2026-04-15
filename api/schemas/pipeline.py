"""
Pipeline Schemas
================

Pydantic v2 schemas for pipeline creation, update, and retrieval endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from api.schemas.common import _CamelModel

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PipelineCreate(_CamelModel):
    """Request body for creating a new pipeline.

    Attributes:
        name: Unique human-readable name for the pipeline.
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        selected_scripts: Ordered list of script keys to execute.
        frequency: Recurrence cadence — ``hourly``, ``daily``, ``weekly``,
            ``monthly``, or ``custom``.
        cron_expression: Five-field cron string; required when
            ``frequency`` is ``custom``.
        config_overrides: Optional per-stage path overrides dict.
        stop_on_error: Whether to halt on first failure (default: ``True``).
        is_active: Whether the pipeline should fire automatically.
    """

    name: str
    fiscal_year: str
    quarter: str
    selected_scripts: list[str]
    frequency: str
    cron_expression: str | None = None
    config_overrides: dict | None = None
    stop_on_error: bool = True
    is_active: bool = True


class PipelineUpdate(_CamelModel):
    """Request body for partially updating an existing pipeline.

    All fields are optional; only supplied fields are written to the database.

    Attributes:
        name: New unique name for this pipeline.
        fiscal_year: New fiscal year string.
        quarter: New quarter string.
        selected_scripts: New ordered list of script keys.
        frequency: New recurrence cadence.
        cron_expression: New five-field cron string.
        config_overrides: New per-stage path overrides dict.
        stop_on_error: New stop-on-error flag value.
        is_active: New active flag value.
    """

    name: str | None = None
    fiscal_year: str | None = None
    quarter: str | None = None
    selected_scripts: list[str] | None = None
    frequency: str | None = None
    cron_expression: str | None = None
    config_overrides: dict | None = None
    stop_on_error: bool | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PipelineResponse(_CamelModel):
    """Response body representing a single pipeline record.

    Attributes:
        id: UUID of the pipeline, serialised as a plain string.
        name: Human-readable name.
        fiscal_year: Fiscal year string.
        quarter: Quarter string.
        selected_scripts: Ordered list of script keys.
        frequency: Recurrence cadence string.
        cron_expression: Five-field cron string, or ``None``.
        config_overrides: Per-stage path overrides dict, or ``None``.
        stop_on_error: Whether the pipeline halts on first failure.
        is_active: Whether the pipeline is enabled.
        next_run_at: ISO 8601 timestamp of the next scheduled run, or ``None``.
        last_run_at: ISO 8601 timestamp of the last run, or ``None``.
        last_status: Status string from the last run, or ``None``.
        created_at: ISO 8601 creation timestamp, or ``None``.
        updated_at: ISO 8601 last-update timestamp, or ``None``.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    id: str
    name: str
    fiscal_year: str
    quarter: str
    selected_scripts: list[str]
    frequency: str
    cron_expression: str | None = None
    config_overrides: dict | None = None
    stop_on_error: bool
    is_active: bool
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
