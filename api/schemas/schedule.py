"""
Schedule Schemas
================

Pydantic v2 schemas for schedule creation, update, and retrieval endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from api.models.schedule import Schedule
from api.schemas.common import _CamelModel

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

_VALID_FREQUENCIES = frozenset({"hourly", "daily", "weekly", "monthly", "quarterly", "custom"})


class ScheduleCreate(_CamelModel):
    """Request body for creating a new schedule.

    Attributes:
        name: Unique human-readable name for the schedule.
        script_name: Registered script identifier, e.g. ``"buyer_id_validation"``.
        frequency: Recurrence cadence — ``hourly``, ``daily``, ``weekly``,
            ``monthly``, or ``custom``.
        cron_expression: Five-field cron string; required when
            ``frequency`` is ``custom``.
        config_data: Arbitrary configuration dict forwarded to the script.
        is_active: Whether the schedule should fire automatically.
    """

    name: str
    script_name: str
    frequency: str
    cron_expression: str | None = None
    config_data: dict | None = None
    is_active: bool = True


class ScheduleUpdate(_CamelModel):
    """Request body for partially updating an existing schedule.

    All fields are optional; only supplied fields are written to the database.

    Attributes:
        name: New unique name for this schedule.
        script_name: New registered script identifier.
        frequency: New recurrence cadence.
        cron_expression: New five-field cron string.
        config_data: New configuration dict.
        is_active: New active flag value.
    """

    name: str | None = None
    script_name: str | None = None
    frequency: str | None = None
    cron_expression: str | None = None
    config_data: dict | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ScheduleResponse(_CamelModel):
    """Response body representing a single schedule record.

    Attributes:
        id: UUID of the schedule, serialised as a plain string.
        name: Human-readable name.
        script_name: Registered script identifier.
        frequency: Recurrence cadence string.
        cron_expression: Five-field cron string, or ``None``.
        config_data: Configuration dict, or ``None``.
        is_active: Whether the schedule is enabled.
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
    script_name: str
    frequency: str
    cron_expression: str | None
    config_data: dict | None
    is_active: bool
    next_run_at: str | None
    last_run_at: str | None
    last_status: str | None
    created_at: str | None
    updated_at: str | None

    @classmethod
    def from_orm_schedule(cls, schedule: Schedule) -> "ScheduleResponse":
        """Construct a ``ScheduleResponse`` from a ``Schedule`` ORM instance.

        Handles UUID-to-string and datetime-to-ISO-8601 conversions.

        Args:
            schedule: A ``Schedule`` ORM instance loaded from the database.

        Returns:
            A fully populated ``ScheduleResponse``.
        """

        def _iso(dt: datetime | None) -> str | None:
            return dt.isoformat() if dt is not None else None

        return cls(
            id=str(schedule.id),
            name=schedule.name,
            script_name=schedule.script_name,
            frequency=schedule.frequency,
            cron_expression=schedule.cron_expression,
            config_data=schedule.config_data,
            is_active=schedule.is_active,
            next_run_at=_iso(schedule.next_run_at),
            last_run_at=_iso(schedule.last_run_at),
            last_status=schedule.last_status,
            created_at=_iso(schedule.created_at),
            updated_at=_iso(schedule.updated_at),
        )


class ScheduleTriggerResponse(_CamelModel):
    """Response body returned when a schedule is manually triggered.

    Attributes:
        job_id: UUID of the newly created background job.
        schedule_id: UUID of the schedule that was triggered.
        message: Human-readable confirmation message.
    """

    job_id: str
    schedule_id: str
    message: str
