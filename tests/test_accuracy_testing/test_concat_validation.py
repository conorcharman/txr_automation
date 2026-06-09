#!/usr/bin/env python3
"""
Test CONCAT Name-Segment Validation
=====================================

Tests for the semantic cross-check that compares the name segments embedded
in an existing CONCAT ID against the record's ``first_name`` and ``surname``
fields.  This covers ``_validate_concat_name_segments()`` directly and the
integration through ``_validate_existing_id()`` and ``process_record()``.

Version 1.0 Changes:
- Initial test suite for CONCAT prefix-in-segment detection

Usage:
    pytest tests/test_accuracy_testing/test_concat_validation.py -v
"""

import pytest

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def processor() -> IDValidationProcessor:
    """Return a processor instance configured for buyer records."""
    return IDValidationProcessor(
        client_type="buyer",
        logger=None,
        verbose=False,
    )


def _make_record(**kwargs) -> ClientRecord:
    """Build a minimal ClientRecord, overriding defaults with kwargs."""
    defaults = dict(
        row_index=0,
        transaction_ref="TEST001",
        account_id="ACC001",
        person_code="PER001",
        account_type="P",
        id_value="GB19800101JANE#SMITH",
        id_type="CONCAT",
        first_name="JANE",
        surname="SMITH",
        date_of_birth="1980-01-01",
        gender="F",
        primary_nationality="GB",
    )
    defaults.update(kwargs)
    return ClientRecord(**defaults)


# ---------------------------------------------------------------------------
# Unit tests: _validate_concat_name_segments()
# ---------------------------------------------------------------------------


class TestValidateConcatNameSegments:
    """Direct unit tests for _validate_concat_name_segments()."""

    def test_correct_segments_pass(self, processor: IDValidationProcessor) -> None:
        """A CONCAT whose segments match the record names must pass."""
        # GB19800101JANE#SMITH
        # [10:15] = JANE#   [15:20] = SMITH
        valid, msg = processor._validate_concat_name_segments(
            "GB19800101JANE#SMITH", "JANE", "SMITH"
        )
        assert valid is True, f"Expected pass, got error: {msg}"
        assert msg == ""

    def test_prefix_included_in_surname_segment_fails(
        self, processor: IDValidationProcessor
    ) -> None:
        """A CONCAT whose surname segment encodes the prefix must fail.

        surname='VAN SMITH' → expected segment 'SMITH', not 'VANSM'.
        """
        # Manually construct a 20-char CONCAT with 'VANSM' at [15:20]
        id_value = "GB19800101JANE#VANSM"
        valid, msg = processor._validate_concat_name_segments(
            id_value, "JANE", "VAN SMITH"
        )
        assert valid is False
        assert "VANSM" in msg, f"Expected 'VANSM' in error message, got: {msg}"
        assert (
            "SMITH" in msg
        ), f"Expected expected segment 'SMITH' in error message, got: {msg}"

    def test_correct_prefix_stripped_surname_passes(
        self, processor: IDValidationProcessor
    ) -> None:
        """A CONCAT whose surname segment correctly strips the VAN prefix must pass.

        surname='VAN SMITH' → expected segment 'SMITH'.
        """
        # [15:20] = SMITH
        id_value = "GB19800101JANE#SMITH"
        valid, msg = processor._validate_concat_name_segments(
            id_value, "JANE", "VAN SMITH"
        )
        assert valid is True, f"Expected pass, got error: {msg}"

    def test_first_name_segment_mismatch_fails(
        self, processor: IDValidationProcessor
    ) -> None:
        """A CONCAT with the wrong first-name segment must fail."""
        # [10:15] = WRONG does not match expected 'JANE#'
        id_value = "GB19800101WRONGSMITH"
        valid, msg = processor._validate_concat_name_segments(id_value, "JANE", "SMITH")
        assert valid is False
        assert "first-name segment" in msg.lower() or "first-name" in msg

    def test_missing_surname_skips_check(
        self, processor: IDValidationProcessor
    ) -> None:
        """When surname is absent the check must be skipped (returns True)."""
        # Even with a clearly wrong segment, absence of surname skips the check
        valid, msg = processor._validate_concat_name_segments(
            "GB19800101JANE#VANSM", "JANE", ""
        )
        assert valid is True
        assert msg == ""

    def test_missing_first_name_skips_check(
        self, processor: IDValidationProcessor
    ) -> None:
        """When first_name is absent the check must be skipped (returns True)."""
        valid, msg = processor._validate_concat_name_segments(
            "GB19800101WRONGSMITH", "", "SMITH"
        )
        assert valid is True
        assert msg == ""

    def test_both_names_missing_skips_check(
        self, processor: IDValidationProcessor
    ) -> None:
        """When both name fields are absent the check is skipped."""
        valid, msg = processor._validate_concat_name_segments(
            "GB19800101WRONGWRONG", "", ""
        )
        assert valid is True
        assert msg == ""

    def test_von_der_prefix_stripped_correctly(
        self, processor: IDValidationProcessor
    ) -> None:
        """VON DER compound prefix is stripped; remaining parts form the segment."""
        # surname='VON DER BERG' → _clean_name_for_concat → 'BERG#'
        id_value = "DE19900515HANS#BERG#"
        valid, msg = processor._validate_concat_name_segments(
            id_value, "HANS", "VON DER BERG"
        )
        assert valid is True, f"Expected pass, got error: {msg}"

    def test_hyphenated_surname_handled_correctly(
        self, processor: IDValidationProcessor
    ) -> None:
        """Hyphenated surplus name cleans to expected 5-char segment."""
        # surname='ROIG-MEYN' → _clean_name_for_concat(is_surname=True) → 'ROIGM'
        id_value = "GB20110301ROGERROIGM"
        valid, msg = processor._validate_concat_name_segments(
            id_value, "ROGER", "ROIG-MEYN"
        )
        assert valid is True, f"Expected pass, got error: {msg}"


# ---------------------------------------------------------------------------
# Integration tests: _validate_existing_id() with name parameters
# ---------------------------------------------------------------------------


class TestValidateExistingIdConcatNameCheck:
    """Integration tests through _validate_existing_id()."""

    def test_concat_with_prefix_in_segment_fails_validation(
        self, processor: IDValidationProcessor
    ) -> None:
        """_validate_existing_id() must fail a CONCAT whose surname segment
        includes the prefix."""
        is_valid, error = processor._validate_existing_id(
            "GB19800101JANE#VANSM",
            "CONCAT",
            "GB",
            first_name="JANE",
            surname="VAN SMITH",
        )
        assert is_valid is False
        assert error != "", "Expected a non-empty error message"

    def test_concat_with_correct_segment_passes_validation(
        self, processor: IDValidationProcessor
    ) -> None:
        """_validate_existing_id() must pass a correctly constructed CONCAT."""
        is_valid, error = processor._validate_existing_id(
            "GB19800101JANE#SMITH",
            "CONCAT",
            "GB",
            first_name="JANE",
            surname="SMITH",
        )
        assert is_valid is True, f"Expected pass, got error: {error}"

    def test_concat_backward_compat_no_name_args(
        self, processor: IDValidationProcessor
    ) -> None:
        """Calling _validate_existing_id() without name args must still pass
        on the regex alone (backward compatibility)."""
        # This CONCAT has the prefix in the segment, but no names supplied
        is_valid, error = processor._validate_existing_id(
            "GB19800101JANE#VANSM",
            "CONCAT",
            "GB",
        )
        assert (
            is_valid is True
        ), f"Backward-compat call without names should pass structurally. Got: {error}"

    def test_structurally_invalid_concat_still_fails(
        self, processor: IDValidationProcessor
    ) -> None:
        """A CONCAT that fails the regex must still fail even without names."""
        is_valid, error = processor._validate_existing_id(
            "TOOLONG12345678901234",  # >20 chars — fails regex
            "CONCAT",
            "GB",
        )
        assert is_valid is False


# ---------------------------------------------------------------------------
# End-to-end integration test: process_record() triggers correction
# ---------------------------------------------------------------------------


class TestConcatPrefixEndToEnd:
    """End-to-end test: a record with prefix-in-segment CONCAT is corrected."""

    def test_record_with_prefix_in_surname_gets_corrected(
        self, processor: IDValidationProcessor
    ) -> None:
        """A record whose CONCAT encodes 'VAN SMITH' as 'VANSM' must be
        flagged invalid and corrected to a CONCAT with 'SMITH'.

        Trace:
            surname='VAN SMITH', first_name='JANE', dob='1980-01-01'
            id_value = 'GB19800101JANE#VANSM'  (prefix-included surname)
            → _validate_existing_id() → False (segment mismatch)
            → _generate_correction() → _generate_concat()
            → correction = 'GB19800101JANE#SMITH', correction_type = 'CONCAT'
        """
        record = _make_record(
            id_value="GB19800101JANE#VANSM",
            id_type="CONCAT",
            first_name="JANE",
            surname="VAN SMITH",
            date_of_birth="1980-01-01",
            primary_nationality="GB",
        )

        result = processor.process_record(record)

        # The existing ID must have been rejected
        assert (
            result.is_valid is False
        ), "Record should be invalid due to segment mismatch"

        # The correction engine must have produced a CONCAT
        assert (
            result.correction_type == "CONCAT"
        ), f"Expected correction_type='CONCAT', got '{result.correction_type}'"

        # The corrected CONCAT must not contain the prefix-inclusive segment
        assert result.correction != "", "Expected a non-empty correction value"
        corrected = result.correction
        # The surname segment (positions 15:20) must be 'SMITH', not 'VANSM'
        assert corrected[15:20] == "SMITH", (
            f"Expected surname segment 'SMITH' at [15:20], got '{corrected[15:20]}' "
            f"in corrected CONCAT '{corrected}'"
        )
        # Country code prefix must be 'GB'
        assert (
            corrected[:2] == "GB"
        ), f"Expected country prefix 'GB', got '{corrected[:2]}'"

    def test_correct_concat_record_passes_without_correction(
        self, processor: IDValidationProcessor
    ) -> None:
        """A record with a correctly formed CONCAT must pass and produce no correction."""
        record = _make_record(
            id_value="GB19800101JANE#SMITH",
            id_type="CONCAT",
            first_name="JANE",
            surname="SMITH",
            date_of_birth="1980-01-01",
            primary_nationality="GB",
        )

        result = processor.process_record(record)

        assert result.is_valid is True, (
            f"Expected valid record. format={result.format_status}, "
            f"logic={result.logic_status}, error='{result.failure_reason}'"
        )
        assert (
            result.correction == ""
        ), f"Expected no correction for valid CONCAT, got '{result.correction}'"

    def test_missing_surname_concat_passes_on_regex(
        self, processor: IDValidationProcessor
    ) -> None:
        """When surname is blank the segment check is skipped; a structurally
        valid CONCAT passes even if name fields cannot be verified."""
        record = _make_record(
            id_value="GB19800101JANE#VANSM",
            id_type="CONCAT",
            first_name="",  # no first name
            surname="",  # no surname — skip check
            date_of_birth="1980-01-01",
            primary_nationality="GB",
        )

        result = processor.process_record(record)

        # Without name data the structural regex is the only gate — should pass
        assert result.is_valid is True, (
            f"Expected pass when name fields absent. "
            f"format={result.format_status}, failure='{result.failure_reason}'"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
