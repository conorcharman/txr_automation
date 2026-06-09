#!/usr/bin/env python3
"""
Unit tests for prefixed nationality validation logic.
Tests the new prefix extraction and validation behavior.
"""

import pytest

from src.accuracy_testing.processor import (
    ClientRecord,
    IDValidationProcessor,
    extract_id_prefix,
)


class TestPrefixExtraction:
    """Test ID prefix extraction logic."""

    def test_extract_valid_prefix_nidn(self):
        """Should extract NL from NLNPPD7P215 for NIDN type."""
        prefix = extract_id_prefix("NLNPPD7P215", "NIDN")
        assert prefix == "NL"

    def test_extract_valid_prefix_ccpt(self):
        """Should extract GB from GBSG500496A for CCPT type."""
        prefix = extract_id_prefix("GBSG500496A", "CCPT")
        assert prefix == "GB"

    def test_extract_valid_prefix_concat(self):
        """Should extract US from US12345678 for CONCAT type."""
        prefix = extract_id_prefix("US12345678", "CONCAT")
        assert prefix == "US"

    def test_no_prefix_for_lei(self):
        """Should return None for LEI (no country prefix)."""
        prefix = extract_id_prefix("123456789012345678", "LEI")
        assert prefix is None

    def test_invalid_prefix_returns_none(self):
        """Should return None if first 2 chars aren't a valid country code."""
        prefix = extract_id_prefix("ZZ12345678", "NIDN")
        assert prefix is None

    def test_too_short_returns_none(self):
        """Should return None if ID is too short."""
        prefix = extract_id_prefix("G", "NIDN")
        assert prefix is None

    def test_empty_returns_none(self):
        """Should return None for empty ID."""
        prefix = extract_id_prefix("", "NIDN")
        assert prefix is None


class TestPrefixedValidation:
    """Test validation using prefixed nationality."""

    def setup_method(self):
        """Set up test processor."""
        self.processor = IDValidationProcessor(client_type="buyer", verbose=True)

    def test_validates_nl_id_with_nl_prefix(self):
        """Should validate NLNPPD7P215 against NL formats (not GB)."""
        record = ClientRecord(
            row_index=1,
            transaction_ref="TEST001",
            account_id="ACC001",
            person_code="PERSON123",
            account_type="IND",
            id_value="NLNPPD7P215",
            id_type="CCPT",
            first_name="Test",
            surname="User",
            date_of_birth="1972-11-06",
            gender="M",
            primary_nationality="GB",  # Different from prefix!
            secondary_nationality="",
        )

        # Get priority country - should use prefix (NL) not nationality (GB)
        priority_country = self.processor._get_priority_country(record)

        assert (
            priority_country == "NL"
        ), f"Expected NL (from prefix), got {priority_country}"
        assert record.prefixed_nationality == "NL", "Prefixed nationality should be set"

    def test_validates_gb_id_with_gb_prefix(self):
        """Should validate GBSG500496A against GB formats."""
        record = ClientRecord(
            row_index=2,
            transaction_ref="TEST002",
            account_id="ACC002",
            person_code="PERSON123",
            account_type="IND",
            id_value="GBSG500496A",
            id_type="NIDN",
            first_name="Test",
            surname="User",
            date_of_birth="1972-11-06",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
        )

        priority_country = self.processor._get_priority_country(record)

        assert priority_country == "GB"
        assert record.prefixed_nationality == "GB"

    def test_falls_back_to_nationality_if_no_valid_prefix(self):
        """Should use nationality if prefix is invalid."""
        record = ClientRecord(
            row_index=3,
            transaction_ref="TEST003",
            account_id="ACC003",
            person_code="PERSON123",
            account_type="IND",
            id_value="ZZ12345678",  # Invalid prefix
            id_type="NIDN",
            first_name="Test",
            surname="User",
            date_of_birth="1972-11-06",
            gender="M",
            primary_nationality="US",
            secondary_nationality="GB",
        )

        priority_country = self.processor._get_priority_country(record)

        # Should fall back to EEA priority (GB over US)
        assert (
            priority_country == "GB"
        ), "Should use nationality priority when prefix invalid"
        assert record.prefixed_nationality == "", "Should not set prefixed nationality"

    def test_lei_uses_nationality_not_prefix(self):
        """LEI IDs don't have country prefixes."""
        record = ClientRecord(
            row_index=4,
            transaction_ref="TEST004",
            account_id="ACC004",
            person_code="PERSON123",
            account_type="IND",
            id_value="213800Y4I7TN34WUBD71",  # LEI format
            id_type="LEI",
            first_name="Test",
            surname="User",
            date_of_birth="1972-11-06",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
        )

        priority_country = self.processor._get_priority_country(record)

        # LEI should use nationality (GB)
        assert priority_country == "GB"
        assert (
            record.prefixed_nationality == ""
        ), "LEI should not have prefixed nationality"


class TestPrefixStripping:
    """Test that prefix stripping works correctly in validation."""

    def setup_method(self):
        """Set up test processor."""
        self.processor = IDValidationProcessor(client_type="buyer", verbose=True)

    def test_strips_prefix_for_nidn_with_valid_prefix(self):
        """Should strip NL prefix before validating NIDN."""
        # NLNPPD7P215 -> NPPD7P215 (9 chars) for validation
        is_valid, error = self.processor._validate_existing_id(
            "NLNPPD7P215", "CCPT", "NL"
        )

        # Should validate the 9-char stripped version
        # Error message should NOT complain about length
        if not is_valid:
            assert (
                "9-character" not in error or "Does not match" in error
            ), f"Validation should use stripped 9-char ID. Error: {error}"

    def test_does_not_strip_invalid_prefix(self):
        """Should not strip prefix if it's not a valid country code."""
        is_valid, error = self.processor._validate_existing_id(
            "ZZ12345678", "NIDN", "US"
        )

        # Should validate full 10-char ID (prefix not stripped)
        # This will likely fail format validation, but that's expected
        assert not is_valid  # Expected to fail

    def test_does_not_strip_lei(self):
        """Should not strip prefix for LEI type."""
        # LEI is 18-20 characters, no country prefix
        is_valid, error = self.processor._validate_existing_id(
            "213800Y4I7TN34WUBD71", "LEI", "GB"
        )

        # Should validate full LEI (no stripping)
        # Validation result depends on LEI patterns, but shouldn't error on prefix


class TestROWCCPTValidation:
    """
    Test that Rest of World passports are assumed correct.

    ROW (non-EEA) countries have no CCPT format patterns defined, but a
    declared CCPT from a ROW client should be treated as valid without
    requiring format pattern matching.
    """

    def setup_method(self) -> None:
        """Set up test processor."""
        self.processor = IDValidationProcessor(
            client_type="buyer",
            verbose=True,
        )

    def test_row_ccpt_returns_valid(self) -> None:
        """A CCPT from a non-EEA country should be treated as valid."""
        is_valid, error = self.processor._validate_existing_id(
            "US12345678",
            "CCPT",
            "US",
        )
        assert is_valid, f"ROW CCPT should be valid; got error: {error}"
        assert error == "", f"No error expected for ROW CCPT; got: {error}"

    def test_row_ccpt_no_ccpt_pattern_error(self) -> None:
        """The 'No CCPT format patterns defined' error must not appear for ROW countries."""
        is_valid, error = self.processor._validate_existing_id(
            "AU87654321",
            "CCPT",
            "AU",
        )
        assert "No CCPT format patterns defined" not in error

    def test_row_ccpt_varies_by_country(self) -> None:
        """Multiple ROW countries should all return valid for CCPT."""
        row_countries = ["US", "AU", "JP", "IN", "BR", "ZA"]
        for country in row_countries:
            is_valid, error = self.processor._validate_existing_id(
                f"{country}12345678",
                "CCPT",
                country,
            )
            assert (
                is_valid
            ), f"ROW CCPT for {country} should be valid; got error: {error}"

    def test_eea_ccpt_still_validated(self) -> None:
        """EEA countries with defined CCPT patterns should still be format-validated."""
        # NL has CCPT patterns defined; an invalid value must still fail
        is_valid, error = self.processor._validate_existing_id(
            "INVALIDPASSPORT!!",
            "CCPT",
            "NL",
        )
        assert not is_valid, "EEA CCPT with invalid format should still fail validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
