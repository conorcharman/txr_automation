"""
Tests for the webapp routes — Phase 1 Foundation.
"""

import json
import pytest

from webapp.app import create_app
from webapp.constants import APP_NAME, APP_VERSION, NAV_SECTIONS


@pytest.fixture()
def app():
    """Create a test Flask application instance."""
    application = create_app("testing")
    yield application


@pytest.fixture()
def client(app):
    """Return a test client for the Flask application."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, client) -> None:
        """Health endpoint should respond with HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client) -> None:
        """Health endpoint should return valid JSON."""
        response = client.get("/health")
        assert response.content_type == "application/json"

    def test_health_payload_status_ok(self, client) -> None:
        """Health response body should contain status 'ok'."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["status"] == "ok"

    def test_health_payload_contains_app_name(self, client) -> None:
        """Health response body should include the application name."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["app"] == APP_NAME

    def test_health_payload_contains_version(self, client) -> None:
        """Health response body should include the application version."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["version"] == APP_VERSION


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    """Tests for the main dashboard page."""

    def test_dashboard_returns_200(self, client) -> None:
        """Dashboard should respond with HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_contains_app_name(self, client) -> None:
        """Dashboard HTML should include the application name."""
        response = client.get("/")
        assert APP_NAME.encode() in response.data

    def test_dashboard_contains_all_section_titles(self, client) -> None:
        """Dashboard should display a card for every navigation section."""
        response = client.get("/")
        for section in NAV_SECTIONS:
            assert section["title"].encode() in response.data


# ---------------------------------------------------------------------------
# Section pages
# ---------------------------------------------------------------------------


class TestSectionPages:
    """Tests for individual section landing pages."""

    def test_known_section_returns_200(self, client) -> None:
        """A valid section identifier should return HTTP 200."""
        response = client.get("/section/accuracy")
        assert response.status_code == 200

    def test_known_section_contains_title(self, client) -> None:
        """Section page should display the section title."""
        response = client.get("/section/accuracy")
        assert b"Accuracy Testing" in response.data

    def test_unknown_section_returns_404(self, client) -> None:
        """An unknown section identifier should return HTTP 404."""
        response = client.get("/section/nonexistent")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "section_id",
        [s["id"] for s in NAV_SECTIONS],
    )
    def test_all_sections_return_200(self, client, section_id: str) -> None:
        """Every section defined in NAV_SECTIONS should return HTTP 200."""
        response = client.get(f"/section/{section_id}")
        assert response.status_code == 200

    def test_section_contains_breadcrumb_link(self, client) -> None:
        """Section pages should contain a breadcrumb link to the dashboard."""
        response = client.get("/section/firds")
        assert b"Dashboard" in response.data


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


class TestAppFactory:
    """Tests for the Flask application factory."""

    def test_testing_config_is_applied(self, app) -> None:
        """create_app('testing') should enable TESTING mode."""
        assert app.config["TESTING"] is True

    def test_debug_disabled_in_production(self) -> None:
        """create_app('production') should disable DEBUG mode."""
        prod_app = create_app("production")
        assert prod_app.config["DEBUG"] is False

    def test_secret_key_is_set(self, app) -> None:
        """Application should have a non-empty SECRET_KEY."""
        assert app.config.get("SECRET_KEY")
