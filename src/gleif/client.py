#!/usr/bin/env python3
"""
GLEIF REST API Client
=====================

HTTP client for the GLEIF LEI Records API (``https://api.gleif.org/api/v1/``),
and a Golden Copy discovery helper that locates the current bulk download.

The GLEIF API is a JSON:API-compliant REST service providing LEI search and
lookup functionality.  Requests are rate-limited to 60 per minute per user.
This client enforces a configurable inter-request delay (default: 1.0 second)
to stay within that limit when making multiple sequential calls.

The Golden Copy bulk download contains the full LEI dataset (~3.2 million
records) as a ZIP-compressed CSV, refreshed three times daily by GLEIF.
This client discovers the current Golden Copy publish date from the API
metadata response and returns the corresponding bulk download URL.

Usage:
    client = GleifApiClient()

    # Discover and download the current Golden Copy
    info = client.get_latest_golden_copy_info()
    print(info.publish_date, info.download_url)

    # Single LEI lookup (for ad-hoc checks; prefer cache for bulk operations)
    record = client.get_by_lei("5493001KJTIIGC8Y1R12")

    # Find all LEIs associated with an ISIN
    leis = client.get_leis_by_isin("DE000ST8MPP0")

    # BIC-to-LEI lookup (BIC data is not included in the Golden Copy CSV)
    lei = client.get_lei_by_bic("ALETITMMXXX")
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_BASE_URL = "https://api.gleif.org/api/v1"

# GLEIF publishes endpoint — returns the latest Golden Copy file metadata,
# including the direct CSV download URL, without requiring authentication.
# Discovered from the GLEIF golden-copy download page JS bundle.
_GLEIF_PUBLISHES_URL = "https://leidata-preview.gleif.org/api/v2/golden-copies/publishes"

# Fallback: if the publishes API is unavailable, this URL is used instead.
# NOTE: as of 2026-03 leidata.gleif.org/api/v2 returns HTTP 403; the publishes
# endpoint on leidata-preview.gleif.org is the correct auto-discovery path.
_DEFAULT_GOLDEN_COPY_URL = "https://leidata-preview.gleif.org/api/v2/golden-copies/publishes"

# GLEIF enforces 60 requests/minute per user.  1.0 second delay keeps usage
# within the limit when making sequential lookup calls.
_REQUEST_DELAY_SECONDS = 1.0

# Maximum results per API page (GLEIF supports up to 500)
_PAGE_SIZE = 500


@dataclass
class GoldenCopyInfo:
    """Metadata for the current GLEIF Golden Copy bulk file.

    Attributes:
        publish_date: ISO 8601 datetime string of the Golden Copy publication
            (e.g. ``"2026-03-23T00:00:00Z"``).
        download_url: URL from which the bulk CSV ZIP can be streamed.
    """

    publish_date: str
    download_url: str


class GleifApiClient:
    """Client for the GLEIF LEI Records REST API.

    Wraps ``api.gleif.org/api/v1`` and handles request construction, response
    parsing, and rate-limit compliance.  Golden Copy auto-discovery uses the
    ``leidata-preview.gleif.org/api/v2/golden-copies/publishes`` endpoint,
    which returns the current CSV download URL without authentication.

    Args:
        timeout: HTTP request timeout in seconds (default: 30).
        request_delay: Pause between successive API calls to respect the
            60-requests-per-minute rate limit (default: 1.0 second).
        golden_copy_url: Override URL for the Golden Copy bulk CSV download.
            When supplied, auto-discovery is skipped and this URL is used
            directly.  Useful when you have a manually obtained download link.
        session: Optional ``requests.Session`` to use (useful for testing).
    """

    def __init__(
        self,
        timeout: int = 30,
        request_delay: float = _REQUEST_DELAY_SECONDS,
        golden_copy_url: str = _DEFAULT_GOLDEN_COPY_URL,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._timeout = timeout
        self._request_delay = request_delay
        self._golden_copy_url = golden_copy_url
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            }
        )

    # ------------------------------------------------------------------
    # Golden Copy discovery
    # ------------------------------------------------------------------

    def get_latest_golden_copy_info(self) -> GoldenCopyInfo:
        """Discover the current Golden Copy publish date and CSV download URL.

        Queries the GLEIF Golden Copy publishes API
        (``leidata-preview.gleif.org/api/v2/golden-copies/publishes``), which
        returns the latest publication metadata including the direct CSV
        download URL.  No authentication is required.

        Returns:
            :class:`GoldenCopyInfo` with the publish date and download URL.

        Raises:
            requests.HTTPError: On non-2xx response from the API.
        """
        # If the caller has overridden the golden_copy_url, use it directly
        # (skip the discovery call — the URL is already known).
        if self._golden_copy_url != _DEFAULT_GOLDEN_COPY_URL:
            # Still need a publish date — fetch from the standard LEI records API
            data = self._fetch_json(
                f"{_API_BASE_URL}/lei-records",
                params={"page[size]": 1, "page[number]": 1},
            )
            publish_date = (
                data.get("meta", {})
                .get("goldenCopy", {})
                .get("publishDate", "")
            )
            return GoldenCopyInfo(
                publish_date=publish_date,
                download_url=self._golden_copy_url,
            )

        # Auto-discover the latest CSV download URL from the publishes API.
        # The API returns the most recent publication first (page=1).
        data = self._fetch_json(
            _GLEIF_PUBLISHES_URL,
            params={"page": 1},
        )
        publications = data.get("data", [])
        if not publications:
            raise ValueError("GLEIF publishes API returned no data.")

        latest = publications[0]
        publish_date = latest.get("publish_date", "").replace(" ", "T") + "Z"
        csv_url = (
            latest.get("lei2", {})
            .get("full_file", {})
            .get("csv", {})
            .get("url", "")
        )
        if not csv_url:
            raise ValueError(
                "GLEIF publishes API response did not contain a CSV download URL."
            )

        logger.info(
            "GLEIF Golden Copy publish date discovered",
            extra={"publish_date": publish_date, "csv_url": csv_url},
        )
        return GoldenCopyInfo(
            publish_date=publish_date,
            download_url=csv_url,
        )

    # ------------------------------------------------------------------
    # LEI lookups
    # ------------------------------------------------------------------

    def get_by_lei(self, lei: str) -> Optional[Dict[str, Any]]:
        """Fetch a single LEI record from the GLEIF API by LEI code.

        This calls the live API and is intended for ad-hoc lookups only.
        Bulk operation should query the local SQLite cache instead.

        Args:
            lei: 20-character LEI code (case-insensitive; normalised to upper).

        Returns:
            Dict of entity attributes extracted from the JSON:API response, or
            ``None`` if the LEI was not found.

        Raises:
            requests.HTTPError: On unexpected non-404 API errors.
        """
        lei = lei.strip().upper()
        try:
            data = self._fetch_json(f"{_API_BASE_URL}/lei-records/{lei}")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise
        item = data.get("data")
        if not item:
            return None
        return _extract_lei_attributes(item)

    def get_leis_by_isin(self, isin: str) -> List[str]:
        """Return all LEI codes associated with the given ISIN via the GLEIF API.

        Uses the ``filter[isin]`` parameter.  The list may contain multiple
        LEIs when an ISIN has been associated with more than one legal entity.

        Args:
            isin: ISO 6166 ISIN code (e.g. ``"DE000ST8MPP0"``).

        Returns:
            List of 20-character LEI strings; empty list if none found.

        Raises:
            requests.HTTPError: On non-2xx API response.
        """
        isin = isin.strip().upper()
        data = self._fetch_json(
            f"{_API_BASE_URL}/lei-records",
            params={"filter[isin]": isin, "page[size]": _PAGE_SIZE},
        )
        items = data.get("data", [])
        return [item["id"] for item in items if item.get("id")]

    def get_lei_by_bic(self, bic: str) -> Optional[str]:
        """Return the LEI code associated with the given BIC.

        BIC data is not included in the Golden Copy CSV, so this method always
        calls the live GLEIF API.

        Args:
            bic: SWIFT/BIC code (e.g. ``"ALETITMMXXX"``).

        Returns:
            20-character LEI string, or ``None`` if not found.

        Raises:
            requests.HTTPError: On non-2xx API response.
        """
        bic = bic.strip().upper()
        data = self._fetch_json(
            f"{_API_BASE_URL}/lei-records",
            params={"filter[bic]": bic, "page[size]": 1},
        )
        items = data.get("data", [])
        if items:
            return items[0].get("id")
        return None

    def search_by_name(
        self,
        name: str,
        fuzzy: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search the GLEIF API for legal entities matching a name.

        When ``fuzzy=False``, uses ``filter[entity.legalName]`` for exact
        substring matching.  When ``fuzzy=True``, uses the ``fuzzycompletions``
        endpoint for statistical similarity matching.

        Args:
            name: Search term.
            fuzzy: Use fuzzy/statistical matching (default: False).
            limit: Maximum number of results to return (default: 20).

        Returns:
            List of attribute dicts (same shape as :meth:`get_by_lei`).

        Raises:
            requests.HTTPError: On non-2xx API response.
        """
        if fuzzy:
            data = self._fetch_json(
                f"{_API_BASE_URL}/fuzzycompletions",
                params={"field": "entity.legalName", "q": name},
            )
            # fuzzycompletions returns matches, not full records
            items = data.get("data", [])
            return [_extract_fuzzy_attributes(item) for item in items[:limit]]

        data = self._fetch_json(
            f"{_API_BASE_URL}/lei-records",
            params={
                "filter[entity.legalName]": name,
                "page[size]": min(limit, _PAGE_SIZE),
            },
        )
        items = data.get("data", [])
        return [_extract_lei_attributes(item) for item in items]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a GET request and return the parsed JSON response.

        Args:
            url: Full endpoint URL.
            params: Optional query parameters dict.

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            requests.HTTPError: On non-2xx response.
        """
        logger.debug("GLEIF API request", extra={"url": url, "params": params})
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.SSLError as exc:
            raise requests.exceptions.SSLError(
                (
                    f"TLS certificate verification failed for {url}. "
                    "If running behind a corporate proxy, ensure the proxy/root CA is trusted "
                    "and exported via REQUESTS_CA_BUNDLE (or SSL_CERT_FILE). "
                    "For immediate workaround, use --golden-copy-url with a manually obtained link, "
                    "or load a local Golden Copy ZIP via the refresher local-file path."
                )
            ) from exc
        response.raise_for_status()

        time.sleep(self._request_delay)
        return response.json()


# ---------------------------------------------------------------------------
# JSON:API response helpers
# ---------------------------------------------------------------------------


def _extract_lei_attributes(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a flat attribute dict from a JSON:API ``lei-records`` item.

    Args:
        item: A single ``data`` item from the GLEIF JSON:API response.

    Returns:
        Flat dict with normalised attribute keys.
    """
    attrs = item.get("attributes", {})
    entity = attrs.get("entity", {})
    reg = attrs.get("registration", {})

    legal_name_obj = entity.get("legalName") or {}
    other_names = [
        n.get("name", "")
        for n in entity.get("otherNames", [])
        if n.get("name")
    ]
    expiration = entity.get("expiration") or {}

    return {
        "lei": attrs.get("lei", item.get("id", "")),
        "legal_name": legal_name_obj.get("name", "") if isinstance(legal_name_obj, dict) else str(legal_name_obj),
        "other_names": "; ".join(other_names),
        "entity_status": entity.get("status", ""),
        "entity_category": entity.get("category", ""),
        "legal_address_country": (entity.get("legalAddress") or {}).get("country", ""),
        "legal_jurisdiction": entity.get("jurisdiction", ""),
        "registration_status": reg.get("status", ""),
        "initial_registration_date": reg.get("initialRegistrationDate", ""),
        "last_update_date": reg.get("lastUpdateDate", ""),
        "next_renewal_date": reg.get("nextRenewalDate", ""),
        "entity_expiration_date": expiration.get("date"),
        "entity_expiration_reason": expiration.get("reason", "") or "",
        "successor_lei": (entity.get("successorEntity") or {}).get("lei", "") or "",
    }


def _extract_fuzzy_attributes(item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract attributes from a ``fuzzycompletions`` response item.

    Fuzzy completion items have a different structure from full LEI records.
    This adapter returns a dict with the same keys as :func:`_extract_lei_attributes`
    but populated only with the fields present in the completion response.

    Args:
        item: A single item from the ``fuzzycompletions`` data array.

    Returns:
        Partial attribute dict.
    """
    attrs = item.get("attributes", {})
    return {
        "lei": item.get("id", ""),
        "legal_name": attrs.get("value", ""),
        "other_names": "",
        "entity_status": "",
        "entity_category": "",
        "legal_address_country": "",
        "legal_jurisdiction": "",
        "registration_status": "",
        "initial_registration_date": "",
        "last_update_date": "",
        "next_renewal_date": "",
        "entity_expiration_date": None,
        "entity_expiration_reason": "",
        "successor_lei": "",
    }
