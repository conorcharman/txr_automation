#!/usr/bin/env python3
"""
FCA FIRDS File Downloader
=========================

Downloads ZIP archives from FCA FIRDS download URLs and extracts their XML
contents to a local staging directory.

Per the FCA FIRDS technical specification, the file download links are served
via a separate CDN solution and are **not** subject to the rate limiting that
applies to the file index API endpoint.

Usage:
    downloader = FirdsDownloader(staging_dir=Path("/tmp/firds_staging"))
    xml_paths = downloader.download_and_extract(file_record)
    for xml_path in xml_paths:
        # parse xml_path ...
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

from .client import FirdsFileRecord

logger = logging.getLogger(__name__)

# Chunk size for streaming downloads (8 MB)
_DOWNLOAD_CHUNK_BYTES = 8 * 1024 * 1024


@dataclass
class DownloadResult:
    """Result of a single file download-and-extract operation.

    Attributes:
        file_record: The :class:`~firds.client.FirdsFileRecord` that was downloaded.
        zip_path: Local path of the downloaded ZIP archive.
        xml_paths: Paths of the extracted XML files.
        success: Whether the operation completed without error.
        error: Error message if ``success`` is ``False``.
    """

    file_record: FirdsFileRecord
    zip_path: Optional[Path] = None
    xml_paths: List[Path] = field(default_factory=list)
    success: bool = True
    error: str = ""


class FirdsDownloader:
    """Downloads and extracts FCA FIRDS ZIP archives to a staging directory.

    Args:
        staging_dir: Directory where ZIPs and extracted XMLs are temporarily
            stored.  Created automatically if it does not exist.
        timeout: HTTP request timeout in seconds (default: 120 – files can be
            large).
        session: Optional ``requests.Session`` to use (useful for testing).
    """

    def __init__(
        self,
        staging_dir: Path,
        timeout: int = 120,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._staging_dir = staging_dir
        self._timeout = timeout
        self._session = session or requests.Session()
        self._staging_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def download_and_extract(self, file_record: FirdsFileRecord) -> DownloadResult:
        """Download a single FIRDS ZIP and extract its XML contents.

        Args:
            file_record: The file index record whose ``download_link`` to fetch.

        Returns:
            :class:`DownloadResult` with paths of extracted XML files, or an
            error description if the operation failed.
        """
        result = DownloadResult(file_record=file_record)

        try:
            zip_path = self._download_zip(file_record)
            result.zip_path = zip_path
            result.xml_paths = self._extract_xml(zip_path, file_record.file_name)
            logger.info(
                "Downloaded and extracted FIRDS file",
                extra={
                    "file_name": file_record.file_name,
                    "xml_count": len(result.xml_paths),
                },
            )
        except requests.HTTPError as exc:
            result.success = False
            result.error = f"HTTP error downloading {file_record.file_name}: {exc}"
            logger.error(result.error)
        except zipfile.BadZipFile as exc:
            result.success = False
            result.error = f"Bad ZIP archive {file_record.file_name}: {exc}"
            logger.error(result.error)
        except Exception as exc:  # noqa: BLE001
            result.success = False
            result.error = f"Unexpected error for {file_record.file_name}: {exc}"
            logger.error(result.error)

        return result

    def cleanup(self) -> None:
        """Remove the entire staging directory and its contents.

        Call this after all XML files have been parsed and their contents
        persisted to the cache.
        """
        if self._staging_dir.exists():
            shutil.rmtree(self._staging_dir)
            logger.info(
                "Cleaned up FIRDS staging directory",
                extra={"path": str(self._staging_dir)},
            )

    def cleanup_file(self, result: DownloadResult) -> None:
        """Remove the ZIP and extracted XMLs for a single download result.

        Useful when processing files one-at-a-time to keep disk usage low.

        Args:
            result: The :class:`DownloadResult` whose files should be removed.
        """
        if result.zip_path and result.zip_path.exists():
            result.zip_path.unlink()
        for xml_path in result.xml_paths:
            if xml_path.exists():
                xml_path.unlink()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_zip(self, file_record: FirdsFileRecord) -> Path:
        """Stream-download a ZIP archive and save it to the staging directory.

        Args:
            file_record: Record containing the ``download_link`` URL.

        Returns:
            :class:`~pathlib.Path` of the saved ZIP file.

        Raises:
            requests.HTTPError: On non-2xx HTTP response.
        """
        url = file_record.download_link
        dest = self._staging_dir / file_record.file_name

        logger.debug("Downloading FIRDS ZIP", extra={"url": url, "dest": str(dest)})

        with self._session.get(url, stream=True, timeout=self._timeout) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    fh.write(chunk)

        logger.debug(
            "ZIP download complete",
            extra={"dest": str(dest), "size_bytes": dest.stat().st_size},
        )
        return dest

    def _extract_xml(self, zip_path: Path, archive_name: str) -> List[Path]:
        """Extract XML files from a ZIP archive into a sub-directory of staging.

        Each ZIP is extracted into its own sub-directory (named after the archive
        without the ``.zip`` suffix) to avoid name collisions when multiple ZIPs
        are downloaded for the same publication date.

        Args:
            zip_path: Path of the downloaded ZIP file.
            archive_name: Original file name (used to derive the sub-directory name).

        Returns:
            List of :class:`~pathlib.Path` objects pointing to extracted XML files.

        Raises:
            zipfile.BadZipFile: If the archive is not a valid ZIP.
        """
        extract_dir = self._staging_dir / Path(archive_name).stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        xml_paths: List[Path] = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith(".xml"):
                    zf.extract(member, extract_dir)
                    xml_paths.append(extract_dir / member)

        logger.debug(
            "Extracted XML files from ZIP",
            extra={"archive": archive_name, "xml_files": [str(p) for p in xml_paths]},
        )
        return xml_paths
