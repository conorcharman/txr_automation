"""
Tests for AutoFileNamer — deterministic output path generation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.gui.scheduler.file_naming import AutoFileNamer
from src.gui.scheduler.models import TestingPeriod as SchedulerTestingPeriod, ValidationType


_TS = datetime(2026, 4, 1, 9, 0, 0)
_PERIOD = SchedulerTestingPeriod("FY26", "Q2")


class TestAutoFileNamer:
    def test_generate_output_path_filename_pattern(self) -> None:
        """Output path should match the canonical naming pattern."""
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "data/output", _TS
        )
        assert path.name == "buyer_id_FY26_Q2_20260401_0900.csv"

    def test_generate_output_path_directory(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "data/output", _TS
        )
        assert path.parent == Path("data/output")

    def test_generate_output_path_returns_path_object(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "data/output", _TS
        )
        assert isinstance(path, Path)

    def test_generate_output_path_accepts_pathlib_dir(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, Path("data/output"), _TS
        )
        assert path.suffix == ".csv"

    def test_generate_output_path_defaults_to_now(self) -> None:
        """Without an explicit timestamp the method should not raise."""
        path = AutoFileNamer.generate_output_path(
            ValidationType.SELLER_ID, _PERIOD, "data/output"
        )
        assert path.suffix == ".csv"

    def test_generate_log_path_has_log_extension(self) -> None:
        path = AutoFileNamer.generate_log_path(
            ValidationType.BUYER_ID, _PERIOD, "logs", _TS
        )
        assert path.suffix == ".log"
        assert path.parent == Path("logs")

    def test_generate_log_path_same_stem_as_output(self) -> None:
        output = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "data", _TS
        )
        log = AutoFileNamer.generate_log_path(
            ValidationType.BUYER_ID, _PERIOD, "data", _TS
        )
        assert output.stem == log.stem

    def test_generate_extract_path_has_extract_suffix(self) -> None:
        path = AutoFileNamer.generate_extract_path(
            ValidationType.BUYER_ID, _PERIOD, "data/output", _TS
        )
        assert path.name.endswith("_extract.csv")

    def test_type_slug_replaces_hyphens(self) -> None:
        assert AutoFileNamer._type_slug(ValidationType.INCONSISTENT_BUYER_ID) == "inconsistent_buyer_id"

    def test_type_slug_no_hyphens_in_output(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.INCONSISTENT_BUYER_ID, _PERIOD, "out", _TS
        )
        assert "-" not in path.name

    def test_type_slug_non_zero_qty(self) -> None:
        assert AutoFileNamer._type_slug(ValidationType.NON_ZERO_NET_QTY) == "non_zero_net_qty"

    def test_fiscal_year_in_filename(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "out", _TS
        )
        assert "FY26" in path.name

    def test_quarter_in_filename(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "out", _TS
        )
        assert "Q2" in path.name

    def test_timestamp_in_filename(self) -> None:
        path = AutoFileNamer.generate_output_path(
            ValidationType.BUYER_ID, _PERIOD, "out", _TS
        )
        assert "20260401_0900" in path.name

    def test_all_validation_types_generate_valid_paths(self) -> None:
        """Every ValidationType should produce a valid, non-empty filename."""
        for vtype in ValidationType:
            path = AutoFileNamer.generate_output_path(vtype, _PERIOD, "out", _TS)
            assert path.name
            assert path.suffix == ".csv"
            assert "-" not in path.name
