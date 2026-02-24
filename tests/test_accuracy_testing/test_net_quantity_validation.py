"""
Tests for Non-Zero Net Quantity Validation
===========================================

Unit tests for the NetQuantityRecord model and NetQuantityValidator
for Incident Code 7_6.
"""

import pytest
from decimal import Decimal
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.net_quantity_record import NetQuantityRecord
from src.accuracy_testing.validators.net_quantity_validator import NetQuantityValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    child_ref: str,
    child_qty: str,
    parent_ref: str = "PARENT001",
    parent_qty: str = "300",
    report_status: str = "ACCEPTED",
    trade_date_time: str = "2024-01-15 09:30:00",
) -> NetQuantityRecord:
    """Construct a NetQuantityRecord with sensible defaults."""
    return NetQuantityRecord(
        child_ref=child_ref,
        child_qty=Decimal(child_qty),
        parent_ref=parent_ref,
        parent_qty=Decimal(parent_qty),
        report_status=report_status,
        trade_date_time=trade_date_time,
    )


# ---------------------------------------------------------------------------
# NetQuantityRecord model tests
# ---------------------------------------------------------------------------

class TestNetQuantityRecord:
    """Unit tests for the NetQuantityRecord dataclass."""

    def test_create_record_with_defaults(self):
        """Test that output fields default to zero and 'N'."""
        record = _make_record("AA2024000001", "100")

        assert record.child_ref == "AA2024000001"
        assert record.child_qty == Decimal("100")
        assert record.parent_ref == "PARENT001"
        assert record.parent_qty == Decimal("300")
        assert record.net_qty == Decimal("0")
        assert record.difference == Decimal("0")
        assert record.error == "N"

    def test_from_dict_with_python_keys(self):
        """Test from_dict() using lowercase Python field names."""
        data = {
            "child_ref": "BB2024000002",
            "child_qty": "50",
            "parent_ref": "PARENT002",
            "parent_qty": "150",
            "report_status": "SUBMITTED",
            "trade_date_time": "2024-03-01 14:00:00",
        }
        record = NetQuantityRecord.from_dict(data)

        assert record.child_ref == "BB2024000002"
        assert record.child_qty == Decimal("50")
        assert record.parent_ref == "PARENT002"
        assert record.parent_qty == Decimal("150")
        assert record.report_status == "SUBMITTED"

    def test_from_dict_with_uppercase_keys(self):
        """Test from_dict() using uppercase SQL column names."""
        data = {
            "CHILD_REF": "CC2024000003",
            "CHILD_QTY": "200",
            "PARENT_REF": "PARENT003",
            "PARENT_QTY": "200",
            "REPORT_STATUS": "ACCEPTED",
            "TRADE_DATE_TIME": "2024-06-10 08:00:00",
        }
        record = NetQuantityRecord.from_dict(data)

        assert record.child_ref == "CC2024000003"
        assert record.child_qty == Decimal("200")

    def test_from_row_positional(self):
        """Test from_row() using positional CSV values."""
        row = ["DD2024000004", "75", "PARENT004", "150", "DRAFT", "2024-09-20 10:00:00"]
        record = NetQuantityRecord.from_row(row, row_index=2)

        assert record.child_ref == "DD2024000004"
        assert record.child_qty == Decimal("75")
        assert record.parent_ref == "PARENT004"
        assert record.parent_qty == Decimal("150")

    def test_from_row_raises_on_too_few_columns(self):
        """Test that from_row() raises ValueError when columns are missing."""
        with pytest.raises(ValueError, match="expected at least 6"):
            NetQuantityRecord.from_row(["REF", "100", "PARENT"], row_index=3)

    def test_from_dict_null_qty_defaults_to_zero(self):
        """Test that null/empty quantity values default to Decimal('0')."""
        data = {
            "child_ref": "EE2024000005",
            "child_qty": None,
            "parent_ref": "PARENT005",
            "parent_qty": "",
            "report_status": "",
            "trade_date_time": "",
        }
        record = NetQuantityRecord.from_dict(data)

        assert record.child_qty == Decimal("0")
        assert record.parent_qty == Decimal("0")

    def test_to_dict_output_columns(self):
        """Test that to_dict() includes all 11 expected keys in order."""
        record = _make_record("FF2024000006", "100")
        record.net_qty = Decimal("300")
        record.difference = Decimal("0")
        record.error = "N"

        d = record.to_dict()
        expected_keys = [
            "child_ref", "child_qty", "parent_ref", "parent_qty",
            "bulk_ref", "bulk_qty",
            "report_status", "trade_date_time", "net_qty", "difference", "error",
        ]
        assert list(d.keys()) == expected_keys
        assert d["error"] == "N"
        assert d["net_qty"] == "300"


# ---------------------------------------------------------------------------
# NetQuantityValidator deduplication tests
# ---------------------------------------------------------------------------

class TestNetQuantityValidatorDeduplication:
    """Tests for deduplicate_group()."""

    def setup_method(self):
        self.validator = NetQuantityValidator()

    def test_no_duplicates_returns_all_records(self):
        """All unique child_refs — nothing removed."""
        records = [
            _make_record("CHILD001", "100"),
            _make_record("CHILD002", "200"),
            _make_record("CHILD003", "50"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 3
        assert dupes == {}

    def test_duplicate_keeps_first_occurrence(self):
        """Duplicate child_ref — first row (index 0) is retained."""
        records = [
            _make_record("CHILD001", "100"),
            _make_record("CHILD001", "999"),  # duplicate — should be removed
            _make_record("CHILD002", "200"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 2
        assert deduped[0].child_qty == Decimal("100")  # first occurrence kept
        assert dupes == {"CHILD001": 1}

    def test_multiple_duplicates_same_ref(self):
        """Three rows with the same child_ref — only the first survives."""
        records = [
            _make_record("CHILD001", "100"),
            _make_record("CHILD001", "200"),
            _make_record("CHILD001", "300"),
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 1
        assert deduped[0].child_qty == Decimal("100")
        assert dupes == {"CHILD001": 2}

    def test_duplicate_count_accumulates_across_refs(self):
        """Two distinct refs each appearing twice."""
        records = [
            _make_record("CHILD001", "10"),
            _make_record("CHILD002", "20"),
            _make_record("CHILD001", "99"),  # dupe of CHILD001
            _make_record("CHILD002", "88"),  # dupe of CHILD002
        ]
        deduped, dupes = self.validator.deduplicate_group(records)

        assert len(deduped) == 2
        assert dupes == {"CHILD001": 1, "CHILD002": 1}


# ---------------------------------------------------------------------------
# NetQuantityValidator validation tests
# ---------------------------------------------------------------------------

class TestNetQuantityValidatorValidation:
    """Tests for validate_group() and validate_all()."""

    def setup_method(self):
        self.validator = NetQuantityValidator()

    def test_matching_quantities_sets_error_n(self):
        """Sum of child_qty equals parent_qty → error = 'N'."""
        records = [
            _make_record("CHILD001", "100", parent_qty="300"),
            _make_record("CHILD002", "100", parent_qty="300"),
            _make_record("CHILD003", "100", parent_qty="300"),
        ]
        self.validator.validate_group(records)

        for rec in records:
            assert rec.error == "N"
            assert rec.net_qty == Decimal("300")
            assert rec.difference == Decimal("0")

    def test_mismatching_quantities_sets_error_y(self):
        """Sum of child_qty does not equal parent_qty → error = 'Y'."""
        records = [
            _make_record("CHILD001", "100", parent_qty="300"),
            _make_record("CHILD002", "90", parent_qty="300"),
        ]
        self.validator.validate_group(records)

        for rec in records:
            assert rec.error == "Y"
            assert rec.net_qty == Decimal("190")
            assert rec.difference == Decimal("-110")

    def test_all_records_in_group_share_same_error_flag(self):
        """Every child in a mismatching group carries error = 'Y'."""
        records = [
            _make_record("CHILD001", "50", parent_qty="200"),
            _make_record("CHILD002", "50", parent_qty="200"),
            _make_record("CHILD003", "50", parent_qty="200"),
        ]
        self.validator.validate_group(records)

        assert all(r.error == "Y" for r in records)

    def test_single_child_record(self):
        """A group with one child works correctly."""
        records = [_make_record("CHILD001", "500", parent_qty="500")]
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].net_qty == Decimal("500")
        assert records[0].difference == Decimal("0")

    def test_validate_group_returns_duplicate_count(self):
        """validate_group() returns the number of duplicates removed."""
        records = [
            _make_record("CHILD001", "100"),
            _make_record("CHILD001", "100"),  # duplicate
            _make_record("CHILD002", "200"),
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
            _make_record("CHILD001", "100", parent_ref="PARENT_A", parent_qty="200"),
            _make_record("CHILD002", "100", parent_ref="PARENT_A", parent_qty="200"),
        ]
        parent_b = [
            _make_record("CHILD003", "50", parent_ref="PARENT_B", parent_qty="100"),
            _make_record("CHILD004", "40", parent_ref="PARENT_B", parent_qty="100"),
        ]
        all_records = parent_a + parent_b

        stats = self.validator.validate_all(all_records)

        # PARENT_A: 100+100 = 200 == 200 → match
        for rec in parent_a:
            assert rec.error == "N", f"{rec.child_ref} should be N"

        # PARENT_B: 50+40 = 90 != 100 → mismatch
        for rec in parent_b:
            assert rec.error == "Y", f"{rec.child_ref} should be Y"

        assert stats["parents_processed"] == 2
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 1
        assert stats["total_records"] == 4

    def test_validate_all_stats_duplicates_removed(self):
        """validate_all() correctly totals duplicates_removed across groups."""
        records = [
            _make_record("CHILD001", "100", parent_ref="P1", parent_qty="200"),
            _make_record("CHILD001", "100", parent_ref="P1", parent_qty="200"),  # dupe
            _make_record("CHILD002", "100", parent_ref="P1", parent_qty="200"),
            _make_record("CHILD003", "50", parent_ref="P2", parent_qty="100"),
            _make_record("CHILD003", "50", parent_ref="P2", parent_qty="100"),   # dupe
            _make_record("CHILD004", "50", parent_ref="P2", parent_qty="100"),
        ]
        stats = self.validator.validate_all(records)

        assert stats["duplicates_removed"] == 2
        assert stats["parents_processed"] == 2

    def test_dedup_does_not_include_duplicate_in_sum(self):
        """Qty sum uses deduplicated records only — duplicate rows are excluded."""
        # parent_qty = 300; only CHILD001 (100) and CHILD002 (200) are unique.
        # CHILD001 appears twice — second occurrence must not be added to sum.
        records = [
            _make_record("CHILD001", "100", parent_qty="300"),
            _make_record("CHILD001", "999", parent_qty="300"),  # dupe — excluded
            _make_record("CHILD002", "200", parent_qty="300"),
        ]
        self.validator.validate_group(records)

        # Sum should be 100+200=300, not 100+999+200=1299
        assert records[0].net_qty == Decimal("300")
        assert records[0].error == "N"

    def test_null_qty_handling(self):
        """Records with missing/null qty values default to Decimal('0')."""
        records = [
            NetQuantityRecord(
                child_ref="CHILD001",
                child_qty=Decimal("0"),  # default from null
                parent_ref="PARENT001",
                parent_qty=Decimal("0"),  # default from null
                report_status="",
                trade_date_time="",
            ),
        ]
        # Should not raise; 0 == 0 so error = 'N'
        self.validator.validate_group(records)

        assert records[0].error == "N"
        assert records[0].difference == Decimal("0")


# ---------------------------------------------------------------------------
# Bulk ref grouping tests
# ---------------------------------------------------------------------------

class TestBulkRefGrouping:
    """Tests that validate_all groups by bulk_ref (first 10 chars of parent_ref)."""

    def setup_method(self):
        self.validator = NetQuantityValidator()

    def test_bulk_ref_derived_from_parent_ref(self):
        """bulk_ref is always the first 10 characters of parent_ref."""
        record = _make_record("CHILD001", "100", parent_ref="44625CPNJMN1G01")
        assert record.bulk_ref == "44625CPNJMN"

    def test_short_parent_ref_uses_full_string(self):
        """parent_ref shorter than 10 chars uses the full string as bulk_ref."""
        record = _make_record("CHILD001", "100", parent_ref="SHORT")
        assert record.bulk_ref == "SHORT"

    def test_sub_parents_grouped_together(self):
        """Records with different parent_ref but same bulk prefix are summed together."""
        # Three sub-parents all belonging to bulk ref "44625CPNJMN".
        # Each carries its own parent_qty (its portion of the contract).
        # bulk_qty = sum of unique parent quantities = 100+150+100 = 350
        # net_qty  = sum of child quantities        = 100+150+100 = 350 -> N
        records = [
            _make_record("CHILD001", "100", parent_ref="44625CPNJMN1G01", parent_qty="100"),
            _make_record("CHILD002", "150", parent_ref="44625CPNJMN1G02", parent_qty="150"),
            _make_record("CHILD003", "100", parent_ref="44625CPNJMN1G03", parent_qty="100"),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 1
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 0
        for rec in records:
            assert rec.error == "N"
            assert rec.net_qty == Decimal("350")
            assert rec.bulk_qty == Decimal("350")
            assert rec.difference == Decimal("0")

    def test_sub_parents_mismatch(self):
        """Mismatch is flagged when net child quantity != total bulk quantity."""
        # Two sub-parents, each with parent_qty=200 -> bulk_qty=400.
        # Children sum to 250 -> difference=-150 -> error Y.
        records = [
            _make_record("CHILD001", "100", parent_ref="44625CPNJMN1G01", parent_qty="200"),
            _make_record("CHILD002", "150", parent_ref="44625CPNJMN1G02", parent_qty="200"),
        ]
        self.validator.validate_all(records)

        for rec in records:
            assert rec.error == "Y"
            assert rec.net_qty == Decimal("250")
            assert rec.bulk_qty == Decimal("400")
            assert rec.difference == Decimal("-150")

    def test_distinct_bulk_refs_processed_independently(self):
        """Two different bulk refs produce independent results."""
        records = [
            _make_record("CHILD001", "200", parent_ref="AAAAAAAAAA1G01", parent_qty="200"),
            _make_record("CHILD002", "100", parent_ref="BBBBBBBBBB1G01", parent_qty="300"),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 2
        assert records[0].error == "N"   # 200 == 200
        assert records[1].error == "Y"   # 100 != 300

    def test_bulk_ref_in_to_dict(self):
        """to_dict() includes bulk_ref and bulk_qty positioned after parent_qty."""
        record = _make_record("CHILD001", "100", parent_ref="44625CPNJMN1G01")
        d = record.to_dict()
        keys = list(d.keys())
        assert "bulk_ref" in keys
        assert "bulk_qty" in keys
        pq_idx = keys.index("parent_qty")
        assert keys.index("bulk_ref") == pq_idx + 1
        assert keys.index("bulk_qty") == pq_idx + 2
        assert d["bulk_ref"] == "44625CPNJMN"

    def test_bulk_qty_sums_unique_parent_quantities(self):
        """
        Regression test: bulk_qty is the SUM of unique parent quantities.

        Previously, validate_group() compared net_qty against records[0].parent_qty
        (a single sub-parent quantity). When a contract was split across multiple
        sub-parents (e.g. 1G01/1G02/1G03) each carrying their own parent_qty, the
        net child sum matched the TOTAL contract but was incorrectly flagged as a
        mismatch against one sub-parent's quantity alone.

        This test asserts that the corrected logic sums all unique parent_qty values
        to form bulk_qty and compares net_qty against that total.
        """
        # Contract "44625CPNJMN" split across three sub-parents:
        #   1G01 -> parent_qty=500,  children sum = 500
        #   1G02 -> parent_qty=300,  children sum = 300
        #   1G03 -> parent_qty=200,  children sum = 200
        # bulk_qty = 500+300+200 = 1000; net_qty = 1000 -> match
        records = [
            _make_record("A0000000001", "300", parent_ref="44625CPNJMN1G01", parent_qty="500"),
            _make_record("A0000000002", "200", parent_ref="44625CPNJMN1G01", parent_qty="500"),
            _make_record("B0000000001", "300", parent_ref="44625CPNJMN1G02", parent_qty="300"),
            _make_record("C0000000001", "100", parent_ref="44625CPNJMN1G03", parent_qty="200"),
            _make_record("C0000000002", "100", parent_ref="44625CPNJMN1G03", parent_qty="200"),
        ]
        stats = self.validator.validate_all(records)

        assert stats["parents_processed"] == 1
        assert stats["match_groups"] == 1
        assert stats["error_groups"] == 0
        for rec in records:
            assert rec.bulk_qty == Decimal("1000")
            assert rec.net_qty == Decimal("1000")
            assert rec.difference == Decimal("0")
            assert rec.error == "N"

    def test_exact_10_char_parent_ref(self):
        """parent_ref of exactly 10 characters uses the entire string as bulk_ref."""
        record = _make_record("CHILD001", "100", parent_ref="1234567890")
        assert record.bulk_ref == "1234567890"
