"""
Dashboard Schemas
=================

Pydantic v2 schemas for the dashboard statistics endpoint.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from __future__ import annotations

from api.schemas.common import _CamelModel


class DashboardStats(_CamelModel):
    """Statistics shown on the main dashboard.

    Attributes:
        jobs_today: Count of jobs created today (UTC midnight boundary).
        running_now: Count of jobs currently in ``"running"`` status.
        success_rate: Fraction of completed jobs that succeeded over the
            last 7 days, in the range 0.0–1.0.  Returns ``1.0`` when there
            are no completed jobs in the window.
        total_saved_configs: Total number of persisted saved configurations.
    """

    jobs_today: int
    running_now: int
    success_rate: float
    total_saved_configs: int
