#!/usr/bin/env python3
"""
No Change Records Analysis
===========================

Analyzes Phase 3 replay output to identify records with "No Change" and 
reports on the decision tree fields from incident files.

Decision Tree Fields:
- Correction
- Correction Field
- Agree With Correction
- Suggested Correction
- Suggested Correction Field

Author: GitHub Copilot
Date: 13 February 2026
"""

import csv
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Configuration
REPLAY_OUTPUT_DIR = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q4\output"
INCIDENT_FILES_DIR = r"F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\FY25\Q4\Incident Code Analysis"
OUTPUT_REPORT = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q4\output\No_Change_Analysis_Report.csv"

# Incident file pattern
INCIDENT_PATTERN = "FY25 Q4 {}.csv"

def parse_replay_record(row: List[str], file_type: str) -> Dict:
    """Parse replay record to extract key information"""
    if file_type == 'IDs':
        # Format: Name~Surname~DOB, ID_TYPE:ID_VALUE, ..., Incident_Desc, Incident_Codes, Count, Correction, Correction_Field
        name_dob = row[0].split('~')
        first_name = name_dob[0].strip() if len(name_dob) > 0 else ""
        surname = name_dob[1].strip() if len(name_dob) > 1 else ""
        dob = name_dob[2].strip() if len(name_dob) > 2 else ""
        
        id_data = row[1].strip()
        if ':' in id_data:
            id_parts = id_data.split(':', 1)
            id_type = id_parts[0].strip()
            id_value = id_parts[1].strip()
        else:
            id_type = ""
            id_value = id_data
        
        incident_codes = row[4].strip() if len(row) > 4 else ""
        correction = row[6].strip() if len(row) > 6 else ""
        correction_field = row[7].strip() if len(row) > 7 else ""
        
        return {
            'first_name': first_name,
            'surname': surname,
            'dob': dob,
            'id_type': id_type,
            'id_value': id_value,
            'incident_codes': incident_codes,
            'correction': correction,
            'correction_field': correction_field
        }
    else:  # Names format
        # Similar parsing for Names files
        id_data = row[0].strip()
        if '~' in id_data:
            id_value = id_data.split('~', 1)[0].strip()
        else:
            id_value = id_data
        
        name_dob = row[1].split(':')
        first_name = name_dob[0].strip() if len(name_dob) > 0 else ""
        surname = name_dob[1].strip() if len(name_dob) > 1 else ""
        dob = name_dob[2].strip() if len(name_dob) > 2 else ""
        
        incident_codes = row[4].strip() if len(row) > 4 else ""
        correction = row[6].strip() if len(row) > 6 else ""
        correction_field = row[7].strip() if len(row) > 7 else ""
        
        return {
            'first_name': first_name,
            'surname': surname,
            'dob': dob,
            'id_type': '',
            'id_value': id_value,
            'incident_codes': incident_codes,
            'correction': correction,
            'correction_field': correction_field
        }

def load_incident_file_index(incident_file: str, cache: Dict) -> Dict:
    """Load and index incident file for fast lookups - with caching"""
    
    if incident_file in cache:
        return cache[incident_file]
    
    if not os.path.exists(incident_file):
        cache[incident_file] = {
            'success': False,
            'reason': f'Incident file not found: {os.path.basename(incident_file)}'
        }
        return cache[incident_file]
    
    try:
        index = {'success': True, 'by_id': {}, 'by_name': {}}
        
        with open(incident_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Find column indices
            try:
                buyer_id_col = header.index("Buyer identification code")
                buyer_first_col = header.index("Buyer - First name(s)")
                buyer_surname_col = header.index("Buyer - Surname(s)")
                correction_col = header.index("Correction")
                correction_field_col = header.index("Correction Field")
                agree_col = header.index("Agree With Correction")
                suggested_corr_col = header.index("Suggested Correction")
                suggested_field_col = header.index("Suggested Correction Field")
            except ValueError as e:
                cache[incident_file] = {
                    'success': False,
                    'reason': f'Column not found: {e}'
                }
                return cache[incident_file]
            
            # Build indexes
            for row in reader:
                max_col = max(buyer_id_col, buyer_first_col, buyer_surname_col, correction_col, 
                             correction_field_col, agree_col, suggested_corr_col, suggested_field_col)
                if len(row) <= max_col:
                    continue
                
                data = {
                    'correction': row[correction_col].strip(),
                    'correction_field': row[correction_field_col].strip(),
                    'agree_with_correction': row[agree_col].strip(),
                    'suggested_correction': row[suggested_corr_col].strip(),
                    'suggested_correction_field': row[suggested_field_col].strip()
                }
                
                # Index by ID
                buyer_id = row[buyer_id_col].strip().lower()
                if buyer_id:
                    index['by_id'][buyer_id] = data
                
                # Index by name
                first_name = row[buyer_first_col].strip().lower()
                surname = row[buyer_surname_col].strip().lower()
                if first_name and surname:
                    name_key = f"{first_name}|{surname}"
                    index['by_name'][name_key] = data
            
            cache[incident_file] = index
            return index
    
    except Exception as e:
        cache[incident_file] = {
            'success': False,
            'reason': f'Error reading file: {e}'
        }
        return cache[incident_file]

def find_incident_record(incident_index: Dict, buyer_id: str, buyer_first: str, buyer_surname: str) -> Dict:
    """Find matching record in pre-indexed incident file"""
    
    if not incident_index.get('success'):
        return {
            'found': False,
            'reason': incident_index.get('reason', 'Index not available')
        }
    
    # Try ID match first
    if buyer_id:
        data = incident_index['by_id'].get(buyer_id.lower())
        if data:
            return {'found': True, **data, 'reason': ''}
    
    # Try name match
    if buyer_first and buyer_surname:
        name_key = f"{buyer_first.lower()}|{buyer_surname.lower()}"
        data = incident_index['by_name'].get(name_key)
        if data:
            return {'found': True, **data, 'reason': ''}
    
    return {
        'found': False,
        'reason': 'No matching record found in incident file'
    }

def analyze_decision_logic(incident_data: Dict) -> str:
    """Analyze why the record resulted in 'No Change'"""
    if not incident_data.get('found'):
        return incident_data.get('reason', 'Unknown error')
    
    correction = incident_data.get('correction', '')
    agree = incident_data.get('agree_with_correction', '')
    suggested = incident_data.get('suggested_correction', '')
    
    # Decision logic analysis
    if not correction:
        if suggested:
            return "ERROR: Correction empty but Suggested populated - should apply Suggested, not No Change"
        else:
            return "CORRECT: No Correction value → No Change (expected behaviour)"
    else:
        # Correction exists
        agree_upper = agree.strip().upper()
        if agree_upper in ('Y', 'P', ''):
            return f"ERROR: Correction exists with Agree='{agree}' → Should apply Correction, not No Change"
        elif agree_upper in ('N', 'F'):
            if suggested:
                return f"ERROR: Correction exists with Agree='{agree}' and Suggested populated → Should apply Suggested, not No Change"
            else:
                return f"CORRECT: Correction exists but Agree='{agree}' with no Suggested → No Change (expected behaviour)"
        else:
            return f"ERROR: Correction exists with unknown Agree value '{agree}' → Should apply Correction, not No Change"

def main():
    """Main analysis function"""
    print("=" * 80)
    print("NO CHANGE RECORDS ANALYSIS")
    print("=" * 80)
    print()
    
    # Find replay output files
    replay_files = []
    if os.path.exists(REPLAY_OUTPUT_DIR):
        for filename in os.listdir(REPLAY_OUTPUT_DIR):
            if filename.endswith('_AJB.csv') and 'PHASE 3' in filename:
                replay_files.append(os.path.join(REPLAY_OUTPUT_DIR, filename))
    
    if not replay_files:
        print(f"ERROR: No replay output files found in {REPLAY_OUTPUT_DIR}")
        return
    
    print(f"Found {len(replay_files)} replay output file(s)")
    
    # Collect all No Change records
    no_change_records = []
    total_records = 0
    
    for replay_file in replay_files:
        file_type = 'IDs' if 'IDs' in os.path.basename(replay_file) else 'Names'
        print(f"\nProcessing: {os.path.basename(replay_file)} ({file_type} format)")
        
        with open(replay_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header
            
            for row in reader:
                total_records += 1
                
                # Check if correction column (index 6) is "No Change"
                if len(row) > 6 and row[6].strip() == "No Change":
                    parsed = parse_replay_record(row, file_type)
                    parsed['source_file'] = os.path.basename(replay_file)
                    no_change_records.append(parsed)
    
    print(f"\nTotal records processed: {total_records}")
    print(f"Records with 'No Change': {len(no_change_records)}")
    print()
    
    # Analyze each No Change record
    print("Analyzing decision tree fields from incident files...")
    print("Loading and indexing incident files...")
    
    results = []
    incident_cache = {}  # Cache indexed incident files
    
    # Pre-load all incident files that will be needed
    incident_codes_needed = set()
    for record in no_change_records:
        codes = [code.strip() for code in record['incident_codes'].split('|') if code.strip()]
        incident_codes_needed.update(codes)
    
    print(f"Pre-loading {len(incident_codes_needed)} incident files...")
    for incident_code in incident_codes_needed:
        incident_file = os.path.join(INCIDENT_FILES_DIR, INCIDENT_PATTERN.format(incident_code))
        load_incident_file_index(incident_file, incident_cache)
    print("✓ All incident files indexed")
    
    print("\nAnalyzing records...")
    for i, record in enumerate(no_change_records):
        if (i + 1) % 500 == 0:
            print(f"  Progress: {i + 1}/{len(no_change_records)}")
        
        incident_codes = [code.strip() for code in record['incident_codes'].split('|') if code.strip()]
        
        for incident_code in incident_codes:
            incident_file = os.path.join(INCIDENT_FILES_DIR, INCIDENT_PATTERN.format(incident_code))
            
            # Get cached incident index
            incident_index = incident_cache.get(incident_file, {'success': False, 'reason': 'Not loaded'})
            
            # Look up incident record in index
            incident_data = find_incident_record(
                incident_index,
                record['id_value'],
                record['first_name'],
                record['surname']
            )
            
            # Analyze decision logic
            decision_analysis = analyze_decision_logic(incident_data)
            
            # Store result
            results.append({
                'Source File': record['source_file'],
                'First Name': record['first_name'],
                'Surname': record['surname'],
                'Date of Birth': record['dob'],
                'ID Value': record['id_value'],
                'Incident Code': incident_code,
                'Correction (Incident)': incident_data.get('correction', 'N/A'),
                'Correction Field (Incident)': incident_data.get('correction_field', 'N/A'),
                'Agree With Correction': incident_data.get('agree_with_correction', 'N/A'),
                'Suggested Correction': incident_data.get('suggested_correction', 'N/A'),
                'Suggested Correction Field': incident_data.get('suggested_correction_field', 'N/A'),
                'Decision Analysis': decision_analysis,
                'Match Found': 'Yes' if incident_data.get('found') else 'No'
            })
    
    # Write report
    print(f"\nWriting report to: {OUTPUT_REPORT}")
    os.makedirs(os.path.dirname(OUTPUT_REPORT), exist_ok=True)
    
    with open(OUTPUT_REPORT, 'w', encoding='utf-8', newline='') as f:
        if results:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    
    print(f"✓ Report written successfully")
    print(f"  Total entries: {len(results)}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    correct_count = sum(1 for r in results if 'CORRECT' in r['Decision Analysis'])
    error_count = sum(1 for r in results if 'ERROR' in r['Decision Analysis'])
    not_found_count = sum(1 for r in results if r['Match Found'] == 'No')
    
    print(f"Expected 'No Change' (CORRECT): {correct_count}")
    print(f"Unexpected 'No Change' (ERROR): {error_count}")
    print(f"Records not found in incident files: {not_found_count}")
    
    if error_count > 0:
        print(f"\n⚠️  WARNING: {error_count} records have unexpected 'No Change' output!")
        print("   These may indicate bugs in the correction logic.")
    else:
        print(f"\n✓ All 'No Change' outputs are expected behaviour")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
