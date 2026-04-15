"""
Reconciliation Schemas
======================

Pydantic v2 schemas for reconciliation schedule creation, update, and
retrieval endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from api.schemas.common import _CamelModel

#: Script keys that are valid for inclusion in a reconciliation schedule.
RECONCILIATION_SCRIPTS: frozenset[str] = frozenset(
    {
        "buyer_id_validation",
        "seller_id_validation",
        "validate_ftbdm",
        "validate_ftsdm",
        "inconsistent_buyer_id_validation",
        "inconsistent_seller_id_validation",
    }
)

#: Trade-by-trade scripts use the shorter rec_period_days window.
TRADE_BY_TRADE_SCRIPTS: frozenset[str] = frozenset(
    {
        "buyer_id_validation",
        "seller_id_validation",
        "validate_ftbdm",
        "validate_ftsdm",
    }
)

#: Inconsistent ID scripts use the longer lookback_days window.
INCONSISTENT_ID_SCRIPTS: frozenset[str] = frozenset(
    {
        "inconsistent_buyer_id_validation",
        "inconsistent_seller_id_validation",
    }
)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ReconciliationCreate(_CamelModel):
    """Request body for creating a new reconciliation schedule.

    Attributes:
        name: Unique human-readable name.
        rec_period_days: Days for the trade-by-trade validation window.
        lookback_days: Days for the inconsistent ID lookback window.
        selected_scripts: Subset of valid reconciliation scripts.
        frequency: Recurrence cadence.
        cron_expression: Five-field cron string (required when ``custom``).
        config_overrides: Optional per-stage path overrides dict.
        stop_on_error: Whether to halt on first failure.
        is_active: Whether the schedule should fire automatically.
    """

    name: str
    rec_period_days: int = 90
    lookback_days: int = 365
    selected_scripts: list[str]
    frequency: str
    cron_expression: str | None = None
    config_overrides: dict | None = None
    stop_on_error: bool = True
    is_active: bool = True

    @field_validator("selected_scripts")
    @classmethod
    def validate_scripts(cls, v: list[str]) -> list[str]:
        """Ensure all selected scripts are valid reconciliation scripts."""
        invalid = set(v) - RECONCILIATION_SCRIPTS
        if invalid:
            raise ValueError(
                f"Invalid reconciliation scripts: {sorted(invalid)}. "
                f"Valid scripts: {sorted(RECONCILIATION_SCRIPTS)}"
            )
        return v

    @field_validator("rec_period_days", "lookback_days")
    @classmethod
    def validate_positive_days(cls, v: int) -> int:
        """Ensure day counts are positive."""
        if v < 1:
            raise ValueError("Day count must be at least 1.")
        return v


class ReconciliationUpdate(_CamelModel):
    """Request body for partially updating a reconciliation schedule.

    All fields are optional; only supplied fields are written.
    """

    name: str | None = None
    rec_period_days: int | None = None
    lookback_days: int | None = None
    selected_scripts: list[str] | None = None
    frequency: str | None = None
    cron_expression: str | None = None
    config_overrides: dict | None = None
    stop_on_error: bool | None = None
    is_active: bool | None = None

    @field_validator("selected_scripts")
    @classmethod
    def validate_scripts(cls, v: list[str] | None) -> list[str] | None:
        """Ensure all selected scripts are valid reconciliation scripts."""
        if v is not None:
            invalid = set(v) - RECONCILIATION_SCRIPTS
            if invalid:
                raise ValueError(
                    f"Invalid reconciliation scripts: {sorted(invalid)}."
                )
        return v

    @field_validator("rec_period_days", "lookback_days")
    @classmethod
    def validate_positive_days(cls, v: int | None) -> int | None:
        """Ensure day counts are positive when provided."""
        if v is not None and v < 1:
            raise ValueError("Day count must be at least 1.")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ReconciliationResponse(_CamelModel):
    """Response body representing a single reconciliation schedule.

    Attributes:
        id: UUID serialised as a plain string.
        name: Human-readable name.
        rec_period_days: Trade-by-trade validation window in days.
        lookback_days: Inconsistent ID lookback window in days.
        selected_scripts: Ordered list of script keys.
        frequency: Recurrence cadence string.
        cron_expression: Five-field cron string, or ``None``.
        config_overrides: Per-stage path overrides dict, or ``None``.
        stop_on_error: Whether the schedule halts on first failure.
        is_active: Whether the schedule is enabled.
        next_run_at: ISO 8601 timestamp of next scheduled run, or ``None``.
        last_run_at: ISO 8601 timestamp of last run, or ``None``.
        last_status: Status string from last run, or ``None``.
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
    rec_period_days: int
    lookback_days: int
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
