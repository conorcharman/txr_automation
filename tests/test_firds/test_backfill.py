"""
Tests for firds.scripts.backfill — column detection, CSV loading, and
integration with the cache (using a mocked downloader).
"""

import csv
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from firds.cache import FirdsCacheManager
from firds.client import FirdsFileRecord
from firds.downloader import DownloadResult
from firds.scripts.backfill import (
    _detect_format,
    _load_trades,
    _refresh_for_period,
    _INCIDENT_DATE_COL,
    _INCIDENT_ISIN_COL,
    _INCIDENT_MIC_COL,
)

_NS_FIRDS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.01"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path) -> FirdsCacheManager:
    cache = FirdsCacheManager(db_path=tmp_path / "test.db")
    cache.initialise_db()
    return cache


def _write_incident_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a minimal FCA incident-style CSV."""
    path = tmp_path / "incidents.csv"
    fieldnames = [
        _INCIDENT_ISIN_COL,
        _INCIDENT_MIC_COL,
        _INCIDENT_DATE_COL,
        "INCIDENT_CODE",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_generic_csv(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a minimal generic trade CSV."""
    path = tmp_path / "trades.csv"
    fieldnames = ["isin", "trade_date", "mic"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _fulins_xml(isin: str, mic: str, admission: str = "2020-01-01") -> str:
    return (
        f'<Document xmlns="{_NS_FIRDS}">'
        f"<FinInstrmRptgRefDataRpt>"
        f"<RefData>"
        f"<FinInstrmGnlAttrbts>"
        f"<Id>{isin}</Id>"
        f"<FullNm>Test</FullNm><ShrtNm>T</ShrtNm><ClssfctnTp>ESXXXX</ClssfctnTp>"
        f"</FinInstrmGnlAttrbts>"
        f"<TradgVnRltdAttrbts>"
        f"<Id>{mic}</Id>"
        f"<AdmssnApprvlDtByTheTradgVn>{admission}</AdmssnApprvlDtByTheTradgVn>"
        f"</TradgVnRltdAttrbts>"
        f"</RefData>"
        f"</FinInstrmRptgRefDataRpt>"
        f"</Document>"
    )


# ---------------------------------------------------------------------------
# _detect_format
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_detects_incident_format(self):
        headers = [
            "INCIDENT_CODE",
            _INCIDENT_ISIN_COL,
            _INCIDENT_MIC_COL,
            _INCIDENT_DATE_COL,
        ]
        assert _detect_format(headers) == "incident"

    def test_detects_generic_format(self):
        headers = ["isin", "trade_date", "mic"]
        assert _detect_format(headers) == "generic"

    def test_partial_incident_headers_falls_back_to_generic(self):
        # Only one of the two required incident headers present
        headers = [_INCIDENT_ISIN_COL, "some_other_column"]
        assert _detect_format(headers) == "generic"


# ---------------------------------------------------------------------------
# _load_trades — incident format
# ---------------------------------------------------------------------------


class TestLoadTradesIncident:
    def test_loads_valid_rows(self, tmp_path):
        csv_path = _write_incident_csv(tmp_path, [
            {_INCIDENT_ISIN_COL: "GB00B3RBWM25", _INCIDENT_MIC_COL: "XLON",
             _INCIDENT_DATE_COL: "2025-07-15", "INCIDENT_CODE": "7_39"},
            {_INCIDENT_ISIN_COL: "DE000CM7VX13", _INCIDENT_MIC_COL: "XFRA",
             _INCIDENT_DATE_COL: "2025-08-01", "INCIDENT_CODE": "7_39"},
        ])
        trades, fieldnames = _load_trades(csv_path, fmt="incident")
        assert len(trades) == 2
        assert trades[0]["_isin"] == "GB00B3RBWM25"
        assert trades[0]["_mic"] == "XLON"
        assert trades[0]["_trade_date"] == date(2025, 7, 15)

    def test_skips_blank_isin_rows(self, tmp_path):
        csv_path = _write_incident_csv(tmp_path, [
            {_INCIDENT_ISIN_COL: "", _INCIDENT_MIC_COL: "", _INCIDENT_DATE_COL: "", "INCIDENT_CODE": ""},
            {_INCIDENT_ISIN_COL: "GB00B3RBWM25", _INCIDENT_MIC_COL: "XLON",
             _INCIDENT_DATE_COL: "2025-07-15", "INCIDENT_CODE": "7_39"},
        ])
        trades, _ = _load_trades(csv_path, fmt="incident")
        assert len(trades) == 1

    def test_isin_uppercased(self, tmp_path):
        csv_path = _write_incident_csv(tmp_path, [
            {_INCIDENT_ISIN_COL: "gb00b3rbwm25", _INCIDENT_MIC_COL: "xlon",
             _INCIDENT_DATE_COL: "2025-07-15", "INCIDENT_CODE": ""},
        ])
        trades, _ = _load_trades(csv_path, fmt="incident")
        assert trades[0]["_isin"] == "GB00B3RBWM25"
        assert trades[0]["_mic"] == "XLON"

    def test_auto_detects_incident_format(self, tmp_path):
        csv_path = _write_incident_csv(tmp_path, [
            {_INCIDENT_ISIN_COL: "GB00B3RBWM25", _INCIDENT_MIC_COL: "XLON",
             _INCIDENT_DATE_COL: "2025-07-15", "INCIDENT_CODE": ""},
        ])
        trades, _ = _load_trades(csv_path, fmt="auto")
        assert len(trades) == 1


# ---------------------------------------------------------------------------
# _load_trades — generic format
# ---------------------------------------------------------------------------


class TestLoadTradesGeneric:
    def test_loads_generic_csv(self, tmp_path):
        csv_path = _write_generic_csv(tmp_path, [
            {"isin": "GB00B3RBWM25", "trade_date": "2025-07-15", "mic": "XLON"},
        ])
        trades, _ = _load_trades(csv_path, fmt="generic")
        assert len(trades) == 1
        assert trades[0]["_isin"] == "GB00B3RBWM25"
        assert trades[0]["_trade_date"] == date(2025, 7, 15)

    def test_mic_is_none_when_empty(self, tmp_path):
        csv_path = _write_generic_csv(tmp_path, [
            {"isin": "GB00B3RBWM25", "trade_date": "2025-07-15", "mic": ""},
        ])
        trades, _ = _load_trades(csv_path, fmt="generic")
        assert trades[0]["_mic"] is None


# ---------------------------------------------------------------------------
# _refresh_for_period
# ---------------------------------------------------------------------------


class TestRefreshForPeriod:
    def _make_file_record(self, name: str, pub_date: str, file_type: str = "FULINS") -> FirdsFileRecord:
        return FirdsFileRecord(
            publication_date=pub_date,
            download_link=f"https://example.com/{name}",
            file_type=file_type,
            file_name=name,
            last_refreshed=pub_date + "T10:00:00Z",
        )

    def test_calls_full_refresh_only(self, db, tmp_path):
        """Only a full refresh is called; DLTINS delta files are not used."""
        fulins_rec = self._make_file_record("FULINS_C_20250628_01of01.zip", "2025-06-28")

        fulins_xml = _fulins_xml("GB00B3RBWM25", "XLON")
        fulins_xml_path = tmp_path / "fulins.xml"
        fulins_xml_path.write_text(fulins_xml, encoding="utf-8")
        fulins_dl = DownloadResult(
            file_record=fulins_rec, zip_path=None, xml_paths=[fulins_xml_path], success=True
        )

        with patch("firds.scripts.backfill.FirdsApiClient") as MockApi, \
             patch("firds.refresher.FirdsDownloader") as MockDl:

            mock_api = MockApi.return_value
            mock_api.get_latest_full_files.return_value = [fulins_rec]
            mock_api.get_cancellation_files.return_value = []

            MockDl.return_value.download_and_extract.return_value = fulins_dl
            MockDl.return_value.cleanup_file = MagicMock()

            _refresh_for_period(db, min_date=date(2025, 7, 1), max_date=date(2025, 7, 3))

        # FULINS was ingested
        assert db.get_by_isin_mic("GB00B3RBWM25", "XLON") is not None
        # FULINS file is in sync log; no DLTINS present
        assert db.is_file_processed("FULINS_C_20250628_01of01.zip")
        mock_api.get_delta_files.assert_not_called()

    def test_fulins_date_is_previous_saturday(self, db, tmp_path):
        """For a Monday trade date the FULINS target is the prior Saturday."""
        monday = date(2025, 7, 7)  # a known Monday
        expected_saturday = date(2025, 7, 5)

        with patch("firds.scripts.backfill.FirdsApiClient") as MockApi, \
             patch("firds.refresher.FirdsDownloader"):

            mock_api = MockApi.return_value
            mock_api.get_latest_full_files.return_value = []
            mock_api.get_cancellation_files.return_value = []

            _refresh_for_period(db, min_date=monday, max_date=monday)

            mock_api.get_latest_full_files.assert_called_once_with(expected_saturday)
            mock_api.get_delta_files.assert_not_called()
