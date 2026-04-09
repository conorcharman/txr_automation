"""
Schedule Service
================

Async service layer for CRUD operations on the ``schedules`` table, plus
next-run calculation logic.

``calculate_next_run`` supports five frequencies:

- ``hourly``  — next whole hour in UTC
- ``daily``   — next midnight UTC
- ``weekly``  — next Monday midnight UTC
- ``monthly`` — first of next month midnight UTC
- ``custom``  — uses the provided five-field cron expression via ``croniter``

Usage::

    from api.services.schedule_service import schedule_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        schedules = await schedule_service.list_schedules(db)
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schedule import Schedule


def calculate_next_run(frequency: str, cron_expression: str | None = None) -> datetime:
    """Calculate the next run datetime for a given frequency.

    Args:
        frequency: One of ``hourly``, ``daily``, ``weekly``, ``monthly``,
            or ``custom``.
        cron_expression: Five-field cron string; required when ``frequency``
            is ``custom``.

    Returns:
        A timezone-aware UTC ``datetime`` representing the next scheduled run.

    Raises:
        ValueError: When frequency is ``custom`` but ``cron_expression`` is
            not provided, or when ``frequency`` is unrecognised.
    """
    now = datetime.now(tz=timezone.utc)

    if frequency == "hourly":
        # Next whole hour
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    if frequency == "daily":
        # Next midnight UTC
        tomorrow = (now + timedelta(days=1)).date()
        return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc)

    if frequency == "weekly":
        # Next Monday midnight UTC
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_monday = (now + timedelta(days=days_until_monday)).date()
        return datetime(next_monday.year, next_monday.month, next_monday.day, tzinfo=timezone.utc)

    if frequency == "monthly":
        # First of next month midnight UTC
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

    if frequency == "custom":
        if not cron_expression:
            raise ValueError("cron_expression is required for custom frequency.")
        try:
            from croniter import croniter  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ValueError(
                "croniter package is required for custom frequency schedules. "
                "Install it with: pip install croniter"
            ) from exc
        cron = croniter(cron_expression, now)
        return cron.get_next(datetime).replace(tzinfo=timezone.utc)

    raise ValueError(f"Unrecognised frequency: '{frequency}'.")


class ScheduleService:
    """Service class encapsulating all schedule persistence operations.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so that the service can be tested with an in-memory
    SQLite session.
    """

    async def list_schedules(self, db: AsyncSession) -> list[Schedule]:
        """Return all schedules ordered by name.

        Args:
            db: Active async database session.

        Returns:
            List of ``Schedule`` ORM instances, possibly empty.
        """
        result = await db.execute(select(Schedule).order_by(Schedule.name))
        return list(result.scalars().all())

    async def get_schedule(self, db: AsyncSession, schedule_id: str) -> Schedule | None:
        """Fetch a single schedule by its UUID string.

        Args:
            db: Active async database session.
            schedule_id: String representation of the schedule UUID.

        Returns:
            The matching ``Schedule`` ORM instance, or ``None`` if not found.
        """
        try:
            parsed_id = uuid.UUID(schedule_id)
        except ValueError:
            return None
        result = await db.execute(select(Schedule).where(Schedule.id == parsed_id))
        return result.scalar_one_or_none()

    async def create_schedule(
        self,
        db: AsyncSession,
        name: str,
        script_name: str,
        frequency: str,
        cron_expression: str | None = None,
        config_data: dict | None = None,
        is_active: bool = True,
    ) -> Schedule:
        """Create a new schedule row and calculate its first ``next_run_at``.

        Args:
            db: Active async database session.
            name: Unique human-readable name.
            script_name: Registered script identifier.
            frequency: Recurrence cadence string.
            cron_expression: Five-field cron string for custom frequency.
            config_data: Arbitrary configuration dict.
            is_active: Whether the schedule is enabled immediately.

        Returns:
            The newly created ``Schedule`` ORM instance.
        """
        next_run = calculate_next_run(frequency, cron_expression) if is_active else None
        schedule = Schedule(
            name=name,
            script_name=script_name,
            frequency=frequency,
            cron_expression=cron_expression,
            config_data=config_data,
            is_active=is_active,
            next_run_at=next_run,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule: Schedule,
        **kwargs: object,
    ) -> Schedule:
        """Apply a partial update to a schedule and recalculate ``next_run_at``.

        Only keys supplied in ``kwargs`` are written to the database.  If
        ``frequency`` or ``cron_expression`` change, or ``is_active`` becomes
        ``True``, ``next_run_at`` is recalculated.

        Args:
            db: Active async database session.
            schedule: The ``Schedule`` ORM instance to update.
            **kwargs: Field values to apply (snake_case column names).

        Returns:
            The updated ``Schedule`` ORM instance after commit.
        """
        for key, value in kwargs.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)

        # Recalculate next run when the schedule is active
        if schedule.is_active:
            schedule.next_run_at = calculate_next_run(
                schedule.frequency, schedule.cron_expression
            )
        else:
            schedule.next_run_at = None

        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def delete_schedule(self, db: AsyncSession, schedule: Schedule) -> None:
        """Delete a schedule row from the database.

        Args:
            db: Active async database session.
            schedule: The ``Schedule`` ORM instance to delete.
        """
        await db.delete(schedule)
        await db.commit()

    async def mark_triggered(
        self,
        db: AsyncSession,
        schedule: Schedule,
        status: str = "pending",
    ) -> Schedule:
        """Record a manual or automatic trigger and advance ``next_run_at``.

        Args:
            db: Active async database session.
            schedule: The ``Schedule`` ORM instance that was triggered.
            status: Initial job status to record as ``last_status``.

        Returns:
            The updated ``Schedule`` ORM instance after commit.
        """
        from datetime import datetime, timezone

        schedule.last_run_at = datetime.now(tz=timezone.utc)
        schedule.last_status = status
        if schedule.is_active:
            schedule.next_run_at = calculate_next_run(
                schedule.frequency, schedule.cron_expression
            )
        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def get_due_schedules(self, db: AsyncSession) -> list[Schedule]:
        """Return all active schedules whose ``next_run_at`` is in the past.

        Used by the Celery beat task to find schedules that need to fire.

        Args:
            db: Active async database session.

        Returns:
            List of ``Schedule`` ORM instances that are overdue.
        """
        from datetime import datetime, timezone

        from sqlalchemy import and_

        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(Schedule).where(
                and_(
                    Schedule.is_active.is_(True),
                    Schedule.next_run_at <= now,
                )
            )
        )
        return list(result.scalars().all())


schedule_service = ScheduleService()
