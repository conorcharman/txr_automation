"""Tests for the FCA Register API client (client.py)."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from fca.client import FcaApiError, FcaRegisterClient, _TokenBucket


# ---------------------------------------------------------------------------
# _TokenBucket
# ---------------------------------------------------------------------------


class TestTokenBucket:
    """Unit tests for the token-bucket rate limiter."""

    def test_consume_does_not_block_within_capacity(self) -> None:
        """Rapid calls within capacity should not block."""
        bucket = _TokenBucket(capacity=10, window=10.0)
        start = time.monotonic()
        for _ in range(10):
            bucket.consume()
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, "Should complete immediately within capacity"

    def test_consume_blocks_when_capacity_exceeded(self) -> None:
        """After exhausting capacity the bucket sleeps until the window rolls."""
        bucket = _TokenBucket(capacity=3, window=0.2)
        with patch("fca.client.time.sleep") as mock_sleep:
            # Fill capacity
            for _ in range(3):
                bucket.consume()
            # This 4th call should trigger a sleep
            bucket.consume()
        mock_sleep.assert_called_once()

    def test_tokens_replenish_after_window(self) -> None:
        """Tokens should be available again after the window expires."""
        bucket = _TokenBucket(capacity=2, window=0.05)
        for _ in range(2):
            bucket.consume()
        time.sleep(0.1)  # Wait for window to expire
        # Should not block
        start = time.monotonic()
        bucket.consume()
        assert time.monotonic() - start < 0.5


# ---------------------------------------------------------------------------
# FcaRegisterClient — auth headers
# ---------------------------------------------------------------------------


class TestFcaRegisterClientAuth:
    """Verify authentication headers are set correctly."""

    def test_auth_headers_set(self) -> None:
        """X-AUTH-EMAIL should carry api_key; X-AUTH-KEY should carry api_email."""
        session = MagicMock(spec=requests.Session)
        session.headers = MagicMock()
        FcaRegisterClient(
            api_email="user@example.com",
            api_key="my-api-key",
            session=session,
        )
        session.headers.update.assert_called_once_with(
            {
                "Accept": "application/json",
                "X-AUTH-EMAIL": "my-api-key",
                "X-AUTH-KEY": "user@example.com",
            }
        )


# ---------------------------------------------------------------------------
# FcaRegisterClient — _get / HTTP error handling
# ---------------------------------------------------------------------------


def _make_client(session: MagicMock) -> FcaRegisterClient:
    """Build a client with a pre-configured mock session and patched bucket."""
    client = FcaRegisterClient(
        api_email="user@example.com",
        api_key="test-key",
        session=session,
    )
    # Disable rate-limiting delay in tests
    client._bucket.consume = MagicMock()  # type: ignore[method-assign]
    return client


def _mock_session(status_code: int = 200, json_body: object = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body or {}
    session = MagicMock(spec=requests.Session)
    session.headers = MagicMock()
    session.get.return_value = response
    return session


class TestFcaRegisterClientGet:
    """Tests for _get, search_firms, get_firm, get_firm_permissions."""

    def test_get_returns_json_on_200(self) -> None:
        body = {"Status": "ok", "Data": [{"FRN": "123"}]}
        session = _mock_session(200, body)
        client = _make_client(session)
        result = client._get("https://example.com/test")
        assert result == body

    def test_get_raises_on_non_200(self) -> None:
        session = _mock_session(500)
        client = _make_client(session)
        with pytest.raises(FcaApiError) as exc_info:
            client._get("https://example.com/test")
        assert exc_info.value.status_code == 500

    def test_get_retries_on_429_then_raises(self) -> None:
        response_429 = MagicMock()
        response_429.status_code = 429
        session = MagicMock(spec=requests.Session)
        session.headers = MagicMock()
        session.get.return_value = response_429

        client = _make_client(session)
        with patch("fca.client.time.sleep") as mock_sleep:
            with pytest.raises(FcaApiError) as exc_info:
                client._get("https://example.com/test")

        mock_sleep.assert_called_once_with(60.0)
        assert exc_info.value.status_code == 429
        assert session.get.call_count == 2

    def test_get_retries_on_429_then_succeeds(self) -> None:
        response_429 = MagicMock()
        response_429.status_code = 429
        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.json.return_value = {"Data": []}
        session = MagicMock(spec=requests.Session)
        session.headers = MagicMock()
        session.get.side_effect = [response_429, response_200]

        client = _make_client(session)
        with patch("fca.client.time.sleep"):
            result = client._get("https://example.com/test")
        assert result == {"Data": []}

    def test_search_firms_returns_data_list(self) -> None:
        body = {"Data": [{"Reference Number": "122702", "Name": "Barclays", "Status": "Authorised"}]}
        session = _mock_session(200, body)
        client = _make_client(session)
        results = client.search_firms("Barclays")
        assert len(results) == 1
        assert results[0]["Reference Number"] == "122702"

    def test_search_firms_returns_empty_list_on_no_data(self) -> None:
        session = _mock_session(200, {"Data": []})
        client = _make_client(session)
        assert client.search_firms("unknown") == []

    def test_get_firm_returns_first_data_element(self) -> None:
        body = {"Data": [{"FRN": "122702", "Organisation Name": "Barclays Bank PLC", "Status": "Authorised"}]}
        session = _mock_session(200, body)
        client = _make_client(session)
        result = client.get_firm("122702")
        assert result["FRN"] == "122702"

    def test_get_firm_raises_404_on_empty_data(self) -> None:
        session = _mock_session(200, {"Data": []})
        client = _make_client(session)
        with pytest.raises(FcaApiError) as exc_info:
            client.get_firm("999999")
        assert exc_info.value.status_code == 404

    def test_get_firm_permissions_returns_data_dict(self) -> None:
        body = {"Data": {"Accepting deposits": [{"Customer Type": ["Retail"]}]}}
        session = _mock_session(200, body)
        client = _make_client(session)
        result = client.get_firm_permissions("122702")
        assert "Accepting deposits" in result

    def test_request_exception_raises_fca_api_error(self) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = MagicMock()
        session.get.side_effect = requests.ConnectionError("network error")
        client = _make_client(session)
        with pytest.raises(FcaApiError) as exc_info:
            client._get("https://example.com")
        assert "Request failed" in str(exc_info.value)
