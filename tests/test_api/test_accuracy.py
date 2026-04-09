"""
Accuracy Router Tests
=====================

Tests for the accuracy testing endpoints:

    GET  /api/accuracy/scripts
    POST /api/accuracy/run
    POST /api/accuracy/run-all
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_accuracy_scripts(client: AsyncClient) -> None:
    """GET /api/accuracy/scripts returns a non-empty list of script name strings.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/accuracy/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) > 0
    assert all(isinstance(s, str) for s in scripts)
    assert "buyer_id_validation" in scripts
    assert "seller_id_validation" in scripts


@pytest.mark.anyio
async def test_run_validation(client: AsyncClient, mocker) -> None:
    """POST /api/accuracy/run creates a pending job and dispatches a Celery task.

    The ``run_script.delay`` call is patched so no real worker is required.  The
    service's ``build_accuracy_argv`` is also patched to avoid writing temp files.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.accuracy.run_script.delay")
    mocker.patch(
        "api.routers.accuracy.script_runner_service.build_accuracy_argv",
        return_value=(
            "src.accuracy_testing.scripts.buyer_id_validation",
            ["--config", "/tmp/test.yaml", "--log-level", "INFO"],
            {"mode": "batch"},
        ),
    )

    response = await client.post(
        "/api/accuracy/run",
        json={
            "scriptName": "buyer_id_validation",
            "testingPeriod": {"fiscalYear": "FY26", "quarter": "Q1"},
            "mode": "batch",
            "batchConfig": {
                "inputDirectory": "/data/input",
                "outputDirectory": "/data/output",
                "templateDirectory": "/data/templates",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "buyer_id_validation"
    assert "id" in data
    assert data["startedAt"] is None
    assert data["completedAt"] is None


@pytest.mark.anyio
async def test_run_validation_dispatches_task(client: AsyncClient, mocker) -> None:
    """POST /api/accuracy/run calls ``run_script.delay`` exactly once.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mock_delay = mocker.patch("api.routers.accuracy.run_script.delay")
    mocker.patch(
        "api.routers.accuracy.script_runner_service.build_accuracy_argv",
        return_value=(
            "src.accuracy_testing.scripts.seller_id_validation",
            ["--config", "/tmp/test.yaml"],
            {},
        ),
    )

    await client.post(
        "/api/accuracy/run",
        json={
            "scriptName": "seller_id_validation",
            "testingPeriod": {"fiscalYear": "FY26", "quarter": "Q1"},
            "mode": "batch",
        },
    )

    mock_delay.assert_called_once()


@pytest.mark.anyio
async def test_run_validation_unknown_script(client: AsyncClient) -> None:
    """POST /api/accuracy/run returns 400 for an unregistered script name.

    The service raises ``HTTPException(400)`` when the script name is not in
    the accuracy validation scripts registry.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.post(
        "/api/accuracy/run",
        json={
            "scriptName": "nonexistent_script",
            "testingPeriod": {"fiscalYear": "FY26", "quarter": "Q1"},
            "mode": "batch",
        },
    )

    assert response.status_code == 400


@pytest.mark.anyio
async def test_run_all_validations(client: AsyncClient, mocker) -> None:
    """POST /api/accuracy/run-all creates a pending job for the orchestrator.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.accuracy.run_script.delay")
    mocker.patch(
        "api.routers.accuracy.script_runner_service.build_run_all_argv",
        return_value=(
            "src.accuracy_testing.scripts.run_all_validations",
            ["--config", "/tmp/run_all.yaml"],
            {"validations": []},
        ),
    )

    response = await client.post(
        "/api/accuracy/run-all",
        json={
            "testingPeriod": {"fiscalYear": "FY26", "quarter": "Q1"},
            "validationTypes": ["buyer_id_validation", "seller_id_validation"],
            "inputDirectory": "/data/input",
            "outputDirectory": "/data/output",
            "templateDirectory": "/data/templates",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "run_all_validations"
