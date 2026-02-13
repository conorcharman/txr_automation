#!/usr/bin/env python3
"""
Phase 2 Processor v4.1
Refactored processor for Phase II replay files using shared txr_replay_core library.
Leverages ConfigManager, StructuredLogger, and shared data structures for maintainability.

Author: GitHub Copilot
Date: December 23, 2025
Version: 4.1 - Updated correction decision logic

CHANGES IN v4.1:
- Implemented new correction decision logic (February 2026)
- Removed Error Flag dependency from decision flow
- Correction column existence checked first (not last)
- Agree With Correction now supports Y/P (apply) and N/F (don't apply) values
- Suggested Correction is fallback when Correction is empty or analyst disagrees
- Added detailed debug logging for correction routing

CHANGES IN v4.0:
- Migrated to txr_replay_core library (ConfigManager, StructuredLogger, data structures)
- Replaced hardcoded paths with configuration file
- Added CLI interface with argparse
- Using shared ReplayRecord, LookupResult, ProcessingStats
- Using CharacterReplacement utility from core library
- Improved logging with structured logger
"""

import csv
import os
import glob
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
from pathlib import Path

# Import from core library
from core import (
    ReplayRecord,
    LookupResult,
    ProcessingStats,
    ConfigManager,
    create_logger,
    CharacterReplacement,
    safe_open_csv,
)
from core.data import Phase2SingleColumns, Phase2CombinedColumns, ClientErrorColumns


class IncidentColumnMapper:
    """Maps column names to indices in incident template files."""
    
    def __init__(self, header: List[str], column_config: Dict[str, str], logger=None):
        """
        Initialize column mapper.
        
        Args:
            header: List of column names from CSV header
            column_config: Dict mapping logical names to column names from config
            logger: Logger instance
        """
        self.header = header
        self.column_config = column_config
        self.logger = logger
        self.indices = {}
        
        self._map_columns()
    
    def _map_columns(self):
        """Map column names to their indices."""
        for logical_name, column_name in self.column_config.items():
            try:
                index = self.header.index(column_name)
                self.indices[logical_name] = index
            except ValueError:
                if self.logger:
                    self.logger.warning(f"Column '{column_name}' not found in incident file")
                self.indices[logical_name] = None
    
    def get(self, logical_name: str, default=None) -> Optional[int]:
        """Get column index by logical name."""
        return self.indices.get(logical_name, default)
    
    def has_column(self, logical_name: str) -> bool:
        """Check if column exists."""
        return self.indices.get(logical_name) is not None


class IncidentFileIndex:
    """Optimized incident file with pre-built indexes for O(1) transaction reference lookups"""
    
    def __init__(self, file_path: str, column_config: Dict[str, str], logger=None):
        self.file_path = file_path
        self.data_rows = []
        self.header = []
        self.column_mapper = None
        self.logger = logger
        self.column_config = column_config
        
        # Pre-built index for O(1) transaction reference lookups
        self.transaction_ref_index = {}  # transaction_ref -> row_index
        
        self.load_and_index()
    
    def load_and_index(self):
        """Load file and build transaction reference index"""
        try:
            f, encoding = safe_open_csv(self.file_path, 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                return
            
            self.header = rows[0]
            self.data_rows = rows[1:]  # Skip header
            
            # Initialize column mapper
            self.column_mapper = IncidentColumnMapper(self.header, self.column_config, self.logger)
            
            self._build_transaction_index()
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error loading {self.file_path}: {e}")
    
    def _build_transaction_index(self):
        """Build transaction reference lookup index"""
        txn_ref_col = self.column_mapper.get('transaction_ref')
        if txn_ref_col is None:
            if self.logger:
                self.logger.error(f"Transaction Reference column not found in {self.file_path}")
            return
        
        for i, row in enumerate(self.data_rows):
            if len(row) <= txn_ref_col:
                continue
                
            # Index transaction reference
            transaction_ref = row[txn_ref_col].strip() if row[txn_ref_col] else ""
            if transaction_ref:
                # Store first occurrence (as per requirement)
                if transaction_ref not in self.transaction_ref_index:
                    self.transaction_ref_index[transaction_ref] = i
    
    def lookup_by_transaction_ref(self, transaction_ref: str) -> Optional[int]:
        """Fast O(1) transaction reference lookup"""
        transaction_ref = transaction_ref.strip()  # Clean whitespace
        return self.transaction_ref_index.get(transaction_ref)

class Phase2Processor:
    """Phase 2 processor with transaction reference indexing and configuration management"""
    
    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize Phase 2 Processor
        
        Args:
            config_path: Path to YAML configuration file
            config_dict: Configuration dictionary (overrides config_path)
        """
        # Load configuration
        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = ConfigManager.load_from_yaml(config_path)
        else:
            raise ValueError("Must provide either config_path or config_dict")
        
        # Get typed configuration objects
        self.path_config = ConfigManager.get_path_config(self.config)
        self.proc_config = ConfigManager.get_processor_config(self.config)
        
        # Setup logging
        self.logger = create_logger(
            name="phase2_processor",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Statistics using ProcessingStats from core library
        self.stats = ProcessingStats()
        
        # Character replacement utility
        self.char_replacer = CharacterReplacement()
        
        # Incident file pattern from config (NO default - user must specify)
        incident_pattern = self.config.get('files', {}).get('incident_pattern')
        if not incident_pattern:
            raise ValueError("Configuration error: 'files.incident_pattern' is required in config file")
        self.incident_pattern = incident_pattern
        
        # Incident template column configuration (NO defaults - user must specify)
        self.incident_columns = self.config.get('incident_columns')
        if not self.incident_columns:
            raise ValueError("Configuration error: 'incident_columns' section is required in config file")
        
        # Ultra-optimized: Pre-indexed incident files
        self.incident_indexes = {}  # incident_code -> IncidentFileIndex
        
        # Output filename replacement pattern (from config)
        replace_config = self.config.get('processor', {}).get('replace_pattern', {})
        self.replace_from = replace_config.get('from', '')
        self.replace_to = replace_config.get('to', '')
        
        if self.replace_from and not self.replace_to:
            raise ValueError("Configuration error: 'replace_pattern.to' is required when 'replace_pattern.from' is specified")
        if self.replace_to and not self.replace_from:
            raise ValueError("Configuration error: 'replace_pattern.from' is required when 'replace_pattern.to' is specified")
    
    def detect_file_type(self, filename: str) -> str:
        """Detect if file is single or combined incident type"""
        # Combined incident files have "+" in the filename
        return 'combined' if '+' in filename else 'single'
    
    def get_column_mapping(self, file_type: str) -> Dict[str, int]:
        """Get column mappings based on file type"""
        if file_type == 'single':
            cols = Phase2SingleColumns
            return {
                'incident_code': cols.INCIDENT_CODE,
                'agrees': cols.AGREES,
                'correction_field': cols.CORRECTION_FIELD, 
                'correction_value': cols.CORRECTION_VALUE,
                'transaction_ref': cols.TRANSACTION_REF
            }
        else:  # combined
            cols = Phase2CombinedColumns
            return {
                'incident_code': cols.INCIDENT_CODE,
                'agrees': cols.AGREES,
                'correction_field': cols.CORRECTION_FIELD,
                'correction_value': cols.CORRECTION_VALUE,
                'transaction_ref': cols.TRANSACTION_REF
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
                record_type='phase2',
                incident_codes=incident_codes,
                transaction_reference=transaction_ref,
                original_row=row.copy(),
                row_index=row_index,
                file_type=file_type,
                source_file=filename
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing replay record at row {row_index + 1} in {filename}: {e}")
            return ReplayRecord(
                record_type='phase2',
                incident_codes=[],
                transaction_reference="",
                original_row=row.copy(),
                row_index=row_index,
                file_type=file_type,
                source_file=filename
            )
    
    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find incident file for given code using configurable pattern"""
        # Extract prefix from pattern (e.g., "FY25 Q4 " from "FY25 Q4 *.csv")
        pattern_prefix = self.incident_pattern.replace('*.csv', '').strip()
        
        # Try primary pattern (space, no dash)
        pattern = f"{pattern_prefix} {incident_code}.csv"
        filepath = os.path.join(self.path_config.incident_files, pattern)
        
        if os.path.exists(filepath):
            return filepath
        
        # Backwards compatibility: Try with dash
        pattern_with_dash = f"{pattern_prefix} - {incident_code}.csv"
        filepath_with_dash = os.path.join(self.path_config.incident_files, pattern_with_dash)
        
        if os.path.exists(filepath_with_dash):
            return filepath_with_dash
        
        # Fallback glob search
        glob_pattern = os.path.join(self.path_config.incident_files, f"*{incident_code}*.csv")
        matches = glob.glob(glob_pattern)
        return matches[0] if matches else None
    
    def preload_and_index_incident_files(self):
        """Preload and index all required incident files"""
        self.logger.log_header("INCIDENT FILE INDEXING")
        self.logger.info("Analyzing replay files for incident codes...")
        
        # Collect all incident codes from replay files
        incident_codes = set()
        
        replay_files = [f for f in os.listdir(self.path_config.replay_input) if f.endswith('.csv')]
        
        for replay_filename in replay_files:
            replay_filepath = os.path.join(self.path_config.replay_input, replay_filename)
            file_type = self.detect_file_type(replay_filename)
            col_map = self.get_column_mapping(file_type)
            
            try:
                f, encoding = safe_open_csv(Path(replay_filepath), 'r', newline='')
                with f:
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
                self.incident_indexes[incident_code] = IncidentFileIndex(
                    incident_file, 
                    self.incident_columns, 
                    self.logger
                )
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
            return self._create_lookup_result(index.data_rows[row_idx], index.column_mapper)
        
        return LookupResult(found=False)
    
    def _create_lookup_result(self, row: List[str], column_mapper: IncidentColumnMapper) -> LookupResult:
        """Create lookup result from incident file row with new correction decision logic.
        
        Decision Flow:
        1. Check if Correction column has value:
           - If YES: Check Agree With Correction
             - If Y/P/empty: Apply Correction
             - If N/F: Check Suggested Correction -> Apply if exists, else No Change
           - If NO: Check Suggested Correction -> Apply if exists, else No Change
        """
        try:
            # Get column indices
            txn_ref_col = column_mapper.get('transaction_ref')
            correction_col = column_mapper.get('correction')
            correction_field_col = column_mapper.get('correction_field')
            agree_col = column_mapper.get('agree_with_correction')
            suggested_correction_col = column_mapper.get('suggested_correction')
            suggested_correction_field_col = column_mapper.get('suggested_correction_field')
            
            # Extract transaction reference
            transaction_ref = row[txn_ref_col].strip() if txn_ref_col is not None and len(row) > txn_ref_col else ""
            
            # Extract correction values
            correction_value = row[correction_col].strip() if correction_col is not None and len(row) > correction_col else ""
            correction_field_value = row[correction_field_col].strip() if correction_field_col is not None and len(row) > correction_field_col else ""
            
            # Extract suggested correction values
            suggested_correction_value = row[suggested_correction_col].strip() if suggested_correction_col is not None and len(row) > suggested_correction_col else ""
            suggested_correction_field_value = row[suggested_correction_field_col].strip() if suggested_correction_field_col is not None and len(row) > suggested_correction_field_col else ""
            
            # NEW DECISION LOGIC
            correction = "No Change"
            correction_field = "No Change"
            
            # Check if Correction column has a value
            if correction_value:
                # Extract Agree With Correction value
                agree_value = row[agree_col].strip().upper() if agree_col is not None and len(row) > agree_col else ""
                
                # If agree is Y, P, or empty -> apply Correction
                if agree_value in ('Y', 'P', ''):
                    correction = correction_value
                    correction_field = correction_field_value
                    self.logger.debug(f"Applying Correction (Agree={agree_value or 'empty'})")
                # If agree is N or F -> check Suggested Correction
                elif agree_value in ('N', 'F'):
                    if suggested_correction_value:
                        correction = suggested_correction_value
                        correction_field = suggested_correction_field_value
                        self.logger.debug(f"Applying Suggested Correction (analyst disagreed)")
                    else:
                        self.logger.debug(f"No correction (analyst disagreed, no suggestion provided)")
                else:
                    # Unknown agree value - default to applying Correction
                    correction = correction_value
                    correction_field = correction_field_value
                    self.logger.warning(f"Unknown Agree value '{agree_value}', defaulting to Correction")
            else:
                # No Correction value -> check Suggested Correction as fallback
                if suggested_correction_value:
                    correction = suggested_correction_value
                    correction_field = suggested_correction_field_value
                    self.logger.debug(f"Applying Suggested Correction (no automated correction)")
                else:
                    self.logger.debug(f"No correction to apply")
            
            return LookupResult(
                found=True,
                correction=correction,
                correction_field=correction_field,
                error_flag="",  # Deprecated - no longer used
                transaction_ref=transaction_ref
            )
        except Exception as e:
            self.logger.error(f"Error creating lookup result: {e}")
            return LookupResult(found=False)
    
    def process_replay_record(self, record: ReplayRecord) -> Tuple[str, str, str]:
        """Process a replay record and return correction data"""
        if not record.incident_codes:
            self.stats.increment('not_found')
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
            self.stats.increment('not_found')
            return "N", "Client not found", "Client not found"
        
        # Handle multiple corrections - check for consistency
        unique_corrections = list(set(all_corrections))
        unique_fields = list(set(all_correction_fields))
        
        if len(unique_corrections) > 1 or len(unique_fields) > 1:
            self.stats.increment('inconsistent_corrections')
            self.logger.warning(f"Inconsistent corrections for {record.transaction_reference}: {unique_corrections}")
            # Return all corrections separated by "|"
            final_correction = "|".join(all_corrections)
            final_field = "|".join(all_correction_fields)
            return "N", final_field, final_correction
        else:
            # Consistent corrections
            self.stats.increment('successful_matches')
            if unique_corrections[0] == "No Change":
                self.stats.increment('no_corrections')
            return "N", unique_fields[0], unique_corrections[0]
    
    def process_replay_file(self, filename: str):
        """Process a single replay file"""
        input_filepath = os.path.join(self.path_config.replay_input, filename)
        
        # Generate output filename: replace pattern from config
        output_filename = filename.replace(self.replace_from, self.replace_to)
        output_filepath = os.path.join(self.path_config.replay_output, output_filename)
        
        file_type = self.detect_file_type(filename)
        col_map = self.get_column_mapping(file_type)
        
        self.logger.info(f"Processing {file_type} incident replay file: {filename}")
        
        if file_type == 'single':
            self.stats.increment('single_incident_files')
        else:
            self.stats.increment('combined_incident_files')
        
        try:
            # Read input file
            f, encoding = safe_open_csv(Path(input_filepath), 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                self.logger.warning(f"No data rows in {filename}")
                return
            
            header = rows[0]
            data_rows = rows[1:]
            processed_rows = [header]
            
            # Process each record
            batch_size = self.proc_config.batch_size
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
                        
                        # Apply character replacement using core library utility
                        row[col_map['agrees']] = agrees
                        row[col_map['correction_field']] = self.char_replacer.colon_to_not_sign(correction_field)
                        row[col_map['correction_value']] = self.char_replacer.colon_to_not_sign(correction_value)
                        
                        processed_rows.append(row)
                        self.stats.increment('processed_records')
                    
                    except Exception as e:
                        self.logger.error(f"Error processing row {i + 1} in {filename}: {e}")
                        # Set error values
                        row[col_map['agrees']] = "N"
                        row[col_map['correction_field']] = "Processing Error"
                        row[col_map['correction_value']] = "Processing Error"
                        processed_rows.append(row)
                        self.stats.increment('errors')
                
                # Progress report
                progress = ((batch_end / total_rows) * 100)
                self.logger.info(f"Progress: {batch_end}/{total_rows} ({progress:.1f}%)")
            
            # Write output file
            os.makedirs(self.path_config.replay_output, exist_ok=True)
            with open(output_filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(processed_rows)
            
            self.logger.info(f"Completed {filename} -> {output_filename}")
            
        except Exception as e:
            self.logger.error(f"Error processing replay file {filename}: {e}")
            self.stats.increment('errors')
    
    def run(self):
        """Main execution method"""
        start_time = datetime.now()
        
        self.logger.log_header("PHASE 2 PROCESSOR v4.0")
        self.logger.info(f"Replay input path: {self.path_config.replay_input}")
        self.logger.info(f"Incident files path: {self.path_config.incident_files}")
        self.logger.info(f"Output path: {self.path_config.replay_output}")
        
        # Ensure directories exist
        os.makedirs(self.path_config.replay_output, exist_ok=True)
        os.makedirs(self.path_config.log_output, exist_ok=True)
        
        # Preload and index all incident files
        self.preload_and_index_incident_files()
        
        # Get all CSV files in replay directory
        replay_files = [f for f in os.listdir(self.path_config.replay_input) if f.endswith('.csv')]
        
        if not replay_files:
            self.logger.error("No CSV replay files found in input directory")
            return
        
        self.logger.log_header(f"PROCESSING {len(replay_files)} REPLAY FILES")
        
        # Process each replay file
        for filename in replay_files:
            self.process_replay_file(filename)
            self.stats.increment('processed_files')
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        self.logger.info(f"Total processing time: {duration}")
        
        self.logger.log_header("PROCESSING SUMMARY")
        self.logger.log_stats(self.stats)
        
        # Additional metrics
        total_indexed = sum(len(idx.transaction_ref_index) for idx in self.incident_indexes.values())
        self.logger.info(f"Incident files indexed: {len(self.incident_indexes)}")
        self.logger.info(f"Total transaction references indexed: {total_indexed}")
        
        self.logger.info("Phase 2 Processor v4.0 completed successfully")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Phase 2 Processor v4.0 - Transaction Reference Lookup Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with configuration file
  python phase_2_processor.py --config config/phase2.yaml
  
  # Run with environment variables
  export TXR_PATHS_REPLAY_INPUT="/path/to/replay"
  export TXR_PATHS_INCIDENT_FILES="/path/to/incidents"
  python phase_2_processor.py --use-env
  
  # Override log level
  python phase_2_processor.py --config config/phase2.yaml --log-level DEBUG
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file (default: config/phase2.yaml)'
    )
    
    parser.add_argument(
        '--use-env',
        action='store_true',
        help='Load configuration from environment variables (TXR_* prefix)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Override log level from configuration'
    )
    
    return parser.parse_args()


def main():
    """Main entry point with CLI support"""
    args = parse_args()
    
    try:
        # Determine configuration source
        if args.use_env:
            print("Loading configuration from environment variables...")
            config = ConfigManager.load_from_env("TXR_")
        elif args.config:
            print(f"Loading configuration from {args.config}...")
            config = ConfigManager.load_from_yaml(args.config)
        else:
            # Default configuration path (use local config)
            default_config = Path(__file__).parent.parent.parent / "config" / "local" / "replay" / "phase2.yaml"
            if default_config.exists():
                print(f"Loading default configuration from {default_config}...")
                config = ConfigManager.load_from_yaml(str(default_config))
            else:
                print("Error: No configuration specified and default config not found")
                print("Use --config or --use-env to specify configuration")
                return 1
        
        # Override log level if specified
        if args.log_level:
            if 'processor' not in config:
                config['processor'] = {}
            config['processor']['log_level'] = args.log_level
        
        # Create and run processor
        processor = Phase2Processor(config_dict=config)
        processor.run()
        
        return 0
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())