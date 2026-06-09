#!/usr/bin/env python3
"""
GLEIF Cache Refresher
=====================

Orchestrates the download, parsing, and caching of GLEIF Golden Copy data.

Two modes of operation:

**Full refresh** (recommended: run daily or on-demand)
    1.  Call the GLEIF API to discover the current Golden Copy publish date.
    2.  Truncate ``lei_records`` and ``lei_isin_map`` tables.
    3.  Download the Golden Copy ZIP, stream-parse the extracted CSV, and
        bulk-upsert records in batches of 5,000.
    4.  Download the ISIN-to-LEI mapping ZIP and populate ``lei_isin_map``.
    5.  Rebuild the FTS5 full-text search index.
    6.  Write a ``SUCCESS`` entry to ``gleif_sync_log`` for each file.

**Delta refresh** (run as needed; default: 24-hour delta)
    1.  Download the 24-hour (or other) delta ZIP and upsert changed records
        without truncating the table.
    2.  Write a ``SUCCESS`` sync log entry.

Delta file type options:  ``8h`` | ``24h`` | ``7d`` | ``31d``.

Usage:
    refresher = GleifRefresher(cache=GleifCacheManager(db_path))
    refresher.run_full_refresh()           # Downloads latest Golden Copy
    refresher.run_delta_refresh("24h")    # 24-hour delta update

Progress Tracking:
    Pass a progress_callback to track multi-phase progress:

    def on_progress(phase: str, percent: int) -> None:
        print(f"{phase}: {percent}%")

    refresher = GleifRefresher(
        cache=cache,
        progress_callback=on_progress
    )
    refresher.run_full_refresh()
"""

import logging
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .cache import GleifCacheManager
from .client import GleifApiClient
from .downloader import GleifDownloader
from .parser import GleifCsvParser, GleifIsinMapParser, LeiRecord

logger = logging.getLogger(__name__)

# Batch size for bulk_upsert — keeps memory bounded while minimising
# the number of individual SQLite transactions
_UPSERT_BATCH_SIZE = 5_000

# Base URL for GLEIF bulk delta downloads
_DELTA_BASE_URL = "https://leidata.gleif.org/api/v2/concatenated-files/lei2-delta"

# GLEIF ISIN-to-LEI mapping download URL
_ISIN_MAP_URL = "https://mapping.gleif.org/api/v2/isin-lei/download"

# Valid delta type strings
_VALID_DELTA_TYPES = {"8h", "24h", "7d", "31d"}


class RefreshResult:
    """Summary of a GLEIF cache refresh operation.

    Attributes:
        files_processed: Number of files successfully downloaded and parsed.
        files_skipped: Number of files skipped (already in sync log).
        files_failed: Number of files that encountered errors.
        total_records: Total LEI records upserted to the cache.
    """

    def __init__(self) -> None:
        self.files_processed: int = 0
        self.files_skipped: int = 0
        self.files_failed: int = 0
        self.total_records: int = 0
        self.critical_failure: bool = False

    def __repr__(self) -> str:
        return (
            f"RefreshResult(processed={self.files_processed}, "
            f"skipped={self.files_skipped}, "
            f"failed={self.files_failed}, "
            f"records={self.total_records}, "
            f"critical_failure={self.critical_failure})"
        )


class GleifRefresher:
    """Orchestrates full and delta refreshes of the GLEIF SQLite cache.

    Args:
        cache: Initialised :class:`~gleif.cache.GleifCacheManager`.
        api_client: :class:`~gleif.client.GleifApiClient` for Golden Copy
            discovery.  Constructed automatically if not provided.
        staging_dir: Directory for temporary ZIP/CSV files.  A system temp
            directory is created per refresh when ``None``.
        progress_callback: Optional callable that receives (phase_name: str,
            phase_percent: int) for multi-phase progress tracking. Called
            whenever phase progress changes.
    """

    def __init__(
        self,
        cache: GleifCacheManager,
        api_client: Optional[GleifApiClient] = None,
        staging_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        download_timeout: int = 300,
    ) -> None:
        self._cache = cache
        self._api_client = api_client or GleifApiClient()
        self._staging_dir = staging_dir
        self._parser = GleifCsvParser()
        self._isin_parser = GleifIsinMapParser()
        self._progress_callback = progress_callback
        self._download_timeout = download_timeout

    def _report_progress(self, phase: str, percent: int) -> None:
        """Report phase progress if a callback is registered."""
        if self._progress_callback:
            try:
                self._progress_callback(phase, max(0, min(100, percent)))
            except Exception as exc:
                logger.warning("Progress callback error: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_from_local_file(
        self,
        zip_path: Path,
        skip_isin_map: bool = False,
    ) -> RefreshResult:
        """Load the LEI cache from a locally downloaded Golden Copy ZIP.

        Use this when the GLEIF CDN blocks programmatic downloads (HTTP 403).
        Download the ZIP manually from
        https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy
        and pass the local path here.

        Args:
            zip_path: Path to a locally saved Golden Copy ZIP file
                (e.g. ``20260323-gleif-goldencopy-lei2-full.csv.zip``).
            skip_isin_map: When ``True``, skip the ISIN-to-LEI mapping step.
                The mapping file is not in the Golden Copy ZIP, so it must be
                downloaded separately — this flag simply omits that step.

        Returns:
            :class:`RefreshResult` summary.

        Raises:
            FileNotFoundError: If ``zip_path`` does not exist.
        """
        if not zip_path.exists():
            raise FileNotFoundError(f"Golden Copy ZIP not found: {zip_path}")

        logger.info("Starting GLEIF load from local file: %s", zip_path.name)
        result = RefreshResult()
        file_name = zip_path.name

        with _staging_context(self._staging_dir) as staging_dir:
            downloader = GleifDownloader(staging_dir, timeout=self._download_timeout)

            if self._cache.is_file_processed(file_name):
                logger.info("Skipping already-processed file: %s", file_name)
                result.files_skipped += 1
            else:
                self._cache.truncate_lei_records()
                self._cache.clear_full_refresh_sync_log()

                gc_result = downloader.extract_local_zip(zip_path)

                if not gc_result.success:
                    logger.error("Failed to extract ZIP: %s", gc_result.error)
                    self._cache.log_sync(
                        sync_type="FULL",
                        file_name=file_name,
                        records_processed=0,
                        status="ERROR",
                    )
                    result.files_failed += 1
                else:
                    total_records = 0
                    try:
                        for csv_path in gc_result.csv_paths:
                            count = self._ingest_golden_copy_csv(csv_path)
                            total_records += count
                            logger.info(
                                "Ingested %s records from %s",
                                f"{count:,}",
                                csv_path.name,
                            )

                        self._cache.rebuild_fts()
                        self._cache.log_sync(
                            sync_type="FULL",
                            file_name=file_name,
                            records_processed=total_records,
                            status="SUCCESS",
                        )
                        result.files_processed += 1
                        result.total_records += total_records
                        logger.info(
                            "Local file load complete -- %s records",
                            f"{total_records:,}",
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Error ingesting local file: %s", exc)
                        self._cache.log_sync(
                            sync_type="FULL",
                            file_name=file_name,
                            records_processed=total_records,
                            status="ERROR",
                        )
                        result.files_failed += 1

        if not skip_isin_map:
            logger.info(
                "ISIN-to-LEI mapping is not included in the Golden Copy ZIP. "
                "Run 'gleif-refresh --type full' (without --golden-copy-file) "
                "to download it, or use --skip-isin-map to suppress this message."
            )

        logger.info("Local file load complete: %r", result)
        return result

    def run_full_refresh(
        self,
        skip_isin_map: bool = False,
    ) -> RefreshResult:
        """Rebuild the LEI cache from the current GLEIF Golden Copy.

        Downloads the latest Golden Copy ZIP, truncates the existing
        ``lei_records`` table, and rebuilds it entirely from the CSV contents.
        Then optionally downloads and loads the ISIN-to-LEI mapping file.

        Args:
            skip_isin_map: When ``True``, skip downloading and loading the
                ISIN-to-LEI mapping file.  Useful if only LEI validation
                (and not ISIN lookups) is required, or if the mapping file
                has already been loaded separately.

        Returns:
            :class:`RefreshResult` summary.
        """
        logger.info("Starting GLEIF full refresh")
        result = RefreshResult()
        self._report_progress("download_gc", 0)

        # Discover the current Golden Copy publish date and download URL
        gc_info = self._api_client.get_latest_golden_copy_info()
        logger.info("Golden Copy publish date: %s", gc_info.publish_date)
        self._report_progress("download_gc", 10)

        # Use a deterministic file name derived from the publish date so that
        # the sync log correctly identifies the file across runs
        publish_slug = gc_info.publish_date.replace(":", "").replace("-", "")[:15]
        golden_copy_file_name = f"gleif-goldencopy-{publish_slug}.zip"

        # Clear the sync log upfront so a forced full refresh always
        # re-downloads and re-ingests, even if today's file was already
        # processed in a previous run.
        self._cache.truncate_lei_records()
        self._cache.clear_full_refresh_sync_log()

        with _staging_context(self._staging_dir) as staging_dir:
            downloader = GleifDownloader(staging_dir, timeout=self._download_timeout)

            # --- Golden Copy ---
            logger.info("Downloading GLEIF Golden Copy from: %s", gc_info.download_url)
            gc_result = downloader.download_and_extract(
                gc_info.download_url, golden_copy_file_name
            )
            self._report_progress("download_gc", 100)
            self._report_progress("ingest_gc", 0)

            if not gc_result.success:
                logger.error("Failed to download Golden Copy: %s", gc_result.error)
                self._cache.log_sync(
                    sync_type="FULL",
                    file_name=golden_copy_file_name,
                    records_processed=0,
                    status="ERROR",
                )
                result.files_failed += 1
                result.critical_failure = True
            else:
                total_records = 0
                try:
                    for idx, csv_path in enumerate(gc_result.csv_paths, 1):
                        count = self._ingest_golden_copy_csv(csv_path)
                        total_records += count
                        # Report ingest progress proportional to number of CSVs
                        ingest_percent = (idx / max(len(gc_result.csv_paths), 1)) * 90
                        self._report_progress("ingest_gc", int(ingest_percent))
                        logger.info(
                            "Golden Copy CSV ingested: %s records from %s",
                            f"{count:,}",
                            csv_path.name,
                        )

                    # Rebuild FTS after bulk load (triggers handle incremental
                    # updates, but a rebuild after full truncate+reload is cleaner)
                    self._cache.rebuild_fts()
                    self._report_progress("ingest_gc", 100)

                    self._cache.log_sync(
                        sync_type="FULL",
                        file_name=golden_copy_file_name,
                        records_processed=total_records,
                        status="SUCCESS",
                    )
                    result.files_processed += 1
                    result.total_records += total_records
                    logger.info(
                        "GLEIF Golden Copy load complete — %s records",
                        f"{total_records:,}",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error ingesting Golden Copy CSV: %s", exc)
                    self._cache.log_sync(
                        sync_type="FULL",
                        file_name=golden_copy_file_name,
                        records_processed=total_records,
                        status="ERROR",
                    )
                    result.files_failed += 1
                    result.critical_failure = True
                finally:
                    downloader.cleanup_file(gc_result)

            # --- ISIN-to-LEI mapping ---
            if not skip_isin_map:
                isin_file_name = f"gleif-isin-lei-map-{publish_slug}.zip"
                self._report_progress("download_isin", 0)

                if self._cache.is_file_processed(isin_file_name):
                    logger.info(
                        "Skipping already-processed ISIN map: %s", isin_file_name
                    )
                    result.files_skipped += 1
                    self._report_progress("download_isin", 100)
                    self._report_progress("ingest_isin", 100)
                else:
                    logger.info("Downloading GLEIF ISIN-to-LEI mapping")
                    self._cache.truncate_isin_map()
                    isin_result = downloader.download_and_extract(
                        _ISIN_MAP_URL, isin_file_name
                    )
                    self._report_progress("download_isin", 100)
                    self._report_progress("ingest_isin", 0)

                    if not isin_result.success:
                        logger.warning(
                            "Failed to download ISIN mapping (non-fatal): %s",
                            isin_result.error,
                        )
                        self._cache.log_sync(
                            sync_type="ISIN_MAP",
                            file_name=isin_file_name,
                            records_processed=0,
                            status="ERROR",
                        )
                        result.files_failed += 1
                    else:
                        total_isin = 0
                        try:
                            for idx, csv_path in enumerate(isin_result.csv_paths, 1):
                                count = self._ingest_isin_map_csv(csv_path)
                                total_isin += count
                                ingest_percent = (
                                    idx / max(len(isin_result.csv_paths), 1)
                                ) * 90
                                self._report_progress(
                                    "ingest_isin", int(ingest_percent)
                                )
                                logger.info(
                                    "ISIN mapping CSV ingested: %s pairs from %s",
                                    f"{count:,}",
                                    csv_path.name,
                                )

                            self._report_progress("ingest_isin", 100)
                            self._cache.log_sync(
                                sync_type="ISIN_MAP",
                                file_name=isin_file_name,
                                records_processed=total_isin,
                                status="SUCCESS",
                            )
                            result.files_processed += 1
                            result.total_records += total_isin
                        except Exception as exc:  # noqa: BLE001
                            logger.error("Error ingesting ISIN mapping CSV: %s", exc)
                            self._cache.log_sync(
                                sync_type="ISIN_MAP",
                                file_name=isin_file_name,
                                records_processed=total_isin,
                                status="ERROR",
                            )
                            result.files_failed += 1
                        finally:
                            downloader.cleanup_file(isin_result)
            else:
                self._report_progress("download_isin", 100)
                self._report_progress("ingest_isin", 100)

        logger.info("GLEIF full refresh complete: %r", result)
        return result

    def run_delta_refresh(self, delta_type: str = "24h") -> RefreshResult:
        """Apply a delta update to the LEI cache.

        Downloads the specified delta file and upserts changed records without
        truncating the existing data.

        Args:
            delta_type: Which delta window to apply — one of ``"8h"``,
                ``"24h"`` (default), ``"7d"``, or ``"31d"``.

        Returns:
            :class:`RefreshResult` summary.

        Raises:
            ValueError: If ``delta_type`` is not one of the valid options.
        """
        if delta_type not in _VALID_DELTA_TYPES:
            raise ValueError(
                f"Invalid delta_type '{delta_type}'. Must be one of: {_VALID_DELTA_TYPES}"
            )

        logger.info("Starting GLEIF delta refresh (type: %s)", delta_type)
        result = RefreshResult()

        # Build the delta download URL and a timestamped file name
        now_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        delta_url = f"{_DELTA_BASE_URL}/{delta_type}"
        delta_file_name = f"gleif-delta-{delta_type}-{now_slug}.zip"

        with _staging_context(self._staging_dir) as staging_dir:
            downloader = GleifDownloader(staging_dir)

            delta_result = downloader.download_and_extract(delta_url, delta_file_name)

            if not delta_result.success:
                logger.error("Failed to download delta file: %s", delta_result.error)
                self._cache.log_sync(
                    sync_type="DELTA",
                    file_name=delta_file_name,
                    records_processed=0,
                    status="ERROR",
                )
                result.files_failed += 1
                result.critical_failure = True
            else:
                total_records = 0
                try:
                    for csv_path in delta_result.csv_paths:
                        count = self._ingest_golden_copy_csv(csv_path)
                        total_records += count
                        logger.info(
                            "Delta CSV ingested: %s records from %s",
                            f"{count:,}",
                            csv_path.name,
                        )

                    self._cache.log_sync(
                        sync_type="DELTA",
                        file_name=delta_file_name,
                        records_processed=total_records,
                        status="SUCCESS",
                    )
                    result.files_processed += 1
                    result.total_records += total_records
                    logger.info(
                        "GLEIF delta refresh complete — %s records updated",
                        f"{total_records:,}",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error ingesting delta CSV: %s", exc)
                    self._cache.log_sync(
                        sync_type="DELTA",
                        file_name=delta_file_name,
                        records_processed=total_records,
                        status="ERROR",
                    )
                    result.files_failed += 1
                    result.critical_failure = True
                finally:
                    downloader.cleanup_file(delta_result)

        logger.info("GLEIF delta refresh complete: %r", result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest_golden_copy_csv(self, csv_path: Path) -> int:
        """Stream-parse a Golden Copy (or delta) CSV and write to cache.

        Records are processed in batches of :data:`_UPSERT_BATCH_SIZE` to
        keep memory usage flat.

        Args:
            csv_path: Path to the extracted CSV file.

        Returns:
            Total number of records upserted.
        """
        count = 0
        batch: List[LeiRecord] = []
        next_progress_log = 100_000

        def flush() -> None:
            nonlocal count, next_progress_log
            if batch:
                self._cache.bulk_upsert(batch)
                count += len(batch)
                while count >= next_progress_log:
                    logger.info(
                        "GLEIF ingest progress: %s records processed from %s",
                        f"{count:,}",
                        csv_path.name,
                    )
                    next_progress_log += 100_000
                batch.clear()

        for record in self._parser.parse(csv_path):
            batch.append(record)
            if len(batch) >= _UPSERT_BATCH_SIZE:
                flush()

        flush()
        return count

    def _ingest_isin_map_csv(self, csv_path: Path) -> int:
        """Stream-parse an ISIN-to-LEI mapping CSV and write to cache.

        Args:
            csv_path: Path to the extracted ISIN mapping CSV file.

        Returns:
            Total number of (lei, isin) pairs upserted.
        """
        count = 0
        batch = []
        next_progress_log = 100_000

        def flush() -> None:
            nonlocal count, next_progress_log
            if batch:
                self._cache.bulk_upsert_isin_map(batch)
                count += len(batch)
                while count >= next_progress_log:
                    logger.info(
                        "GLEIF ISIN map ingest progress: %s pairs processed from %s",
                        f"{count:,}",
                        csv_path.name,
                    )
                    next_progress_log += 100_000
                batch.clear()

        for pair in self._isin_parser.parse(csv_path):
            batch.append(pair)
            if len(batch) >= _UPSERT_BATCH_SIZE:
                flush()

        flush()
        return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _staging_context(provided_dir: Optional[Path]):
    """Context manager that provides a staging directory.

    If ``provided_dir`` is given, it is used directly (and not cleaned up).
    Otherwise, a temporary directory is created and removed on exit.

    Args:
        provided_dir: Caller-supplied staging path, or ``None``.

    Yields:
        :class:`~pathlib.Path` to the staging directory.
    """
    if provided_dir is not None:
        provided_dir.mkdir(parents=True, exist_ok=True)
        yield provided_dir
    else:
        with tempfile.TemporaryDirectory(prefix="gleif_staging_") as tmp:
            yield Path(tmp)
