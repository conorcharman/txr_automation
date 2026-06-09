#!/usr/bin/env python3
"""Test script to verify Error flag is set correctly on template mismatch."""

import csv
from pathlib import Path

from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor

template_file = Path(
    r"c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 - 7_37.csv"
)

# Create a test record with INVALID ID that will generate a correction
test_record = ClientRecord(
    row_index=1,
    transaction_ref="44625CHP68Q1",  # From validated file - has a correction
    account_id="ACCGJCD",
    person_code="ACCGJC",
    account_type="IND",
    id_value="ITDPSMRA55B12C034P",  # Italian NIDN that will be replaced with fallback
    id_type="NIDN",
    first_name="MARIO",
    surname="DI,PASCALE",
    date_of_birth="12/02/1955",
    gender="M",
    primary_nationality="IT",
    secondary_nationality="",
    original_row=[],
)

# Initialize processor with template
processor = IDValidationProcessor(
    client_type="buyer",
    verbose=False,
    template_path=str(template_file),
    template_id_column=3,
    template_type_column=4,
)

print("=" * 80)
print("TEST: Error Flag Set on Template Mismatch")
print("=" * 80)
print(f"Template loaded: {len(processor.template_data)} records")
print()

# Process the record
processed = processor.process_record(test_record)

print(f"Transaction Ref: {processed.transaction_ref}")
print(f"Original ID: {processed.id_value}")
print(f"Original Type: {processed.id_type}")
print(f"Is Valid: {processed.is_valid}")
print()
print(f"Correction Output: '{processed.correction_output}'")
print(f"Kaizen Error (Template): '{processed.kaizen_error}'")
print(f"Match: '{processed.match}'")
print(f"Error Flag: '{processed.error}'")
print()

# Verify Error flag logic
if processed.correction_output and processed.kaizen_error:
    if processed.correction_output == processed.kaizen_error:
        expected_match = "TRUE"
        expected_error = "N"
    else:
        expected_match = "FALSE"
        expected_error = "Y"

    print(f"Expected Match: {expected_match}, Actual: {processed.match}")
    print(f"Expected Error: {expected_error}, Actual: {processed.error}")

    if processed.match == expected_match and processed.error == expected_error:
        print("✅ SUCCESS: Error flag logic is correct!")
    else:
        print("❌ FAILED: Error flag logic is incorrect!")
else:
    print("⚠️  No correction or template data to compare")
