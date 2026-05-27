"""Tests for header detection and column alias handling in check_reportability."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from firds.reportability import ReportabilityReason, ReportabilityResult
from firds.scripts.check_reportability import _process_file


class _StubChecker:
    """Simple checker stub that always returns reportable for test inputs."""

    def is_reportable(self, isin: str, trade_date: date, mic: str | None = None) -> ReportabilityResult:
        return ReportabilityResult(
            is_reportable=True,
            reason=ReportabilityReason.ACTIVE,
            isin=isin,
            trade_date=trade_date,
            mic=mic,
            matched_mics=[mic] if mic else [],
        )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]], encoding: str = "utf-8") -> None:
    with path.open("w", newline="", encoding=encoding) as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_process_file_accepts_instrument_id_alias(tmp_path: Path) -> None:
    csv_path = tmp_path / "firds_eg.csv"
    _write_csv(
        csv_path,
        ["Instrument ID", "Trade Date", "MIC"],
        [{"Instrument ID": "gb00b3rbwm25", "Trade Date": "2026-05-21", "MIC": "xlon"}],
    )

    rows, row_count, error_count = _process_file(_StubChecker(), csv_path, file_date=None)

    assert rows is not None
    assert row_count == 1
    assert error_count == 0
    assert rows[0]["is_reportable"] == "Y"
    assert rows[0]["reportability_reason"] == ReportabilityReason.ACTIVE
    assert rows[0]["matched_mics"] == "xlon"


def test_process_file_accepts_whitespace_and_case_variants(tmp_path: Path) -> None:
    csv_path = tmp_path / "messy_headers.csv"
    _write_csv(
        csv_path,
        ["  ISIN  ", "  trade_date ", "  Mic"],
        [{"  ISIN  ": "GB00B3RBWM25", "  trade_date ": "2026-05-21", "  Mic": "XLON"}],
    )

    rows, row_count, error_count = _process_file(_StubChecker(), csv_path, file_date=None)

    assert rows is not None
    assert row_count == 1
    assert error_count == 0
    assert rows[0]["is_reportable"] == "Y"


def test_process_file_accepts_bom_prefixed_isin_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "bom_headers.csv"
    _write_csv(
        csv_path,
        ["ISIN", "trade_date", "mic"],
        [{"ISIN": "GB00B3RBWM25", "trade_date": "2026-05-21", "mic": "XLON"}],
        encoding="utf-8-sig",
    )

    rows, row_count, error_count = _process_file(_StubChecker(), csv_path, file_date=None)

    assert rows is not None
    assert row_count == 1
    assert error_count == 0
    assert rows[0]["is_reportable"] == "Y"


def test_process_file_uses_filename_date_when_date_column_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "firds_21-05-2026.csv"
    _write_csv(
        csv_path,
        ["instrument_identifier", "mic"],
        [{"instrument_identifier": "GB00B3RBWM25", "mic": "XLON"}],
    )

    rows, row_count, error_count = _process_file(_StubChecker(), csv_path, file_date=date(2026, 5, 21))

    assert rows is not None
    assert row_count == 1
    assert error_count == 0
    assert rows[0]["is_reportable"] == "Y"
