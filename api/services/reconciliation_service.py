"""
Reconciliation Service
======================

Async service layer for CRUD operations on the ``reconciliation_schedules``
table, plus next-run calculation logic.

Usage::

    from api.services.reconciliation_service import reconciliation_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        recs = await reconciliation_service.list_reconciliations(db)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.reconciliation import ReconciliationSchedule
from api.services.schedule_service import calculate_next_run


class ReconciliationService:
    """Service class encapsulating all reconciliation schedule operations.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so the service can be tested with an in-memory SQLite
    session.
    """

    async def list_reconciliations(
        self, db: AsyncSession
    ) -> list[ReconciliationSchedule]:
        """Return all reconciliation schedules ordered by name.

        Args:
            db: Active async database session.

        Returns:
            List of ``ReconciliationSchedule`` ORM instances, possibly empty.
        """
        result = await db.execute(
            select(ReconciliationSchedule).order_by(ReconciliationSchedule.name)
        )
        return list(result.scalars().all())

    async def get_reconciliation(
        self, db: AsyncSession, rec_id: str
    ) -> ReconciliationSchedule | None:
        """Fetch a single reconciliation schedule by its UUID string.

        Args:
            db: Active async database session.
            rec_id: String representation of the UUID.

        Returns:
            The matching ORM instance, or ``None`` if not found.
        """
        try:
            parsed_id = uuid.UUID(rec_id)
        except ValueError:
            return None
        result = await db.execute(
            select(ReconciliationSchedule).where(ReconciliationSchedule.id == parsed_id)
        )
        return result.scalar_one_or_none()

    async def create_reconciliation(
        self,
        db: AsyncSession,
        name: str,
        selected_scripts: list[str],
        frequency: str,
        rec_period_days: int = 90,
        lookback_days: int = 365,
        cron_expression: str | None = None,
        config_overrides: dict | None = None,
        stop_on_error: bool = True,
        is_active: bool = True,
    ) -> ReconciliationSchedule:
        """Create a new reconciliation schedule row.

        Args:
            db: Active async database session.
            name: Unique human-readable name.
            selected_scripts: Subset of valid reconciliation scripts.
            frequency: Recurrence cadence string.
            rec_period_days: Trade-by-trade window in days.
            lookback_days: Inconsistent ID lookback window in days.
            cron_expression: Five-field cron string for custom frequency.
            config_overrides: Optional per-stage path overrides.
            stop_on_error: Whether to halt on first failure.
            is_active: Whether the schedule is enabled immediately.

        Returns:
            The newly created ORM instance.
        """
        next_run = calculate_next_run(frequency, cron_expression) if is_active else None
        rec = ReconciliationSchedule(
            name=name,
            rec_period_days=rec_period_days,
            lookback_days=lookback_days,
            selected_scripts=selected_scripts,
            frequency=frequency,
            cron_expression=cron_expression,
            config_overrides=config_overrides,
            stop_on_error=stop_on_error,
            is_active=is_active,
            next_run_at=next_run,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return rec

    async def update_reconciliation(
        self,
        db: AsyncSession,
        rec: ReconciliationSchedule,
        **kwargs: object,
    ) -> ReconciliationSchedule:
        """Apply a partial update to a reconciliation schedule.

        Only keys supplied in ``kwargs`` are written.  If ``frequency``,
        ``cron_expression``, or ``is_active`` change, ``next_run_at`` is
        recalculated.

        Args:
            db: Active async database session.
            rec: The ORM instance to update.
            **kwargs: Field values to apply.

        Returns:
            The updated ORM instance after commit.
        """
        for key, value in kwargs.items():
            if hasattr(rec, key):
                setattr(rec, key, value)

        if rec.is_active:
            rec.next_run_at = calculate_next_run(rec.frequency, rec.cron_expression)
        else:
            rec.next_run_at = None

        await db.commit()
        await db.refresh(rec)
        return rec

    async def delete_reconciliation(
        self, db: AsyncSession, rec: ReconciliationSchedule
    ) -> None:
        """Delete a reconciliation schedule from the database.

        Args:
            db: Active async database session.
            rec: The ORM instance to delete.
        """
        await db.delete(rec)
        await db.commit()

    async def get_due_reconciliations(
        self, db: AsyncSession
    ) -> list[ReconciliationSchedule]:
        """Return active schedules whose ``next_run_at`` is in the past.

        Args:
            db: Active async database session.

        Returns:
            List of due ``ReconciliationSchedule`` ORM instances.
        """
        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(ReconciliationSchedule).where(
                ReconciliationSchedule.is_active.is_(True),
                ReconciliationSchedule.next_run_at <= now,
            )
        )
        return list(result.scalars().all())

    async def mark_triggered(
        self,
        db: AsyncSession,
        rec: ReconciliationSchedule,
        status: str = "pending",
    ) -> ReconciliationSchedule:
        """Advance a schedule's ``last_run_at`` and recalculate ``next_run_at``.

        Called after a reconciliation run has been dispatched.

        Args:
            db: Active async database session.
            rec: The ORM instance that was just triggered.
            status: Status string to record.

        Returns:
            The updated ORM instance.
        """
        rec.last_run_at = datetime.now(tz=timezone.utc)
        rec.last_status = status
        rec.next_run_at = calculate_next_run(rec.frequency, rec.cron_expression)
        await db.commit()
        await db.refresh(rec)
        return rec


#: Module-level singleton for use in route handlers via dependency injection.
reconciliation_service = ReconciliationService()
