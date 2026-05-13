"""
Jobs Router Tests
=================

Tests for the job management endpoints:

    GET  /api/jobs
    GET  /api/jobs/{job_id}
    POST /api/jobs
    POST /api/jobs/{job_id}/cancel
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_jobs_empty(client: AsyncClient) -> None:
    """GET /api/jobs returns an empty list when no jobs exist.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_get_job_not_found(client: AsyncClient) -> None:
    """GET /api/jobs/{id} returns 404 for an unknown job UUID.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get(f"/api/jobs/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_job_invalid_uuid(client: AsyncClient) -> None:
    """GET /api/jobs/{id} returns 404 for a malformed UUID string.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/jobs/not-a-uuid")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_create_job(client: AsyncClient, mocker) -> None:
    """POST /api/jobs creates a pending job and dispatches a Celery task.

    The Celery ``delay`` call is patched so no real worker is required.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    response = await client.post(
        "/api/jobs",
        json={"scriptName": "buyer_id_validation", "config": {"fiscalYear": "FY26"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "buyer_id_validation"
    assert "id" in data
    assert data["startedAt"] is None
    assert data["completedAt"] is None


@pytest.mark.anyio
async def test_create_job_dispatches_task(client: AsyncClient, mocker) -> None:
    """POST /api/jobs calls ``run_script.delay`` exactly once.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mock_delay = mocker.patch("api.routers.jobs.run_script.delay")

    await client.post(
        "/api/jobs",
        json={"scriptName": "buyer_id_validation", "config": {}},
    )

    mock_delay.assert_called_once()


@pytest.mark.anyio
async def test_create_job_unknown_script(client: AsyncClient) -> None:
    """POST /api/jobs returns 400 for an unregistered script name.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.post(
        "/api/jobs",
        json={"scriptName": "nonexistent_script", "config": {}},
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_list_jobs_after_create(client: AsyncClient, mocker) -> None:
    """GET /api/jobs returns the created job after POST /api/jobs.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    await client.post(
        "/api/jobs",
        json={"scriptName": "seller_id_validation", "config": {}},
    )
    response = await client.get("/api/jobs")

    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["scriptName"] == "seller_id_validation"


@pytest.mark.anyio
async def test_get_job_by_id(client: AsyncClient, mocker) -> None:
    """GET /api/jobs/{id} returns the correct job after creation.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    create_resp = await client.post(
        "/api/jobs",
        json={"scriptName": "buyer_id_validation", "config": {"key": "val"}},
    )
    job_id = create_resp.json()["id"]

    response = await client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["scriptName"] == "buyer_id_validation"


@pytest.mark.anyio
async def test_cancel_job(client: AsyncClient, mocker) -> None:
    """POST /api/jobs/{id}/cancel sets status to ``cancelled`` for a pending job.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    create_resp = await client.post(
        "/api/jobs",
        json={"scriptName": "buyer_id_validation", "config": {}},
    )
    job_id = create_resp.json()["id"]

    response = await client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_cancel_job_not_found(client: AsyncClient) -> None:
    """POST /api/jobs/{id}/cancel returns 404 for an unknown job.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.post(f"/api/jobs/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_last_runs_empty(client: AsyncClient) -> None:
    """GET /api/jobs/last-runs returns an empty mapping on a fresh database.

    This protects against backend-specific SQL that may fail on SQLite during
    API tests.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/jobs/last-runs")

    assert response.status_code == 200
    assert response.json() == {}


@pytest.mark.anyio
async def test_create_job_replay_phase2_final(client: AsyncClient, mocker) -> None:
    """POST /api/jobs accepts the replay_phase2_final registered script.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.jobs.run_script.delay")

    response = await client.post(
        "/api/jobs",
        json={"scriptName": "replay_phase2_final", "config": {}},
    )

    assert response.status_code == 200
    assert response.json()["scriptName"] == "replay_phase2_final"
