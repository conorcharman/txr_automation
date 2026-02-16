#!/usr/bin/env python3
"""
Diagnostic script to test Phase 3 matching logic
"""
import csv
import os
from pathlib import Path

# Test data
replay_record = "ALEKSANDAR~MILCHEV~2001-02-27,NIDN:BG0142271827,,Incorrect NIDN,7_37,3,,,"
incident_file_path = r"F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\FY25\Q4\Incident Code Analysis\FY25 Q4 7_37.csv"

print("=" * 80)
print("PHASE 3 MATCHING DIAGNOSTIC")
print("=" * 80)

# Parse replay record
parts = replay_record.split(',')
name_dob = parts[0]
id_data = parts[1]
incident_codes = parts[4]

name_parts = name_dob.split('~')
first_name = name_parts[0].strip()
surname = name_parts[1].strip()
dob = name_parts[2].strip()

# Parse ID
if ':' in id_data:
    id_type, id_value = id_data.split(':', 1)
    id_type = id_type.strip()
    id_value = id_value.strip()
else:
    id_type = ""
    id_value = id_data.strip()

print("\nREPLAY RECORD:")
print(f"  First Name: '{first_name}'")
print(f"  Surname: '{surname}'")
print(f"  DOB: '{dob}'")
print(f"  ID Type: '{id_type}'")
print(f"  ID Value: '{id_value}'")
print(f"  Incident Codes: '{incident_codes}'")

# Check incident file
print("\n" + "=" * 80)
print(f"INCIDENT FILE: {os.path.basename(incident_file_path)}")
print("=" * 80)

if not os.path.exists(incident_file_path):
    print(f"\n❌ ERROR: Incident file not found!")
    print(f"   Path: {incident_file_path}")
    exit(1)

print(f"✓ File exists")

# Read incident file
with open(incident_file_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    
    # Find column indices
    try:
        buyer_id_col = header.index("Buyer identification code")
        buyer_first_col = header.index("Buyer - First name(s)")
        buyer_surname_col = header.index("Buyer - Surname(s)")
        buyer_dob_col = header.index("Buyer - Date of birth")
        print(f"✓ Found required columns")
        print(f"  Buyer ID column: {buyer_id_col}")
        print(f"  Buyer First Name column: {buyer_first_col}")
        print(f"  Buyer Surname column: {buyer_surname_col}")
        print(f"  Buyer DOB column: {buyer_dob_col}")
    except ValueError as e:
        print(f"\n❌ ERROR: Required column not found: {e}")
        print(f"\nAvailable columns:")
        for i, col in enumerate(header):
            print(f"  {i}: {col}")
        exit(1)
    
    # Search for matching records
    print("\n" + "=" * 80)
    print("SEARCHING FOR MATCHES...")
    print("=" * 80)
    
    id_matches = []
    name_matches = []
    
    for row_idx, row in enumerate(reader):
        if len(row) <= max(buyer_id_col, buyer_first_col, buyer_surname_col, buyer_dob_col):
            continue
        
        incident_buyer_id = row[buyer_id_col].strip()
        incident_first = row[buyer_first_col].strip()
        incident_surname = row[buyer_surname_col].strip()
        incident_dob = row[buyer_dob_col].strip()
        
        # Check ID match (case-insensitive)
        if incident_buyer_id.lower() == id_value.lower():
            id_matches.append({
                'row': row_idx + 2,  # +2 because of header and 0-indexing
                'id': incident_buyer_id,
                'name': f"{incident_first} {incident_surname}",
                'dob': incident_dob
            })
        
        # Check name match (case-insensitive)
        if (incident_first.lower() == first_name.lower() and 
            incident_surname.lower() == surname.lower()):
            name_matches.append({
                'row': row_idx + 2,
                'id': incident_buyer_id,
                'name': f"{incident_first} {incident_surname}",
                'dob': incident_dob
            })
    
    print(f"\nID MATCHES: {len(id_matches)}")
    if id_matches:
        print(f"✓ Found {len(id_matches)} record(s) matching ID '{id_value}':")
        for match in id_matches[:5]:  # Show first 5
            print(f"  Row {match['row']}: ID={match['id']}, Name={match['name']}, DOB={match['dob']}")
    else:
        print(f"❌ No records found with Buyer ID = '{id_value}'")
        print(f"   (Searched case-insensitive)")
    
    print(f"\nNAME MATCHES: {len(name_matches)}")
    if name_matches:
        print(f"✓ Found {len(name_matches)} record(s) matching name '{first_name} {surname}':")
        for match in name_matches[:5]:  # Show first 5
            print(f"  Row {match['row']}: ID={match['id']}, Name={match['name']}, DOB={match['dob']}")
    else:
        print(f"❌ No records found with name = '{first_name} {surname}'")
        print(f"   (Searched case-insensitive)")

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
