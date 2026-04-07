"""
Tests: Configs Endpoints
========================

Integration tests for the ``/api/configs`` REST API using an in-memory
SQLite database via the shared ``client`` fixture.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_configs_empty(client: AsyncClient) -> None:
    """GET /api/configs returns an empty list when no configs exist."""
    response = await client.get("/api/configs")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_create_config(client: AsyncClient) -> None:
    """POST /api/configs creates a config and returns the correct shape."""
    payload = {
        "name": "My Test Config",
        "scriptName": "buyer_id_validation",
        "configData": {"key": "value", "threshold": 0.9},
    }
    response = await client.post("/api/configs", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "My Test Config"
    assert data["scriptName"] == "buyer_id_validation"
    assert data["configData"] == {"key": "value", "threshold": 0.9}
    assert "id" in data
    assert "createdAt" in data
    assert "updatedAt" in data


@pytest.mark.anyio
async def test_create_config_duplicate_name(client: AsyncClient) -> None:
    """POST /api/configs with a duplicate name returns 409 Conflict."""
    payload = {
        "name": "Duplicate Name",
        "scriptName": "buyer_id_validation",
        "configData": {},
    }
    first = await client.post("/api/configs", json=payload)
    assert first.status_code == 200

    second = await client.post("/api/configs", json=payload)
    assert second.status_code == 409


@pytest.mark.anyio
async def test_get_config_by_id(client: AsyncClient) -> None:
    """GET /api/configs/{id} returns the correct config."""
    payload = {
        "name": "Fetch By ID Config",
        "scriptName": "seller_id_validation",
        "configData": {"foo": "bar"},
    }
    created = await client.post("/api/configs", json=payload)
    assert created.status_code == 200
    config_id = created.json()["id"]

    response = await client.get(f"/api/configs/{config_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == config_id
    assert data["name"] == "Fetch By ID Config"
    assert data["scriptName"] == "seller_id_validation"
    assert data["configData"] == {"foo": "bar"}


@pytest.mark.anyio
async def test_get_config_not_found(client: AsyncClient) -> None:
    """GET /api/configs/{id} returns 404 for an unknown UUID."""
    response = await client.get("/api/configs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_config(client: AsyncClient) -> None:
    """PUT /api/configs/{id} updates the name and returns the updated record."""
    payload = {
        "name": "Original Name",
        "scriptName": "buyer_id_validation",
        "configData": {"mode": "strict"},
    }
    created = await client.post("/api/configs", json=payload)
    assert created.status_code == 200
    config_id = created.json()["id"]

    update_payload = {"name": "Updated Name"}
    response = await client.put(f"/api/configs/{config_id}", json=update_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == config_id
    assert data["name"] == "Updated Name"
    # Config data should be unchanged.
    assert data["configData"] == {"mode": "strict"}


@pytest.mark.anyio
async def test_delete_config(client: AsyncClient) -> None:
    """DELETE /api/configs/{id} removes the config and returns {"deleted": true}."""
    payload = {
        "name": "Config To Delete",
        "scriptName": "buyer_id_validation",
        "configData": {},
    }
    created = await client.post("/api/configs", json=payload)
    assert created.status_code == 200
    config_id = created.json()["id"]

    delete_response = await client.delete(f"/api/configs/{config_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    # Verify it is gone.
    get_response = await client.get(f"/api/configs/{config_id}")
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_list_configs_filter(client: AsyncClient) -> None:
    """GET /api/configs?script_name=x returns only configs for that script."""
    await client.post(
        "/api/configs",
        json={"name": "Buyer Config", "scriptName": "buyer_id_validation", "configData": {}},
    )
    await client.post(
        "/api/configs",
        json={"name": "Seller Config", "scriptName": "seller_id_validation", "configData": {}},
    )

    response = await client.get("/api/configs?script_name=buyer_id_validation")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["scriptName"] == "buyer_id_validation"
    assert data[0]["name"] == "Buyer Config"
