"""
Unit tests for FCA FIRDS SQLite cache (firds.cache).

Tests cover:
- Database initialisation (idempotency)
- Instrument upsert (insert and update semantics)
- Bulk upsert
- apply_termination (existing and missing rows)
- apply_cancellation (existing and missing rows)
- Sync log: is_file_processed, log_sync
- get_by_isin / get_by_isin_mic queries
- truncate_instruments
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from firds.cache import FirdsCacheManager
from firds.parser import InstrumentRecord


@pytest.fixture()
def db(tmp_path) -> FirdsCacheManager:
    """Provide an initialised in-memory-like SQLite cache for each test."""
    cache = FirdsCacheManager(db_path=tmp_path / "test_firds.db")
    cache.initialise_db()
    return cache


def _make_record(
    isin: str = "GB00B3RBWM25",
    mic: str = "XLON",
    record_type: str = "FULL",
    cfi_code: str = "ESXXXX",
    full_name: str = "Test Instrument",
    short_name: str = "TESTINST",
    admission_date: str = "2020-01-15",
    termination_date=None,
    rca: str = "GB",
) -> InstrumentRecord:
    return InstrumentRecord(
        isin=isin,
        mic=mic,
        record_type=record_type,
        cfi_code=cfi_code,
        full_name=full_name,
        short_name=short_name,
        admission_date=admission_date,
        termination_date=termination_date,
        rca=rca,
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInitialiseDb:
    def test_tables_created(self, db):
        """Both tables should exist after initialisation."""
        with db._connect() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "instruments" in tables
        assert "firds_sync_log" in tables

    def test_idempotent(self, db):
        """Calling initialise_db twice must not raise."""
        db.initialise_db()  # second call
        with db._connect() as conn:
            count = conn.execute("SELECT count(*) FROM instruments").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


class TestUpsertInstrument:
    def test_insert_new_record(self, db):
        db.upsert_instrument(_make_record())
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row is not None
        assert row["isin"] == "GB00B3RBWM25"
        assert row["mic"] == "XLON"

    def test_full_name_stored(self, db):
        db.upsert_instrument(_make_record(full_name="My Fund"))
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["full_name"] == "My Fund"

    def test_update_existing_record(self, db):
        db.upsert_instrument(_make_record(full_name="Old Name"))
        db.upsert_instrument(_make_record(full_name="New Name"))
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["full_name"] == "New Name"

    def test_admission_date_stored(self, db):
        db.upsert_instrument(_make_record(admission_date="2021-06-01"))
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["admission_date"] == "2021-06-01"

    def test_termination_date_stored(self, db):
        db.upsert_instrument(_make_record(termination_date="2025-12-31"))
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["termination_date"] == "2025-12-31"

    def test_not_cancelled_by_default(self, db):
        db.upsert_instrument(_make_record())
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["is_cancelled"] == 0

    def test_different_mic_creates_separate_row(self, db):
        db.upsert_instrument(_make_record(mic="XLON"))
        db.upsert_instrument(_make_record(mic="XPAR"))
        rows = db.get_by_isin("GB00B3RBWM25")
        assert len(rows) == 2


class TestBulkUpsert:
    def test_bulk_upsert_count(self, db):
        records = [
            _make_record(isin=f"GB{str(i).zfill(10)}", mic="XLON") for i in range(10)
        ]
        count = db.bulk_upsert(records)
        assert count == 10

    def test_bulk_upsert_rows_present(self, db):
        records = [
            _make_record(isin=f"GB{str(i).zfill(10)}", mic="XLON") for i in range(3)
        ]
        db.bulk_upsert(records)
        for i in range(3):
            assert db.get_by_isin_mic(f"GB{str(i).zfill(10)}", "XLON") is not None


# ---------------------------------------------------------------------------
# apply_termination
# ---------------------------------------------------------------------------


class TestApplyTermination:
    def test_sets_termination_date(self, db):
        db.upsert_instrument(_make_record())
        db.apply_termination("GB00B3RBWM25", "XLON", "2025-06-30")
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["termination_date"] == "2025-06-30"

    def test_creates_row_if_missing(self, db):
        """apply_termination on a non-existent row should insert a minimal record."""
        db.apply_termination("XX0000000000", "XXXX", "2024-01-01")
        row = db.get_by_isin_mic("XX0000000000", "XXXX")
        assert row is not None
        assert row["termination_date"] == "2024-01-01"

    def test_does_not_clear_other_fields(self, db):
        db.upsert_instrument(_make_record(full_name="Keep Me"))
        db.apply_termination("GB00B3RBWM25", "XLON", "2025-06-30")
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["full_name"] == "Keep Me"


# ---------------------------------------------------------------------------
# apply_cancellation
# ---------------------------------------------------------------------------


class TestApplyCancellation:
    def test_sets_is_cancelled(self, db):
        db.upsert_instrument(_make_record())
        db.apply_cancellation("GB00B3RBWM25", "XLON", "2025-01-01")
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["is_cancelled"] == 1

    def test_sets_cancelled_date(self, db):
        db.upsert_instrument(_make_record())
        db.apply_cancellation("GB00B3RBWM25", "XLON", "2025-01-01")
        row = db.get_by_isin_mic("GB00B3RBWM25", "XLON")
        assert row["cancelled_date"] == "2025-01-01"

    def test_creates_row_if_missing(self, db):
        db.apply_cancellation("YY0000000000", "YYYY", "2024-06-01")
        row = db.get_by_isin_mic("YY0000000000", "YYYY")
        assert row is not None
        assert row["is_cancelled"] == 1


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------


class TestSyncLog:
    def test_unprocessed_file_returns_false(self, db):
        assert db.is_file_processed("DLTINS_20260308_01of01.zip") is False

    def test_processed_file_returns_true(self, db):
        db.log_sync(
            sync_type="DELTA",
            publication_date="2026-03-08",
            file_name="DLTINS_20260308_01of01.zip",
            records_processed=100,
        )
        assert db.is_file_processed("DLTINS_20260308_01of01.zip") is True

    def test_error_status_not_counted_as_processed(self, db):
        db.log_sync(
            sync_type="DELTA",
            publication_date="2026-03-08",
            file_name="DLTINS_20260308_02of01.zip",
            records_processed=0,
            status="ERROR",
        )
        assert db.is_file_processed("DLTINS_20260308_02of01.zip") is False

    def test_log_sync_idempotent(self, db):
        """Logging the same file twice (INSERT OR REPLACE) should not raise."""
        for _ in range(2):
            db.log_sync(
                sync_type="FULL",
                publication_date="2026-03-07",
                file_name="FULINS_C_20260307_01of01.zip",
                records_processed=500,
            )
        assert db.is_file_processed("FULINS_C_20260307_01of01.zip") is True


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestQueries:
    def test_get_by_isin_returns_all_venues(self, db):
        db.upsert_instrument(_make_record(mic="XLON"))
        db.upsert_instrument(_make_record(mic="XPAR"))
        rows = db.get_by_isin("GB00B3RBWM25")
        mics = {r["mic"] for r in rows}
        assert mics == {"XLON", "XPAR"}

    def test_get_by_isin_empty_for_unknown(self, db):
        rows = db.get_by_isin("UNKNOWN000000")
        assert rows == []

    def test_get_by_isin_mic_returns_none_for_unknown(self, db):
        assert db.get_by_isin_mic("UNKNOWN000000", "XXXX") is None


# ---------------------------------------------------------------------------
# Truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_truncate_removes_all_rows(self, db):
        db.bulk_upsert([_make_record(), _make_record(mic="XPAR")])
        db.truncate_instruments()
        assert db.get_by_isin("GB00B3RBWM25") == []

    def test_truncate_preserves_sync_log(self, db):
        db.log_sync("FULL", "2026-03-07", "FULINS_C_20260307_01of01.zip", 100)
        db.truncate_instruments()
        assert db.is_file_processed("FULINS_C_20260307_01of01.zip") is True


class TestClearFullRefreshSyncLog:
    def test_clears_full_and_cancel_entries(self, db):
        db.log_sync("FULL", "2026-03-07", "FULINS_C_20260307_01of01.zip", 100)
        db.log_sync("CANCEL", "2026-03-07", "FULCAN_C_20260307_01of01.zip", 10)
        db.log_sync("DELTA", "2026-03-10", "DLTINS_20260310_01of01.zip", 50)
        db.clear_full_refresh_sync_log()
        assert db.is_file_processed("FULINS_C_20260307_01of01.zip") is False
        assert db.is_file_processed("FULCAN_C_20260307_01of01.zip") is False

    def test_delta_entries_are_preserved(self, db):
        db.log_sync("FULL", "2026-03-07", "FULINS_C_20260307_01of01.zip", 100)
        db.log_sync("DELTA", "2026-03-10", "DLTINS_20260310_01of01.zip", 50)
        db.clear_full_refresh_sync_log()
        assert db.is_file_processed("DLTINS_20260310_01of01.zip") is True

    def test_idempotent_on_empty_log(self, db):
        # Should not raise even when there are no FULL/CANCEL entries
        db.clear_full_refresh_sync_log()  # no-op
        db.clear_full_refresh_sync_log()  # second call also fine
