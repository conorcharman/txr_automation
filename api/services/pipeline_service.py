"""
Pipeline Service
================

Async service layer for CRUD operations on the ``pipelines`` table, plus
next-run calculation logic (reuses ``calculate_next_run`` from schedule_service).

Usage::

    from api.services.pipeline_service import pipeline_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        pipelines = await pipeline_service.list_pipelines(db)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.pipeline import Pipeline
from api.services.schedule_service import calculate_next_run


class PipelineService:
    """Service class encapsulating all pipeline persistence operations.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so that the service can be tested with an in-memory
    SQLite session.
    """

    async def list_pipelines(self, db: AsyncSession) -> list[Pipeline]:
        """Return all pipelines ordered by name.

        Args:
            db: Active async database session.

        Returns:
            List of ``Pipeline`` ORM instances, possibly empty.
        """
        result = await db.execute(select(Pipeline).order_by(Pipeline.name))
        return list(result.scalars().all())

    async def get_pipeline(self, db: AsyncSession, pipeline_id: str) -> Pipeline | None:
        """Fetch a single pipeline by its UUID string.

        Args:
            db: Active async database session.
            pipeline_id: String representation of the pipeline UUID.

        Returns:
            The matching ``Pipeline`` ORM instance, or ``None`` if not found.
        """
        try:
            parsed_id = uuid.UUID(pipeline_id)
        except ValueError:
            return None
        result = await db.execute(select(Pipeline).where(Pipeline.id == parsed_id))
        return result.scalar_one_or_none()

    async def create_pipeline(
        self,
        db: AsyncSession,
        name: str,
        fiscal_year: str,
        quarter: str,
        selected_scripts: list[str],
        frequency: str,
        cron_expression: str | None = None,
        config_overrides: dict | None = None,
        stop_on_error: bool = True,
        is_active: bool = True,
    ) -> Pipeline:
        """Create a new pipeline row and calculate its first ``next_run_at``.

        Args:
            db: Active async database session.
            name: Unique human-readable name.
            fiscal_year: Fiscal year string, e.g. ``"FY26"``.
            quarter: Quarter string, e.g. ``"Q1"``.
            selected_scripts: Ordered list of script keys.
            frequency: Recurrence cadence string.
            cron_expression: Five-field cron string for custom frequency.
            config_overrides: Optional per-stage path overrides.
            stop_on_error: Whether to halt on first failure.
            is_active: Whether the pipeline is enabled immediately.

        Returns:
            The newly created ``Pipeline`` ORM instance.
        """
        next_run = calculate_next_run(frequency, cron_expression) if is_active else None
        pipeline = Pipeline(
            name=name,
            fiscal_year=fiscal_year,
            quarter=quarter,
            selected_scripts=selected_scripts,
            frequency=frequency,
            cron_expression=cron_expression,
            config_overrides=config_overrides,
            stop_on_error=stop_on_error,
            is_active=is_active,
            next_run_at=next_run,
        )
        db.add(pipeline)
        await db.commit()
        await db.refresh(pipeline)
        return pipeline

    async def update_pipeline(
        self,
        db: AsyncSession,
        pipeline: Pipeline,
        **kwargs: object,
    ) -> Pipeline:
        """Apply a partial update to a pipeline and recalculate ``next_run_at``.

        Only keys supplied in ``kwargs`` are written to the database.  If
        ``frequency`` or ``cron_expression`` change, or ``is_active`` becomes
        ``True``, ``next_run_at`` is recalculated.

        Args:
            db: Active async database session.
            pipeline: The ``Pipeline`` ORM instance to update.
            **kwargs: Field values to apply (snake_case column names).

        Returns:
            The updated ``Pipeline`` ORM instance after commit.
        """
        for key, value in kwargs.items():
            if hasattr(pipeline, key):
                setattr(pipeline, key, value)

        if pipeline.is_active:
            pipeline.next_run_at = calculate_next_run(
                pipeline.frequency, pipeline.cron_expression
            )
        else:
            pipeline.next_run_at = None

        await db.commit()
        await db.refresh(pipeline)
        return pipeline

    async def delete_pipeline(self, db: AsyncSession, pipeline: Pipeline) -> None:
        """Delete a pipeline from the database.

        Args:
            db: Active async database session.
            pipeline: The ``Pipeline`` ORM instance to delete.
        """
        await db.delete(pipeline)
        await db.commit()

    async def get_due_pipelines(self, db: AsyncSession) -> list[Pipeline]:
        """Return active pipelines whose ``next_run_at`` is in the past.

        Args:
            db: Active async database session.

        Returns:
            List of due ``Pipeline`` ORM instances.
        """
        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(Pipeline).where(
                Pipeline.is_active.is_(True),
                Pipeline.next_run_at <= now,
            )
        )
        return list(result.scalars().all())

    async def mark_triggered(
        self,
        db: AsyncSession,
        pipeline: Pipeline,
        status: str = "pending",
    ) -> Pipeline:
        """Advance a pipeline's ``last_run_at`` and recalculate ``next_run_at``.

        Called after a pipeline run has been dispatched.

        Args:
            db: Active async database session.
            pipeline: The ``Pipeline`` ORM instance that was just triggered.
            status: Status string to record, e.g. ``"pending"``.

        Returns:
            The updated ``Pipeline`` ORM instance.
        """
        pipeline.last_run_at = datetime.now(tz=timezone.utc)
        pipeline.last_status = status
        pipeline.next_run_at = calculate_next_run(
            pipeline.frequency, pipeline.cron_expression
        )
        await db.commit()
        await db.refresh(pipeline)
        return pipeline


#: Module-level singleton for use in route handlers via dependency injection.
pipeline_service = PipelineService()
