"""
Tests: Dashboard Endpoints
==========================

Integration tests for the ``GET /api/dashboard/stats`` endpoint using an
in-memory SQLite database via the shared ``client`` fixture.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_dashboard_stats_empty(client: AsyncClient) -> None:
    """GET /api/dashboard/stats on an empty database returns sensible defaults.

    Expects:
        - jobs_today = 0
        - running_now = 0
        - success_rate = 1.0 (no completed jobs in window)
        - total_saved_configs = 0
    """
    response = await client.get("/api/dashboard/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["jobsToday"] == 0
    assert data["runningNow"] == 0
    assert data["successRate"] == 1.0
    assert data["totalSavedConfigs"] == 0


@pytest.mark.anyio
async def test_dashboard_stats_with_jobs(client: AsyncClient, mocker) -> None:
    """GET /api/dashboard/stats reflects created jobs and configs in counts.

    The Celery ``delay`` call is patched so no real worker or Redis
    connection is required.

    Creates:
        - 2 jobs via POST /api/jobs (both start as "pending")
        - 1 saved config via POST /api/configs

    Verifies:
        - jobs_today = 2  (both were created today)
        - running_now = 0  (no jobs are running)
        - total_saved_configs = 1
        - success_rate = 1.0  (no completed jobs yet)
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    # Create two jobs.
    for _ in range(2):
        job_response = await client.post(
            "/api/jobs",
            json={"scriptName": "buyer_id_validation", "config": {}},
        )
        assert job_response.status_code == 200

    # Create one saved config.
    config_response = await client.post(
        "/api/configs",
        json={
            "name": "Dashboard Test Config",
            "scriptName": "buyer_id_validation",
            "configData": {},
        },
    )
    assert config_response.status_code == 200

    response = await client.get("/api/dashboard/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["jobsToday"] == 2
    assert data["runningNow"] == 0
    assert data["successRate"] == 1.0
    assert data["totalSavedConfigs"] == 1
