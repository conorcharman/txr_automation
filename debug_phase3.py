#!/usr/bin/env python3
"""
Debug script for Phase 3 processor column mapping issue
"""

import csv
import os
from pathlib import Path

# Test incident file
incident_file = r"C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_68.csv"

# Column names from config
incident_columns_config = {
    "correction": "Correction",
    "correction_field": "Correction Field",
    "agree_with_correction": "Agree With Correction",
    "suggested_correction": "Suggested Correction",
    "suggested_correction_field": "Suggested Correction Field",
}

print("=" * 80)
print("DEBUGGING PHASE 3 COLUMN MAPPING")
print("=" * 80)
print(f"\nIncident file: {os.path.basename(incident_file)}\n")

# Read file
with open(incident_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = list(next(reader))
    rows = list(reader)

print(f"Total columns in header: {len(header)}")
print(f"Total data rows: {len(rows)}\n")

# Map columns
print("Column Mapping:")
print("-" * 80)
for logical_name, column_name in incident_columns_config.items():
    try:
        index = header.index(column_name)
        print(f"  {logical_name:30} -> column {index:3}: '{column_name}'")
    except ValueError:
        print(f"  {logical_name:30} -> NOT FOUND: '{column_name}'")

print("\n" + "=" * 80)
print("TESTING ALEXANDER STEIDL RECORD")
print("=" * 80)

# Find the ALEXANDER STEIDL record
buyer_first_col = header.index("Buyer - First name(s)")
buyer_last_col = header.index("Buyer - Surname(s)")
correction_col = header.index("Correction")
correction_field_col = header.index("Correction Field")
agree_col = header.index("Agree With Correction")
suggested_corr_col = header.index("Suggested Correction")

for i, row in enumerate(rows):
    if len(row) > max(buyer_first_col, buyer_last_col):
        first = row[buyer_first_col].strip()
        last = row[buyer_last_col].strip()
        
        if first == "ALEXANDER" and last == "STEIDL":
            print(f"\nFound at row {i + 2} (row index {i}):")
            print(f"  Buyer First Name: '{first}'")
            print(f"  Buyer Last Name: '{last}'")
            print(f"  Correction: '{row[correction_col]}' (column {correction_col})")
            print(f"  Correction Field: '{row[correction_field_col]}' (column {correction_field_col})")
            print(f"  Agree With Correction: '{row[agree_col]}' (column {agree_col})")
            print(f"  Suggested Correction: '{row[suggested_corr_col]}' (column {suggested_corr_col})")
            
            # Test the decision logic
            print("\nDecision Logic Test:")
            correction_value = row[correction_col].strip() if correction_col is not None and len(row) > correction_col else ""
            correction_field_value = row[correction_field_col].strip() if correction_field_col is not None and len(row) > correction_field_col else ""
            suggested_correction_value = row[suggested_corr_col].strip() if suggested_corr_col is not None and len(row) > suggested_corr_col else ""
            
            print(f"  correction_value after strip: '{correction_value}' (truthy: {bool(correction_value)})")
            print(f"  correction_field_value after strip: '{correction_field_value}'")
            print(f"  suggested_correction_value after strip: '{suggested_correction_value}'")
            
            if correction_value:
                agree_value = row[agree_col].strip().upper() if agree_col is not None and len(row) > agree_col else ""
                print(f"  agree_value after strip/upper: '{agree_value}'")
                print(f"  agree_value in ('Y', 'P', ''): {agree_value in ('Y', 'P', '')}")
                
                if agree_value in ('Y', 'P', ''):
                    print(f"\n  ✓ SHOULD apply correction: '{correction_value}' -> '{correction_field_value}'")
                else:
                    print(f"\n  ✗ Should NOT apply (agree={agree_value})")
            else:
                print(f"\n  ✗ correction_value is empty, checking suggested...")
                if suggested_correction_value:
                    print(f"  ✓ SHOULD apply suggested: '{suggested_correction_value}'")
                else:
                    print(f"  ✓ Correctly returns 'No Change'")
            
            break
else:
    print("\nALEXANDER STEIDL not found in file!")

print("\n" + "=" * 80)
