#!/usr/bin/env python3
"""Test script to verify Error column is populated for all records."""

from pathlib import Path
from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor


def test_error_column_populated_for_no_valid_country():
    """Test that Error column is populated when no valid country code exists."""
    # Create a test record with NO valid country code (empty nationalities)
    test_record = ClientRecord(
        row_index=1,
        transaction_ref="TEST123",
        account_id="ACC123",
        person_code="PER123",
        account_type="IND",
        id_value="INVALID123",
        id_type="NIDN",
        first_name="John",
        surname="Doe",
        date_of_birth="01/01/1990",
        gender="M",
        primary_nationality="",  # Empty
        secondary_nationality="",  # Empty
        original_row=[]
    )

    # Initialize processor (no template loaded, verbose mode)
    processor = IDValidationProcessor(
        client_type="buyer",
        verbose=False  # Turn off verbose to reduce output
    )

    # Process the record
    processed = processor.process_record(test_record)

    # Verify Error field is populated
    assert processed.error != "", f"Error field should be populated but got: '{processed.error}'"


if __name__ == "__main__":
    # Standalone script mode for manual testing
    test_record = ClientRecord(
        row_index=1,
        transaction_ref="TEST123",
        account_id="ACC123",
        person_code="PER123",
        account_type="IND",
        id_value="INVALID123",
        id_type="NIDN",
        first_name="John",
        surname="Doe",
        date_of_birth="01/01/1990",
        gender="M",
        primary_nationality="",  # Empty
        secondary_nationality="",  # Empty
        original_row=[]
    )

    processor = IDValidationProcessor(
        client_type="buyer",
        verbose=False
    )

    processed = processor.process_record(test_record)

    print("=" * 80)
    print("TEST: Error column populated for record with NO valid country code")
    print("=" * 80)
    print(f"Transaction Ref: {processed.transaction_ref}")
    print(f"Primary Nationality: '{processed.primary_nationality}'")
    print(f"Secondary Nationality: '{processed.secondary_nationality}'")
    print(f"Validation Error: {processed.validation_error}")
    print(f"Actions Taken: {processed.actions_taken}")
    print()
    print(f"Error field value: '{processed.error}'")
    print(f"Kaizen Error: '{processed.kaizen_error}'")
    print(f"Match: '{processed.match}'")
    print()

    if processed.error == "":
        print("❌ FAILED: Error field is BLANK")
        print("The early exit issue is NOT fixed")
        exit(1)
    else:
        print(f"✅ PASSED: Error field is populated with: '{processed.error}'")
        print("The early exit issue is FIXED")
        exit(0)
