"""
Tests for Phase 4 period-based SQL extraction.

Covers:
- fiscal_period_to_dates date range calculations
- DTFRunner template generation and variable substitution
- SQL_TEMPLATE_MAP coverage of all ValidationType members
- VALIDATION_TYPE_MAP coverage
- period_extract_generator.main() dry-run (no files written)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from src.accuracy_testing.core.dtf_runner import DTFRunner
from src.accuracy_testing.scripts.period_extract_generator import (
    VALIDATION_TYPE_MAP,
    SQL_TEMPLATE_MAP,
    ValidationType,
    fiscal_period_to_dates,
    main,
)


# ---------------------------------------------------------------------------
# fiscal_period_to_dates — date range calculations
# ---------------------------------------------------------------------------

class TestFiscalPeriodToDates:
    """Verify date ranges for all quarters across two fiscal years."""

    def test_fiscal_period_fy26_q1_dates(self) -> None:
        """FY26 Q1 should map to 2025-04-01 to 2025-06-30."""
        start, end = fiscal_period_to_dates("FY26", "Q1")
        assert start == date(2025, 4, 1)
        assert end == date(2025, 6, 30)

    def test_fiscal_period_fy26_q2_dates(self) -> None:
        """FY26 Q2 should map to 2025-07-01 to 2025-09-30."""
        start, end = fiscal_period_to_dates("FY26", "Q2")
        assert start == date(2025, 7, 1)
        assert end == date(2025, 9, 30)

    def test_fiscal_period_fy26_q3_dates(self) -> None:
        """FY26 Q3 should map to 2025-10-01 to 2025-12-31."""
        start, end = fiscal_period_to_dates("FY26", "Q3")
        assert start == date(2025, 10, 1)
        assert end == date(2025, 12, 31)

    def test_fiscal_period_fy26_q4_dates(self) -> None:
        """FY26 Q4 should map to 2026-01-01 to 2026-03-31."""
        start, end = fiscal_period_to_dates("FY26", "Q4")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 31)

    def test_fiscal_period_fy27_q1_dates(self) -> None:
        """FY27 Q1 should map to 2026-04-01 to 2026-06-30."""
        start, end = fiscal_period_to_dates("FY27", "Q1")
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)

    def test_fiscal_period_case_insensitive(self) -> None:
        """Lowercase quarter label should produce the same result as uppercase."""
        start_upper, end_upper = fiscal_period_to_dates("FY26", "Q2")
        start_lower, end_lower = fiscal_period_to_dates("FY26", "q2")
        assert start_lower == start_upper
        assert end_lower == end_upper


# ---------------------------------------------------------------------------
# DTFRunner.generate_dtf — template variable substitution
# ---------------------------------------------------------------------------

class TestDTFRunnerGenerateDtf:
    """Verify that DTFRunner correctly injects SQL and output path into the template."""

    def test_generate_dtf_substitutes_variables(self, tmp_path: Path) -> None:
        """generate_dtf should replace {SQL_QUERY} and {OUTPUT_PATH} in the template.

        Reads the real AS400_DataTransfer_template.dtf, substitutes the
        placeholders, and writes the result to a temp file.
        """
        runner = DTFRunner()
        dtf_path = tmp_path / "test.dtf"
        result = runner.generate_dtf(
            sql_query="SELECT 1 FROM SYSIBM.SYSDUMMY1",
            output_csv_path="/tmp/out.csv",
            dtf_output_path=dtf_path,
        )

        assert result == dtf_path
        assert dtf_path.exists()
        content = dtf_path.read_text(encoding="utf-8")
        assert "SELECT 1 FROM SYSIBM.SYSDUMMY1" in content
        assert "/tmp/out.csv" in content

    def test_generate_dtf_from_template_substitutes_dates(self, tmp_path: Path) -> None:
        """generate_dtf_from_template should substitute {START_DATE} and {END_DATE} from a SQL template."""
        sql_template = tmp_path / "period_test.sql"
        sql_template.write_text(
            "SELECT * FROM TXNRPTSMF WHERE TXN_DATE BETWEEN '{START_DATE}' AND '{END_DATE}'",
            encoding="utf-8",
        )

        runner = DTFRunner()
        dtf_path = tmp_path / "out.dtf"
        result = runner.generate_dtf_from_template(
            sql_template_path=sql_template,
            parameters={"START_DATE": "2025-07-01", "END_DATE": "2025-09-30"},
            output_csv_path=str(tmp_path / "extract.csv"),
            dtf_output_path=dtf_path,
        )

        assert result == dtf_path
        content = dtf_path.read_text(encoding="utf-8")
        assert "2025-07-01" in content
        assert "2025-09-30" in content
        # Original placeholders should be replaced, not present in output.
        assert "{START_DATE}" not in content
        assert "{END_DATE}" not in content

    def test_execute_dtf_returns_false(self) -> None:
        """execute_dtf is a stub that should always return False."""
        runner = DTFRunner()
        result = runner.execute_dtf("nonexistent.dtf")
        assert result is False


# ---------------------------------------------------------------------------
# Path conversion for Windows DTF compatibility
# ---------------------------------------------------------------------------

class TestDTFRunnerPathConversion:
    """Verify Linux-to-Windows path conversion for DTF compatibility."""

    def test_convert_path_windows_path_unchanged(self) -> None:
        """Windows paths should be returned unchanged."""
        win_path = r"C:\Users\ccharm\Documents\data\FY26\Q2\extract.csv"
        result = DTFRunner._convert_path_to_windows(win_path)
        assert result == win_path

    def test_convert_path_linux_app_data(self) -> None:
        """Linux /app/data paths should be converted to Windows format."""
        linux_path = "/app/data/FY26/Q2/accuracy_testing/extracts/csv/extract.csv"
        result = DTFRunner._convert_path_to_windows(linux_path)
        # Should convert to Windows path
        assert "\\" in result or ":" in result
        # Should preserve the relative subdirectory structure
        assert "FY26" in result and "Q2" in result and "extract.csv" in result
        # Should not contain forward slashes from the /app/data prefix
        assert not result.startswith("/app")

    def test_convert_path_linux_app_only(self) -> None:
        """Linux /app paths (not /app/data) should be converted to Windows format."""
        linux_path = "/app/src/accuracy_testing/file.py"
        result = DTFRunner._convert_path_to_windows(linux_path)
        # Should convert to Windows path
        assert "\\" in result or ":" in result
        # Should preserve the relative subdirectory structure
        assert "accuracy_testing" in result and "file.py" in result
        # Should not be a Linux path
        assert not result.startswith("/")

    def test_convert_path_with_env_override(self) -> None:
        """Should use DTF_WINDOWS_APP_DATA_PATH environment variable if set."""
        import os
        from unittest.mock import patch

        linux_path = "/app/data/FY26/Q2/extract.csv"
        custom_base = r"D:\custom\data\location"
        
        with patch.dict(os.environ, {"DTF_WINDOWS_APP_DATA_PATH": custom_base}):
            result = DTFRunner._convert_path_to_windows(linux_path)
            assert result.startswith(r"D:\custom")
            assert "FY26" in result and "Q2" in result

    def test_generate_dtf_converts_linux_paths_to_windows(self, tmp_path: Path) -> None:
        """When given a Linux path, generate_dtf should write Windows path to DTF."""
        runner = DTFRunner()
        
        # Simulate a Docker container Linux path for the CSV output
        linux_csv_path = "/app/data/FY26/Q2/accuracy_testing/extracts/csv/extract.csv"
        dtf_output = tmp_path / "test.dtf"
        
        # Generate DTF with a simple SQL query
        runner.generate_dtf(
            sql_query="SELECT * FROM GLDATA/TXNREPESMA",
            output_csv_path=linux_csv_path,
            dtf_output_path=dtf_output,
        )
        
        # Read the generated DTF and verify it contains a Windows path
        dtf_content = dtf_output.read_text(encoding="utf-8")
        
        # The PCFile should contain a Windows path, not the Linux path
        assert "PCFile=" in dtf_content
        
        # Extract the PCFile line
        pcfile_line = [l for l in dtf_content.split("\n") if l.startswith("PCFile=")][0]
        pcfile_value = pcfile_line.split("=", 1)[1].strip()
        
        # Verify it's a Windows path (has backslashes or drive letter) and not the Linux path
        assert "\\" in pcfile_value or ":" in pcfile_value, f"Expected Windows path, got: {pcfile_value}"
        assert not pcfile_value.startswith("/app"), f"Should not contain Linux path, got: {pcfile_value}"
        assert "FY26" in pcfile_value and "Q2" in pcfile_value


# ---------------------------------------------------------------------------
# SQL_TEMPLATE_MAP / VALIDATION_TYPE_MAP coverage
# ---------------------------------------------------------------------------

class TestTemplateMaps:
    """Verify that the template and validation-type maps are complete."""

    def test_sql_template_map_covers_all_validation_types(self) -> None:
        """SQL_TEMPLATE_MAP must have one entry for every ValidationType member."""
        for vtype in ValidationType:
            assert vtype in SQL_TEMPLATE_MAP, (
                f"SQL_TEMPLATE_MAP is missing an entry for {vtype!r}"
            )

    def test_validation_type_map_covers_all_cli_keys(self) -> None:
        """VALIDATION_TYPE_MAP must map the same number of entries as there are ValidationType members."""
        assert len(VALIDATION_TYPE_MAP) == len(ValidationType)
        for key, value in VALIDATION_TYPE_MAP.items():
            assert isinstance(value, ValidationType), (
                f"VALIDATION_TYPE_MAP[{key!r}] is not a ValidationType: {value!r}"
            )


# ---------------------------------------------------------------------------
# main() dry-run
# ---------------------------------------------------------------------------

class TestPeriodExtractGeneratorMainDryRun:
    """Verify that --dry-run exits without writing any files."""

    def test_period_extract_generator_dry_run(self, tmp_path: Path) -> None:
        """main() with --dry-run should return without writing any files to output_dir."""
        test_argv = [
            "period_extract_generator",
            "--validation-type", "buyer_id",
            "--fiscal-year", "FY26",
            "--quarter", "Q2",
            "--output-dir", str(tmp_path),
            "--dry-run",
        ]
        with patch.object(sys, "argv", test_argv):
            main()  # Should return cleanly with no SystemExit.

        # No files should have been created in the output directory.
        assert list(tmp_path.iterdir()) == []
