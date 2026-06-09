#!/usr/bin/env python3
"""
FCA FIRDS Cache Refresher
=========================

Orchestrates the download, parsing, and caching of FCA FIRDS instrument
reference data files.

Two modes of operation:

**Full refresh** (run weekly, Saturday)
    1.  Query the FCA FIRDS file index for all FULINS files on the target date.
    2.  Truncate the ``instruments`` table for a clean rebuild.
    3.  Download each ZIP, stream-parse the extracted XML, and bulk-upsert
        all records to the cache.
    4.  Repeat for FULCAN cancellation files.
    5.  Write a ``SUCCESS`` entry to ``firds_sync_log`` for each file.

**Delta refresh** (run daily)
    1.  Query the file index for all DLTINS files since the last processed
        delta date (or a given ``since_date``).
    2.  For each file (skipping any already in the sync log):
        -   ``NewRcrd`` / ``ModfdRcrd`` → upsert instrument.
        -   ``TermntdRcrd`` → apply termination date.
        -   ``CancRcrd`` → apply cancellation flag.
    3.  Write a ``SUCCESS`` entry to the sync log.

Usage:
    refresher = FirdsRefresher.from_config(config)
    refresher.run_full_refresh()          # Uses most recent Saturday
    refresher.run_delta_refresh()         # Since last processed delta

Progress Tracking:
    Pass a progress_callback to track multi-phase progress:

    def on_progress(phase: str, percent: int) -> None:
        print(f"{phase}: {percent}%")

    refresher = FirdsRefresher(
        cache=cache,
        progress_callback=on_progress
    )
    refresher.run_full_refresh()
"""

import logging
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, List, Optional

from .cache import FirdsCacheManager
from .client import FirdsApiClient, FirdsFileRecord
from .downloader import FirdsDownloader
from .parser import FirdsXmlParser, InstrumentRecord

logger = logging.getLogger(__name__)

# Batch size for bulk_upsert calls – keeps memory usage bounded
_UPSERT_BATCH_SIZE = 5_000

# FULINS file prefixes that are in scope for ingestion:
# C = Collective Investment Vehicles
# D = Debt
# E = Equities
_INSCOPE_FULINS_PREFIXES = ("FULINS_C_", "FULINS_D_", "FULINS_E_")


def _is_inscope_fulins(file_name: str) -> bool:
    """Return True if ``file_name`` belongs to an in-scope FULINS category (C, D, or E)."""
    return any(file_name.startswith(p) for p in _INSCOPE_FULINS_PREFIXES)


class RefreshResult:
    """Summary of a refresh operation.

    Attributes:
        files_processed: Number of files successfully processed.
        files_skipped: Number of files skipped (already in sync log).
        files_failed: Number of files that encountered errors.
        total_records: Total instrument records upserted / updated.
    """

    def __init__(self) -> None:
        self.files_processed: int = 0
        self.files_skipped: int = 0
        self.files_failed: int = 0
        self.total_records: int = 0

    def __repr__(self) -> str:
        return (
            f"RefreshResult(processed={self.files_processed}, "
            f"skipped={self.files_skipped}, "
            f"failed={self.files_failed}, "
            f"records={self.total_records})"
        )


class FirdsRefresher:
    """Orchestrates full and delta refreshes of the FIRDS SQLite cache.

    Args:
        cache: Initialised :class:`~firds.cache.FirdsCacheManager`.
        api_client: :class:`~firds.client.FirdsApiClient` for the file index.
        staging_dir: Directory for temporary ZIP / XML files.  A fresh temp
            directory is created per refresh if ``None`` is provided.
        progress_callback: Optional callable that receives (phase_name: str,
            phase_percent: int) for multi-phase progress tracking. Called
            whenever phase progress changes.
    """

    def __init__(
        self,
        cache: FirdsCacheManager,
        api_client: Optional[FirdsApiClient] = None,
        staging_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        download_timeout: int = 120,
    ) -> None:
        self._cache = cache
        self._api_client = api_client or FirdsApiClient()
        self._staging_dir = staging_dir
        self._parser = FirdsXmlParser()
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

    def run_full_refresh(self, target_date: Optional[date] = None) -> RefreshResult:
        """Rebuild the instruments cache from FULINS and FULCAN files.

        Downloads in-scope FULINS files (C = Collective Investment Vehicles,
        D = Debt, E = Equities) published on ``target_date`` (defaults to the
        most recent Saturday), truncates the instruments table, and rebuilds it
        from scratch.  Cancellations from FULCAN are applied last.

        Args:
            target_date: Publication date of the full files.  Must be a
                Saturday per the FCA FIRDS schedule.  Defaults to the most
                recent Saturday relative to today.

        Returns:
            :class:`RefreshResult` summary.
        """
        if target_date is None:
            target_date = _most_recent_saturday()

        logger.info(
            "Starting FIRDS full refresh", extra={"target_date": str(target_date)}
        )

        result = RefreshResult()
        self._report_progress("fulins", 0)

        with _staging_context(self._staging_dir) as staging_dir:
            downloader = FirdsDownloader(staging_dir, timeout=self._download_timeout)

            # --- FULINS: full instrument reference data ---
            all_full_files = self._api_client.get_latest_full_files(target_date)
            full_files = [f for f in all_full_files if _is_inscope_fulins(f.file_name)]
            excluded = len(all_full_files) - len(full_files)
            if excluded:
                logger.info(
                    "Excluding %d out-of-scope FULINS file(s) (only C, D, E categories ingested)",
                    excluded,
                )
            total_fulins = len(full_files)
            if not full_files:
                logger.warning(
                    "No in-scope FULINS files found for date",
                    extra={"date": str(target_date)},
                )
                self._report_progress("fulins", 100)
            else:
                logger.info("Found %d in-scope FULINS file(s) to process", total_fulins)
                # Truncate instruments and clear FULL/CANCEL sync_log entries so
                # all FULINS files are (re-)processed on every full refresh.
                self._cache.truncate_instruments()
                self._cache.clear_full_refresh_sync_log()

                for idx, file_record in enumerate(full_files, start=1):
                    logger.info(
                        "[%d/%d] Downloading FULINS: %s",
                        idx,
                        total_fulins,
                        file_record.file_name,
                    )
                    file_result = self._process_file(
                        file_record,
                        downloader,
                        sync_type="FULL",
                        result=result,
                    )
                    # Report progress as percentage of FULINS files completed
                    fulins_percent = (idx / total_fulins) * 100
                    self._report_progress("fulins", int(fulins_percent))
                    if file_result is not None:
                        logger.info(
                            "[%d/%d] FULINS complete — %s records",
                            idx,
                            total_fulins,
                            f"{file_result:,}",
                        )

            # --- FULCAN: cancellations ---
            cancel_files = self._api_client.get_cancellation_files(target_date)
            total_cancel = len(cancel_files)
            self._report_progress("fulcan", 0)
            if total_cancel:
                logger.info(
                    "Found %d FULCAN cancellation file(s) to process", total_cancel
                )
            for idx, file_record in enumerate(cancel_files, start=1):
                logger.info(
                    "[%d/%d] Downloading FULCAN: %s",
                    idx,
                    total_cancel,
                    file_record.file_name,
                )
                self._process_file(
                    file_record,
                    downloader,
                    sync_type="CANCEL",
                    result=result,
                )
                # Report progress as percentage of FULCAN files completed
                fulcan_percent = (idx / max(total_cancel, 1)) * 100
                self._report_progress("fulcan", int(fulcan_percent))

            if not total_cancel:
                self._report_progress("fulcan", 100)

        logger.info("FIRDS full refresh complete", extra={"result": repr(result)})
        return result

    def run_delta_refresh(
        self,
        since_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> RefreshResult:
        """No-op: DLTINS delta refreshes are not used in this workflow.

        The cache is maintained by weekly full refreshes of the in-scope FULINS
        (C = Collective Investment Vehicles, D = Debt, E = Equities) and FULCAN
        cancellation files.  DLTINS files are therefore not downloaded or
        ingested.  This method is retained for API compatibility.

        Args:
            since_date: Ignored.
            to_date: Ignored.

        Returns:
            Empty :class:`RefreshResult`.
        """
        logger.warning(
            "run_delta_refresh called but DLTINS processing is disabled. "
            "Use run_full_refresh for weekly cache updates."
        )
        return RefreshResult()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_file(
        self,
        file_record: FirdsFileRecord,
        downloader: FirdsDownloader,
        sync_type: str,
        result: RefreshResult,
    ) -> Optional[int]:
        """Download, parse, and persist a single FIRDS file.

        Skips the file if it is already present in the sync log with a
        SUCCESS status.

        Args:
            file_record: The file index entry to process.
            downloader: Configured :class:`~firds.downloader.FirdsDownloader`.
            sync_type: ``FULL``, ``DELTA``, or ``CANCEL``.
            result: Mutated in-place with progress counters.

        Returns:
            Number of records processed, or ``None`` if skipped / failed.
        """
        if self._cache.is_file_processed(file_record.file_name):
            logger.info(
                "Skipping already-processed file", extra={"file": file_record.file_name}
            )
            result.files_skipped += 1
            return None

        download_result = downloader.download_and_extract(file_record)

        if not download_result.success:
            logger.error(
                "Failed to download FIRDS file",
                extra={"file": file_record.file_name, "error": download_result.error},
            )
            self._cache.log_sync(
                sync_type=sync_type,
                publication_date=file_record.publication_date,
                file_name=file_record.file_name,
                records_processed=0,
                status="ERROR",
            )
            result.files_failed += 1
            return None

        total_records = 0
        try:
            for xml_path in download_result.xml_paths:
                count = self._ingest_xml(xml_path, sync_type)
                total_records += count

            self._cache.log_sync(
                sync_type=sync_type,
                publication_date=file_record.publication_date,
                file_name=file_record.file_name,
                records_processed=total_records,
                status="SUCCESS",
            )
            result.files_processed += 1
            result.total_records += total_records

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error ingesting FIRDS XML",
                extra={"file": file_record.file_name, "error": str(exc)},
            )
            self._cache.log_sync(
                sync_type=sync_type,
                publication_date=file_record.publication_date,
                file_name=file_record.file_name,
                records_processed=total_records,
                status="ERROR",
            )
            result.files_failed += 1
            return None
        finally:
            downloader.cleanup_file(download_result)

        return total_records

    def _ingest_xml(self, xml_path: Path, sync_type: str) -> int:
        """Stream-parse an XML file and write records to the cache.

        For FULL/NEW/MOD records: bulk upsert.
        For TERM records: call ``apply_termination``.
        For CANC records: call ``apply_cancellation``.

        Records are batched into groups of :data:`_UPSERT_BATCH_SIZE` to
        keep memory usage bounded.

        Args:
            xml_path: Path to the extracted XML.
            sync_type: ``FULL``, ``DELTA``, or ``CANCEL`` – affects how
                record types are handled.

        Returns:
            Total number of records ingested.
        """
        count = 0
        batch: List[InstrumentRecord] = []
        next_progress_log = 100_000

        def flush_batch() -> None:
            nonlocal count, next_progress_log
            if batch:
                self._cache.bulk_upsert(batch)
                count += len(batch)
                while count >= next_progress_log:
                    logger.info(
                        "FIRDS ingest progress: %s records processed from %s",
                        f"{count:,}",
                        xml_path.name,
                    )
                    next_progress_log += 100_000
                batch.clear()

        for record in self._parser.parse(xml_path):
            if record.record_type in ("FULL", "NEW", "MOD"):
                batch.append(record)
                if len(batch) >= _UPSERT_BATCH_SIZE:
                    flush_batch()

            elif record.record_type == "TERM":
                flush_batch()  # ensure any pending upserts land first
                if record.termination_date:
                    self._cache.apply_termination(
                        record.isin, record.mic, record.termination_date
                    )
                count += 1

            elif record.record_type == "CANC":
                flush_batch()
                # publication_date used as cancelled_date when field absent
                cancelled_date = record.termination_date or ""
                self._cache.apply_cancellation(record.isin, record.mic, cancelled_date)
                count += 1

        flush_batch()
        logger.debug("Ingested XML", extra={"xml": xml_path.name, "records": count})
        return count


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _most_recent_saturday(reference: Optional[date] = None) -> date:
    """Return the most recent Saturday on or before ``reference``.

    FCA FIRDS full files are published on Saturday mornings.

    Args:
        reference: Reference date (defaults to today).

    Returns:
        A :class:`~datetime.date` that is a Saturday (weekday 5).
    """
    ref = reference or date.today()
    # weekday(): Monday=0 … Saturday=5, Sunday=6
    days_since_saturday = (ref.weekday() - 5) % 7
    return ref - timedelta(days=days_since_saturday)


import os
from contextlib import contextmanager


@contextmanager
def _staging_context(staging_dir: Optional[Path]):
    """Context manager providing a staging directory.

    If ``staging_dir`` is provided it is used as-is (and not cleaned up).
    If ``None``, a temporary directory is created and removed on exit.

    Args:
        staging_dir: Explicit staging path, or ``None`` to use a temp dir.

    Yields:
        :class:`~pathlib.Path` of the staging directory.
    """
    if staging_dir is not None:
        staging_dir.mkdir(parents=True, exist_ok=True)
        yield staging_dir
    else:
        with tempfile.TemporaryDirectory(prefix="firds_staging_") as tmp:
            yield Path(tmp)
