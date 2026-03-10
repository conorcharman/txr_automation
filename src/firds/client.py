#!/usr/bin/env python3
"""
FCA FIRDS API Client
====================

HTTP client for the FCA Financial Instruments Reference Data System file index API.

The FCA FIRDS API (`https://api.data.fca.org.uk/fca_data_firds_files`) is an
AWS ElasticSearch index of downloadable bulk files, not a per-instrument endpoint.
This client queries that index to discover download URLs for Full (FULINS),
Delta (DLTINS) and Cancellations (FULCAN) files.

Usage:
    client = FirdsApiClient()
    files = client.get_files(
        file_type="FULINS",
        date_from="2026-03-01",
        date_to="2026-03-08",
    )
    for f in files:
        print(f.download_link)
"""

import time
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Public FCA FIRDS file index endpoint
_API_BASE_URL = "https://api.data.fca.org.uk/fca_data_firds_files"

# Page size for paginated requests – API supports up to at least 100
_PAGE_SIZE = 100

# Politeness delay between paginated index calls (seconds).
# Download links are served from a separate CDN and are not rate-limited.
_INDEX_REQUEST_DELAY_SECONDS = 1.0

# Supported file type values
VALID_FILE_TYPES = {"FULINS", "DLTINS", "FULCAN"}


@dataclass(frozen=True)
class FirdsFileRecord:
    """A single entry from the FCA FIRDS file index.

    Attributes:
        publication_date: ISO date string (YYYY-MM-DD) for which the file was published.
        download_link: Fully qualified URL for downloading the ZIP archive.
        file_type: One of FULINS, DLTINS, or FULCAN.
        file_name: Bare file name, e.g. ``FULINS_C_20260308_01of02.zip``.
        last_refreshed: ISO timestamp when this entry was last added to the index.
    """

    publication_date: str
    download_link: str
    file_type: str
    file_name: str
    last_refreshed: str


class FirdsApiClient:
    """Client for the FCA FIRDS file index API.

    Wraps the ElasticSearch-backed endpoint at ``api.data.fca.org.uk`` and
    handles pagination transparently.

    Args:
        timeout: HTTP request timeout in seconds (default: 30).
        request_delay: Delay between paginated index requests to respect
            rate limiting (default: 1.0 seconds).
        session: Optional ``requests.Session`` to use (useful for testing).
    """

    def __init__(
        self,
        timeout: int = 30,
        request_delay: float = _INDEX_REQUEST_DELAY_SECONDS,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._timeout = timeout
        self._request_delay = request_delay
        self._session = session or requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_files(
        self,
        file_type: str,
        date_from: str,
        date_to: str,
    ) -> List[FirdsFileRecord]:
        """Return all file records matching the given type and date range.

        Args:
            file_type: One of ``FULINS``, ``DLTINS``, or ``FULCAN``.
            date_from: Start of publication date range, ``YYYY-MM-DD``.
            date_to: End of publication date range, ``YYYY-MM-DD``.

        Returns:
            List of :class:`FirdsFileRecord` sorted by file name ascending.

        Raises:
            ValueError: If ``file_type`` is not one of the supported values.
            requests.HTTPError: If the API returns a non-2xx response.
        """
        if file_type not in VALID_FILE_TYPES:
            raise ValueError(
                f"Invalid file_type '{file_type}'. Must be one of: {VALID_FILE_TYPES}"
            )

        results: List[FirdsFileRecord] = []
        for record in self._paginate(file_type, date_from, date_to):
            results.append(record)

        logger.info(
            "FCA FIRDS index query complete",
            extra={
                "file_type": file_type,
                "date_from": date_from,
                "date_to": date_to,
                "records_found": len(results),
            },
        )
        return results

    def get_latest_full_files(self, publication_date: date) -> List[FirdsFileRecord]:
        """Convenience wrapper: fetch all FULINS files for a specific Saturday.

        Args:
            publication_date: The Saturday publication date.

        Returns:
            List of :class:`FirdsFileRecord` for FULINS files on that date.
        """
        date_str = publication_date.isoformat()
        return self.get_files("FULINS", date_str, date_str)

    def get_cancellation_files(self, publication_date: date) -> List[FirdsFileRecord]:
        """Convenience wrapper: fetch all FULCAN files for a specific Saturday.

        Args:
            publication_date: The Saturday publication date.

        Returns:
            List of :class:`FirdsFileRecord` for FULCAN files on that date.
        """
        date_str = publication_date.isoformat()
        return self.get_files("FULCAN", date_str, date_str)

    def get_delta_files(
        self, date_from: date, date_to: date
    ) -> List[FirdsFileRecord]:
        """Convenience wrapper: fetch DLTINS delta files in an inclusive date range.

        Args:
            date_from: Start date (inclusive).
            date_to: End date (inclusive).

        Returns:
            List of :class:`FirdsFileRecord` for DLTINS files in the range.
        """
        return self.get_files(
            "DLTINS",
            date_from.isoformat(),
            date_to.isoformat(),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _paginate(
        self,
        file_type: str,
        date_from: str,
        date_to: str,
    ) -> Iterator[FirdsFileRecord]:
        """Iterate over all pages from the FIRDS file index API.

        Yields:
            :class:`FirdsFileRecord` for each entry returned by the API.
        """
        from_index = 0

        while True:
            payload = self._fetch_page(file_type, date_from, date_to, from_index)
            hits = payload.get("hits", {})
            total = hits.get("total", 0)

            # AWS ElasticSearch 6.x returns total as an integer
            if isinstance(total, dict):
                total = total.get("value", 0)

            records_on_page = hits.get("hits", [])
            if not records_on_page:
                break

            for hit in records_on_page:
                source = hit.get("_source", {})
                record = FirdsFileRecord(
                    publication_date=_normalise_date(
                        source.get("publication_date", "")
                    ),
                    download_link=source.get("download_link", ""),
                    file_type=source.get("file_type", ""),
                    file_name=source.get("file_name", ""),
                    last_refreshed=source.get("last_refreshed", ""),
                )
                yield record

            from_index += len(records_on_page)
            if from_index >= total:
                break

            # Polite pause before next page to avoid triggering rate limiting
            time.sleep(self._request_delay)

    def _fetch_page(
        self,
        file_type: str,
        date_from: str,
        date_to: str,
        from_index: int,
    ) -> dict:
        """Execute a single HTTP request to the FIRDS file index API.

        Args:
            file_type: FULINS, DLTINS, or FULCAN.
            date_from: Start date string (YYYY-MM-DD).
            date_to: End date string (YYYY-MM-DD).
            from_index: Offset for pagination.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            requests.HTTPError: On non-2xx HTTP responses.
        """
        # Build the ElasticSearch query string; dates are included in bracket syntax
        query = (
            f"(file_type:{file_type})"
            f" AND (publication_date:[{date_from} TO {date_to}])"
        )

        params = {
            "q": query,
            "from": from_index,
            "size": _PAGE_SIZE,
            "sort": "file_name:asc",
        }

        logger.debug(
            "Fetching FIRDS file index page",
            extra={"params": params},
        )

        response = self._session.get(
            _API_BASE_URL,
            params=params,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()


def _normalise_date(value: str) -> str:
    """Extract the YYYY-MM-DD portion from an ISO timestamp returned by the API.

    The API returns strings like ``2026-03-08T00:00:00Z``. This strips the
    time component so cache keys and human display are consistent.

    Args:
        value: Raw date/timestamp string from the API.

    Returns:
        ``YYYY-MM-DD`` string, or the original value if parsing fails.
    """
    if not value:
        return value
    # Handles both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SSZ"
    return value[:10]
