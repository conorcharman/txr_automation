"""Tests for GLEIF SQLite cache manager (cache.py)."""

from datetime import date
from pathlib import Path

import pytest

from gleif.cache import GleifCacheManager
from gleif.parser import LeiRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    lei: str = "5493001KJTIIGC8Y1R12",
    legal_name: str = "Test Entity Ltd",
    registration_status: str = "ISSUED",
    entity_status: str = "ACTIVE",
    entity_category: str = "GENERAL",
    legal_address_country: str = "GB",
    legal_jurisdiction: str = "GB",
    next_renewal_date: str = "2027-01-01T00:00:00Z",
    entity_expiration_date: str | None = None,
    entity_expiration_reason: str = "",
    successor_lei: str = "",
    other_names: str = "",
) -> LeiRecord:
    return LeiRecord(
        lei=lei,
        legal_name=legal_name,
        registration_status=registration_status,
        entity_status=entity_status,
        entity_category=entity_category,
        legal_address_country=legal_address_country,
        legal_jurisdiction=legal_jurisdiction,
        other_names=other_names,
        initial_registration_date="2020-01-01T00:00:00Z",
        last_update_date="2025-01-01T00:00:00Z",
        next_renewal_date=next_renewal_date,
        entity_expiration_date=entity_expiration_date,
        entity_expiration_reason=entity_expiration_reason,
        successor_lei=successor_lei,
    )


@pytest.fixture
def db(tmp_path: Path) -> GleifCacheManager:
    """Return an initialised, empty GleifCacheManager backed by a temp file."""
    cache = GleifCacheManager(db_path=tmp_path / "gleif_test.db")
    cache.initialise_db()
    return cache


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInitialiseDb:
    def test_idempotent_second_call(self, db: GleifCacheManager) -> None:
        """Calling initialise_db twice must not raise."""
        db.initialise_db()  # second call — should be a no-op

    def test_db_file_created(self, tmp_path: Path) -> None:
        cache = GleifCacheManager(db_path=tmp_path / "sub" / "gleif.db")
        cache.initialise_db()
        assert (tmp_path / "sub" / "gleif.db").exists()


# ---------------------------------------------------------------------------
# bulk_upsert and get_by_lei
# ---------------------------------------------------------------------------


class TestBulkUpsert:
    def test_upsert_single_record(self, db: GleifCacheManager) -> None:
        count = db.bulk_upsert([_make_record()])
        assert count == 1
        row = db.get_by_lei("5493001KJTIIGC8Y1R12")
        assert row is not None
        assert row["legal_name"] == "Test Entity Ltd"
        assert row["registration_status"] == "ISSUED"
        assert row["entity_status"] == "ACTIVE"
        assert row["legal_address_country"] == "GB"

    def test_upsert_updates_existing_record(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(legal_name="Original Name")])
        db.bulk_upsert([_make_record(legal_name="Updated Name")])
        row = db.get_by_lei("5493001KJTIIGC8Y1R12")
        assert row is not None
        assert row["legal_name"] == "Updated Name"

    def test_upsert_multiple_records(self, db: GleifCacheManager) -> None:
        records = [
            _make_record(lei="5493001KJTIIGC8Y1R12", legal_name="Alpha Corp"),
            _make_record(lei="213800WAVVOPS85N2205", legal_name="Beta Ltd"),
        ]
        count = db.bulk_upsert(records)
        assert count == 2
        assert db.get_by_lei("213800WAVVOPS85N2205")["legal_name"] == "Beta Ltd"  # type: ignore[index]

    def test_get_by_lei_not_found(self, db: GleifCacheManager) -> None:
        assert db.get_by_lei("UNKNOWNLEICODE000000") is None

    def test_get_by_lei_case_insensitive(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(lei="5493001KJTIIGC8Y1R12")])
        row = db.get_by_lei("5493001kjtiigc8y1r12")
        assert row is not None

    def test_returns_correct_expiration_date(self, db: GleifCacheManager) -> None:
        record = _make_record(
            entity_expiration_date="2024-06-01T00:00:00Z",
            entity_expiration_reason="DISSOLVED",
        )
        db.bulk_upsert([record])
        row = db.get_by_lei("5493001KJTIIGC8Y1R12")
        assert row is not None
        assert row["entity_expiration_date"] == "2024-06-01T00:00:00Z"
        assert row["entity_expiration_reason"] == "DISSOLVED"


# ---------------------------------------------------------------------------
# Truncate and clear
# ---------------------------------------------------------------------------


class TestTruncate:
    def test_truncate_lei_records_clears_table(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record()])
        db.truncate_lei_records()
        assert db.get_by_lei("5493001KJTIIGC8Y1R12") is None

    def test_truncate_isin_map_clears_table(self, db: GleifCacheManager) -> None:
        db.bulk_upsert_isin_map([("5493001KJTIIGC8Y1R12", "GB00B3RBWM25")])
        db.truncate_isin_map()
        assert db.get_leis_for_isin("GB00B3RBWM25") == []

    def test_clear_full_refresh_sync_log(self, db: GleifCacheManager) -> None:
        db.log_sync("FULL", "gleif-goldencopy.zip", 100, "SUCCESS")
        db.log_sync("DELTA", "gleif-delta.zip", 10, "SUCCESS")
        db.clear_full_refresh_sync_log()
        assert not db.is_file_processed("gleif-goldencopy.zip")
        # DELTA entries must be preserved
        assert db.is_file_processed("gleif-delta.zip")


# ---------------------------------------------------------------------------
# ISIN mapping
# ---------------------------------------------------------------------------


class TestIsinMap:
    def test_upsert_and_retrieve_isin_mapping(self, db: GleifCacheManager) -> None:
        db.bulk_upsert_isin_map(
            [
                ("5493001KJTIIGC8Y1R12", "GB00B3RBWM25"),
                ("5493001KJTIIGC8Y1R12", "GB00ABC12345"),
            ]
        )
        leis = db.get_leis_for_isin("GB00B3RBWM25")
        assert "5493001KJTIIGC8Y1R12" in leis

    def test_get_isins_for_lei(self, db: GleifCacheManager) -> None:
        db.bulk_upsert_isin_map(
            [
                ("5493001KJTIIGC8Y1R12", "GB00B3RBWM25"),
                ("5493001KJTIIGC8Y1R12", "GB00ABC12345"),
            ]
        )
        isins = db.get_isins_for_lei("5493001KJTIIGC8Y1R12")
        assert set(isins) == {"GB00B3RBWM25", "GB00ABC12345"}

    def test_isin_insert_or_ignore_idempotent(self, db: GleifCacheManager) -> None:
        db.bulk_upsert_isin_map([("5493001KJTIIGC8Y1R12", "GB00B3RBWM25")])
        db.bulk_upsert_isin_map([("5493001KJTIIGC8Y1R12", "GB00B3RBWM25")])  # duplicate
        leis = db.get_leis_for_isin("GB00B3RBWM25")
        assert leis.count("5493001KJTIIGC8Y1R12") == 1

    def test_unknown_isin_returns_empty(self, db: GleifCacheManager) -> None:
        assert db.get_leis_for_isin("UNKNOWNISIN123") == []


# ---------------------------------------------------------------------------
# FTS5 name search
# ---------------------------------------------------------------------------


class TestNameSearch:
    def test_search_by_exact_name(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(legal_name="Citibank Europe plc")])
        results = db.search_by_name("Citibank Europe")
        assert len(results) >= 1
        assert results[0]["legal_name"] == "Citibank Europe plc"

    def test_search_returns_empty_for_unknown(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(legal_name="Known Corp")])
        results = db.search_by_name("ZZZUnknownXXX")
        assert results == []

    def test_search_case_insensitive(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(legal_name="DEUTSCHE BANK AG")])
        results = db.search_by_name("deutsche bank")
        assert len(results) >= 1

    def test_search_by_other_names(self, db: GleifCacheManager) -> None:
        db.bulk_upsert(
            [
                _make_record(
                    legal_name="Barclays PLC",
                    other_names="Barclays Bank; Barclays Capital",
                )
            ]
        )
        results = db.search_by_name("Barclays Capital")
        assert len(results) >= 1
        assert results[0]["legal_name"] == "Barclays PLC"

    def test_search_empty_query_returns_empty(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record()])
        results = db.search_by_name("")
        assert results == []

    def test_rebuild_fts_after_truncate(self, db: GleifCacheManager) -> None:
        db.bulk_upsert([_make_record(legal_name="HSBC Holdings plc")])
        db.truncate_lei_records()
        db.rebuild_fts()
        results = db.search_by_name("HSBC")
        assert results == []


# ---------------------------------------------------------------------------
# Sync log
# ---------------------------------------------------------------------------


class TestSyncLog:
    def test_log_sync_and_is_file_processed(self, db: GleifCacheManager) -> None:
        assert not db.is_file_processed("gleif-goldencopy.zip")
        db.log_sync("FULL", "gleif-goldencopy.zip", 100_000, "SUCCESS")
        assert db.is_file_processed("gleif-goldencopy.zip")

    def test_error_file_is_not_considered_processed(
        self, db: GleifCacheManager
    ) -> None:
        db.log_sync("FULL", "gleif-goldencopy.zip", 0, "ERROR")
        assert not db.is_file_processed("gleif-goldencopy.zip")

    def test_get_last_sync_date_none_when_empty(self, db: GleifCacheManager) -> None:
        assert db.get_last_sync_date() is None

    def test_get_last_sync_date_returns_value(self, db: GleifCacheManager) -> None:
        db.log_sync("FULL", "gleif-goldencopy.zip", 100, "SUCCESS")
        result = db.get_last_sync_date()
        assert result is not None
        assert len(result) > 0
