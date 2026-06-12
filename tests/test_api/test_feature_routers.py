"""
Feature Routers Tests
=====================

Tests for the domain-specific feature endpoints:

    GET  /api/replay/scripts
    GET  /api/firds/scripts
    GET  /api/gleif/scripts
    GET  /api/utilities/scripts
    POST /api/replay/phase2
    POST /api/firds/refresh
    POST /api/gleif/refresh
    POST /api/utilities/xlsx-convert
    POST /api/utilities/xsd-parse
"""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Script list endpoints
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_replay_scripts(client: AsyncClient) -> None:
    """GET /api/replay/scripts returns a non-empty list of script name strings.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/replay/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) > 0
    assert "replay_phase2" in scripts
    assert "replay_phase3" in scripts


@pytest.mark.anyio
async def test_list_firds_scripts(client: AsyncClient) -> None:
    """GET /api/firds/scripts returns a non-empty list of script name strings.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/firds/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) > 0
    assert "firds_refresh" in scripts
    assert "firds_check" in scripts


@pytest.mark.anyio
async def test_list_gleif_scripts(client: AsyncClient) -> None:
    """GET /api/gleif/scripts returns a non-empty list of script name strings.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/gleif/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) > 0
    assert "gleif_refresh" in scripts
    assert "gleif_check" in scripts


@pytest.mark.anyio
async def test_list_utilities_scripts(client: AsyncClient) -> None:
    """GET /api/utilities/scripts returns a non-empty list of script name strings.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/utilities/scripts")

    assert response.status_code == 200
    scripts = response.json()
    assert isinstance(scripts, list)
    assert len(scripts) > 0
    assert "xlsx_csv_converter" in scripts
    assert "xml_csv_converter" in scripts


# ---------------------------------------------------------------------------
# Job-dispatching endpoints
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_replay_phase2(client: AsyncClient, mocker) -> None:
    """POST /api/replay/phase2 creates a pending job and dispatches a Celery task.

    The ``run_script.delay`` call and the service method are both patched so no
    real worker or file-system access is required.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.replay.run_script.delay")
    mocker.patch(
        "api.routers.replay.script_runner_service.build_replay_argv",
        return_value=(
            "src.replay.phase_2_processor",
            ["--config", "/tmp/test.yaml"],
            {"paths": {"replay_input": "/data/input"}},
        ),
    )

    response = await client.post(
        "/api/replay/phase2",
        json={
            "inputFile": "/data/replay/phase2",
            "outputFile": "/data/output/phase2",
            "fiscalYear": "FY26",
            "quarter": "Q1",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "replay_phase2"
    assert "id" in data


@pytest.mark.anyio
async def test_replay_phase2_dispatches_task(client: AsyncClient, mocker) -> None:
    """POST /api/replay/phase2 calls ``run_script.delay`` exactly once.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mock_delay = mocker.patch("api.routers.replay.run_script.delay")
    mocker.patch(
        "api.routers.replay.script_runner_service.build_replay_argv",
        return_value=("src.replay.phase_2_processor", [], {}),
    )

    await client.post(
        "/api/replay/phase2",
        json={
            "inputFile": "/in",
            "outputFile": "/out",
            "fiscalYear": "FY26",
            "quarter": "Q1",
        },
    )

    mock_delay.assert_called_once()


@pytest.mark.anyio
async def test_firds_refresh(client: AsyncClient, mocker) -> None:
    """POST /api/firds/refresh creates a pending job and dispatches a Celery task.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.firds.run_script.delay")
    mocker.patch(
        "api.routers.firds.script_runner_service.build_firds_argv",
        return_value=(
            "src.firds.scripts.refresh_cache",
            ["--config", "/tmp/test.yaml"],
            {"refresh": {"type": "full"}},
        ),
    )

    response = await client.post(
        "/api/firds/refresh",
        json={"refreshType": "full"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "firds_refresh"
    assert "id" in data


@pytest.mark.anyio
async def test_gleif_refresh(client: AsyncClient, mocker) -> None:
    """POST /api/gleif/refresh creates a pending job and dispatches a Celery task.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.gleif.run_script.delay")
    mocker.patch(
        "api.routers.gleif.script_runner_service.build_gleif_argv",
        return_value=(
            "src.gleif.scripts.refresh_cache",
            ["--config", "/tmp/test.yaml"],
            {"refresh": {"type": "full"}},
        ),
    )

    response = await client.post(
        "/api/gleif/refresh",
        json={"refreshType": "full"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "gleif_refresh"
    assert "id" in data


@pytest.mark.anyio
async def test_xlsx_convert(client: AsyncClient, mocker) -> None:
    """POST /api/utilities/xlsx-convert creates a pending job and dispatches a Celery task.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.utilities.run_script.delay")
    mocker.patch(
        "api.routers.utilities.script_runner_service.build_utilities_argv",
        return_value=(
            "src.utils.xlsx_csv_converter",
            ["--config", "/tmp/test.yaml"],
            {"conversion": {"mode": "recursive"}},
        ),
    )

    response = await client.post(
        "/api/utilities/xlsx-convert",
        json={"mode": "recursive", "parentDir": "/data/source"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "xlsx_csv_converter"
    assert "id" in data


@pytest.mark.anyio
async def test_xml_convert(client: AsyncClient, mocker) -> None:
    """POST /api/utilities/xml-convert creates a pending job and dispatches a Celery task.

    Args:
        client: Async HTTP client fixture from conftest.
        mocker: pytest-mock fixture.
    """
    mocker.patch("api.routers.utilities.run_script.delay")
    mocker.patch(
        "api.routers.utilities.script_runner_service.build_utilities_argv",
        return_value=(
            "src.utils.xml_csv_converter",
            ["--config", "/tmp/test.yaml"],
            {"paths": {"input_file": "/in.xml", "output_file": "/out.csv"}},
        ),
    )

    response = await client.post(
        "/api/utilities/xml-convert",
        json={"inputFile": "/data/source.xml", "outputFile": "/data/output.csv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["scriptName"] == "xml_csv_converter"
    assert "id" in data


@pytest.mark.anyio
async def test_xsd_parse(client: AsyncClient) -> None:
        """POST /api/utilities/xsd-parse returns flattened schema columns."""
        xsd_content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">
    <xs:element name=\"Root\">
        <xs:complexType>
            <xs:sequence>
                <xs:element name=\"Child\" type=\"xs:string\"/>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>
"""

        response = await client.post(
                "/api/utilities/xsd-parse",
                json={"xsdContent": xsd_content},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["columnCount"] >= 1
        assert isinstance(data["columns"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)
        assert isinstance(data["unsupportedConstructs"], list)
        assert isinstance(data["stats"], dict)


@pytest.mark.anyio
async def test_xsd_parse_invalid_schema_returns_422(client: AsyncClient) -> None:
        """POST /api/utilities/xsd-parse rejects malformed XSD content."""
        response = await client.post(
                "/api/utilities/xsd-parse",
                json={"xsdContent": "not xml"},
        )

        assert response.status_code == 422
