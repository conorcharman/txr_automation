#!/usr/bin/env python3
"""
FCA FIRDS SQLite Cache
======================

Manages a local SQLite database that stores instrument reference data
downloaded from FCA FIRDS, enabling fast point-in-time reportability lookups
without repeated calls to the FIRDS API.

Schema
------
``instruments`` table
    Primary key: ``(isin, mic)``.  One row per ISIN/trading-venue combination.
    Stores admission date, termination date, cancellation status, and
    other reference data fields copied from BTS 23.

``firds_sync_log`` table
    Records every FIRDS file that has been successfully processed.  Used to
    ensure idempotency – the refresher will skip any file whose ``file_name``
    already appears here with a ``SUCCESS`` status.

Usage:
    db = FirdsCacheManager(db_path=Path("data/firds_cache.db"))
    db.initialise_db()
    db.upsert_instrument(record)
    db.apply_termination("GB00B3RBWM25", "XLON", "2025-12-01")
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from .parser import InstrumentRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

_CREATE_INSTRUMENTS = """
CREATE TABLE IF NOT EXISTS instruments (
    isin              TEXT NOT NULL,
    mic               TEXT NOT NULL,
    cfi_code          TEXT NOT NULL DEFAULT '',
    full_name         TEXT NOT NULL DEFAULT '',
    short_name        TEXT NOT NULL DEFAULT '',
    admission_date    TEXT,
    termination_date  TEXT,
    is_cancelled      INTEGER NOT NULL DEFAULT 0,
    cancelled_date    TEXT,
    rca               TEXT NOT NULL DEFAULT '',
    last_updated      TEXT NOT NULL,
    PRIMARY KEY (isin, mic)
);
"""

_CREATE_SYNC_LOG = """
CREATE TABLE IF NOT EXISTS firds_sync_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type          TEXT NOT NULL,
    publication_date   TEXT NOT NULL,
    file_name          TEXT NOT NULL UNIQUE,
    synced_at          TEXT NOT NULL,
    records_processed  INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'SUCCESS'
);
"""

_CREATE_INDEX_ISIN = """
CREATE INDEX IF NOT EXISTS idx_instruments_isin ON instruments (isin);
"""

# ---------------------------------------------------------------------------
# DML constants
# ---------------------------------------------------------------------------

_UPSERT_INSTRUMENT = """
INSERT INTO instruments
    (isin, mic, cfi_code, full_name, short_name,
     admission_date, termination_date, is_cancelled,
     cancelled_date, rca, last_updated)
VALUES
    (:isin, :mic, :cfi_code, :full_name, :short_name,
     :admission_date, :termination_date, :is_cancelled,
     :cancelled_date, :rca, :last_updated)
ON CONFLICT(isin, mic) DO UPDATE SET
    cfi_code         = excluded.cfi_code,
    full_name        = excluded.full_name,
    short_name       = excluded.short_name,
    admission_date   = excluded.admission_date,
    termination_date = excluded.termination_date,
    is_cancelled     = excluded.is_cancelled,
    cancelled_date   = excluded.cancelled_date,
    rca              = excluded.rca,
    last_updated     = excluded.last_updated;
"""

_APPLY_TERMINATION = """
UPDATE instruments
SET    termination_date = :termination_date,
       last_updated     = :last_updated
WHERE  isin = :isin
  AND  mic  = :mic;
"""

_APPLY_CANCELLATION = """
UPDATE instruments
SET    is_cancelled  = 1,
       cancelled_date = :cancelled_date,
       last_updated   = :last_updated
WHERE  isin = :isin
  AND  mic  = :mic;
"""

_UPSERT_CANCELLED_INSTRUMENT = """
INSERT INTO instruments
    (isin, mic, cfi_code, full_name, short_name,
     admission_date, termination_date, is_cancelled,
     cancelled_date, rca, last_updated)
VALUES
    (:isin, :mic, '', '', '', NULL, NULL, 1,
     :cancelled_date, '', :last_updated)
ON CONFLICT(isin, mic) DO UPDATE SET
    is_cancelled   = 1,
    cancelled_date = excluded.cancelled_date,
    last_updated   = excluded.last_updated;
"""

_INSERT_SYNC_LOG = """
INSERT OR REPLACE INTO firds_sync_log
    (sync_type, publication_date, file_name, synced_at,
     records_processed, status)
VALUES
    (:sync_type, :publication_date, :file_name, :synced_at,
     :records_processed, :status);
"""

_SELECT_SYNC_LOG = """
SELECT COUNT(*) FROM firds_sync_log
WHERE  file_name = :file_name
  AND  status    = 'SUCCESS';
"""

_SELECT_ALL_BY_ISIN = """
SELECT isin, mic, cfi_code, full_name, short_name,
       admission_date, termination_date, is_cancelled,
       cancelled_date, rca
FROM   instruments
WHERE  isin = :isin;
"""

_SELECT_BY_ISIN_MIC = """
SELECT isin, mic, cfi_code, full_name, short_name,
       admission_date, termination_date, is_cancelled,
       cancelled_date, rca
FROM   instruments
WHERE  isin = :isin
  AND  mic  = :mic;
"""

_TRUNCATE_INSTRUMENTS = "DELETE FROM instruments;"


class FirdsCacheManager:
    """Manages the local FIRDS SQLite cache.

    Args:
        db_path: Path to the SQLite database file.  Created (along with any
            parent directories) if it does not exist.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def initialise_db(self) -> None:
        """Create tables and indexes if they do not already exist.

        Safe to call on every startup – all DDL statements use
        ``CREATE ... IF NOT EXISTS``.
        """
        with self._connect() as conn:
            conn.execute(_CREATE_INSTRUMENTS)
            conn.execute(_CREATE_SYNC_LOG)
            conn.execute(_CREATE_INDEX_ISIN)
            conn.commit()
        logger.info("FIRDS cache database initialised", extra={"db_path": str(self._db_path)})

    def truncate_instruments(self) -> None:
        """Delete all rows from the ``instruments`` table.

        Used at the start of a full refresh to ensure a clean slate.
        Call :meth:`clear_full_refresh_sync_log` alongside this method when
        you want previously-processed FULINS files to be re-ingested.
        """
        with self._connect() as conn:
            conn.execute(_TRUNCATE_INSTRUMENTS)
            conn.commit()
        logger.info("Truncated instruments table for full refresh")

    def clear_full_refresh_sync_log(self) -> None:
        """Remove all FULL and CANCEL entries from the sync log.

        Call this before a full refresh so that previously-processed FULINS
        and FULCAN files are re-ingested rather than skipped.  Delta (DLTINS)
        entries are left intact so incremental history is preserved.
        """
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM firds_sync_log WHERE sync_type IN ('FULL', 'CANCEL');"
            )
            conn.commit()
        logger.info("Cleared FULL/CANCEL entries from sync log")

    # ------------------------------------------------------------------
    # Instrument writes
    # ------------------------------------------------------------------

    def upsert_instrument(self, record: InstrumentRecord) -> None:
        """Insert or update a single instrument record.

        Args:
            record: :class:`~firds.parser.InstrumentRecord` parsed from XML.
        """
        now = _utc_now()
        params = {
            "isin": record.isin,
            "mic": record.mic,
            "cfi_code": record.cfi_code,
            "full_name": record.full_name,
            "short_name": record.short_name,
            "admission_date": record.admission_date or None,
            "termination_date": record.termination_date,
            "is_cancelled": 0,
            "cancelled_date": None,
            "rca": record.rca,
            "last_updated": now,
        }
        with self._connect() as conn:
            conn.execute(_UPSERT_INSTRUMENT, params)
            conn.commit()

    def bulk_upsert(self, records: List[InstrumentRecord]) -> int:
        """Insert or update many instrument records in a single transaction.

        Args:
            records: Iterable of :class:`~firds.parser.InstrumentRecord`.

        Returns:
            Number of records processed.
        """
        now = _utc_now()
        params_list = [
            {
                "isin": r.isin,
                "mic": r.mic,
                "cfi_code": r.cfi_code,
                "full_name": r.full_name,
                "short_name": r.short_name,
                "admission_date": r.admission_date or None,
                "termination_date": r.termination_date,
                "is_cancelled": 0,
                "cancelled_date": None,
                "rca": r.rca,
                "last_updated": now,
            }
            for r in records
        ]
        with self._connect() as conn:
            conn.executemany(_UPSERT_INSTRUMENT, params_list)
            conn.commit()
        return len(params_list)

    def apply_termination(self, isin: str, mic: str, termination_date: str) -> None:
        """Set the termination date for an (ISIN, MIC) pair.

        If no matching row exists a new minimal row is inserted so that the
        termination is still recorded (handles the edge case in the spec where
        a termination is reported for the first time after the instrument was
        terminated).

        Args:
            isin: Instrument ISIN.
            mic: Trading venue MIC.
            termination_date: ``YYYY-MM-DD`` termination date.
        """
        now = _utc_now()
        with self._connect() as conn:
            result = conn.execute(
                _APPLY_TERMINATION,
                {"isin": isin, "mic": mic, "termination_date": termination_date, "last_updated": now},
            )
            if result.rowcount == 0:
                # Row did not exist – insert a minimal record
                conn.execute(
                    _UPSERT_INSTRUMENT,
                    {
                        "isin": isin,
                        "mic": mic,
                        "cfi_code": "",
                        "full_name": "",
                        "short_name": "",
                        "admission_date": None,
                        "termination_date": termination_date,
                        "is_cancelled": 0,
                        "cancelled_date": None,
                        "rca": "",
                        "last_updated": now,
                    },
                )
            conn.commit()

    def apply_cancellation(self, isin: str, mic: str, cancelled_date: str) -> None:
        """Mark an (ISIN, MIC) pair as cancelled.

        If no matching row exists a minimal cancelled record is inserted.

        Args:
            isin: Instrument ISIN.
            mic: Trading venue MIC.
            cancelled_date: ``YYYY-MM-DD`` date the cancellation was published.
        """
        now = _utc_now()
        with self._connect() as conn:
            result = conn.execute(
                _APPLY_CANCELLATION,
                {"isin": isin, "mic": mic, "cancelled_date": cancelled_date, "last_updated": now},
            )
            if result.rowcount == 0:
                conn.execute(
                    _UPSERT_CANCELLED_INSTRUMENT,
                    {"isin": isin, "mic": mic, "cancelled_date": cancelled_date, "last_updated": now},
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    def is_file_processed(self, file_name: str) -> bool:
        """Check whether a FIRDS file has already been successfully processed.

        Args:
            file_name: Bare file name, e.g. ``DLTINS_20260308_01of01.zip``.

        Returns:
            ``True`` if the file appears in the sync log with ``SUCCESS`` status.
        """
        with self._connect() as conn:
            row = conn.execute(_SELECT_SYNC_LOG, {"file_name": file_name}).fetchone()
            return bool(row and row[0] > 0)

    def log_sync(
        self,
        sync_type: str,
        publication_date: str,
        file_name: str,
        records_processed: int,
        status: str = "SUCCESS",
    ) -> None:
        """Record a processed FIRDS file in the sync log.

        Args:
            sync_type: One of ``FULL``, ``DELTA``, or ``CANCEL``.
            publication_date: Publication date as ``YYYY-MM-DD``.
            file_name: Bare file name (unique key).
            records_processed: Number of records written to the instruments table.
            status: ``SUCCESS`` or ``ERROR``.
        """
        with self._connect() as conn:
            conn.execute(
                _INSERT_SYNC_LOG,
                {
                    "sync_type": sync_type,
                    "publication_date": publication_date,
                    "file_name": file_name,
                    "synced_at": _utc_now(),
                    "records_processed": records_processed,
                    "status": status,
                },
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Instrument reads
    # ------------------------------------------------------------------

    def get_by_isin(self, isin: str) -> List[dict]:
        """Return all rows for a given ISIN across all trading venues.

        Args:
            isin: The ISIN to look up.

        Returns:
            List of row dicts.  Empty if no match.
        """
        with self._connect() as conn:
            rows = conn.execute(_SELECT_ALL_BY_ISIN, {"isin": isin}).fetchall()
            return [_row_to_dict(row) for row in rows]

    def get_by_isin_mic(self, isin: str, mic: str) -> Optional[dict]:
        """Return the single row for an (ISIN, MIC) pair, or ``None``.

        Args:
            isin: The ISIN.
            mic: The trading venue MIC.

        Returns:
            Row dict or ``None`` if not found.
        """
        with self._connect() as conn:
            row = conn.execute(_SELECT_BY_ISIN_MIC, {"isin": isin, "mic": mic}).fetchone()
            return _row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager yielding a SQLite connection.

        Uses ``isolation_level=None`` so that transaction control (``commit``,
        ``rollback``) is explicit in calling code.

        Yields:
            An open :class:`sqlite3.Connection`.
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent read performance
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Returns:
        String of the form ``YYYY-MM-DDTHH:MM:SS+00:00``.
    """
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a :class:`sqlite3.Row` to a plain Python dict.

    Args:
        row: SQLite row object.

    Returns:
        Dictionary keyed by column name.
    """
    return dict(row)
