#!/usr/bin/env python3
"""
Test Inconsistent ID Standardization Feature (v1.4)
===================================================

Tests the new feature where ALL IDs (including valid ones) are standardized
to the most recent valid ID within each (Person Code, ID Type, Prefix) group.

Test Scenario:
- Person has 3 records with NIDN:
  - Record A (2024-01-01): GBNZ283821B - VALID
  - Record B (2024-02-01): GBNZG283821B - INVALID (wrong format)
  - Record C (2024-03-01): GBNZ283821A - VALID
- Expected: ALL records corrected to GBNZ283821A (most recent valid)
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.processor import (
    ClientRecord,
    IDValidationProcessor,
    InconsistentIDProcessor,
)


def test_standardize_valid_ids_to_most_recent():
    """
    Test that valid IDs differing from most recent valid are standardized.
    """
    # Create test records
    records = [
        ClientRecord(
            row_index=1,
            transaction_ref="TXN001",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZ283821B",  # Valid but not most recent
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-01-01-10-00-00-000000",
            prefixed_nationality="GB",
        ),
        ClientRecord(
            row_index=2,
            transaction_ref="TXN002",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZG283821B",  # Invalid format
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-02-01-10-00-00-000000",
            prefixed_nationality="GB",
        ),
        ClientRecord(
            row_index=3,
            transaction_ref="TXN003",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZ283821A",  # Valid - most recent
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-03-01-10-00-00-000000",
            prefixed_nationality="GB",
        ),
    ]

    # Parse trade datetimes
    for record in records:
        record.trade_date_time_parsed = InconsistentIDProcessor.parse_trade_date_time(
            record.trade_date_time_raw
        )

    # Create processors
    inconsistent = InconsistentIDProcessor(client_type="buyer", verbose=True)
    id_processor = IDValidationProcessor(client_type="buyer")

    # Manually set validation status for testing
    # In real scenario, preprocess_for_inconsistent_validation would do this
    records[0].is_valid_id = True  # GBNZ283821B is valid
    records[0].is_fallback_id = False
    records[1].is_valid_id = False  # GBNZG283821B is invalid
    records[1].is_fallback_id = False
    records[2].is_valid_id = True  # GBNZ283821A is valid (most recent)
    records[2].is_fallback_id = False

    # Set priority country codes
    for record in records:
        record.priority_country_code = "GB"

    # Apply correction logic
    indices = [0, 1, 2]  # All three records
    inconsistent.apply_prior_valid_corrections(records, indices)

    # Verify results
    print("\n" + "=" * 70)
    print("TEST RESULTS:")
    print("=" * 70)

    # Record A (valid but not most recent) should be corrected
    assert (
        records[0].correction == "GBNZ283821A"
    ), f"Record A should be corrected to GBNZ283821A, got {records[0].correction}"
    assert (
        records[0].requires_standard_validation == False
    ), "Record A should not require standard validation"
    print("✓ Record A (valid GBNZ283821B): Standardized to GBNZ283821A")

    # Record B (invalid) should be corrected
    assert (
        records[1].correction == "GBNZ283821A"
    ), f"Record B should be corrected to GBNZ283821A, got {records[1].correction}"
    assert (
        records[1].requires_standard_validation == False
    ), "Record B should not require standard validation"
    print("✓ Record B (invalid GBNZG283821B): Corrected to GBNZ283821A")

    # Record C (most recent valid) should NOT be corrected
    assert (
        records[2].correction == ""
    ), f"Record C should not be corrected, got {records[2].correction}"
    assert (
        records[2].requires_standard_validation == False
    ), "Record C should not require standard validation"
    print("✓ Record C (valid GBNZ283821A): Already most recent, no change")

    # Check statistics
    print("\nStatistics:")
    print(f"  Valid standardized: {inconsistent.stats.valid_standardized}")
    print(f"  Invalid corrected: {inconsistent.stats.corrected_to_most_recent}")
    print(f"  Already most recent: {inconsistent.stats.already_most_recent}")

    assert (
        inconsistent.stats.valid_standardized == 1
    ), f"Should have 1 valid standardized, got {inconsistent.stats.valid_standardized}"
    assert (
        inconsistent.stats.corrected_to_most_recent == 1
    ), f"Should have 1 invalid corrected, got {inconsistent.stats.corrected_to_most_recent}"
    assert (
        inconsistent.stats.already_most_recent == 1
    ), f"Should have 1 already most recent, got {inconsistent.stats.already_most_recent}"

    print("\n✅ All tests passed!")
    print("=" * 70)


def test_no_valid_id_in_group():
    """
    Test that when no valid ID exists, all records are marked for standard correction.
    """
    # Create test records - all invalid
    records = [
        ClientRecord(
            row_index=1,
            transaction_ref="TXN001",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZG283821C",  # Invalid
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-01-01-10-00-00-000000",
            prefixed_nationality="GB",
        ),
        ClientRecord(
            row_index=2,
            transaction_ref="TXN002",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZG283821B",  # Invalid
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-02-01-10-00-00-000000",
            prefixed_nationality="GB",
        ),
    ]

    # Parse trade datetimes
    for record in records:
        record.trade_date_time_parsed = InconsistentIDProcessor.parse_trade_date_time(
            record.trade_date_time_raw
        )

    # Create processor
    inconsistent = InconsistentIDProcessor(client_type="buyer", verbose=True)

    # Manually set validation status
    records[0].is_valid_id = False
    records[0].is_fallback_id = False
    records[1].is_valid_id = False
    records[1].is_fallback_id = False

    # Set priority country codes
    for record in records:
        record.priority_country_code = "GB"

    # Apply correction logic
    indices = [0, 1]
    inconsistent.apply_prior_valid_corrections(records, indices)

    # Verify results
    print("\n" + "=" * 70)
    print("TEST RESULTS (No Valid ID):")
    print("=" * 70)

    # Both should be marked for standard validation
    assert (
        records[0].requires_standard_validation == True
    ), "Record A should require standard validation"
    assert (
        records[1].requires_standard_validation == True
    ), "Record B should require standard validation"

    print("✓ Record A: Marked for standard correction")
    print("✓ Record B: Marked for standard correction")

    # Check statistics
    assert (
        inconsistent.stats.no_valid_in_group == 2
    ), f"Should have 2 marked for standard, got {inconsistent.stats.no_valid_in_group}"

    print("\n✅ All tests passed!")
    print("=" * 70)


if __name__ == "__main__":
    print("Testing Inconsistent ID Standardization Feature (v1.4)")
    print("=" * 70)

    test_standardize_valid_ids_to_most_recent()
    print()
    test_no_valid_id_in_group()

    print("\n🎉 All tests completed successfully!")
