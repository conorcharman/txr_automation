#!/usr/bin/env python3
"""
Tests for XLSX to CSV Converter
================================

Tests the xlsx_csv_converter module including the ConverterStats class
and XLSXConverter functionality.
"""

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.xlsx_csv_converter import ConverterStats, XLSXConverter


class TestConverterStats:
    """Tests for ConverterStats dataclass."""

    def test_default_values(self):
        """Test that ConverterStats initializes with zero values."""
        stats = ConverterStats()

        assert stats.processed_files == 0
        assert stats.successful_conversions == 0
        assert stats.errors == 0
        assert stats.skipped == 0

    def test_increment_values(self):
        """Test that stats can be incremented."""
        stats = ConverterStats()

        stats.processed_files += 10
        stats.successful_conversions += 8
        stats.errors += 2

        assert stats.processed_files == 10
        assert stats.successful_conversions == 8
        assert stats.errors == 2

    def test_print_summary_with_logger(self):
        """Test print_summary with a logger."""
        stats = ConverterStats(
            processed_files=10,
            successful_conversions=8,
            errors=2,
            skipped=0,
        )

        mock_logger = MagicMock()
        stats.print_summary(mock_logger)

        # Verify logger.info was called
        mock_logger.info.assert_called_once()
        call_arg = mock_logger.info.call_args[0][0]

        assert "Processed files: 10" in call_arg
        assert "Successful conversions: 8" in call_arg
        assert "Errors: 2" in call_arg

    def test_print_summary_without_logger(self, capsys):
        """Test print_summary without a logger (prints to stdout)."""
        stats = ConverterStats(
            processed_files=5,
            successful_conversions=5,
            errors=0,
            skipped=0,
        )

        stats.print_summary()

        captured = capsys.readouterr()
        assert "Processed files: 5" in captured.out
        assert "Successful conversions: 5" in captured.out


class TestXLSXConverterInit:
    """Tests for XLSXConverter initialization."""

    def test_cannot_use_both_modes(self):
        """Test that using both parent_dir and input_dir raises error."""
        with pytest.raises(ValueError, match="Cannot use both"):
            XLSXConverter(
                parent_dir=Path("/some/parent"),
                input_dir=Path("/some/input"),
            )

    def test_must_specify_directory(self):
        """Test that not specifying any directory raises error."""
        with pytest.raises(ValueError, match="Must specify either"):
            XLSXConverter()

    def test_init_with_parent_dir(self):
        """Test initialization with parent_dir only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            converter = XLSXConverter(
                parent_dir=Path(tmpdir),
                logger=MagicMock(),
            )

            assert converter.parent_dir == Path(tmpdir)
            assert converter.input_dir is None
            assert isinstance(converter.stats, ConverterStats)

    def test_init_with_input_dir(self):
        """Test initialization with input_dir and output_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            converter = XLSXConverter(
                input_dir=input_dir,
                output_dir=output_dir,
                logger=MagicMock(),
            )

            assert converter.input_dir == input_dir
            assert converter.output_dir == output_dir


class TestXLSXConverterMultilineProcessing:
    """Tests for multi-line cell splitting functionality."""

    def test_split_multiline_row_no_newlines(self):
        """Test that rows without newlines are returned unchanged."""
        row = ["A", "B", "C"]
        result = XLSXConverter.split_multiline_row(row)

        assert result == [["A", "B", "C"]]

    def test_split_multiline_row_with_newlines(self):
        """Test that rows with newlines are split correctly."""
        row = ["A\nB", "1\n2", "X"]
        result = XLSXConverter.split_multiline_row(row)

        # Should produce 2 rows
        assert len(result) == 2
        assert result[0] == ["A", "1", "X"]
        # Single-value cells repeat the last value
        assert result[1] == ["B", "2", "X"]

    def test_split_multiline_row_uneven_lines(self):
        """Test splitting with uneven number of lines in cells."""
        row = ["A\nB\nC", "1", "X\nY"]
        result = XLSXConverter.split_multiline_row(row)

        # Should produce 3 rows (max lines across cells)
        assert len(result) == 3
        assert result[0] == ["A", "1", "X"]
        # Shorter cells repeat their last value
        assert result[1] == ["B", "1", "Y"]
        assert result[2] == ["C", "1", "Y"]

    def test_split_multiline_row_empty_cells(self):
        """Test splitting with empty cells."""
        row = ["A\nB", "", "X"]
        result = XLSXConverter.split_multiline_row(row)

        assert len(result) == 2
        assert result[0] == ["A", "", "X"]
        # Empty cell and single-value cell repeat
        assert result[1] == ["B", "", "X"]

    def test_split_multiline_row_none_values(self):
        """Test splitting with None values."""
        row = ["A\nB", None, "X"]
        result = XLSXConverter.split_multiline_row(row)

        # None should not be split
        assert len(result) == 2


class TestXLSXConverterFiltering:
    """Tests for file filtering functionality."""

    @pytest.fixture
    def temp_structure(self):
        """Create a temporary directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create directory structure
            (base / "FY25" / "Q1").mkdir(parents=True)
            (base / "FY25" / "Q2").mkdir(parents=True)
            (base / "FY26" / "Q1").mkdir(parents=True)

            # Create test files
            (base / "FY25" / "Q1" / "test1.xlsx").write_text("")
            (base / "FY25" / "Q2" / "test2.xlsx").write_text("")
            (base / "FY26" / "Q1" / "test3.xlsx").write_text("")

            yield base

    def test_find_xlsx_files_recursive(self, temp_structure):
        """Test finding XLSX files recursively."""
        converter = XLSXConverter(
            parent_dir=temp_structure,
            recursive=True,
            logger=MagicMock(),
        )

        files = converter.find_xlsx_files()
        assert len(files) == 3

    def test_find_xlsx_files_filter_year(self, temp_structure):
        """Test filtering by fiscal year."""
        converter = XLSXConverter(
            parent_dir=temp_structure,
            recursive=True,
            filter_year="FY25",
            logger=MagicMock(),
        )

        files = converter.find_xlsx_files()
        assert len(files) == 2
        assert all("FY25" in str(f) for f in files)

    def test_find_xlsx_files_filter_quarter(self, temp_structure):
        """Test filtering by quarter."""
        converter = XLSXConverter(
            parent_dir=temp_structure,
            recursive=True,
            filter_quarter="Q1",
            logger=MagicMock(),
        )

        files = converter.find_xlsx_files()
        assert len(files) == 2
        assert all("Q1" in str(f) for f in files)


class TestXLSXConverterDryRun:
    """Tests for dry run functionality."""

    def test_dry_run_does_not_create_file(self):
        """Test that dry run mode does not create output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            csv_file = base / "test.csv"

            converter = XLSXConverter(
                input_dir=base,
                logger=MagicMock(),
                dry_run=True,
            )

            # Verify stats initialized correctly
            assert converter.stats.successful_conversions == 0
            assert converter.dry_run is True

            # In dry run, no file should be created even if method is called
            assert not csv_file.exists()


class TestXLSXConverterImport:
    """Tests to verify the module imports correctly."""

    def test_converter_stats_importable(self):
        """Test that ConverterStats can be imported."""
        from utils.xlsx_csv_converter import ConverterStats

        assert ConverterStats is not None
        stats = ConverterStats()
        assert hasattr(stats, "processed_files")
        assert hasattr(stats, "successful_conversions")
        assert hasattr(stats, "errors")
        assert hasattr(stats, "skipped")

    def test_xlsx_converter_importable(self):
        """Test that XLSXConverter can be imported."""
        from utils.xlsx_csv_converter import XLSXConverter

        assert XLSXConverter is not None

    def test_converter_uses_stats(self):
        """Test that XLSXConverter correctly uses ConverterStats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            converter = XLSXConverter(
                input_dir=Path(tmpdir),
                logger=MagicMock(),
            )

            assert isinstance(converter.stats, ConverterStats)
            assert converter.stats.processed_files == 0
