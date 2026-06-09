"""
Job Service
===========

Async service layer for CRUD operations on the ``jobs`` table.

All methods accept an ``AsyncSession`` injected via ``Depends(get_db)``
and perform their own commit so that callers do not need to manage
transactions directly.

Usage:
    from api.services.job_service import job_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        job = await job_service.create_job(db, "buyer_id_validation", {})
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.job import Job


class JobService:
    """Service class encapsulating all job persistence operations.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so that the service can be used with any session,
    including the test-provided in-memory SQLite session.
    """

    async def create_job(
        self,
        db: AsyncSession,
        script_name: str,
        config: dict,
    ) -> Job:
        """Create a new job row in ``pending`` status and return it.

        Args:
            db: Active async database session.
            script_name: Registered identifier of the script to run.
            config: Arbitrary configuration dict stored as ``config_snapshot``.

        Returns:
            The newly created ``Job`` ORM instance with all server-default
            fields populated after a flush.
        """
        job = Job(
            script_name=script_name,
            status="pending",
            config_snapshot=config,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def get_job(self, db: AsyncSession, job_id: str) -> Job | None:
        """Fetch a single job by its UUID string.

        Args:
            db: Active async database session.
            job_id: String representation of the job UUID.

        Returns:
            The matching ``Job`` ORM instance, or ``None`` if not found.
        """
        try:
            parsed_id = uuid.UUID(job_id)
        except ValueError:
            return None

        result = await db.execute(select(Job).where(Job.id == parsed_id))
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs ordered by creation time, most recent first.

        Args:
            db: Active async database session.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip (for pagination).

        Returns:
            A list of ``Job`` ORM instances, possibly empty.
        """
        result = await db.execute(
            select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        db: AsyncSession,
        job_id: str,
        status: str,
        error_message: str | None = None,
        output_files: list[str] | None = None,
        log_output: str | None = None,
    ) -> None:
        """Update the status of an existing job, setting lifecycle timestamps.

        Sets ``started_at`` when transitioning to ``"running"``, and
        ``completed_at`` when transitioning to ``"success"``, ``"failed"``,
        or ``"cancelled"``.

        Args:
            db: Active async database session.
            job_id: String representation of the job UUID.
            status: New status string (``"running"``, ``"success"``, etc.).
            error_message: Optional error description; stored when status is
                ``"failed"``.
            output_files: Optional list of relative output file paths to record.
            log_output: Optional full captured stdout/stderr to persist on
                completion so the frontend can display logs after the job finishes.
        """
        job = await self.get_job(db, job_id)
        if job is None:
            return

        now = datetime.now(tz=timezone.utc)
        job.status = status

        if status == "running":
            job.started_at = now
        elif status in ("success", "failed", "cancelled"):
            job.completed_at = now

        if error_message is not None:
            job.error_message = error_message

        if output_files is not None:
            job.output_files = output_files

        if log_output is not None:
            job.log_output = log_output

        await db.commit()

    async def delete_completed_jobs(self, db: AsyncSession) -> int:
        """Delete all jobs that are in a terminal state.

        Only jobs with status ``success``, ``failed``, or ``cancelled`` are
        removed.  Jobs with status ``pending``, ``running``, or ``waiting``
        are never deleted.

        Args:
            db: Active async database session.

        Returns:
            The number of rows deleted.
        """
        result = await db.execute(
            delete(Job).where(Job.status.in_(["success", "failed", "cancelled"]))
        )
        await db.commit()
        return result.rowcount


job_service = JobService()
