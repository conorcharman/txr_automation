"""
Integration tests for FCA FIRDS refresher (firds.refresher).

Tests use mocked HTTP responses and in-memory fixture XML so no real network
calls are made.  They verify end-to-end flow through client → downloader →
parser → cache.
"""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from firds.cache import FirdsCacheManager
from firds.client import FirdsFileRecord
from firds.downloader import DownloadResult
from firds.refresher import FirdsRefresher, RefreshResult, _most_recent_saturday

# ---------------------------------------------------------------------------
# _most_recent_saturday helper
# ---------------------------------------------------------------------------


class TestMostRecentSaturday:
    def test_saturday_returns_itself(self):
        saturday = date(2026, 3, 7)  # a known Saturday
        assert _most_recent_saturday(saturday) == saturday

    def test_sunday_returns_previous_saturday(self):
        sunday = date(2026, 3, 8)
        assert _most_recent_saturday(sunday) == date(2026, 3, 7)

    def test_monday_returns_previous_saturday(self):
        monday = date(2026, 3, 9)
        assert _most_recent_saturday(monday) == date(2026, 3, 7)

    def test_friday_returns_previous_saturday(self):
        friday = date(2026, 3, 13)
        assert _most_recent_saturday(friday) == date(2026, 3, 7)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_NS = "urn:iso:std:iso:20022:tech:xsd:auth.017.001.01"
_DELTA_NS = "urn:iso:std:iso:20022:tech:xsd:auth.036.001.03"


def _make_fulins_xml(records: list[dict]) -> str:
    """Build a minimal FULINS XML string for a list of (isin, mic) dicts."""
    ref_data_blocks = ""
    for r in records:
        term = (
            f"<TermntnDt>{r['termination']}</TermntnDt>" if r.get("termination") else ""
        )
        ref_data_blocks += (
            f"<RefData>"
            f"<FinInstrmGnlAttrbts>"
            f"<Id>{r['isin']}</Id>"
            f"<FullNm>Test</FullNm><ShrtNm>T</ShrtNm><ClssfctnTp>ESXXXX</ClssfctnTp>"
            f"</FinInstrmGnlAttrbts>"
            f"<TradgVnRltdAttrbts>"
            f"<Id>{r['mic']}</Id>"
            f"<AdmssnApprvlDtByTheTradgVn>{r.get('admission', '2020-01-01')}</AdmssnApprvlDtByTheTradgVn>"
            f"{term}"
            f"</TradgVnRltdAttrbts>"
            f"<TechRcrdId><TechAttrbts><RlvntCmptntAuthrty>GB</RlvntCmptntAuthrty></TechAttrbts></TechRcrdId>"
            f"</RefData>"
        )
    return (
        f'<Document xmlns="{_NS}">'
        f"<FinInstrmRptgRefDataRpt>{ref_data_blocks}</FinInstrmRptgRefDataRpt>"
        f"</Document>"
    )


def _make_delta_xml(entries: list[dict]) -> str:
    """Build a minimal DLTINS XML string.

    Each entry dict: tag (NewRcrd/ModfdRcrd/TermntdRcrd/CancRcrd), isin, mic,
    admission (optional), termination (optional).
    """
    blocks = ""
    for e in entries:
        term = (
            f"<TermntnDt>{e['termination']}</TermntnDt>" if e.get("termination") else ""
        )
        tag = e["tag"]
        blocks += (
            f"<{tag}>"
            f"<FinInstrmGnlAttrbts>"
            f"<Id>{e['isin']}</Id>"
            f"<FullNm>Delta</FullNm><ShrtNm>D</ShrtNm><ClssfctnTp>ESXXXX</ClssfctnTp>"
            f"</FinInstrmGnlAttrbts>"
            f"<TradgVnRltdAttrbts>"
            f"<Id>{e['mic']}</Id>"
            f"<AdmssnApprvlDtByTheTradgVn>{e.get('admission', '2020-01-01')}</AdmssnApprvlDtByTheTradgVn>"
            f"{term}"
            f"</TradgVnRltdAttrbts>"
            f"</{tag}>"
        )
    return (
        f'<Document xmlns="{_DELTA_NS}">'
        f"<FinInstrmRptgDltaRpt>{blocks}</FinInstrmRptgDltaRpt>"
        f"</Document>"
    )


def _write_xml(tmp_path: Path, xml_content: str, name: str = "data.xml") -> Path:
    """Write XML content to a temp file and return its path."""
    xml_path = tmp_path / name
    xml_path.write_text(xml_content, encoding="utf-8")
    return xml_path


def _make_download_result(
    file_record: FirdsFileRecord, xml_paths: list[Path]
) -> DownloadResult:
    """Return a successful DownloadResult pointing at real XML files."""
    return DownloadResult(
        file_record=file_record,
        zip_path=None,
        xml_paths=xml_paths,
        success=True,
    )


def _make_file_record(
    file_name: str,
    file_type: str = "FULINS",
    pub_date: str = "2026-03-07",
) -> FirdsFileRecord:
    return FirdsFileRecord(
        publication_date=pub_date,
        download_link=f"https://example.com/{file_name}",
        file_type=file_type,
        file_name=file_name,
        last_refreshed="2026-03-07T10:00:00Z",
    )


@pytest.fixture()
def db(tmp_path) -> FirdsCacheManager:
    cache = FirdsCacheManager(db_path=tmp_path / "test.db")
    cache.initialise_db()
    return cache


# ---------------------------------------------------------------------------
# Full refresh
# ---------------------------------------------------------------------------


class TestFullRefresh:
    def _make_refresher(self, db, tmp_path, mock_api):
        return FirdsRefresher(
            cache=db,
            api_client=mock_api,
            staging_dir=tmp_path / "staging",
        )

    def test_instruments_loaded(self, db, tmp_path):
        xml = _make_fulins_xml([{"isin": "GB00B3RBWM25", "mic": "XLON"}])
        xml_path = _write_xml(tmp_path, xml)
        file_record = _make_file_record("FULINS_C_20260307_01of01.zip")
        dl_result = _make_download_result(file_record, [xml_path])

        mock_api = MagicMock()
        mock_api.get_latest_full_files.return_value = [file_record]
        mock_api.get_cancellation_files.return_value = []

        with patch("firds.refresher.FirdsDownloader") as MockDownloader:
            MockDownloader.return_value.download_and_extract.return_value = dl_result
            MockDownloader.return_value.cleanup_file = MagicMock()
            result = self._make_refresher(db, tmp_path, mock_api).run_full_refresh(
                target_date=date(2026, 3, 7)
            )

        assert result.files_processed == 1
        assert result.total_records == 1
        assert db.get_by_isin_mic("GB00B3RBWM25", "XLON") is not None

    def test_file_logged_in_sync_log(self, db, tmp_path):
        xml = _make_fulins_xml([{"isin": "GB00B3RBWM25", "mic": "XLON"}])
        xml_path = _write_xml(tmp_path, xml)
        file_record = _make_file_record("FULINS_C_20260307_01of01.zip")
        dl_result = _make_download_result(file_record, [xml_path])

        mock_api = MagicMock()
        mock_api.get_latest_full_files.return_value = [file_record]
        mock_api.get_cancellation_files.return_value = []

        with patch("firds.refresher.FirdsDownloader") as MockDownloader:
            MockDownloader.return_value.download_and_extract.return_value = dl_result
            MockDownloader.return_value.cleanup_file = MagicMock()
            self._make_refresher(db, tmp_path, mock_api).run_full_refresh(
                target_date=date(2026, 3, 7)
            )

        assert db.is_file_processed("FULINS_C_20260307_01of01.zip") is True

    def test_full_refresh_clears_sync_log_and_reprocesses(self, db, tmp_path):
        # A FULL entry in the sync_log should be cleared by run_full_refresh
        # so the file is re-ingested, not skipped (idempotent full rebuild).
        db.log_sync("FULL", "2026-03-07", "FULINS_C_20260307_01of01.zip", 100)
        file_record = _make_file_record("FULINS_C_20260307_01of01.zip")

        mock_api = MagicMock()
        mock_api.get_latest_full_files.return_value = [file_record]
        mock_api.get_cancellation_files.return_value = []

        xml_path = tmp_path / "FULINS_C_20260307_01of01.xml"
        xml_path.write_text(
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:auth.017.001.01">'
            "<FinInstrmRptgRefDataRpt></FinInstrmRptgRefDataRpt></Document>",
            encoding="utf-8",
        )
        dl_result = MagicMock()
        dl_result.success = True
        dl_result.xml_paths = [xml_path]

        with patch("firds.refresher.FirdsDownloader") as MockDownloader:
            MockDownloader.return_value.download_and_extract.return_value = dl_result
            result = self._make_refresher(db, tmp_path, mock_api).run_full_refresh(
                target_date=date(2026, 3, 7)
            )

        # File should be processed (not skipped) because sync_log was cleared
        assert result.files_skipped == 0
        assert result.files_processed == 1

    def test_no_files_returned(self, db, tmp_path):
        mock_api = MagicMock()
        mock_api.get_latest_full_files.return_value = []
        mock_api.get_cancellation_files.return_value = []

        with patch("firds.refresher.FirdsDownloader"):
            result = self._make_refresher(db, tmp_path, mock_api).run_full_refresh(
                target_date=date(2026, 3, 7)
            )

        assert result.files_processed == 0
        assert result.total_records == 0


# ---------------------------------------------------------------------------
# Delta refresh
# ---------------------------------------------------------------------------


class TestDeltaRefresh:
    def test_run_delta_refresh_is_noop(self, db, tmp_path):
        """run_delta_refresh is a no-op — DLTINS files are not used."""
        mock_api = MagicMock()
        refresher = FirdsRefresher(
            cache=db, api_client=mock_api, staging_dir=tmp_path / "staging"
        )
        result = refresher.run_delta_refresh(since_date=date(2026, 3, 8))
        assert result.files_processed == 0
        assert result.total_records == 0
        mock_api.get_delta_files.assert_not_called()

    def test_run_delta_refresh_noop_with_to_date(self, db, tmp_path):
        """run_delta_refresh ignores to_date and returns empty result."""
        mock_api = MagicMock()
        refresher = FirdsRefresher(
            cache=db, api_client=mock_api, staging_dir=tmp_path / "staging"
        )
        result = refresher.run_delta_refresh(
            since_date=date(2025, 1, 1), to_date=date(2025, 12, 31)
        )
        assert result.files_failed == 0
        mock_api.get_delta_files.assert_not_called()
