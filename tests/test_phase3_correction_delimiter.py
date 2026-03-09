"""
Tests for Phase 3 Final Lookup: correction field delimiter handling.

Covers the dual-delimiter support in ``_parse_corrections`` and the
``_split_correction_parts`` helper — both the standard ``:`` syntax
inherited from VBA and the ``¬`` alternative that may appear in exported
correction CSVs.
"""

import logging

import pytest

from src.replay.phase_3_final_lookup import ReplayRecordIndex


@pytest.fixture(scope="module")
def index() -> ReplayRecordIndex:
    """Return a ReplayRecordIndex instance with a null logger (no file I/O)."""
    logger = logging.getLogger("test_phase3_correction_delimiter")
    logger.addHandler(logging.NullHandler())
    return ReplayRecordIndex(logger=logger)


# ===========================================================================
# _split_correction_parts  (static method — no instance required)
# ===========================================================================

class TestSplitCorrectionParts:
    """Unit tests for the _split_correction_parts static helper."""

    def test_colon_single_value(self):
        result = ReplayRecordIndex._split_correction_parts("ABC123")
        assert result == ["ABC123"]

    def test_colon_multiple_values(self):
        result = ReplayRecordIndex._split_correction_parts("Val1:Val2:Val3")
        assert result == ["Val1", "Val2", "Val3"]

    def test_colon_strips_whitespace(self):
        result = ReplayRecordIndex._split_correction_parts("  Val1 : Val2 ")
        assert result == ["Val1", "Val2"]

    def test_negation_single_value(self):
        result = ReplayRecordIndex._split_correction_parts("ABC123")
        assert result == ["ABC123"]

    def test_negation_multiple_values(self):
        result = ReplayRecordIndex._split_correction_parts("Val1¬Val2¬Val3")
        assert result == ["Val1", "Val2", "Val3"]

    def test_negation_strips_whitespace(self):
        result = ReplayRecordIndex._split_correction_parts(" Val1 ¬ Val2 ")
        assert result == ["Val1", "Val2"]

    def test_negation_takes_precedence_over_colon(self):
        """If ¬ is present, the string should NOT be split on : as well."""
        # e.g. a value that contains a colon inside it when ¬ is the delimiter
        result = ReplayRecordIndex._split_correction_parts("2020-01-01¬XY:Z")
        assert result == ["2020-01-01", "XY:Z"]

    def test_empty_string(self):
        result = ReplayRecordIndex._split_correction_parts("")
        assert result == [""]


# ===========================================================================
# _parse_corrections  (instance method)
# ===========================================================================

class TestParseCorrectionsColonDelimiter:
    """Baseline tests confirming the existing colon behaviour is unchanged."""

    def test_single_field_colon(self, index):
        result = index._parse_corrections("ID123", "BuyerID")
        assert result == {"BuyerID": "ID123"}

    def test_multiple_fields_colon(self, index):
        result = index._parse_corrections("V1:V2:V3", "F1:F2:F3")
        assert result == {"F1": "V1", "F2": "V2", "F3": "V3"}

    def test_ampersand_combined_fields_colon(self, index):
        result = index._parse_corrections("V1:V2", "F1:F2 & F3")
        assert result == {"F1": "V1", "F2": "V2", "F3": "V2"}

    def test_no_change_sentinel_colon(self, index):
        result = index._parse_corrections("No Change", "")
        assert result == {"No Change": "No Change"}

    def test_empty_correction_returns_empty_dict(self, index):
        result = index._parse_corrections("", "")
        assert result == {}

    def test_empty_field_str_returns_empty_dict(self, index):
        result = index._parse_corrections("V1:V2", "")
        assert result == {}


class TestParseCorrectionsNegationDelimiter:
    """Tests for the ¬ alternative delimiter in both correction and field strings."""

    def test_single_value_negation(self, index):
        result = index._parse_corrections("ID123", "BuyerID")
        assert result == {"BuyerID": "ID123"}

    def test_multiple_values_negation(self, index):
        result = index._parse_corrections("V1¬V2¬V3", "F1¬F2¬F3")
        assert result == {"F1": "V1", "F2": "V2", "F3": "V3"}

    def test_ampersand_combined_fields_negation(self, index):
        """¬ delimiter should compose correctly with the ' & ' field-grouping logic."""
        result = index._parse_corrections("V1¬V2", "F1¬F2 & F3")
        assert result == {"F1": "V1", "F2": "V2", "F3": "V2"}

    def test_negation_strips_whitespace(self, index):
        result = index._parse_corrections(" V1 ¬ V2 ", " F1 ¬ F2 ")
        assert result == {"F1": "V1", "F2": "V2"}

    def test_empty_correction_negation_returns_empty_dict(self, index):
        result = index._parse_corrections("", "")
        assert result == {}

    def test_empty_field_str_negation_returns_empty_dict(self, index):
        """Non-empty ¬-delimited correction but empty field string → still empty dict."""
        result = index._parse_corrections("V1¬V2", "")
        assert result == {}

    def test_no_change_with_negation_returns_sentinel(self, index):
        """'No Change' value with empty field str should still return sentinel."""
        result = index._parse_corrections("No Change", "")
        assert result == {"No Change": "No Change"}

    def test_negation_with_agree_override(self, index):
        """When Agree='N', Suggested Correction with ¬ delimiter is honoured."""
        result = index._parse_corrections(
            correction_str="OldVal1¬OldVal2",
            field_str="F1¬F2",
            agree_str="N",
            suggested_str="NewV1¬NewV2",
            suggested_field_str="F1¬F2",
        )
        assert result == {"F1": "NewV1", "F2": "NewV2"}

    def test_negation_agree_no_suggested_returns_no_change_sentinel(self, index):
        """When Agree='N' with no suggested correction, sentinel is returned regardless
        of the delimiter used in the original correction string."""
        result = index._parse_corrections(
            correction_str="V1¬V2",
            field_str="F1¬F2",
            agree_str="N",
        )
        assert result == {"No Change": "No Change"}

    def test_mismatched_counts_negation(self, index):
        """Fewer fields than values — zip truncates silently (unchanged behaviour)."""
        result = index._parse_corrections("V1¬V2¬V3", "F1¬F2")
        assert result == {"F1": "V1", "F2": "V2"}
