"""Tests for CSV extract collation header handling and reconcile behaviour."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from src.accuracy_testing.scripts.collate_csv_extracts import CSVExtractCollator


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_collate_ignores_header_case_and_whitespace_differences(
    tmp_path: Path, caplog
) -> None:
    _write_csv(
        tmp_path / "7_37_Extract1.csv",
        ["Transaction Ref", "Value"],
        [["T1", "100"]],
    )
    _write_csv(
        tmp_path / "7_37_Extract2.csv",
        [" transaction ref ", "value"],
        [["T2", "200"]],
    )

    collator = CSVExtractCollator(input_dir=tmp_path, output_dir=tmp_path)
    stats = collator.collate_incident("7_37")

    assert stats.success is True
    assert stats.total_rows == 2
    assert "Header mismatch" not in caplog.text


def test_reconcile_existing_deletes_stale_extracts(tmp_path: Path) -> None:
    extract1 = tmp_path / "7_42_Extract1.csv"
    extract2 = tmp_path / "7_42_Extract2.csv"
    output = tmp_path / "7_42_extract.csv"

    _write_csv(extract1, ["Transaction Ref", "Value"], [["A", "1"]])
    _write_csv(extract2, ["Transaction Ref", "Value"], [["B", "2"]])
    _write_csv(output, ["Transaction Ref", "Value"], [["A", "1"], ["B", "2"]])

    old_time = output.stat().st_mtime - 60
    os.utime(extract1, (old_time, old_time))
    os.utime(extract2, (old_time, old_time))

    collator = CSVExtractCollator(
        input_dir=tmp_path,
        output_dir=tmp_path,
        delete_originals=True,
        reconcile_existing=True,
    )
    stats = collator.collate_incident("7_42")

    assert stats.success is True
    assert stats.files_deleted == 2
    assert not extract1.exists()
    assert not extract2.exists()


def test_existing_output_skip_keeps_extracts_without_reconcile(tmp_path: Path) -> None:
    extract1 = tmp_path / "7_66_Extract1.csv"
    output = tmp_path / "7_66_extract.csv"

    _write_csv(extract1, ["Transaction Ref", "Value"], [["A", "1"]])
    _write_csv(output, ["Transaction Ref", "Value"], [["A", "1"]])

    collator = CSVExtractCollator(
        input_dir=tmp_path,
        output_dir=tmp_path,
        delete_originals=True,
        reconcile_existing=False,
    )
    stats = collator.collate_incident("7_66")

    assert stats.success is False
    assert "Output file exists" in stats.error_message
    assert extract1.exists()


# ---------------------------------------------------------------------------
# Headerless CSV tests (has_header=False)
# ---------------------------------------------------------------------------


def _write_headerless_csv(path: Path, rows: list[list[str]]) -> None:
    """Write a CSV file with no header row — first row is the first data record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)


def test_headerless_merge_no_rows_dropped(tmp_path: Path, caplog) -> None:
    """When has_header=False every row from every file must appear in the output.

    Previously the collator treated row 0 of each file as a header and silently
    skipped it for files 2-N, losing one data record per file.
    """
    _write_headerless_csv(
        tmp_path / "7_6_FY26_Q2_extract_Extract1.csv",
        [["T1", "10.00", "ACCT1"], ["T2", "20.00", "ACCT2"]],
    )
    _write_headerless_csv(
        tmp_path / "7_6_FY26_Q2_extract_Extract2.csv",
        [["T3", "30.00", "ACCT3"], ["T4", "40.00", "ACCT4"]],
    )
    _write_headerless_csv(
        tmp_path / "7_6_FY26_Q2_extract_Extract3.csv",
        [["T5", "50.00", "ACCT5"]],
    )

    collator = CSVExtractCollator(
        input_dir=tmp_path,
        output_dir=tmp_path,
        has_header=False,
        fiscal_year="FY26",
        quarter="Q2",
    )
    stats = collator.collate_incident("7_6")

    assert stats.success is True
    # All 5 rows must be present — none skipped as false "headers"
    assert stats.total_rows == 5
    assert stats.header_rows_skipped == 0

    # Verify file contents: read the output and confirm all 5 transactions present
    out_path = tmp_path / "7_6_FY26_Q2_extract.csv"
    with out_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    txn_refs = [r[0] for r in rows]
    assert txn_refs == ["T1", "T2", "T3", "T4", "T5"]


def test_headerless_merge_no_mismatch_warnings(tmp_path: Path, caplog) -> None:
    """With has_header=False no 'Header mismatch' warnings should be emitted."""
    _write_headerless_csv(
        tmp_path / "7_42_FY26_Q2_extract_Extract1.csv",
        [["44626CVJCCN1", "30016.62000", "44626ZBTVGB1"]],
    )
    _write_headerless_csv(
        tmp_path / "7_42_FY26_Q2_extract_Extract2.csv",
        [["44626CVH38J1", "6890.74000", "44626CVH4DJ1G07"]],
    )

    collator = CSVExtractCollator(
        input_dir=tmp_path,
        output_dir=tmp_path,
        has_header=False,
        fiscal_year="FY26",
        quarter="Q2",
    )
    stats = collator.collate_incident("7_42")

    assert stats.success is True
    assert "Header mismatch" not in caplog.text


def test_has_header_true_still_deduplicates_header(tmp_path: Path, caplog) -> None:
    """has_header=True (default) must still skip duplicate headers in subsequent files."""
    _write_csv(
        tmp_path / "12_17_FY26_Q2_extract_Extract1.csv",
        ["TXN_REF", "LEI", "VALUE"],
        [["T1", "L1", "100"]],
    )
    _write_csv(
        tmp_path / "12_17_FY26_Q2_extract_Extract2.csv",
        ["TXN_REF", "LEI", "VALUE"],
        [["T2", "L2", "200"]],
    )

    collator = CSVExtractCollator(
        input_dir=tmp_path,
        output_dir=tmp_path,
        has_header=True,
        fiscal_year="FY26",
        quarter="Q2",
    )
    stats = collator.collate_incident("12_17")

    assert stats.success is True
    assert stats.total_rows == 2
    assert stats.header_rows_skipped == 1
    assert "Header mismatch" not in caplog.text
