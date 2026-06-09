"""
Unit tests for FCA FIRDS reportability checker (firds.reportability).

Tests cover all six scenarios:
- ACTIVE (exact MIC match, active at trade date)
- ACTIVE (no MIC, at least one active venue)
- NOT_IN_FIRDS (ISIN not in cache)
- NOT_IN_FIRDS (ISIN present but not for the given MIC)
- ADMISSION_AFTER_TRADE (instrument not yet admitted at trade date)
- TERMINATED_BEFORE_TRADE (instrument terminated before trade date)
- TERMINATED on same day as trade (should be NOT reportable)
- CANCELLED
"""

from datetime import date
from pathlib import Path

import pytest

from firds.cache import FirdsCacheManager
from firds.parser import InstrumentRecord
from firds.reportability import (
    FirdsReportabilityChecker,
    ReportabilityReason,
    ReportabilityResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path) -> FirdsCacheManager:
    cache = FirdsCacheManager(db_path=tmp_path / "test.db")
    cache.initialise_db()
    return cache


@pytest.fixture()
def checker(db) -> FirdsReportabilityChecker:
    return FirdsReportabilityChecker(cache=db)


def _insert(
    db: FirdsCacheManager,
    isin: str,
    mic: str,
    admission: str = "2020-01-01",
    termination: str | None = None,
    cancelled: bool = False,
    cancelled_date: str | None = None,
) -> None:
    record = InstrumentRecord(
        isin=isin,
        mic=mic,
        record_type="FULL",
        cfi_code="ESXXXX",
        full_name="Test",
        short_name="T",
        admission_date=admission,
        termination_date=termination,
        rca="GB",
    )
    db.upsert_instrument(record)
    if cancelled:
        db.apply_cancellation(isin, mic, cancelled_date or "2023-01-01")


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_raises_without_db_or_cache(self):
        with pytest.raises(ValueError):
            FirdsReportabilityChecker()

    def test_accepts_db_path(self, tmp_path):
        db_path = tmp_path / "new.db"
        cache = FirdsCacheManager(db_path)
        cache.initialise_db()
        checker = FirdsReportabilityChecker(db_path=db_path)
        assert checker is not None

    def test_accepts_cache_object(self, db):
        checker = FirdsReportabilityChecker(cache=db)
        assert checker is not None


# ---------------------------------------------------------------------------
# ACTIVE
# ---------------------------------------------------------------------------


class TestActive:
    def test_active_with_mic(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is True
        assert result.reason == ReportabilityReason.ACTIVE

    def test_active_without_mic(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15))
        assert result.is_reportable is True
        assert "XLON" in result.matched_mics

    def test_active_no_termination_date(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01", termination=None)
        result = checker.is_reportable("GB00B3RBWM25", date(2099, 1, 1), mic="XLON")
        assert result.is_reportable is True

    def test_active_on_exact_admission_date(self, db, checker):
        """Instrument should be reportable on its admission date."""
        _insert(db, "GB00B3RBWM25", "XLON", admission="2025-06-15")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is True

    def test_multiple_venues_matched(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01")
        _insert(db, "GB00B3RBWM25", "XPAR", admission="2021-01-01")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15))
        assert result.is_reportable is True
        assert set(result.matched_mics) == {"XLON", "XPAR"}

    def test_isin_case_normalised(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01")
        result = checker.is_reportable("gb00b3rbwm25", date(2025, 6, 15), mic="xlon")
        assert result.is_reportable is True


# ---------------------------------------------------------------------------
# NOT_IN_FIRDS
# ---------------------------------------------------------------------------


class TestNotInFirds:
    def test_isin_not_in_cache(self, checker):
        result = checker.is_reportable("ZZNONE000000", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.NOT_IN_FIRDS

    def test_isin_present_wrong_mic(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XPAR")
        assert result.is_reportable is True
        assert result.reason == ReportabilityReason.ACTIVE_OTHER_VENUE
        assert "XLON" in result.matched_mics

    def test_isin_not_in_cache_no_mic(self, checker):
        result = checker.is_reportable("ZZNONE000000", date(2025, 6, 15))
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.NOT_IN_FIRDS


# ---------------------------------------------------------------------------
# ADMISSION_AFTER_TRADE
# ---------------------------------------------------------------------------


class TestAdmissionAfterTrade:
    def test_not_reportable_before_admission(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2025-07-01")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.ADMISSION_AFTER_TRADE

    def test_reportable_day_after_admission(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2025-06-14")
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is True


# ---------------------------------------------------------------------------
# TERMINATED_BEFORE_TRADE
# ---------------------------------------------------------------------------


class TestTerminatedBeforeTrade:
    def test_not_reportable_after_termination(self, db, checker):
        _insert(
            db, "GB00B3RBWM25", "XLON", admission="2020-01-01", termination="2024-12-31"
        )
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.TERMINATED_BEFORE_TRADE

    def test_not_reportable_on_termination_date(self, db, checker):
        """Instrument terminated ON the trade date should not be reportable."""
        _insert(
            db, "GB00B3RBWM25", "XLON", admission="2020-01-01", termination="2025-06-15"
        )
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.TERMINATED_BEFORE_TRADE

    def test_reportable_day_before_termination(self, db, checker):
        _insert(
            db, "GB00B3RBWM25", "XLON", admission="2020-01-01", termination="2025-06-16"
        )
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is True

    def test_only_terminated_venue_not_reportable_any(self, db, checker):
        """With only terminated venues, any-venue check should also fail."""
        _insert(
            db, "GB00B3RBWM25", "XLON", admission="2020-01-01", termination="2023-01-01"
        )
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15))
        assert result.is_reportable is False


# ---------------------------------------------------------------------------
# CANCELLED
# ---------------------------------------------------------------------------


class TestCancelled:
    def test_cancelled_instrument_not_reportable(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", cancelled=True)
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.is_reportable is False
        assert result.reason == ReportabilityReason.CANCELLED

    def test_cancellation_takes_precedence_over_termination(self, db, checker):
        """A cancelled+terminated instrument should report CANCELLED, not TERMINATED."""
        _insert(
            db,
            "GB00B3RBWM25",
            "XLON",
            admission="2020-01-01",
            termination="2024-01-01",
            cancelled=True,
        )
        result = checker.is_reportable("GB00B3RBWM25", date(2025, 6, 15), mic="XLON")
        assert result.reason == ReportabilityReason.CANCELLED


# ---------------------------------------------------------------------------
# Bulk check
# ---------------------------------------------------------------------------


class TestBulkCheck:
    def test_bulk_returns_all_results(self, db, checker):
        _insert(db, "GB00B3RBWM25", "XLON", admission="2020-01-01")
        checks = [
            {"isin": "GB00B3RBWM25", "trade_date": date(2025, 6, 15), "mic": "XLON"},
            {"isin": "ZZNONE000000", "trade_date": date(2025, 6, 15)},
        ]
        results = checker.bulk_check(checks)
        assert len(results) == 2
        assert results[0].is_reportable is True
        assert results[1].is_reportable is False

    def test_bulk_order_preserved(self, db, checker):
        isins = [f"GB{str(i).zfill(10)}" for i in range(5)]
        for isin in isins:
            _insert(db, isin, "XLON")
        checks = [{"isin": isin, "trade_date": date(2025, 1, 1)} for isin in isins]
        results = checker.bulk_check(checks)
        for i, result in enumerate(results):
            assert result.isin == isins[i]
