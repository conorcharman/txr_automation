#!/usr/bin/env python3
"""Test auto-detection of column names based on client_type."""

from pathlib import Path
from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor

template_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 - 7_35.csv')

# Create a test record
test_record = ClientRecord(
    row_index=1,
    transaction_ref="44625CF6KXV1",
    account_id="ACCLKVS",
    person_code="ACCLKV",
    account_type="IND",
    id_value="GB20210216ANTHOZALES",
    id_type="CONCAT",
    first_name="ANTHONY",
    surname="ZAKESKI-MILNER",
    date_of_birth="16/02/21",
    gender="M",
    primary_nationality="GB",
    secondary_nationality="",
    original_row=[]
)

print("=" * 80)
print("TEST: Auto-detection of Column Names Based on client_type")
print("=" * 80)

# Initialize processor WITHOUT specifying column names
# Should auto-detect based on client_type="buyer"
processor = IDValidationProcessor(
    client_type="buyer",
    verbose=False,
    template_path=str(template_file)
    # NO template_id_column or template_type_column specified!
)

print(f"Client Type: buyer")
print(f"Auto-detected ID Column: '{processor.template_id_column}'")
print(f"Auto-detected Type Column: '{processor.template_type_column}'")
print(f"Template loaded: {len(processor.template_data)} records")
print()

# Process the record
processed = processor.process_record(test_record)

print(f"Transaction Ref: {processed.transaction_ref}")
print(f"Kaizen Error: '{processed.kaizen_error}'")
print(f"Error: '{processed.error}'")
print()

if processor.template_id_column == "Buyer ID Code":
    print("✅ SUCCESS: Auto-detection is WORKING!")
    print("   Correctly defaulted to 'Buyer ID Code' for buyer client_type")
else:
    print(f"❌ FAILED: Expected 'Buyer ID Code', got '{processor.template_id_column}'")
