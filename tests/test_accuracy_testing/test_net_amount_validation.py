"""
Tests for Non-Zero Net Amount Validation
==========================================

Unit tests for the NetAmountRecord model and NetAmountValidator
for Incident Code 7_42.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.net_amount_record import NetAmountRecord
from src.accuracy_testing.validators.net_amount_validator import NetAmountValidator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    child_ref: str,
    child_netamt: str,
    parent_ref: str = "PARENT001",
    parent_netamt: str = "3000.00",
    report_status: str = "ACCEPTED",
    trade_date_time: str = "2024-01-15 09:30:00",
) -> NetAmountRecord:
    """Construct a NetAmountRecord with sensible defaults."""
    return NetAmountRecord(
        child_ref=child_ref,
        child_netamt=Decimal(child_netamt),
        parent_ref=parent_ref,
        parent_netamt=Decimal(parent_netamt),
        report_status=report_status,
        trade_date_time=trade_date_time,
    )


# ---------------------------------------------------------------------------
# NetAmountRecord model tests
# ---------------------------------------------------------------------------


class TestNetAmountRecord:
    """Unit tests for the NetAmountRecord dataclass."""

    def test_create_record_with_defaults(self):
        """Test that output fields default to zero and 'N'."""
        record = _make_record("AA2024000001", "1000.00")

        assert record.child_ref == "AA2024000001"
        assert record.child_netamt == Decimal("1000.00")
        assert record.parent_ref == "PARENT001"
        assert record.parent_netamt == Decimal("3000.00")
        assert record.net_amt == Decimal("0")
        assert record.difference == Decimal("0")
        assert record.error == "N"

    def test_from_dict_with_python_keys(self):
        """Test from_dict() using lowercase Python field names."""
        data = {
            "child_ref": "BB2024000002",
            "child_netamt": "500.00",
            "parent_ref": "PARENT002",
            "parent_netamt": "1500.00",
            "report_status": "SUBMITTED",
            "trade_date_time": "2024-03-01 14:00:00",
        }
        record = NetAmountRecord.from_dict(data)

        assert record.child_ref == "BB2024000002"
        assert record.child_netamt == Decimal("500.00")
        assert record.parent_ref == "PARENT002"
        assert record.parent_netamt == Decimal("1500.00")
        assert record.report_status == "SUBMITTED"

    def test_from_dict_with_uppercase_keys(self):
        """Test from_dict() using uppercase SQL column names."""
        data = {
            "CHILD_REF": "CC2024000003",
            "CHILD_NETAMT": "2000.00",
            "PARENT_REF": "PARENT003",
            "PARENT_NETAMT": "2000.00",
            "REPORT_STATUS": "ACCEPTED",
            "TRADE_DATE_TIME": "2024-06-10 08:00:00",
        }
        record = NetAmountRecord.from_dict(data)

        assert record.child_ref == "CC2024000003"
        assert record.child_netamt == Decimal("2000.00")

    def test_from_row_positional(self):
        """Test from_row() using positional CSV values."""
        row = [
            "DD2024000004",
            "750.50",
            "PARENT004",
            "1500.00",
            "DRAFT",
            "2024-09-20 10:00:00",
        ]
        record = NetAmountRecord.from_row(row, row_index=2)

        assert record.child_ref == "DD2024000004"
        assert record.child_netamt == Decimal("750.50")
        assert record.parent_ref == "PARENT004"
        assert record.parent_netamt == Decimal("1500.00")

    def test_from_row_raises_on_too_few_columns(self):
        """Test that from_row() raises ValueError when columns are missing."""
        with pytest.raises(ValueError, match="expected at least 6"):
            NetAmountRecord.from_row(["REF", "100.00", "PARENT"], row_index=3)

    def test_from_dict_null_netamt_defaults_to_zero(self):
        """Test that null/empty net amount values default to Decimal('0')."""
        data = {
            "child_ref": "EE2024000005",
            "child_netamt": None,
            "parent_ref": "PARENT005",
            "parent_netamt": "",
            "report_status": "",
            "trade_date_time": "",
        }
        record = NetAmountRecord.from_dict(data)

        assert record.child_netamt == Decimal("0")
        assert record.parent_netamt == Decimal("0")

    def test_to_dict_output_columns(self):
        """Test that to_dict() includes all 11 expected keys in order."""
        record = _make_record("FF2024000006", "1000.00")
        record.net_amt = Decimal("3000.00")
        record.difference = Decimal("0")
        record.error = "N"

        d = record.to_dict()
        expected_keys = [
            "child_ref",
            "child_netamt",
            "parent_ref",
            "parent_netamt",
            "bulk_ref",
            "bulk_netamt",
            "report_status",
            "trade_date_time",
            "net_amt",
            "difference",
            "error",
        ]
        assert list(d.keys()) == expected_keys
        assert d["error"] == "N"
        assert d["net_amt"] == "3000.00"

    def test_bulk_ref_derived_from_parent_ref(self):
        """bulk_ref is always the first 11 characters of parent_ref."""
        record = _make_record("CHILD001", "100.00", parent_ref="44625CPNJMN1G01")
        assert record.bulk_ref == "44625CPNJMN"

    def test_short_parent_ref_uses_full_string(self):
        """parent_ref shorter than 11 chars uses the full string as bulk_ref."""
        record = _make_record("CHILD001", "100.00", parent_ref="SHORT")
        assert record.bulk_ref == "SHORT"


# ---------------------------------------------------------------------------
# NetAmountValidator deduplication tests
# ---------------------------------------------------------------------------


class TestNetAmountValidatorDeduplication:
    """Tests for deduplicate_group()."""

    def setup_method(self):
        self.validator = NetAmountValidator()

    def test_no_duplicates_returns_all_records(self):
        """All unique child_refs — nothing removed."""
        records = [
            _make_record("CHILD001", "1000.00"),
            _make_record("CHILD002", "2000.00"),
            _make_record("CHILD003", "500.00"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 3
        assert dupes == {}

    def test_duplicate_keeps_first_occurrence(self):
        """Duplicate child_ref — first row (index 0) is retained."""
        records = [
            _make_record("CHILD001", "1000.00"),
            _make_record("CHILD001", "9999.00"),  # duplicate — should be removed
            _make_record("CHILD002", "2000.00"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 2
        assert deduped[0].child_netamt == Decimal("1000.00")  # first occurrence kept
        assert dupes == {"CHILD001": 1}

    def test_multiple_duplicates_same_ref(self):
        """Three rows with the same child_ref — only the first survives."""
        records = [
            _make_record("CHILD001", "1000.00"),
            _make_record("CHILD001", "2000.00"),
            _make_record("CHILD001", "3000.00"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 1
        assert deduped[0].child_netamt == Decimal("1000.00")
        assert dupes == {"CHILD001": 2}

    def test_duplicate_count_accumulates_across_refs(self):
        """Two distinct refs each appearing twice."""
        records = [
            _make_record("CHILD001", "100.00"),
            _make_record("CHILD002", "200.00"),
            _make_record("CHILD001", "99.00"),  # dupe of CHILD001
            _make_record("CHILD002", "88.00"),  # dupe of CHILD002
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 2
        assert dupes == {"CHILD001": 1, "CHILD002": 1}


# ---------------------------------------------------------------------------
# NetAmountValidator validation tests
# ---------------------------------------------------------------------------


class TestNetAmountValidatorValidation:
    """Tests for validate_group() and validate_all()."""

    def setup_method(self):
        self.validator = NetAmountValidator()

    def test_matching_amounts_sets_error_n(self):
        """Sum of child_netamt equals parent_netamt -> error = 'N'."""
        records = [
            _make_record("CHILD001", "1000.00", parent_netamt="3000.00"),
            _make_record("CHILD002", "1000.00", parent_netamt="3000.00"),
            _make_record("CHILD003", "1000.00", parent_netamt="3000.00"),
        ]
        self.validator.validate_group(records)

        for rec in records:
            assert rec.error == "N"
            assert rec.net_amt == Decimal("3000.00")
            assert rec.difference == Decimal("0")

    def test_mismatching_amounts_sets_error_y(self):
        """Sum of child_netamt does not equal parent_netamt -> error = 'Y'."""
        records = [
            _make_record("CHILD001", "1000.00", parent_netamt="3000.00"),
            _make_record("CHILD002", "900.00", parent_netamt="3000.00"),
        ]
        self.validator.validate_group(records)

        for rec in records:
            assert rec.error == "Y"
            assert rec.net_amt == Decimal("1900.00")
            assert rec.difference == Decimal("-1100.00")

    def test_all_records_in_group_share_same_error_flag(self):
        """Every child in a mismatching group carries error = 'Y'."""
        records = [
            _make_record("CHILD001", "500.00", parent_netamt="2000.00"),
            _make_record("CHILD002", "500.00", parent_netamt="2000.00"),
            _make_record("CHILD003", "500.00", parent_netamt="2000.00"),
        ]
        self.validator.validate_group(records)

        assert all(r.error == "Y" for r in records)

    def test_single_child_record(self):
        """A group with one child works correctly."""
        records = [_make_record("CHILD001", "5000.00", parent_netamt="5000.00")]
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].net_amt == Decimal("5000.00")
        assert records[0].difference == Decimal("0")

    def test_validate_group_returns_duplicate_count(self):
        """validate_group() returns the number of duplicates removed."""
        records = [
            _make_record("CHILD001", "1000.00"),
            _make_record("CHILD001", "1000.00"),  # duplicate
            _make_record("CHILD002", "2000.00"),
        ]
        removed = self.validator.validate_group(records)
        assert removed == 1

    def test_validate_group_empty_raises(self):
        """validate_group() raises ValueError on an empty list."""
        with pytest.raises(ValueError):
            self.validator.validate_group([])

    def test_validate_all_multiple_parent_groups(self):
        """Two separate parent groups are each validated independently."""
        parent_a = [
            _make_record(
                "CHILD001", "1000.00", parent_ref="PARENT_A", parent_netamt="2000.00"
            ),
            _make_record(
                "CHILD002", "1000.00", parent_ref="PARENT_A", parent_netamt="2000.00"
            ),
        ]
        parent_b = [
            _make_record(
                "CHILD003", "500.00", parent_ref="PARENT_B", parent_netamt="1000.00"
            ),
            _make_record(
                "CHILD004", "400.00", parent_ref="PARENT_B", parent_netamt="1000.00"
            ),
        ]
        all_records = parent_a + parent_b

        stats = self.validator.validate_all(all_records)

        # PARENT_A: 1000+1000 = 2000 == 2000 -> match
        for rec in parent_a:
            assert rec.error == "N", f"{rec.child_ref} should be N"

        # PARENT_B: 500+400 = 900 != 1000 -> mismatch
        for rec in parent_b:
            assert rec.error == "Y", f"{rec.child_ref} should be Y"

        assert stats["parents_processed"] == 2
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 1
        assert stats["total_records"] == 4

    def test_validate_all_stats_duplicates_removed(self):
        """validate_all() correctly totals duplicates_removed across groups."""
        records = [
            _make_record(
                "CHILD001", "1000.00", parent_ref="P1", parent_netamt="2000.00"
            ),
            _make_record(
                "CHILD001", "1000.00", parent_ref="P1", parent_netamt="2000.00"
            ),  # dupe
            _make_record(
                "CHILD002", "1000.00", parent_ref="P1", parent_netamt="2000.00"
            ),
            _make_record(
                "CHILD003", "500.00", parent_ref="P2", parent_netamt="1000.00"
            ),
            _make_record(
                "CHILD003", "500.00", parent_ref="P2", parent_netamt="1000.00"
            ),  # dupe
            _make_record(
                "CHILD004", "500.00", parent_ref="P2", parent_netamt="1000.00"
            ),
        ]
        stats = self.validator.validate_all(records)

        assert stats["duplicates_removed"] == 2
        assert stats["parents_processed"] == 2

    def test_dedup_does_not_include_duplicate_in_sum(self):
        """Net amount sum uses deduplicated records only — duplicate rows are excluded."""
        # parent_netamt = 3000; only CHILD001 (1000) and CHILD002 (2000) are unique.
        # CHILD001 appears twice — second occurrence must not be added to sum.
        records = [
            _make_record("CHILD001", "1000.00", parent_netamt="3000.00"),
            _make_record(
                "CHILD001", "9999.00", parent_netamt="3000.00"
            ),  # dupe — excluded
            _make_record("CHILD002", "2000.00", parent_netamt="3000.00"),
        ]
        self.validator.validate_group(records)

        # Sum should be 1000+2000=3000, not 1000+9999+2000=12999
        assert records[0].net_amt == Decimal("3000.00")
        assert records[0].error == "N"

    def test_null_netamt_handling(self):
        """Records with missing/null net amount values default to Decimal('0')."""
        records = [
            NetAmountRecord(
                child_ref="CHILD001",
                child_netamt=Decimal("0"),  # default from null
                parent_ref="PARENT001",
                parent_netamt=Decimal("0"),  # default from null
                report_status="",
                trade_date_time="",
            ),
        ]
        # Should not raise; 0 == 0 so error = 'N'
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].difference == Decimal("0")

    def test_decimal_precision_match(self):
        """Net amount comparison handles decimal precision correctly."""
        records = [
            _make_record("CHILD001", "1234.56", parent_netamt="2469.12"),
            _make_record("CHILD002", "1234.56", parent_netamt="2469.12"),
        ]
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].net_amt == Decimal("2469.12")
        assert records[0].difference == Decimal("0")

    def test_negative_net_amount(self):
        """Negative net amounts (sell-side) are handled correctly."""
        records = [
            _make_record("CHILD001", "-1000.00", parent_netamt="-2000.00"),
            _make_record("CHILD002", "-1000.00", parent_netamt="-2000.00"),
        ]
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].net_amt == Decimal("-2000.00")
        assert records[0].difference == Decimal("0")


# ---------------------------------------------------------------------------
# Bulk ref grouping tests
# ---------------------------------------------------------------------------


class TestBulkRefGrouping:
    """Tests that validate_all groups by bulk_ref (first 11 chars of parent_ref)."""

    def setup_method(self):
        self.validator = NetAmountValidator()

    def test_sub_parents_grouped_together(self):
        """Records with different parent_ref but same bulk prefix are grouped together."""
        # Three sub-parents all belonging to bulk ref "44625CPNJMN".
        # All carry the same bulk-level parent_netamt (the SQL SUBSTR join returns
        # the same total for every sub-parent). bulk_netamt = 3500.
        # net_amt = 1000+1500+1000 = 3500 -> N
        records = [
            _make_record(
                "CHILD001",
                "1000.00",
                parent_ref="44625CPNJMN1G01",
                parent_netamt="3500.00",
            ),
            _make_record(
                "CHILD002",
                "1500.00",
                parent_ref="44625CPNJMN1G02",
                parent_netamt="3500.00",
            ),
            _make_record(
                "CHILD003",
                "1000.00",
                parent_ref="44625CPNJMN1G03",
                parent_netamt="3500.00",
            ),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 1
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 0
        for rec in records:
            assert rec.error == "N"
            assert rec.net_amt == Decimal("3500.00")
            assert rec.bulk_netamt == Decimal("3500.00")
            assert rec.difference == Decimal("0")

    def test_sub_parents_mismatch(self):
        """Mismatch is flagged when net child amount != total bulk amount."""
        # Two sub-parents, both carrying the shared bulk-level parent_netamt=2000.
        # Children sum to 2500 -> difference=500 -> error Y.
        records = [
            _make_record(
                "CHILD001",
                "1000.00",
                parent_ref="44625CPNJMN1G01",
                parent_netamt="2000.00",
            ),
            _make_record(
                "CHILD002",
                "1500.00",
                parent_ref="44625CPNJMN1G02",
                parent_netamt="2000.00",
            ),
        ]
        self.validator.validate_all(records)

        for rec in records:
            assert rec.error == "Y"
            assert rec.net_amt == Decimal("2500.00")
            assert rec.bulk_netamt == Decimal("2000.00")
            assert rec.difference == Decimal("500.00")

    def test_distinct_bulk_refs_processed_independently(self):
        """Two different bulk refs produce independent results."""
        records = [
            _make_record(
                "CHILD001",
                "2000.00",
                parent_ref="AAAAAAAAAA1G01",
                parent_netamt="2000.00",
            ),
            _make_record(
                "CHILD002",
                "1000.00",
                parent_ref="BBBBBBBBBB1G01",
                parent_netamt="3000.00",
            ),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 2
        assert records[0].error == "N"  # 2000 == 2000
        assert records[1].error == "Y"  # 1000 != 3000

    def test_sub_parents_carry_same_netamt_no_double_count(self):
        """
        Regression test: bulk_netamt is taken directly from the first record,
        not summed across sub-parents.

        The SQL for 7_42 joins on SUBSTR(parent_ref, 1, 12), so every sub-parent
        in the group carries the same bulk-level parent_netamt. The old (buggy)
        code summed one value per unique parent_ref, inflating bulk_netamt by N
        (the number of distinct sub-parent suffixes). This test verifies the fix.
        """
        # Contract "44625CPNJMN" split across two sub-parents.
        # Both carry the same bulk-level parent_netamt=1000 (the SQL returns
        # the same total for 1G01 and 1G02 via the SUBSTR join).
        # bulk_netamt = 1000 (NOT 2000 as the old summing code would produce).
        # Children: A0000000001(600) + B0000000001(400) = 1000 -> match.
        records = [
            _make_record(
                "A0000000001",
                "600.00",
                parent_ref="44625CPNJMN1G01",
                parent_netamt="1000.00",
            ),
            _make_record(
                "B0000000001",
                "400.00",
                parent_ref="44625CPNJMN1G02",
                parent_netamt="1000.00",
            ),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 1
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 0
        for rec in records:
            assert rec.bulk_netamt == Decimal("1000.00")  # not 2000 (no double-count)
            assert rec.net_amt == Decimal("1000.00")
            assert rec.difference == Decimal("0")
            assert rec.error == "N"


# ---------------------------------------------------------------------------
# Tolerance threshold tests
# ---------------------------------------------------------------------------


class TestNetAmountTolerance:
    """Tests for the ±1.0 difference tolerance applied to 7_42 only."""

    def setup_method(self):
        # Disable per-record scaling so these tests exercise the fixed floor only.
        self.validator = NetAmountValidator(
            tolerance=Decimal("1.0"), tolerance_per_record=Decimal("0")
        )

    def test_exact_zero_still_matches(self):
        """Zero difference is within tolerance -> error N."""
        records = [_make_record("CHILD001", "1000.00", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "N"

    def test_positive_within_tolerance(self):
        """Difference of +0.50 is within ±1.0 -> error N."""
        records = [_make_record("CHILD001", "1000.50", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "N"
        assert records[0].difference == Decimal("0.50")

    def test_negative_within_tolerance(self):
        """Difference of -0.99 is within ±1.0 -> error N."""
        records = [_make_record("CHILD001", "999.01", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "N"
        assert records[0].difference == Decimal("-0.99")

    def test_positive_at_boundary(self):
        """Difference of exactly +1.0 is at the boundary -> error N (inclusive)."""
        records = [_make_record("CHILD001", "1001.00", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "N"
        assert records[0].difference == Decimal("1.00")

    def test_negative_at_boundary(self):
        """Difference of exactly -1.0 is at the boundary -> error N (inclusive)."""
        records = [_make_record("CHILD001", "999.00", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "N"
        assert records[0].difference == Decimal("-1.00")

    def test_positive_just_outside_tolerance(self):
        """Difference of +1.01 exceeds ±1.0 -> error Y."""
        records = [_make_record("CHILD001", "1001.01", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "Y"
        assert records[0].difference == Decimal("1.01")

    def test_negative_just_outside_tolerance(self):
        """Difference of -1.01 exceeds ±1.0 -> error Y."""
        records = [_make_record("CHILD001", "998.99", parent_netamt="1000.00")]
        self.validator.validate_group(records)
        assert records[0].error == "Y"
        assert records[0].difference == Decimal("-1.01")

    def test_custom_tolerance_zero_is_strict(self):
        """tolerance=0 reverts to exact match behaviour."""
        validator = NetAmountValidator(tolerance=Decimal("0"))
        records = [_make_record("CHILD001", "1000.50", parent_netamt="1000.00")]
        validator.validate_group(records)
        assert records[0].error == "Y"

    def test_tolerance_applies_across_all_records_in_group(self):
        """All records in a within-tolerance group receive error N."""
        records = [
            _make_record("CHILD001", "500.50", parent_netamt="1000.00"),
            _make_record("CHILD002", "500.00", parent_netamt="1000.00"),
        ]
        self.validator.validate_group(records)
        # net_amt=1000.50, difference=+0.50, within ±1.0
        assert all(r.error == "N" for r in records)
        assert records[0].difference == Decimal("0.50")


# ---------------------------------------------------------------------------
# Per-record scaling tolerance tests
# ---------------------------------------------------------------------------


class TestNetAmountPerRecordTolerance:
    """Tests for the per-record scaling component of effective tolerance."""

    def test_small_group_uses_fixed_floor(self):
        """For a 2-record group: max(1.0, 0.005×2)=1.0 — floor wins."""
        validator = (
            NetAmountValidator()
        )  # defaults: tolerance=1.0, tolerance_per_record=0.005
        records = [
            _make_record("CHILD001", "500.50", parent_netamt="1000.00"),
            _make_record("CHILD002", "500.00", parent_netamt="1000.00"),
        ]
        validator.validate_group(records)
        # difference=0.50, effective_tolerance=max(1.0, 0.01)=1.0 -> N
        assert records[0].error == "N"

    def test_638_records_difference_1_28_passes(self):
        """638 records: max(1.0, 0.005×638)=3.19 — £1.28 difference passes."""
        validator = NetAmountValidator()
        # 637 records contributing 1.00 each, 1 record contributing 2.28
        # net_amt = 637 + 2.28 = 639.28; parent_netamt = 638.00; difference = +1.28
        records = [
            _make_record(f"C{i:06}", "1.00", parent_netamt="638.00") for i in range(637)
        ] + [_make_record("C000638", "2.28", parent_netamt="638.00")]
        validator.validate_group(records)
        assert records[0].difference == Decimal("1.28")
        assert records[0].error == "N"  # 1.28 <= 3.19

    def test_638_records_difference_4_00_still_errors(self):
        """638 records: difference of 4.00 exceeds scaled tolerance of 3.19 -> Y."""
        validator = NetAmountValidator()
        # net_amt = 637 + 5.00 = 642.00; difference = +4.00
        records = [
            _make_record(f"C{i:06}", "1.00", parent_netamt="638.00") for i in range(637)
        ] + [_make_record("C000638", "5.00", parent_netamt="638.00")]
        validator.validate_group(records)
        assert records[0].difference == Decimal("4.00")
        assert records[0].error == "Y"  # 4.00 > 3.19

    def test_per_record_zero_disables_scaling(self):
        """tolerance_per_record=0 means effective_tolerance is always self.tolerance."""
        validator = NetAmountValidator(
            tolerance=Decimal("1.0"), tolerance_per_record=Decimal("0")
        )
        records = [
            _make_record(f"C{i:06}", "1.00", parent_netamt="638.00") for i in range(637)
        ] + [_make_record("C000638", "2.28", parent_netamt="638.00")]
        # difference=1.28, effective_tolerance=max(1.0, 0)=1.0 -> 1.28 > 1.0 -> Y
        validator.validate_group(records)
        assert records[0].error == "Y"

    def test_scaling_boundary_exactly_at_effective_tolerance(self):
        """Difference equal to the scaled tolerance is accepted (inclusive)."""
        validator = NetAmountValidator()
        # 200 records: effective_tolerance = max(1.0, 0.005×200) = max(1.0, 1.0) = 1.0
        # difference = exactly 1.0 -> N
        records = [
            _make_record(f"C{i:06}", "1.00", parent_netamt="200.00") for i in range(199)
        ] + [_make_record("C000200", "2.00", parent_netamt="200.00")]
        validator.validate_group(records)
        assert records[0].difference == Decimal("1.00")
        assert records[0].error == "N"
