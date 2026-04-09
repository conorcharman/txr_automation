"""
Health Endpoint Tests
=====================

Tests for ``GET /api/health``.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_ok(client: AsyncClient) -> None:
    """Health endpoint returns HTTP 200 with status ``ok`` and a version string.

    Args:
        client: Async HTTP client fixture from conftest.
    """
    response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
