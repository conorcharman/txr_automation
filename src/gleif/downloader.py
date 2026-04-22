#!/usr/bin/env python3
"""
GLEIF File Downloader
=====================

Downloads ZIP archives from GLEIF bulk data endpoints and extracts their CSV
contents to a local staging directory.

Two file types are supported:

- **Golden Copy** (full LEI dataset, ~3.2 million records) — a single ZIP
  containing one CSV, available from ``leidata.gleif.org``.  Published three
  times daily at 00:00, 08:00, and 16:00 UTC.

- **Delta files** — incremental updates published alongside each Golden Copy
  refresh.  Available for 8-hour, 24-hour, 7-day, and 31-day windows.

- **ISIN-to-LEI mapping** — a separate CSV published by GLEIF listing ISIN
  codes and their associated issuing-entity LEI as reported by ANNA.

Usage:
    downloader = GleifDownloader(staging_dir=Path("/tmp/gleif_staging"))
    result = downloader.download_and_extract(url, "lei2_full.zip")
    for csv_path in result.csv_paths:
        # parse csv_path ...
        pass
    downloader.cleanup()
"""

import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# Chunk size for streaming downloads (8 MB)
_DOWNLOAD_CHUNK_BYTES = 8 * 1024 * 1024

# GLEIF ISIN-to-LEI mapping file URL
_ISIN_MAP_URL = (
    "https://mapping.gleif.org/api/v2/isin-lei/download"
)


@dataclass
class GleifDownloadResult:
    """Result of a single GLEIF file download-and-extract operation.

    Attributes:
        url: The source URL that was downloaded.
        file_name: Local file name used for the downloaded ZIP.
        zip_path: Local path of the downloaded ZIP archive.
        csv_paths: Paths of extracted CSV files.
        success: Whether the operation completed without error.
        error: Error message string if ``success`` is ``False``.
    """

    url: str
    file_name: str
    zip_path: Optional[Path] = None
    csv_paths: List[Path] = field(default_factory=list)
    success: bool = True
    error: str = ""


class GleifDownloader:
    """Downloads and extracts GLEIF ZIP archives to a staging directory.

    Args:
        staging_dir: Directory where ZIPs and extracted CSVs are temporarily
            stored.  Created automatically if it does not exist.
        timeout: HTTP request timeout in seconds (default: 300 — Golden Copy
            is a large file and may take several minutes to download).
        session: Optional ``requests.Session`` to use (useful for testing).

    .. note::
        Use :meth:`extract_local_zip` when a ZIP has already been downloaded
        manually (e.g. because the GLEIF CDN blocks programmatic access).
    """

    def __init__(
        self,
        staging_dir: Path,
        timeout: int = 300,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._staging_dir = staging_dir
        self._timeout = timeout
        self._session = session or requests.Session()
        # Use a realistic User-Agent; the GLEIF CDN may reject empty UA strings
        self._session.headers.setdefault(
            "User-Agent",
            "txr-automation/1.0 (GLEIF data download; contact: info@example.com)",
        )
        self._staging_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_local_zip(
        self,
        zip_path: Path,
    ) -> GleifDownloadResult:
        """Extract CSV files from a locally saved GLEIF ZIP archive.

        Use this when the GLEIF CDN returns 403 and the ZIP has been
        downloaded manually from the GLEIF website.

        Args:
            zip_path: Path to the local ``.zip`` file.

        Returns:
            :class:`GleifDownloadResult` with paths of extracted CSV files.
        """
        result = GleifDownloadResult(
            url=str(zip_path),
            file_name=zip_path.name,
            zip_path=zip_path,
        )
        try:
            result.csv_paths = self._extract_csv(zip_path, zip_path.name)
            logger.info(
                "Extracted %d CSV file(s) from local ZIP: %s",
                len(result.csv_paths),
                zip_path.name,
            )
        except Exception as exc:  # noqa: BLE001
            result.success = False
            result.error = f"Failed to extract local ZIP {zip_path.name}: {exc}"
            logger.error(result.error)
        return result

    def download_and_extract(
        self,
        url: str,
        file_name: str,
    ) -> GleifDownloadResult:
        """Download a ZIP from ``url`` and extract its CSV contents.

        Args:
            url: Source URL of the ZIP file (Golden Copy, delta, or mapping).
            file_name: Local file name to use when saving the ZIP (must end
                in ``.zip``).

        Returns:
            :class:`GleifDownloadResult` with paths of extracted CSV files, or
            an error description if the operation failed.
        """
        result = GleifDownloadResult(url=url, file_name=file_name)

        try:
            zip_path = self._download_zip(url, file_name)
            result.zip_path = zip_path
            result.csv_paths = self._extract_csv(zip_path, file_name)
            logger.info(
                "Downloaded and extracted GLEIF file",
                extra={
                    "file_name": file_name,
                    "csv_count": len(result.csv_paths),
                },
            )
        except requests.HTTPError as exc:
            result.success = False
            result.error = (
                f"HTTP {exc.response.status_code if exc.response is not None else '?'} "
                f"downloading {file_name}: {exc}"
            )
            if exc.response is not None and exc.response.status_code == 403:
                result.error += (
                    "\n\nThe GLEIF CDN returned 403 Forbidden.  "
                    "Try supplying --golden-copy-url with a manually obtained download "
                    "link from https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy"
                )
            logger.error(result.error)
        except zipfile.BadZipFile as exc:
            result.success = False
            result.error = f"Bad ZIP archive {file_name}: {exc}"
            logger.error(result.error)
        except Exception as exc:  # noqa: BLE001
            result.success = False
            result.error = f"Unexpected error for {file_name}: {exc}"
            logger.error(result.error)

        return result

    def cleanup(self) -> None:
        """Remove the entire staging directory and its contents.

        Call this after all CSV files have been parsed and their contents
        persisted to the cache.
        """
        if self._staging_dir.exists():
            shutil.rmtree(self._staging_dir)
            logger.info(
                "Cleaned up GLEIF staging directory",
                extra={"path": str(self._staging_dir)},
            )

    def cleanup_file(self, result: GleifDownloadResult) -> None:
        """Remove the ZIP and extracted CSVs for a single download result.

        Args:
            result: The :class:`GleifDownloadResult` whose files to remove.
        """
        if result.zip_path and result.zip_path.exists():
            result.zip_path.unlink()
        for csv_path in result.csv_paths:
            if csv_path.exists():
                csv_path.unlink()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_zip(self, url: str, file_name: str) -> Path:
        """Stream-download a ZIP archive to the staging directory.

        Args:
            url: Source URL.
            file_name: Destination file name within ``staging_dir``.

        Returns:
            :class:`~pathlib.Path` of the saved ZIP.

        Raises:
            requests.HTTPError: On non-2xx response.
        """
        dest = self._staging_dir / file_name
        logger.debug("Downloading GLEIF ZIP", extra={"url": url, "dest": str(dest)})

        with self._session.get(
            url,
            stream=True,
            timeout=self._timeout,
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    fh.write(chunk)

        logger.debug(
            "ZIP download complete",
            extra={"dest": str(dest), "size_bytes": dest.stat().st_size},
        )
        return dest

    def _extract_csv(self, zip_path: Path, archive_name: str) -> List[Path]:
        """Extract CSV files from a ZIP archive into a sub-directory.

        Each ZIP is extracted into its own sub-directory (named after the
        archive without the ``.zip`` suffix) to avoid name collisions.

        Args:
            zip_path: Path of the downloaded ZIP file.
            archive_name: Original file name (used for the sub-directory name).

        Returns:
            List of :class:`~pathlib.Path` objects pointing to extracted CSV files.

        Raises:
            zipfile.BadZipFile: If the archive is not a valid ZIP.
        """
        extract_dir = self._staging_dir / Path(archive_name).stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        csv_paths: List[Path] = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith(".csv"):
                    zf.extract(member, extract_dir)
                    csv_paths.append(extract_dir / member)

        if not csv_paths:
            all_members = ", ".join(zipfile.ZipFile(zip_path).namelist()[:5])
            raise ValueError(
                f"No CSV files found in ZIP archive '{archive_name}'. "
                f"Archive contains: {all_members}. "
                f"Ensure the download URL points to a CSV Golden Copy (not XML)."
            )

        logger.debug(
            "Extracted CSV files from ZIP",
            extra={"archive": archive_name, "csv_files": [str(p) for p in csv_paths]},
        )
        return csv_paths
