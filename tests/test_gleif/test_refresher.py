"""Tests for GLEIF cache refresher (refresher.py)."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from gleif.cache import GleifCacheManager
from gleif.client import GleifApiClient, GoldenCopyInfo
from gleif.downloader import GleifDownloadResult
from gleif.parser import LeiRecord
from gleif.refresher import GleifRefresher, RefreshResult, _VALID_DELTA_TYPES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_download_result(
    csv_paths: list[Path],
    success: bool = True,
    error: str = "",
) -> GleifDownloadResult:
    """Build a mock GleifDownloadResult."""
    return GleifDownloadResult(
        url="https://example.com/test.zip",
        file_name="test.zip",
        zip_path=None,
        csv_paths=csv_paths,
        success=success,
        error=error,
    )


def _make_lei_records(n: int = 3) -> list[LeiRecord]:
    return [
        LeiRecord(
            lei=f"5493001KJTIIGC8Y{i:04d}",
            legal_name=f"Entity {i}",
            registration_status="ISSUED",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cache(tmp_path: Path) -> GleifCacheManager:
    c = GleifCacheManager(db_path=tmp_path / "gleif.db")
    c.initialise_db()
    return c


@pytest.fixture
def mock_api_client() -> MagicMock:
    client = MagicMock(spec=GleifApiClient)
    client.get_latest_golden_copy_info.return_value = GoldenCopyInfo(
        publish_date="2026-03-23T00:00:00Z",
        download_url="https://example.com/gleif-full.zip",
    )
    return client


@pytest.fixture
def refresher(cache: GleifCacheManager, mock_api_client: MagicMock) -> GleifRefresher:
    return GleifRefresher(cache=cache, api_client=mock_api_client)


# ---------------------------------------------------------------------------
# RefreshResult
# ---------------------------------------------------------------------------


class TestRefreshResult:
    def test_default_values(self) -> None:
        r = RefreshResult()
        assert r.files_processed == 0
        assert r.files_skipped == 0
        assert r.files_failed == 0
        assert r.total_records == 0

    def test_repr_contains_counts(self) -> None:
        r = RefreshResult()
        r.files_processed = 2
        r.total_records = 1000
        s = repr(r)
        assert "2" in s
        assert "1000" in s


# ---------------------------------------------------------------------------
# run_full_refresh — happy path
# ---------------------------------------------------------------------------


class TestRunFullRefreshHappyPath:
    def test_processes_golden_copy_and_returns_result(
        self,
        refresher: GleifRefresher,
        cache: GleifCacheManager,
        tmp_path: Path,
    ) -> None:
        csv_path = tmp_path / "lei2.csv"
        csv_path.write_text("LEI,Entity.LegalName\n", encoding="utf-8")
        records = _make_lei_records(5)

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter(records)),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([csv_path])
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=True)

        assert isinstance(result, RefreshResult)
        assert result.files_processed == 1
        assert result.total_records == 5
        assert result.files_failed == 0

    def test_isin_map_processed_when_not_skipped(
        self,
        refresher: GleifRefresher,
        tmp_path: Path,
    ) -> None:
        gc_csv = tmp_path / "lei2.csv"
        isin_csv = tmp_path / "isin.csv"
        gc_csv.write_text("", encoding="utf-8")
        isin_csv.write_text("", encoding="utf-8")

        lei_records = _make_lei_records(2)
        isin_pairs = [("5493001KJTIIGC8Y0000", "GB00B3RBWM25")]

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter(lei_records)),
            patch.object(refresher._isin_parser, "parse", return_value=iter(isin_pairs)),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            # First call → Golden Copy, second → ISIN map
            mock_dl.download_and_extract.side_effect = [
                _make_download_result([gc_csv]),
                _make_download_result([isin_csv]),
            ]
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=False)

        assert result.files_processed == 2

    def test_skip_isin_map_flag_respected(
        self,
        refresher: GleifRefresher,
        tmp_path: Path,
    ) -> None:
        gc_csv = tmp_path / "lei2.csv"
        gc_csv.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter([])),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([gc_csv])
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=True)

        # download_and_extract should only have been called once (no ISIN map)
        assert mock_dl.download_and_extract.call_count == 1

    def test_already_processed_file_is_reprocessed_for_full_refresh(
        self,
        refresher: GleifRefresher,
        cache: GleifCacheManager,
        tmp_path: Path,
    ) -> None:
        # Simulate the file being in the sync log already.
        # Full refresh now intentionally clears previous FULL entries and
        # reprocesses the latest Golden Copy.
        cache.log_sync(
            sync_type="FULL",
            file_name="gleif-goldencopy-20260323T000000.zip",
            records_processed=100,
            status="SUCCESS",
        )

        gc_csv = tmp_path / "lei2.csv"
        gc_csv.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter([])),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([gc_csv])
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=True)

        mock_dl.download_and_extract.assert_called_once()
        assert result.files_skipped == 0
        assert result.files_processed == 1


# ---------------------------------------------------------------------------
# run_full_refresh — failure paths
# ---------------------------------------------------------------------------


class TestRunFullRefreshFailure:
    def test_download_failure_increments_files_failed(
        self,
        refresher: GleifRefresher,
        tmp_path: Path,
    ) -> None:
        with patch("gleif.refresher.GleifDownloader") as mock_dl_cls:
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result(
                csv_paths=[], success=False, error="HTTP 403"
            )
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=True)

        assert result.files_failed == 1
        assert result.files_processed == 0

    def test_parse_error_increments_files_failed(
        self,
        refresher: GleifRefresher,
        tmp_path: Path,
    ) -> None:
        gc_csv = tmp_path / "lei2.csv"
        gc_csv.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(
                refresher._parser, "parse", side_effect=RuntimeError("parse boom")
            ),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([gc_csv])
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_full_refresh(skip_isin_map=True)

        assert result.files_failed == 1

    def test_error_sync_log_written_on_failure(
        self,
        refresher: GleifRefresher,
        cache: GleifCacheManager,
        tmp_path: Path,
    ) -> None:
        with patch("gleif.refresher.GleifDownloader") as mock_dl_cls:
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result(
                csv_paths=[], success=False, error="network error"
            )
            mock_dl.cleanup_file.return_value = None
            refresher.run_full_refresh(skip_isin_map=True)

        # An ERROR entry should exist in gleif_sync_log
        import sqlite3
        conn = sqlite3.connect(cache._db_path)
        rows = conn.execute("SELECT status FROM gleif_sync_log").fetchall()
        conn.close()
        statuses = [r[0] for r in rows]
        assert "ERROR" in statuses


# ---------------------------------------------------------------------------
# run_delta_refresh
# ---------------------------------------------------------------------------


class TestRunDeltaRefresh:
    def test_invalid_delta_type_raises(self, refresher: GleifRefresher) -> None:
        with pytest.raises(ValueError, match="Invalid delta_type"):
            refresher.run_delta_refresh("13h")

    @pytest.mark.parametrize("delta_type", list(_VALID_DELTA_TYPES))
    def test_valid_delta_types_accepted(
        self, refresher: GleifRefresher, tmp_path: Path, delta_type: str
    ) -> None:
        csv_path = tmp_path / "delta.csv"
        csv_path.write_text("", encoding="utf-8")
        records = _make_lei_records(2)

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter(records)),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([csv_path])
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_delta_refresh(delta_type)

        assert result.files_processed == 1
        assert result.total_records == 2

    def test_delta_download_url_contains_delta_type(
        self, refresher: GleifRefresher, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "delta.csv"
        csv_path.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter([])),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([csv_path])
            mock_dl.cleanup_file.return_value = None

            refresher.run_delta_refresh("24h")

        download_call_url = mock_dl.download_and_extract.call_args[0][0]
        assert "24h" in download_call_url

    def test_delta_download_failure_increments_files_failed(
        self, refresher: GleifRefresher, tmp_path: Path
    ) -> None:
        with patch("gleif.refresher.GleifDownloader") as mock_dl_cls:
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result(
                csv_paths=[], success=False, error="HTTP 503"
            )
            mock_dl.cleanup_file.return_value = None

            result = refresher.run_delta_refresh("24h")

        assert result.files_failed == 1
        assert result.total_records == 0

    def test_default_delta_type_is_24h(
        self, refresher: GleifRefresher, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "delta.csv"
        csv_path.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter([])),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([csv_path])
            mock_dl.cleanup_file.return_value = None

            refresher.run_delta_refresh()

        download_url = mock_dl.download_and_extract.call_args[0][0]
        assert "24h" in download_url

    def test_sync_log_written_on_success(
        self, refresher: GleifRefresher, cache: GleifCacheManager, tmp_path: Path
    ) -> None:
        csv_path = tmp_path / "delta.csv"
        csv_path.write_text("", encoding="utf-8")

        with (
            patch("gleif.refresher.GleifDownloader") as mock_dl_cls,
            patch.object(refresher._parser, "parse", return_value=iter([])),
        ):
            mock_dl = MagicMock()
            mock_dl_cls.return_value = mock_dl
            mock_dl.download_and_extract.return_value = _make_download_result([csv_path])
            mock_dl.cleanup_file.return_value = None

            refresher.run_delta_refresh("24h")

        import sqlite3
        conn = sqlite3.connect(cache._db_path)
        rows = conn.execute(
            "SELECT sync_type, status FROM gleif_sync_log WHERE sync_type='DELTA'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][1] == "SUCCESS"
