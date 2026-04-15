#!/usr/bin/env python3
"""
API Client
==========

Synchronous HTTP client for the FastAPI backend.  Uses the ``requests``
library to avoid asyncio / Qt event-loop conflicts.

The base URL defaults to ``http://localhost:8000`` and can be changed
at runtime via QSettings or the API Settings dialog.
"""

from typing import Any, Dict, Optional

import requests

from gui.constants import API_DEFAULT_URL
from gui.utils.settings import settings


class ApiError(Exception):
    """Raised when the API returns a non-2xx status code."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """Synchronous HTTP client for the TXR Automation API."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30) -> None:
        self._base_url = (
            base_url
            or settings.load("api/url", API_DEFAULT_URL)
            or API_DEFAULT_URL
        )
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    @property
    def base_url(self) -> str:
        """Return the current API base URL."""
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        """Update the API base URL and persist to QSettings."""
        self._base_url = value.rstrip("/")
        settings.save("api/url", self._base_url)

    @property
    def ws_url(self) -> str:
        """Return the WebSocket base URL derived from the HTTP base URL."""
        return self._base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )

    def _url(self, endpoint: str) -> str:
        """Build the full URL for an endpoint."""
        endpoint = endpoint.lstrip("/")
        return f"{self._base_url}/{endpoint}"

    def _handle_response(self, response: requests.Response) -> Any:
        """Raise ``ApiError`` on non-2xx, otherwise return parsed JSON."""
        if response.ok:
            if response.status_code == 204:
                return None
            try:
                return response.json()
            except ValueError:
                return None

        # Try to extract detail message from JSON body
        detail = f"HTTP {response.status_code}"
        try:
            body = response.json()
            if isinstance(body, dict) and "detail" in body:
                detail = body["detail"]
        except (ValueError, KeyError):
            detail = response.text[:200] if response.text else detail

        raise ApiError(detail, status_code=response.status_code)

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a GET request and return the JSON response.

        Args:
            endpoint: API path, e.g. ``"/api/health"``.
            params: Optional query parameters.

        Returns:
            Parsed JSON response body.

        Raises:
            ApiError: On non-2xx status.
            requests.ConnectionError: If the API is unreachable.
        """
        resp = self._session.get(
            self._url(endpoint), params=params, timeout=self._timeout
        )
        return self._handle_response(resp)

    def post(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a POST request with a JSON body.

        Args:
            endpoint: API path.
            payload: JSON-serialisable dict (sent as request body).

        Returns:
            Parsed JSON response body.

        Raises:
            ApiError: On non-2xx status.
        """
        resp = self._session.post(
            self._url(endpoint), json=payload, timeout=self._timeout
        )
        return self._handle_response(resp)

    def put(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a PUT request with a JSON body.

        Args:
            endpoint: API path.
            payload: JSON-serialisable dict.

        Returns:
            Parsed JSON response body.

        Raises:
            ApiError: On non-2xx status.
        """
        resp = self._session.put(
            self._url(endpoint), json=payload, timeout=self._timeout
        )
        return self._handle_response(resp)

    def delete(self, endpoint: str) -> Any:
        """Send a DELETE request.

        Args:
            endpoint: API path.

        Returns:
            Parsed JSON response body (or None for 204).

        Raises:
            ApiError: On non-2xx status.
        """
        resp = self._session.delete(self._url(endpoint), timeout=self._timeout)
        return self._handle_response(resp)

    def health_check(self) -> bool:
        """Check API liveness via ``GET /api/health``.

        Returns:
            ``True`` if the API responded with ``{"status": "ok"}``,
            ``False`` otherwise.
        """
        try:
            data = self.get("/api/health")
            return isinstance(data, dict) and data.get("status") == "ok"
        except (ApiError, requests.ConnectionError, requests.Timeout):
            return False
