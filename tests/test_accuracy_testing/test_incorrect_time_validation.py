"""
Tests for IncorrectTime validation (Incident Code 7_30).

Covers:
- Exact match (datetimes identical to the second)
- Mismatch by 1 second
- Microsecond-only difference → treated as match
- Mismatch by minutes
- Mismatch by hours
- Mismatch by days
- Missing parent_datetime → error=Y, time_difference='parent datetime missing'
- validate_all stats aggregation
- _format_difference edge cases (plural/singular units)
- IncorrectTimeRecord construction and derived fields
"""

from datetime import timedelta

import pytest

from src.accuracy_testing.models.incorrect_time_record import (
    BULK_REF_LENGTH,
    PARENT_DATETIME_MISSING,
    IncorrectTimeRecord,
)
from src.accuracy_testing.validators.incorrect_time_validator import (
    IncorrectTimeValidator,
    _format_difference,
    _parse_datetime,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_record(
    child_ref: str = "AA2024A00001",
    child_datetime: str = "2024-01-15-09.30.00.000000",
    parent_ref: str = "AA2024A00011",
    parent_datetime: str = "2024-01-15-09.30.00.000000",
) -> IncorrectTimeRecord:
    return IncorrectTimeRecord(
        child_ref=child_ref,
        child_datetime=child_datetime,
        parent_ref=parent_ref,
        parent_datetime=parent_datetime,
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestIncorrectTimeRecord:

    def test_bulk_ref_derived_from_parent_ref(self):
        record = make_record(parent_ref="AA2024A00011G01")
        assert record.bulk_ref == "AA2024A0001"
        assert len(record.bulk_ref) == BULK_REF_LENGTH

    def test_from_dict(self):
        data = {
            "child_ref": "XX2025B00001",
            "child_datetime": "2025-03-10-14.00.00.000000",
            "parent_ref": "XX2025B00011",
            "parent_datetime": "2025-03-10-14.00.00.000000",
        }
        record = IncorrectTimeRecord.from_dict(data)
        assert record.child_ref == "XX2025B00001"
        assert record.bulk_ref == "XX2025B0001"

    def test_from_dict_uppercase_keys(self):
        data = {
            "CHILD_REF": "XX2025B00001",
            "CHILD_DATETIME": "2025-03-10-14.00.00.000000",
            "PARENT_REF": "XX2025B00011",
            "PARENT_DATETIME": "2025-03-10-14.00.00.000000",
        }
        record = IncorrectTimeRecord.from_dict(data)
        assert record.child_ref == "XX2025B00001"

    def test_from_row(self):
        row = [
            "AA2024A00001",
            "2024-01-15-09.30.00.000000",
            "AA2024A00011",
            "2024-01-15-09.30.00.000000",
        ]
        record = IncorrectTimeRecord.from_row(row, row_index=2)
        assert record.child_ref == "AA2024A00001"
        assert record.parent_ref == "AA2024A00011"

    def test_from_row_too_few_columns(self):
        with pytest.raises(ValueError, match="expected at least 4"):
            IncorrectTimeRecord.from_row(["only", "three"], row_index=5)

    def test_to_dict_keys(self):
        record = make_record()
        d = record.to_dict()
        assert set(d.keys()) == {
            "child_ref",
            "child_datetime",
            "parent_ref",
            "parent_datetime",
            "bulk_ref",
            "time_difference",
            "error",
        }

    def test_default_output_fields(self):
        record = make_record()
        assert record.error == "N"
        assert record.time_difference == ""


# ---------------------------------------------------------------------------
# _format_difference tests
# ---------------------------------------------------------------------------


class TestFormatDifference:

    def test_seconds_singular(self):
        assert _format_difference(timedelta(seconds=1)) == "1 second"

    def test_seconds_plural(self):
        assert _format_difference(timedelta(seconds=45)) == "45 seconds"

    def test_minutes_only(self):
        assert _format_difference(timedelta(minutes=2)) == "2 minutes"

    def test_minutes_and_seconds(self):
        assert _format_difference(timedelta(seconds=90)) == "1 minute 30 seconds"

    def test_hours_only(self):
        assert _format_difference(timedelta(hours=3)) == "3 hours"

    def test_hours_and_minutes(self):
        assert _format_difference(timedelta(hours=1, minutes=5)) == "1 hour 5 minutes"

    def test_hours_no_minutes(self):
        # Exactly 2 hours, no minutes component shown
        assert _format_difference(timedelta(hours=2)) == "2 hours"

    def test_days_and_hours(self):
        assert _format_difference(timedelta(days=1, hours=3)) == "1 day 3 hours"

    def test_days_no_hours(self):
        assert _format_difference(timedelta(days=2)) == "2 days"

    def test_zero_seconds(self):
        assert _format_difference(timedelta(seconds=0)) == "0 seconds"


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


class TestIncorrectTimeValidator:

    def setup_method(self):
        self.validator = IncorrectTimeValidator(verbose=False)

    def test_exact_match(self):
        record = make_record(
            child_datetime="2024-01-15-09.30.00.000000",
            parent_datetime="2024-01-15-09.30.00.000000",
        )
        self.validator.validate_record(record)
        assert record.error == "N"
        assert record.time_difference == ""

    def test_microsecond_only_diff_is_match(self):
        """Microsecond differences must not trigger an error."""
        record = make_record(
            child_datetime="2024-01-15-09.30.00.123456",
            parent_datetime="2024-01-15-09.30.00.999999",
        )
        self.validator.validate_record(record)
        assert record.error == "N"
        assert record.time_difference == ""

    def test_one_second_mismatch(self):
        record = make_record(
            child_datetime="2024-01-15-09.30.01.000000",
            parent_datetime="2024-01-15-09.30.00.000000",
        )
        self.validator.validate_record(record)
        assert record.error == "Y"
        assert record.time_difference == "1 second"

    def test_minutes_mismatch(self):
        record = make_record(
            child_datetime="2024-01-15-09.32.30.000000",
            parent_datetime="2024-01-15-09.30.00.000000",
        )
        self.validator.validate_record(record)
        assert record.error == "Y"
        assert record.time_difference == "2 minutes 30 seconds"

    def test_hours_mismatch(self):
        record = make_record(
            child_datetime="2024-01-15-11.30.00.000000",
            parent_datetime="2024-01-15-09.30.00.000000",
        )
        self.validator.validate_record(record)
        assert record.error == "Y"
        assert record.time_difference == "2 hours"

    def test_missing_parent_datetime(self):
        record = make_record(parent_datetime="")
        self.validator.validate_record(record)
        assert record.error == "Y"
        assert record.time_difference == PARENT_DATETIME_MISSING

    def test_validate_all_stats(self):
        records = [
            make_record(
                child_datetime="2024-01-15-09.30.00.000000",
                parent_datetime="2024-01-15-09.30.00.000000",
            ),
            make_record(
                child_ref="AA2024A00002",
                child_datetime="2024-01-15-09.31.00.000000",
                parent_datetime="2024-01-15-09.30.00.000000",
            ),
            make_record(
                child_ref="AA2024A00003",
                child_datetime="2024-01-15-09.30.00.000000",
                parent_datetime="",
            ),
        ]
        stats = self.validator.validate_all(records)
        assert stats["total"] == 3
        assert stats["matches"] == 1
        assert stats["errors"] == 2
        assert stats["missing"] == 1
        assert stats["parse_errors"] == 0

    def test_all_records_mutated(self):
        """validate_all mutates records in place."""
        records = [
            make_record(
                child_datetime="2024-01-15-09.30.00.000000",
                parent_datetime="2024-01-15-09.30.00.000000",
            ),
            make_record(
                child_ref="AA2024A00002",
                child_datetime="2024-01-15-10.00.00.000000",
                parent_datetime="2024-01-15-09.30.00.000000",
            ),
        ]
        self.validator.validate_all(records)
        assert records[0].error == "N"
        assert records[1].error == "Y"
        assert records[1].time_difference == "30 minutes"
