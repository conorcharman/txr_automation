"""
Dashboard Router
================

REST endpoints for dashboard summary statistics.

Endpoints:
    GET /api/dashboard/stats — Return aggregated statistics for the main dashboard
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas.dashboard import DashboardStats
from api.services.dashboard_service import dashboard_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """Return aggregated statistics for display on the main dashboard.

    Computes the following metrics from the database:

    - ``jobs_today``: number of jobs created since UTC midnight today.
    - ``running_now``: number of jobs currently in ``"running"`` status.
    - ``success_rate``: fraction of completed jobs that succeeded over
      the last 7 days (1.0 when no completed jobs exist in the window).
    - ``total_saved_configs``: total count of persisted saved configurations.

    Args:
        db: Async database session injected by FastAPI.

    Returns:
        A ``DashboardStats`` instance with the computed values.
    """
    return await dashboard_service.get_stats(db)
