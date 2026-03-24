#!/usr/bin/env python3
"""
GLEIF LEI SQLite Cache
======================

Manages a local SQLite database that stores GLEIF LEI records downloaded from
the Golden Copy, enabling fast lookups without repeated calls to the GLEIF API.

Schema
------
``lei_records`` table
    Primary key: ``lei``.  One row per Legal Entity Identifier.  Stores
    registration status, entity name, country, and date fields.

``lei_isin_map`` table
    Primary key: ``(lei, isin)``.  Maps ISIN codes to their issuer LEI.
    Populated from the GLEIF ISIN-to-LEI mapping file published separately
    from the Golden Copy.

``lei_fts`` virtual table (FTS5)
    Full-text search index over ``legal_name`` and ``other_names`` columns of
    ``lei_records``.  Enables fast name-to-LEI reverse lookups using SQLite's
    built-in full-text search engine.

``gleif_sync_log`` table
    Records every GLEIF file that has been successfully processed.  Used to
    ensure idempotency — the refresher skips any file whose ``file_name``
    already appears here with a ``SUCCESS`` status.

Usage:
    db = GleifCacheManager(db_path=Path("data/gleif_cache.db"))
    db.initialise_db()
    db.bulk_upsert(records)
    result = db.get_by_lei("5493001KJTIIGC8Y1R12")
    matches = db.search_by_name("citibank", limit=10)
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from .parser import LeiRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

_CREATE_LEI_RECORDS = """
CREATE TABLE IF NOT EXISTS lei_records (
    lei                       TEXT PRIMARY KEY,
    legal_name                TEXT NOT NULL DEFAULT '',
    other_names               TEXT NOT NULL DEFAULT '',
    registration_status       TEXT NOT NULL DEFAULT '',
    entity_status             TEXT NOT NULL DEFAULT '',
    entity_category           TEXT NOT NULL DEFAULT '',
    legal_address_country     TEXT NOT NULL DEFAULT '',
    legal_jurisdiction        TEXT NOT NULL DEFAULT '',
    initial_registration_date TEXT NOT NULL DEFAULT '',
    last_update_date          TEXT NOT NULL DEFAULT '',
    next_renewal_date         TEXT NOT NULL DEFAULT '',
    entity_expiration_date    TEXT,
    entity_expiration_reason  TEXT NOT NULL DEFAULT '',
    successor_lei             TEXT NOT NULL DEFAULT '',
    last_synced               TEXT NOT NULL
);
"""

_CREATE_LEI_ISIN_MAP = """
CREATE TABLE IF NOT EXISTS lei_isin_map (
    lei  TEXT NOT NULL,
    isin TEXT NOT NULL,
    PRIMARY KEY (lei, isin)
);
"""

_CREATE_INDEX_ISIN_MAP = """
CREATE INDEX IF NOT EXISTS idx_lei_isin_map_isin ON lei_isin_map (isin);
"""

_CREATE_SYNC_LOG = """
CREATE TABLE IF NOT EXISTS gleif_sync_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type         TEXT NOT NULL,
    file_name         TEXT NOT NULL UNIQUE,
    synced_at         TEXT NOT NULL,
    records_processed INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'SUCCESS'
);
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS lei_fts USING fts5(
    legal_name,
    other_names,
    content=lei_records,
    content_rowid=rowid
);
"""

# Triggers to keep FTS table in sync with lei_records
_FTS_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS lei_records_ai AFTER INSERT ON lei_records BEGIN
    INSERT INTO lei_fts(rowid, legal_name, other_names)
    VALUES (new.rowid, new.legal_name, new.other_names);
END;
"""

_FTS_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS lei_records_ad AFTER DELETE ON lei_records BEGIN
    INSERT INTO lei_fts(lei_fts, rowid, legal_name, other_names)
    VALUES ('delete', old.rowid, old.legal_name, old.other_names);
END;
"""

_FTS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS lei_records_au AFTER UPDATE ON lei_records BEGIN
    INSERT INTO lei_fts(lei_fts, rowid, legal_name, other_names)
    VALUES ('delete', old.rowid, old.legal_name, old.other_names);
    INSERT INTO lei_fts(rowid, legal_name, other_names)
    VALUES (new.rowid, new.legal_name, new.other_names);
END;
"""

# ---------------------------------------------------------------------------
# DML constants
# ---------------------------------------------------------------------------

_UPSERT_LEI_RECORD = """
INSERT INTO lei_records (
    lei, legal_name, other_names,
    registration_status, entity_status, entity_category,
    legal_address_country, legal_jurisdiction,
    initial_registration_date, last_update_date,
    next_renewal_date, entity_expiration_date,
    entity_expiration_reason, successor_lei, last_synced
) VALUES (
    :lei, :legal_name, :other_names,
    :registration_status, :entity_status, :entity_category,
    :legal_address_country, :legal_jurisdiction,
    :initial_registration_date, :last_update_date,
    :next_renewal_date, :entity_expiration_date,
    :entity_expiration_reason, :successor_lei, :last_synced
)
ON CONFLICT(lei) DO UPDATE SET
    legal_name                = excluded.legal_name,
    other_names               = excluded.other_names,
    registration_status       = excluded.registration_status,
    entity_status             = excluded.entity_status,
    entity_category           = excluded.entity_category,
    legal_address_country     = excluded.legal_address_country,
    legal_jurisdiction        = excluded.legal_jurisdiction,
    initial_registration_date = excluded.initial_registration_date,
    last_update_date          = excluded.last_update_date,
    next_renewal_date         = excluded.next_renewal_date,
    entity_expiration_date    = excluded.entity_expiration_date,
    entity_expiration_reason  = excluded.entity_expiration_reason,
    successor_lei             = excluded.successor_lei,
    last_synced               = excluded.last_synced;
"""

_UPSERT_ISIN_MAP = """
INSERT OR IGNORE INTO lei_isin_map (lei, isin) VALUES (?, ?);
"""

_INSERT_SYNC_LOG = """
INSERT OR REPLACE INTO gleif_sync_log
    (sync_type, file_name, synced_at, records_processed, status)
VALUES
    (:sync_type, :file_name, :synced_at, :records_processed, :status);
"""

_SELECT_SYNC_LOG = """
SELECT COUNT(*) FROM gleif_sync_log
WHERE  file_name = :file_name
  AND  status    = 'SUCCESS';
"""

_SELECT_BY_LEI = """
SELECT lei, legal_name, other_names,
       registration_status, entity_status, entity_category,
       legal_address_country, legal_jurisdiction,
       initial_registration_date, last_update_date,
       next_renewal_date, entity_expiration_date,
       entity_expiration_reason, successor_lei
FROM   lei_records
WHERE  lei = :lei;
"""

_SELECT_LEIS_FOR_ISIN = """
SELECT lei FROM lei_isin_map WHERE isin = :isin;
"""

_SELECT_ISINS_FOR_LEI = """
SELECT isin FROM lei_isin_map WHERE lei = :lei;
"""

_SELECT_LAST_SYNC = """
SELECT MAX(synced_at) FROM gleif_sync_log WHERE status = 'SUCCESS';
"""

_TRUNCATE_LEI_RECORDS = "DELETE FROM lei_records;"
_TRUNCATE_ISIN_MAP = "DELETE FROM lei_isin_map;"
_CLEAR_FULL_SYNC_LOG = "DELETE FROM gleif_sync_log WHERE sync_type IN ('FULL', 'ISIN_MAP');"


class GleifCacheManager:
    """Manages the local GLEIF LEI SQLite cache.

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
        """Create all tables, indexes, and the FTS5 virtual table.

        Safe to call on every startup — all DDL uses ``CREATE ... IF NOT EXISTS``.
        The FTS synchronisation triggers are also created idempotently.
        """
        with self._connect() as conn:
            conn.execute(_CREATE_LEI_RECORDS)
            conn.execute(_CREATE_LEI_ISIN_MAP)
            conn.execute(_CREATE_INDEX_ISIN_MAP)
            conn.execute(_CREATE_SYNC_LOG)
            conn.execute(_CREATE_FTS)
            conn.execute(_FTS_INSERT_TRIGGER)
            conn.execute(_FTS_DELETE_TRIGGER)
            conn.execute(_FTS_UPDATE_TRIGGER)
            conn.commit()
        logger.info(
            "GLEIF cache database initialised",
            extra={"db_path": str(self._db_path)},
        )

    def truncate_lei_records(self) -> None:
        """Delete all rows from ``lei_records``.

        Also rebuilds the FTS index so it reflects the now-empty table.
        Call :meth:`clear_full_refresh_sync_log` alongside this before
        a full refresh.
        """
        with self._connect() as conn:
            conn.execute(_TRUNCATE_LEI_RECORDS)
            conn.execute("INSERT INTO lei_fts(lei_fts) VALUES('rebuild');")
            conn.commit()
        logger.info("Truncated lei_records and rebuilt FTS index")

    def truncate_isin_map(self) -> None:
        """Delete all rows from ``lei_isin_map``."""
        with self._connect() as conn:
            conn.execute(_TRUNCATE_ISIN_MAP)
            conn.commit()
        logger.info("Truncated lei_isin_map")

    def clear_full_refresh_sync_log(self) -> None:
        """Remove FULL and ISIN_MAP entries from the sync log.

        Call this before a full refresh so that previously-processed Golden
        Copy and ISIN mapping files are re-ingested on the next run.
        """
        with self._connect() as conn:
            conn.execute(_CLEAR_FULL_SYNC_LOG)
            conn.commit()
        logger.info("Cleared FULL/ISIN_MAP entries from gleif_sync_log")

    def rebuild_fts(self) -> None:
        """Rebuild the FTS5 index from the current ``lei_records`` content.

        Use this after a bulk upsert performed outside of the trigger mechanism
        (e.g. when triggers were disabled for performance).  This is called
        automatically by :meth:`truncate_lei_records`.
        """
        with self._connect() as conn:
            conn.execute("INSERT INTO lei_fts(lei_fts) VALUES('rebuild');")
            conn.commit()
        logger.info("Rebuilt FTS5 index on lei_records")

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def bulk_upsert(self, records: List[LeiRecord]) -> int:
        """Insert or update many LEI records in a single transaction.

        Args:
            records: List of :class:`~gleif.parser.LeiRecord` instances.

        Returns:
            Number of records processed.
        """
        now = _utc_now()
        params_list = [
            {
                "lei": r.lei,
                "legal_name": r.legal_name,
                "other_names": r.other_names,
                "registration_status": r.registration_status,
                "entity_status": r.entity_status,
                "entity_category": r.entity_category,
                "legal_address_country": r.legal_address_country,
                "legal_jurisdiction": r.legal_jurisdiction,
                "initial_registration_date": r.initial_registration_date,
                "last_update_date": r.last_update_date,
                "next_renewal_date": r.next_renewal_date,
                "entity_expiration_date": r.entity_expiration_date,
                "entity_expiration_reason": r.entity_expiration_reason,
                "successor_lei": r.successor_lei,
                "last_synced": now,
            }
            for r in records
        ]
        with self._connect() as conn:
            conn.executemany(_UPSERT_LEI_RECORD, params_list)
            conn.commit()
        return len(params_list)

    def bulk_upsert_isin_map(self, mappings: List[Tuple[str, str]]) -> int:
        """Insert ISIN-to-LEI mappings in a single transaction.

        Existing mappings are preserved (``INSERT OR IGNORE``).

        Args:
            mappings: List of ``(lei, isin)`` tuples.

        Returns:
            Number of pairs submitted (not deduplicated).
        """
        with self._connect() as conn:
            conn.executemany(_UPSERT_ISIN_MAP, mappings)
            conn.commit()
        return len(mappings)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_lei(self, lei: str) -> Optional[Dict]:
        """Return the LEI record dict for a given LEI code.

        Args:
            lei: 20-character LEI code.

        Returns:
            Row as a ``dict``, or ``None`` if not found.
        """
        with self._connect() as conn:
            row = conn.execute(_SELECT_BY_LEI, {"lei": lei.strip().upper()}).fetchone()
        return _row_to_dict(row) if row else None

    def search_by_name(self, name: str, limit: int = 20) -> List[Dict]:
        """Search LEI records by legal name or other names using FTS5.

        Uses SQLite FTS5 prefix matching.  Searches ``legal_name`` and
        ``other_names`` in a single query.

        Args:
            name: Name fragment to search for.  Partial words are matched
                when the term ends with ``*``.
            limit: Maximum number of results to return (default: 20).

        Returns:
            List of row dicts ordered by FTS relevance (``rank`` ascending).
        """
        # Sanitise: strip FTS5 special characters that could cause parse errors
        safe_name = name.replace('"', "").replace("*", "").strip()
        if not safe_name:
            return []

        query = f'"{safe_name}"'
        sql = """
            SELECT r.lei, r.legal_name, r.other_names,
                   r.registration_status, r.entity_status, r.entity_category,
                   r.legal_address_country, r.legal_jurisdiction,
                   r.initial_registration_date, r.last_update_date,
                   r.next_renewal_date, r.entity_expiration_date,
                   r.entity_expiration_reason, r.successor_lei
            FROM   lei_fts
            JOIN   lei_records r ON lei_fts.rowid = r.rowid
            WHERE  lei_fts MATCH ?
            ORDER  BY rank
            LIMIT  ?;
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (query, limit)).fetchall()
        return [_row_to_dict(row) for row in rows]

    def get_leis_for_isin(self, isin: str) -> List[str]:
        """Return all LEI codes mapped to the given ISIN.

        Args:
            isin: ISO 6166 ISIN code.

        Returns:
            List of LEI strings; empty list if no mapping is found.
        """
        with self._connect() as conn:
            rows = conn.execute(
                _SELECT_LEIS_FOR_ISIN, {"isin": isin.strip().upper()}
            ).fetchall()
        return [row[0] for row in rows]

    def get_isins_for_lei(self, lei: str) -> List[str]:
        """Return all ISIN codes mapped to the given LEI.

        Args:
            lei: 20-character LEI code.

        Returns:
            List of ISIN strings; empty list if no mapping is found.
        """
        with self._connect() as conn:
            rows = conn.execute(
                _SELECT_ISINS_FOR_LEI, {"lei": lei.strip().upper()}
            ).fetchall()
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    def is_file_processed(self, file_name: str) -> bool:
        """Check whether a file has already been successfully processed.

        Args:
            file_name: Logical file name (used as a unique sync key).

        Returns:
            ``True`` if ``file_name`` is in the sync log with ``SUCCESS`` status.
        """
        with self._connect() as conn:
            row = conn.execute(
                _SELECT_SYNC_LOG, {"file_name": file_name}
            ).fetchone()
        return bool(row and row[0] > 0)

    def log_sync(
        self,
        sync_type: str,
        file_name: str,
        records_processed: int,
        status: str = "SUCCESS",
    ) -> None:
        """Record a processed GLEIF file in the sync log.

        Args:
            sync_type: One of ``FULL``, ``DELTA``, or ``ISIN_MAP``.
            file_name: Logical file name (unique key — duplicate entries
                replace the earlier row via ``INSERT OR REPLACE``).
            records_processed: Number of rows written to the cache.
            status: ``SUCCESS`` or ``ERROR``.
        """
        with self._connect() as conn:
            conn.execute(
                _INSERT_SYNC_LOG,
                {
                    "sync_type": sync_type,
                    "file_name": file_name,
                    "synced_at": _utc_now(),
                    "records_processed": records_processed,
                    "status": status,
                },
            )
            conn.commit()

    def get_last_sync_date(self) -> Optional[str]:
        """Return the ISO timestamp of the most recent successful sync.

        Returns:
            ISO timestamp string, or ``None`` if no successful sync has run.
        """
        with self._connect() as conn:
            row = conn.execute(_SELECT_LAST_SYNC).fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a WAL-mode SQLite connection as a context manager.

        Yields:
            :class:`sqlite3.Connection` with row_factory set to
            :attr:`sqlite3.Row` for dict-like access.
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> Dict:
    """Convert a :class:`sqlite3.Row` to a plain ``dict``.

    Args:
        row: SQLite row from a query with ``row_factory=sqlite3.Row``.

    Returns:
        Plain Python dict.
    """
    return dict(row)
