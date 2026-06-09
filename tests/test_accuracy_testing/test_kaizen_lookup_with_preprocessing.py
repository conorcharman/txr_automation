#!/usr/bin/env python3
"""
Test Kaizen Lookup with Inconsistent ID Preprocessing
======================================================

Verifies that Kaizen template validation works correctly for records
that are corrected during inconsistent ID preprocessing.

Issue: Records corrected by InconsistentIDProcessor were skipping
the _perform_template_validation() call because they never went through
process_record().

Fix: Added explicit Kaizen validation phase for preprocessed records.
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


def test_kaizen_lookup_for_preprocessed_records():
    """
    Test that Kaizen template validation works for records corrected in preprocessing.
    """
    # Create test records with inconsistent IDs
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
            id_value="GBNZ283821A",  # Valid - most recent
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

    # Create processors
    inconsistent = InconsistentIDProcessor(client_type="buyer", verbose=False)
    id_processor = IDValidationProcessor(client_type="buyer", verbose=False)

    # Create mock template data
    id_processor.template_data = {
        "TXN001": {"id": "GBNZ283821A", "type": "NIDN"},  # Expected correction
        "TXN002": {"id": "GBNZ283821A", "type": "NIDN"},  # Already correct
    }

    # Manually set validation status for testing
    records[0].is_valid_id = True
    records[0].is_fallback_id = False
    records[0].priority_country_code = "GB"

    records[1].is_valid_id = True
    records[1].is_fallback_id = False
    records[1].priority_country_code = "GB"

    # Apply inconsistent ID correction logic
    indices = [0, 1]
    inconsistent.apply_prior_valid_corrections(records, indices)

    # Simulate what the script does: perform Kaizen validation on preprocessed records
    records_already_corrected = [
        r for r in records if not r.requires_standard_validation
    ]

    print("\n" + "=" * 70)
    print("TEST: KAIZEN VALIDATION FOR PREPROCESSED RECORDS")
    print("=" * 70)

    # Perform Kaizen validation on preprocessed records
    for record in records_already_corrected:
        id_processor._perform_template_validation(record)

    # Verify results
    print(f"\nRecord 1 (TXN001 - standardized from GBNZ283821B to GBNZ283821A):")
    print(f"  correction_output: '{records[0].correction_output}'")
    print(f"  kaizen_error: '{records[0].kaizen_error}'")
    print(f"  match: '{records[0].match}'")
    print(f"  error: '{records[0].error}'")

    # Record 1 should have been corrected and should match template
    assert (
        records[0].correction_output == "GBNZ283821A:NIDN"
    ), f"Record 1 should have correction_output 'GBNZ283821A:NIDN', got '{records[0].correction_output}'"
    assert (
        records[0].kaizen_error == "GBNZ283821A:NIDN"
    ), f"Record 1 should have kaizen_error 'GBNZ283821A:NIDN', got '{records[0].kaizen_error}'"
    assert (
        records[0].match == "TRUE"
    ), f"Record 1 should match template (TRUE), got '{records[0].match}'"
    assert (
        records[0].error == "N"
    ), f"Record 1 should have error='N', got '{records[0].error}'"

    print("  ✓ Kaizen validation successful: correction matches template")

    print(f"\nRecord 2 (TXN002 - already most recent GBNZ283821A):")
    print(f"  correction_output: '{records[1].correction_output}'")
    print(f"  kaizen_error: '{records[1].kaizen_error}'")
    print(f"  match: '{records[1].match}'")
    print(f"  error: '{records[1].error}'")

    # Record 2 should not have correction (already most recent)
    assert (
        records[1].correction_output == ""
    ), f"Record 2 should have empty correction_output, got '{records[1].correction_output}'"
    assert (
        records[1].kaizen_error == "GBNZ283821A:NIDN"
    ), f"Record 2 should still have kaizen_error loaded from template"
    assert (
        records[1].match == ""
    ), f"Record 2 should have empty match (no correction), got '{records[1].match}'"
    assert (
        records[1].error == "N"
    ), f"Record 2 should have error='N', got '{records[1].error}'"

    print("  ✓ Kaizen validation successful: no correction needed")

    print("\n✅ All Kaizen lookup tests passed!")
    print("=" * 70)


def test_kaizen_lookup_without_template():
    """
    Test that validation works gracefully when no template is loaded.
    """
    records = [
        ClientRecord(
            row_index=1,
            transaction_ref="TXN001",
            account_id="ACC001",
            person_code="12345",
            account_type="IND",
            id_value="GBNZ283821A",
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1982-08-28",
            gender="M",
            primary_nationality="GB",
            secondary_nationality="",
            trade_date_time_raw="2024-01-01-10-00-00-000000",
            prefixed_nationality="GB",
            correction_output="GBNZ283821B:NIDN",
        ),
    ]

    # Create processor without template
    id_processor = IDValidationProcessor(client_type="buyer", verbose=False)

    print("\n" + "=" * 70)
    print("TEST: KAIZEN VALIDATION WITHOUT TEMPLATE")
    print("=" * 70)

    # Perform validation
    id_processor._perform_template_validation(records[0])

    # Should gracefully handle no template
    assert (
        records[0].kaizen_error == ""
    ), f"Should have empty kaizen_error with no template, got '{records[0].kaizen_error}'"
    assert (
        records[0].match == ""
    ), f"Should have empty match with no template, got '{records[0].match}'"
    assert (
        records[0].error == "N"
    ), f"Should have error='N' with no template, got '{records[0].error}'"

    print("✓ Validation works correctly without template")
    print("✅ Test passed!")
    print("=" * 70)


if __name__ == "__main__":
    print("Testing Kaizen Lookup with Inconsistent ID Preprocessing")
    print("=" * 70)

    test_kaizen_lookup_for_preprocessed_records()
    print()
    test_kaizen_lookup_without_template()

    print("\n🎉 All Kaizen lookup tests completed successfully!")
