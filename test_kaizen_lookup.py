#!/usr/bin/env python3
"""Test script to verify Kaizen template lookup is working with column names."""

import csv
from pathlib import Path
from src.accuracy_testing.processor import ClientRecord, IDValidationProcessor

# Test with a real transaction from the 7_35 incident
template_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 - 7_35.csv')

# Create a test record
test_record = ClientRecord(
    row_index=1,
    transaction_ref="44625CF6KXV1",  # From the validated file
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

# Initialize processor with template (using column NAMES)
processor = IDValidationProcessor(
    client_type="buyer",
    verbose=False,
    template_path=str(template_file),
    template_id_column="Buyer ID Code",  # Column NAME
    template_type_column="Type of Buyer ID Code"  # Column NAME
)

print("=" * 80)
print("TEST: Kaizen Template Lookup with Column Names (Not Indices)")
print("=" * 80)
print(f"Template file: {template_file.name}")
print(f"ID Column: 'Buyer ID Code'")
print(f"Type Column: 'Type of Buyer ID Code'")
print(f"Template loaded: {len(processor.template_data)} records")
print()

# Process the record
processed = processor.process_record(test_record)

print(f"Transaction Ref: {processed.transaction_ref}")
print(f"ID Value: {processed.id_value}")
print(f"ID Type: {processed.id_type}")
print(f"Is Valid: {processed.is_valid}")
print()
print(f"Correction Output: '{processed.correction_output}'")
print(f"Error: '{processed.error}'")
print(f"Kaizen Error: '{processed.kaizen_error}'")
print(f"Match: '{processed.match}'")
print()

# Check if template lookup happened
if processed.kaizen_error:
    print("✅ SUCCESS: Column name template lookup is WORKING!")
    print(f"   Template returned: {processed.kaizen_error}")
else:
    print("❌ FAILED: Template lookup is NOT working")
    print("   Kaizen Error field is empty")
    
    # Debug: Check if transaction exists in template
    if processed.transaction_ref in processor.template_data:
        template_entry = processor.template_data[processed.transaction_ref]
        print(f"   DEBUG: Template entry exists: {template_entry}")
    else:
        print(f"   DEBUG: Transaction {processed.transaction_ref} not found in template")
        print(f"   DEBUG: First 3 template keys: {list(processor.template_data.keys())[:3]}")
