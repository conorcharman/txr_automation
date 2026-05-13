"""
Dashboard Service
=================

Async service layer for computing dashboard statistics from the database.

All methods accept an ``AsyncSession`` injected via ``Depends(get_db)``
and issue read-only aggregate queries.

Usage:
    from api.services.dashboard_service import dashboard_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        stats = await dashboard_service.get_stats(db)
"""

from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.job import Job
from api.models.saved_config import SavedConfig
from api.schemas.dashboard import DashboardStats


class DashboardService:
    """Service class encapsulating dashboard statistics queries.

    Methods are intentionally stateless — the ``AsyncSession`` is accepted
    as a parameter so that the service can be used with any session,
    including the test-provided in-memory SQLite session.
    """

    async def get_stats(self, db: AsyncSession) -> DashboardStats:
        """Compute dashboard statistics from the database.

        Executes four lightweight aggregate queries:

        - ``jobs_today``: count of ``Job`` rows created since UTC midnight today.
        - ``running_now``: count of ``Job`` rows with ``status = "running"``.
        - ``success_rate``: ratio of successful jobs to all completed jobs
          (``"success"`` + ``"failed"``) over the last 7 days.  Returns
          ``1.0`` when there are no completed jobs in the window.
        - ``total_saved_configs``: total count of ``SavedConfig`` rows.

        Args:
            db: Active async database session.

        Returns:
            A ``DashboardStats`` instance populated with the computed values.
        """
        today_utc = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Jobs created today (UTC).
        jobs_today_result = await db.execute(
            select(func.count(Job.id)).where(Job.created_at >= today_utc)
        )
        jobs_today: int = jobs_today_result.scalar_one() or 0

        # Jobs currently running.
        running_result = await db.execute(
            select(func.count(Job.id)).where(Job.status == "running")
        )
        running_now: int = running_result.scalar_one() or 0

        # Success/failed counts over the last 7 days.
        success_result = await db.execute(
            select(func.count(Job.id)).where(
                Job.status == "success",
                Job.completed_at >= seven_days_ago,
            )
        )
        success_count: int = success_result.scalar_one() or 0

        failed_result = await db.execute(
            select(func.count(Job.id)).where(
                Job.status == "failed",
                Job.completed_at >= seven_days_ago,
            )
        )
        failed_count: int = failed_result.scalar_one() or 0

        total_completed = success_count + failed_count
        success_rate: float = (success_count / total_completed) if total_completed > 0 else 1.0

        # Total saved configurations.
        configs_result = await db.execute(select(func.count(SavedConfig.id)))
        total_saved_configs: int = configs_result.scalar_one() or 0

        return DashboardStats(
            jobs_today=jobs_today,
            running_now=running_now,
            success_rate=success_rate,
            total_saved_configs=total_saved_configs,
        )


dashboard_service = DashboardService()
