#!/usr/bin/env python3
"""
FCA Financial Services Register API Client
==========================================

HTTP client for the UK FCA Financial Services Register REST API
(``https://register.fca.org.uk/services/V0.1``).

Authentication
--------------
All requests require two headers obtained from the FCA Developer Portal
(https://register.fca.org.uk/Developer/s/):

    X-AUTH-EMAIL: <signup email / API username>
    X-AUTH-KEY:   <API key>

Rate Limiting
-------------
The API enforces a limit of 50 requests per 10 seconds per user.
Violations return HTTP 429, after which the user is blocked for 60
seconds.  This client uses a token-bucket to stay within the limit
automatically.  On HTTP 429 it sleeps for 60 seconds and retries once.

Usage:
    from pathlib import Path
    from fca.client import FcaRegisterClient

    client = FcaRegisterClient(api_email="user@example.com", api_key="key")

    # Search for firms by name
    results = client.search_firms("Barclays Bank")

    # Fetch full firm details by FRN
    firm = client.get_firm("122702")

    # Fetch firm permissions
    permissions = client.get_firm_permissions("122702")
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_BASE_URL = "https://register.fca.org.uk/services/V0.1"

# Rate limit: 50 requests per 10 seconds per user.
_RATE_LIMIT_REQUESTS = 50
_RATE_LIMIT_WINDOW_SECONDS = 10.0

# On HTTP 429 the API blocks the user for 60 seconds.
_RETRY_AFTER_SECONDS = 60.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FcaApiError(Exception):
    """Raised when the FCA Register API returns an unexpected response.

    Attributes:
        status_code: HTTP status code of the failed response, or ``None``
            for connection-level errors.
        message: Human-readable description of the error.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"FcaApiError(status={self.status_code}): {self.message}"
        return f"FcaApiError: {self.message}"


# ---------------------------------------------------------------------------
# Token-bucket rate limiter
# ---------------------------------------------------------------------------


class _TokenBucket:
    """Thread-safe token-bucket rate limiter.

    Allows up to ``capacity`` calls within ``window`` seconds.  Callers
    invoke ``consume()`` before each request; it blocks until a token is
    available.

    Args:
        capacity: Maximum number of tokens (requests) per window.
        window: Rolling window duration in seconds.
    """

    def __init__(self, capacity: int, window: float) -> None:
        self._capacity = capacity
        self._window = window
        self._timestamps: List[float] = []
        self._lock = threading.Lock()

    def consume(self) -> None:
        """Block until a request token is available, then consume one."""
        with self._lock:
            now = time.monotonic()
            # Remove timestamps older than the rolling window.
            cutoff = now - self._window
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self._capacity:
                # Must wait until the oldest timestamp in the window expires.
                sleep_for = self._timestamps[0] - cutoff
                if sleep_for > 0:
                    time.sleep(sleep_for)
                # Purge again after sleeping.
                now = time.monotonic()
                cutoff = now - self._window
                self._timestamps = [t for t in self._timestamps if t > cutoff]

            self._timestamps.append(time.monotonic())


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FcaRegisterClient:
    """Client for the FCA Financial Services Register API.

    Wraps the REST API at ``register.fca.org.uk/services/V0.1``, handling
    authentication headers, transparent rate-limit compliance via a
    token-bucket, and HTTP 429 back-off with a single retry.

    Args:
        api_email: FCA Developer Portal signup email used as the API username.
        api_key: FCA Developer Portal API key.
        timeout: HTTP request timeout in seconds (default: 30).
        session: Optional ``requests.Session`` to use.  Useful for testing.
    """

    def __init__(
        self,
        api_email: str,
        api_key: str,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "X-AUTH-EMAIL": api_email,
                "X-AUTH-KEY": api_key,
            }
        )
        self._bucket = _TokenBucket(
            capacity=_RATE_LIMIT_REQUESTS,
            window=_RATE_LIMIT_WINDOW_SECONDS,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, url: str, params: Optional[Dict[str, str]] = None) -> Any:
        """Execute a rate-limited GET request.

        On HTTP 429 sleeps for ``_RETRY_AFTER_SECONDS`` and retries once.
        Raises :class:`FcaApiError` on any non-200 final response.

        Args:
            url: Full URL to request.
            params: Optional query parameters.

        Returns:
            Parsed JSON response body.

        Raises:
            FcaApiError: If the API returns a non-200 status after retries.
        """
        for attempt in (1, 2):
            self._bucket.consume()
            try:
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                raise FcaApiError(f"Request failed: {exc}") from exc

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                if attempt == 1:
                    logger.warning(
                        "FCA API rate limit hit (HTTP 429). "
                        "Sleeping %s seconds before retry.",
                        _RETRY_AFTER_SECONDS,
                    )
                    time.sleep(_RETRY_AFTER_SECONDS)
                    continue
                raise FcaApiError(
                    "HTTP 429 rate limit exceeded after retry.",
                    status_code=429,
                )

            raise FcaApiError(
                f"Unexpected HTTP {response.status_code} from FCA API: {url}",
                status_code=response.status_code,
            )

        # Unreachable — satisfies type checker.
        raise FcaApiError("Request failed after retry.")  # pragma: no cover

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_firms(self, name: str) -> List[Dict[str, Any]]:
        """Search for firms by name.

        Calls ``GET /V0.1/Search?q=<name>&type=firm``.  Returns all matching
        results from the ``Data`` key of the response.

        Args:
            name: Firm name or name substring to search for.

        Returns:
            List of result dicts, each containing at minimum ``Reference
            Number``, ``Name``, ``Status``, and ``URL`` keys.  Empty list
            when no firms match.

        Raises:
            FcaApiError: If the API returns a non-200 response.

        Example:
            >>> client.search_firms("Barclays Bank")
            [{'Reference Number': '122702', 'Name': 'Barclays Bank Plc', ...}]
        """
        url = f"{_API_BASE_URL}/Search"
        params = {"q": name, "type": "firm"}
        logger.debug("FCA search: q=%r", name)
        body = self._get(url, params=params)
        return body.get("Data", []) or []

    def get_firm(self, frn: str) -> Dict[str, Any]:
        """Retrieve full details for a firm by FRN.

        Calls ``GET /V0.1/Firm/{FRN}``.

        Args:
            frn: Firm Reference Number (FRN) as a string.

        Returns:
            Dict of firm details from the first element of the ``Data`` list.
            Keys include ``FRN``, ``Organisation Name``, ``Status``,
            ``Business Type``, ``Companies House Number``, and
            ``Status Effective Date``.

        Raises:
            FcaApiError: If the FRN is not found or the API returns an error.

        Example:
            >>> client.get_firm("122702")
            {'FRN': '122702', 'Organisation Name': 'Barclays Bank Plc', ...}
        """
        url = f"{_API_BASE_URL}/Firm/{frn}"
        logger.debug("FCA get_firm: frn=%r", frn)
        body = self._get(url)
        data = body.get("Data", [])
        if not data:
            raise FcaApiError(
                f"No firm found for FRN {frn!r}.",
                status_code=404,
            )
        return data[0]

    def get_firm_permissions(self, frn: str) -> Dict[str, Any]:
        """Retrieve regulated activity permissions for a firm.

        Calls ``GET /V0.1/Firm/{FRN}/Permissions``.

        Args:
            frn: Firm Reference Number (FRN) as a string.

        Returns:
            Dict mapping activity name to a list of permission detail dicts.
            Each detail dict may contain ``Customer Type``, ``Investment Type``,
            and ``Limitation`` keys.

        Raises:
            FcaApiError: If the API returns an error.

        Example:
            >>> client.get_firm_permissions("122702")
            {'Accepting Deposits': [{'Customer Type': ['All']}, ...], ...}
        """
        url = f"{_API_BASE_URL}/Firm/{frn}/Permissions"
        logger.debug("FCA get_firm_permissions: frn=%r", frn)
        body = self._get(url)
        return body.get("Data", {}) or {}
