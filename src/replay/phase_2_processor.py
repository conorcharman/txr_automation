#!/usr/bin/env python3
"""
Phase 2 Processor v3.1
Ultra-optimized processor for Phase II replay files using transaction reference lookups.
Adapted from Phase 3 v4.2 template with hash table indexing for maximum performance.

Author: GitHub Copilot
Date: October 9, 2025
Version: 3.1 - Bug Fixes for Character Replacement Scope and Encoding

CHANGES IN v3.1:
- Fixed character replacement scope (only applied to output CSV, not internal processing)
- Fixed character encoding issue (chr(172) instead of Unicode to prevent "Â¬")
- Added apply_character_replacement() method for output-only processing
- Preserved original values for internal consistency checking
"""

import csv
import os
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
import logging
from dataclasses import dataclass
import re
from collections import defaultdict

@dataclass
class ReplayRecord:
    """Represents a replay file record with parsed details"""
    incident_codes: List[str]
    transaction_reference: str
    original_row: List[str]
    row_index: int
    file_type: str  # 'single' or 'combined'
    filename: str

@dataclass
class LookupResult:
    """Represents the result of a transaction reference lookup"""
    found: bool
    correction: str = ""
    correction_field: str = ""
    error_flag: str = ""
    transaction_ref: str = ""

class IncidentFileIndex:
    """Optimized incident file with pre-built indexes for O(1) transaction reference lookups"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data_rows = []
        
        # Pre-built index for O(1) transaction reference lookups
        self.transaction_ref_index = {}  # transaction_ref -> row_index
        
        self.load_and_index()
    
    def load_and_index(self):
        """Load file and build transaction reference index"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                return
                
            self.data_rows = rows[1:]  # Skip header
            self._build_transaction_index()
            
        except Exception as e:
            logging.error(f"Error loading {self.file_path}: {e}")
    
    def _build_transaction_index(self):
        """Build transaction reference lookup index"""
        for i, row in enumerate(self.data_rows):
            if len(row) < 7:  # Ensure minimum columns
                continue
                
            # Index transaction reference (column 0)
            transaction_ref = row[0].strip() if row[0] else ""
            if transaction_ref:
                # Store first occurrence (as per requirement)
                if transaction_ref not in self.transaction_ref_index:
                    self.transaction_ref_index[transaction_ref] = i
    
    def lookup_by_transaction_ref(self, transaction_ref: str) -> Optional[int]:
        """Fast O(1) transaction reference lookup"""
        transaction_ref = transaction_ref.strip()  # Clean whitespace
        return self.transaction_ref_index.get(transaction_ref)

class Phase2ProcessorOptimized:
    """Ultra-optimized Phase 2 processor with transaction reference indexing"""
    
    def __init__(self):
        # File paths
        self.replay_input_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\reference\csv"
        self.incident_files_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\reference\FY25\Q3\incident_code_files\csv"
        self.replay_output_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\output"
        self.log_output_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\output\logs"
        
        self.setup_logging()
        
        # Statistics
        self.stats = {
            'processed_files': 0,
            'processed_records': 0,
            'successful_matches': 0,
            'not_found': 0,
            'no_corrections': 0,
            'inconsistent_corrections': 0,
            'errors': 0,
            'single_incident_files': 0,
            'combined_incident_files': 0
        }
        
        # Ultra-optimized: Pre-indexed incident files
        self.incident_indexes = {}  # incident_code -> IncidentFileIndex
        
    def setup_logging(self):
        """Setup logging configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"phase_2_processor_v3_1_log_{timestamp}.txt"
        log_filepath = os.path.join(self.log_output_path, log_filename)
        
        os.makedirs(self.log_output_path, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.log_filepath = log_filepath
    
    def detect_file_type(self, filename: str) -> str:
        """Detect if file is single or combined incident type"""
        # Combined incident files have "+" in the filename
        return 'combined' if '+' in filename else 'single'
    
    def get_column_mapping(self, file_type: str) -> Dict[str, int]:
        """Get column mappings based on file type"""
        if file_type == 'single':
            return {
                'incident_code': 0,
                'agrees': 8,
                'correction_field': 9, 
                'correction_value': 10,
                'transaction_ref': 13
            }
        else:  # combined
            return {
                'incident_code': 0,
                'agrees': 7,
                'correction_field': 8,
                'correction_value': 9,
                'transaction_ref': 12
            }
    
    def parse_incident_codes(self, incident_codes_str: str) -> List[str]:
        """Parse incident codes from column 0, handling multiple codes"""
        if not incident_codes_str or not incident_codes_str.strip():
            return []
        
        # Split on "|" and filter empty strings
        codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
        return codes
    
    def parse_replay_record(self, row: List[str], row_index: int, file_type: str, filename: str) -> ReplayRecord:
        """Parse a replay file record"""
        try:
            col_map = self.get_column_mapping(file_type)
            
            # Ensure row has enough columns
            while len(row) < max(col_map.values()) + 1:
                row.append("")
            
            # Extract incident codes from column 0
            incident_codes_str = row[col_map['incident_code']].strip()
            incident_codes = self.parse_incident_codes(incident_codes_str)
            
            # Extract transaction reference
            transaction_ref = row[col_map['transaction_ref']].strip()
            
            return ReplayRecord(
                incident_codes=incident_codes,
                transaction_reference=transaction_ref,
                original_row=row.copy(),
                row_index=row_index,
                file_type=file_type,
                filename=filename
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing replay record at row {row_index + 1} in {filename}: {e}")
            return ReplayRecord([], "", row.copy(), row_index, file_type, filename)
    
    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find incident file for given code"""
        pattern = f"FY25 Q3 - {incident_code}.csv"
        filepath = os.path.join(self.incident_files_path, pattern)
        
        if os.path.exists(filepath):
            return filepath
        
        # Fallback glob search
        glob_pattern = os.path.join(self.incident_files_path, f"*{incident_code}*.csv")
        matches = glob.glob(glob_pattern)
        return matches[0] if matches else None
    
    def preload_and_index_incident_files(self):
        """Preload and index all required incident files"""
        self.logger.info("Analyzing replay files for incident codes...")
        
        # Collect all incident codes from replay files
        incident_codes = set()
        
        replay_files = [f for f in os.listdir(self.replay_input_path) if f.endswith('.csv')]
        
        for replay_filename in replay_files:
            replay_filepath = os.path.join(self.replay_input_path, replay_filename)
            file_type = self.detect_file_type(replay_filename)
            col_map = self.get_column_mapping(file_type)
            
            try:
                with open(replay_filepath, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                
                for row in rows[1:]:  # Skip header
                    if len(row) > col_map['incident_code']:
                        incident_codes_str = row[col_map['incident_code']].strip()
                        codes = self.parse_incident_codes(incident_codes_str)
                        incident_codes.update(codes)
                        
            except Exception as e:
                self.logger.warning(f"Error analyzing {replay_filename}: {e}")
        
        # Load and index incident files
        self.logger.info(f"Loading and indexing {len(incident_codes)} incident files...")
        
        loaded_count = 0
        for incident_code in incident_codes:
            incident_file = self.find_incident_file(incident_code)
            if incident_file:
                self.logger.debug(f"Indexing {incident_code}...")
                self.incident_indexes[incident_code] = IncidentFileIndex(incident_file)
                loaded_count += 1
            else:
                self.logger.warning(f"Incident file not found for code: {incident_code}")
        
        self.logger.info(f"Successfully indexed {loaded_count} incident files")
    
    def lookup_transaction(self, record: ReplayRecord, incident_code: str) -> LookupResult:
        """Ultra-fast transaction lookup using pre-built indexes"""
        if incident_code not in self.incident_indexes:
            return LookupResult(found=False)
        
        index = self.incident_indexes[incident_code]
        
        # O(1) transaction reference lookup
        row_idx = index.lookup_by_transaction_ref(record.transaction_reference)
        
        if row_idx is not None:
            return self._create_lookup_result(index.data_rows[row_idx])
        
        return LookupResult(found=False)
    
    def _create_lookup_result(self, row: List[str]) -> LookupResult:
        """Create lookup result from incident file row"""
        try:
            error_flag = row[4].strip() if len(row) > 4 else ""
            transaction_ref = row[0].strip() if len(row) > 0 else ""
            
            if error_flag.upper() == 'Y':
                correction = row[5].strip() if len(row) > 5 else ""
                correction_field = row[6].strip() if len(row) > 6 else ""
                
                # v3.1 FIX: Character replacement will be done when writing to output file
                # Keep original values here for consistency checking
            else:
                correction = "No Change"
                correction_field = "No Change"
            
            return LookupResult(
                found=True,
                correction=correction,
                correction_field=correction_field,
                error_flag=error_flag,
                transaction_ref=transaction_ref
            )
        except Exception as e:
            self.logger.error(f"Error creating lookup result: {e}")
            return LookupResult(found=False)
    
    def apply_character_replacement(self, value: str) -> str:
        """Apply character replacement for output file (: -> ¬)
        
        v3.1 FIX: Only apply replacement to values being written to output CSV.
        This prevents encoding issues and preserves original values for internal processing.
        """
        if not value or value in ["No Change", "Client not found", "Processing Error"]:
            return value
        # Use ASCII character replacement to avoid encoding issues (chr(172) = ¬)
        return value.replace(':', chr(172))  # chr(172) = ¬ (NOT SIGN)
    
    def process_replay_record(self, record: ReplayRecord) -> Tuple[str, str, str]:
        """Process a replay record and return correction data"""
        if not record.incident_codes:
            self.stats['not_found'] += 1
            return "N", "Client not found", "Client not found"
        
        all_corrections = []
        all_correction_fields = []
        
        for incident_code in record.incident_codes:
            result = self.lookup_transaction(record, incident_code)
            
            if result.found:
                all_corrections.append(result.correction)
                all_correction_fields.append(result.correction_field)
                self.logger.debug(f"Found match for {record.transaction_reference} in {incident_code}")
            else:
                self.logger.warning(f"Transaction {record.transaction_reference} not found in {incident_code}")
        
        if not all_corrections:
            self.stats['not_found'] += 1
            return "N", "Client not found", "Client not found"
        
        # Handle multiple corrections - check for consistency
        unique_corrections = list(set(all_corrections))
        unique_fields = list(set(all_correction_fields))
        
        if len(unique_corrections) > 1 or len(unique_fields) > 1:
            self.stats['inconsistent_corrections'] += 1
            self.logger.warning(f"Inconsistent corrections for {record.transaction_reference}: {unique_corrections}")
            # Return all corrections separated by "|"
            final_correction = "|".join(all_corrections)
            final_field = "|".join(all_correction_fields)
            return "N", final_field, final_correction
        else:
            # Consistent corrections
            self.stats['successful_matches'] += 1
            if unique_corrections[0] == "No Change":
                self.stats['no_corrections'] += 1
            return "N", unique_fields[0], unique_corrections[0]
    
    def process_replay_file(self, filename: str):
        """Process a single replay file"""
        input_filepath = os.path.join(self.replay_input_path, filename)
        
        # Generate output filename: replace "KR" with "AJB"
        output_filename = filename.replace('KR', 'AJB')
        output_filepath = os.path.join(self.replay_output_path, output_filename)
        
        file_type = self.detect_file_type(filename)
        col_map = self.get_column_mapping(file_type)
        
        self.logger.info(f"Processing {file_type} incident replay file: {filename}")
        
        if file_type == 'single':
            self.stats['single_incident_files'] += 1
        else:
            self.stats['combined_incident_files'] += 1
        
        try:
            # Read input file
            with open(input_filepath, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                self.logger.warning(f"No data rows in {filename}")
                return
            
            header = rows[0]
            data_rows = rows[1:]
            processed_rows = [header]
            
            # Process each record
            batch_size = 50
            total_rows = len(data_rows)
            
            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                
                for i in range(batch_start, batch_end):
                    row = data_rows[i]
                    
                    try:
                        # Parse replay record
                        record = self.parse_replay_record(row, i + 1, file_type, filename)
                        
                        # Process record
                        agrees, correction_field, correction_value = self.process_replay_record(record)
                        
                        # v3.1 FIX: Apply character replacement ONLY when writing to output file
                        row[col_map['agrees']] = agrees
                        row[col_map['correction_field']] = self.apply_character_replacement(correction_field)
                        row[col_map['correction_value']] = self.apply_character_replacement(correction_value)
                        
                        processed_rows.append(row)
                        self.stats['processed_records'] += 1
                    
                    except Exception as e:
                        self.logger.error(f"Error processing row {i + 1} in {filename}: {e}")
                        # Set error values
                        row[col_map['agrees']] = "N"
                        row[col_map['correction_field']] = "Processing Error"
                        row[col_map['correction_value']] = "Processing Error"
                        processed_rows.append(row)
                        self.stats['errors'] += 1
                
                # Progress report
                progress = ((batch_end / total_rows) * 100)
                self.logger.info(f"Progress: {batch_end}/{total_rows} ({progress:.1f}%)")
            
            # Write output file
            os.makedirs(self.replay_output_path, exist_ok=True)
            with open(output_filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(processed_rows)
            
            self.logger.info(f"Completed {filename} -> {output_filename}")
            
        except Exception as e:
            self.logger.error(f"Error processing replay file {filename}: {e}")
            self.stats['errors'] += 1
    
    def generate_summary_log(self):
        """Generate processing summary"""
        summary_lines = [
            "=" * 80,
            "PHASE 2 PROCESSOR v3.1 (BUG FIXES) - SUMMARY",
            "=" * 80,
            f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "v3.1 IMPROVEMENTS:",
            "  ✓ Fixed character replacement scope (output-only)",
            "  ✓ Fixed encoding issue (chr(172) prevents 'Â¬')",
            "  ✓ Preserved original values for internal consistency",
            "",
            "FILE STATISTICS:",
            f"  Replay files processed: {self.stats['processed_files']}",
            f"  Single incident files: {self.stats['single_incident_files']}",
            f"  Combined incident files: {self.stats['combined_incident_files']}",
            "",
            "RECORD STATISTICS:",
            f"  Records processed: {self.stats['processed_records']}",
            f"  Successful matches: {self.stats['successful_matches']}",
            f"  Not found: {self.stats['not_found']}",
            f"  No corrections needed: {self.stats['no_corrections']}",
            f"  Inconsistent corrections: {self.stats['inconsistent_corrections']}",
            f"  Processing errors: {self.stats['errors']}",
            "",
            "OPTIMIZATION INFO:",
            f"  Incident files indexed: {len(self.incident_indexes)}",
            f"  Total transaction references indexed: {sum(len(idx.transaction_ref_index) for idx in self.incident_indexes.values())}",
            "=" * 80
        ]
        
        with open(self.log_filepath, 'a', encoding='utf-8') as f:
            f.write('\n' + '\n'.join(summary_lines) + '\n')
        
        for line in summary_lines:
            print(line)
    
    def run(self):
        """Main execution method"""
        start_time = datetime.now()
        
        self.logger.info("Starting Phase 2 Processor v3.1 (Bug Fixes)")
        self.logger.info(f"Replay input path: {self.replay_input_path}")
        self.logger.info(f"Incident files path: {self.incident_files_path}")
        self.logger.info(f"Output path: {self.replay_output_path}")
        
        # Ensure directories exist
        os.makedirs(self.replay_output_path, exist_ok=True)
        os.makedirs(self.log_output_path, exist_ok=True)
        
        # Preload and index all incident files
        self.preload_and_index_incident_files()
        
        # Get all CSV files in replay directory
        replay_files = [f for f in os.listdir(self.replay_input_path) if f.endswith('.csv')]
        
        if not replay_files:
            self.logger.error("No CSV replay files found in input directory")
            return
        
        self.logger.info(f"Found {len(replay_files)} replay files to process")
        
        # Process each replay file
        for filename in replay_files:
            self.process_replay_file(filename)
            self.stats['processed_files'] += 1
        
        # Generate summary
        end_time = datetime.now()
        self.logger.info(f"Total processing time: {end_time - start_time}")
        self.generate_summary_log()
        
        self.logger.info("Phase 2 Processor v3.1 completed successfully")

def main():
    """Main entry point"""
    try:
        processor = Phase2ProcessorOptimized()
        processor.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())