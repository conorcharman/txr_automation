#!/usr/bin/env python3
"""
Buyer ID Validation Script v3.0
================================

Validates buyer identification codes for transaction reporting accuracy testing.
Migrated from VBA macro BuyerIDValidation5_6.vb.

This script:
1. Reads buyer ID data from CSV
2. Validates IDs against country-specific formats
3. Generates corrections for invalid IDs
4. Outputs results with validation status and corrections

Version 3.0 Changes:
- Full ConfigManager integration matching replay scripts
- Supports YAML config files, environment variables, and CLI arguments
- Uses PathConfig and ProcessorConfig from txr_replay_core
- Consistent architecture with Phase 2/3 replay processors

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.buyer_id_validation --config config/local/accuracy_testing/buyer_validation.yaml
    
    # With environment variables
    export TXR_PATHS_INPUT_FILE="data/buyer_input.csv"
    export TXR_PATHS_OUTPUT_FILE="data/buyer_output.csv"
    export TXR_PATHS_LOG_OUTPUT="logs"
    python -m src.accuracy_testing.scripts.buyer_id_validation --use-env
    
    # With direct CLI arguments (backward compatible)
    python -m src.accuracy_testing.scripts.buyer_id_validation input.csv output.csv --log-level DEBUG

Input CSV columns (minimum required):
    - Transaction Reference
    - Person Code  
    - Account Type
    - Buyer ID Code
    - Type of Buyer ID Code
    - First Name
    - Surname
    - Date of Birth
    - Gender
    - Primary Nationality
    - Secondary Nationality (optional)

Output CSV adds:
    - Validation Status
    - Correction
    - Correction Type
    - Actions Taken
"""

import sys
import csv
import argparse
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.processor import (
    ClientRecord,
    IDValidationProcessor,
    ProcessingStats,
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
)

# Import core utilities
from core import (
    create_logger,
    StructuredLogger,
    safe_open_csv,
    get_buyer_incident_codes,
    get_validation_type,
    get_incident_description,
)


class BuyerIDValidator:
    """Main application class for buyer ID validation."""
    
    # CSV column mapping (0-indexed)
    COL_TRANSACTION_REF = 0
    COL_ACCOUNT_ID = 1
    COL_PERSON_CODE = 5
    COL_ACCOUNT_TYPE = 6
    COL_ID_VALUE = 7
    COL_ID_TYPE = 8
    COL_FNAME = 9
    COL_SNAME = 10
    COL_DOB = 11
    COL_GENDER = 12
    COL_PRIMARY_NAT = 13
    COL_SECONDARY_NAT = 14
    
    def __init__(
        self, 
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
        dry_run: bool = False,
        show_progress: bool = False
    ):
        """
        Initialize validator with configuration.
        
        Args:
            config_path: Path to YAML configuration file
            config_dict: Configuration dictionary (overrides config_path)
            dry_run: If True, preview changes without writing output
            show_progress: If True, display progress bar
        """
        self.dry_run = dry_run
        self.show_progress = show_progress
        # Load configuration
        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = AccuracyConfigManager.load_from_yaml(config_path)
        else:
            raise ValueError("Must provide either config_path or config_dict")
        
        # Get typed configuration objects
        self.path_config = AccuracyConfigManager.get_path_config(self.config)
        self.proc_config = AccuracyConfigManager.get_processor_config(self.config)
        
        # Setup logging
        self.logger = create_logger(
            name="buyer_id_validation",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Initialize processor
        self.processor = IDValidationProcessor(
            client_type="buyer",
            logger=self.logger,
            verbose=self.proc_config.verbose,
            italian_tracker_path=self.path_config.italian_tracker,
            main_tracker_path=self.path_config.main_tracker,
            template_path=self.path_config.template_file,
            template_id_column=self.path_config.template_id_column,
            template_type_column=self.path_config.template_type_column
        )
        
        # Get input/output files from path config
        self.input_file = Path(self.path_config.input_file)
        self.output_file = Path(self.path_config.output_file)
    
    def read_input_csv(self) -> List[ClientRecord]:
        """
        Read and parse input CSV file.
        
        Returns:
            List of ClientRecord objects
        """
        self.logger.info(f"Reading input file: {self.input_file}")
        records = []
        
        # Use safe_open_csv for automatic encoding detection
        f, encoding = safe_open_csv(self.input_file, 'r', newline='')
        self.logger.info(f"Detected encoding: {encoding}")
        
        try:
            with f:
                reader = csv.reader(f)
                header = next(reader)  # Skip header row
                
                for row_idx, row in enumerate(reader, start=2):  # Start at 2 (after header)
                    if len(row) < 15:  # Minimum required columns
                        self.logger.warning(f"Row {row_idx} has insufficient columns, skipping")
                        continue
                    
                    try:
                        record = ClientRecord(
                            row_index=row_idx,
                            transaction_ref=row[self.COL_TRANSACTION_REF].strip(),
                            account_id=row[self.COL_ACCOUNT_ID].strip(),
                            person_code=row[self.COL_PERSON_CODE].strip(),
                            account_type=row[self.COL_ACCOUNT_TYPE].strip(),
                            id_value=row[self.COL_ID_VALUE].strip(),
                            id_type=row[self.COL_ID_TYPE].strip(),
                            first_name=row[self.COL_FNAME].strip(),
                            surname=row[self.COL_SNAME].strip(),
                            date_of_birth=row[self.COL_DOB].strip(),
                            gender=row[self.COL_GENDER].strip(),
                            primary_nationality=row[self.COL_PRIMARY_NAT].strip(),
                            secondary_nationality=row[self.COL_SECONDARY_NAT].strip() if len(row) > self.COL_SECONDARY_NAT else "",
                            original_row=row
                        )
                        records.append(record)
                    
                    except Exception as e:
                        self.logger.error(f"Error parsing row {row_idx}: {e}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error reading CSV file: {e}", exc_info=True)
            raise
        
        self.logger.info(f"Successfully read {len(records)} records")
        return records
    
    def write_output_csv(self, records: List[ClientRecord]):
        """
        Write processed records to output CSV.
        
        Args:
            records: List of processed ClientRecord objects
        """
        self.logger.info(f"Writing output file: {self.output_file}")
        
        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Define output columns (matching VBA output format)
        output_columns = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Account Type",
            "Buyer ID Code",
            "Type of Buyer ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",  # VBA format: "ID:TYPE"
            "Correction Fields",  # VBA: "ID:IDT"
            "Tracker Status",  # Tracker system status
            "Pass/Fail",  # Format and logic validation status
            "Failure Reason",  # Specific reason for validation failure
            "Actions Taken",
            "Error",  # "Y" if mismatch, "N" if match
            "Kaizen Error",  # Template lookup result (ID:TYPE)
            "Match"  # "TRUE" if match, "FALSE" if not
        ]
        
        try:
            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in records:
                    # Swap nationalities if priority country is in secondary position (for easier review)
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    # Get priority country to check if swap is needed
                    priority_country = self._get_priority_country_for_record(record)
                    if priority_country:
                        # Check if priority is in secondary but not in primary
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat) if secondary_nat else None
                        
                        # If priority matches secondary (not primary), swap them
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                # Swap: put priority in Nat 1
                                primary_nat = secondary_nat
                                secondary_nat = record.primary_nationality
                    
                    # Build output row from original data + validation results
                    output_row = [
                        record.transaction_ref,
                        record.account_id,
                        record.person_code,
                        record.account_type,
                        record.id_value,
                        record.id_type,
                        record.first_name,
                        record.surname,
                        record.date_of_birth,
                        record.gender,
                        primary_nat,
                        secondary_nat,
                        record.correction_output or "",  # ID:TYPE format
                        record.correction_fields or "",  # Fields corrected
                        record.tracker_status or "",  # Tracker status
                        f"Format: {record.format_status} | Logic: {record.logic_status}" if record.format_status else "",  # Pass/Fail status
                        record.failure_reason or "",  # Failure reason
                        " | ".join(record.actions_taken) if record.actions_taken else "",
                        record.error or "",  # Error flag (Y/N)
                        record.kaizen_error or "",  # Template lookup result
                        record.match or ""  # Match result (TRUE/FALSE)
                    ]
                    writer.writerow(output_row)
            
            self.logger.info(f"Successfully wrote {len(records)} records")
        
        except Exception as e:
            self.logger.error(f"Error writing output CSV: {e}", exc_info=True)
            raise
    
    def _get_priority_country_for_record(self, record):
        """Get priority country for a single record (helper for nationality swapping)."""
        return self.processor._get_priority_country(record)
    
    def write_errors_only_csv(self, records: List[ClientRecord]):
        """
        Write only records with errors to a separate CSV file.
        
        Args:
            records: List of processed ClientRecord objects
        """
        errors_file = self.output_file.parent / f"{self.output_file.stem}_errors_only{self.output_file.suffix}"
        self.logger.info(f"Writing errors-only file: {errors_file}")
        
        # Filter to only invalid records
        error_records = [r for r in records if not r.is_valid]
        
        if not error_records:
            self.logger.info("No errors to write - all records passed validation")
            return
        
        # Ensure output directory exists
        errors_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Define output columns (matching main output)
        output_columns = [
            "Transaction Reference",
            "Person Code",
            "Account Type",
            "Buyer ID Code",
            "Type of Buyer ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",
            "Correction Fields",
            "Tracker Status",
            "Pass/Fail",
            "Failure Reason",
            "Actions Taken",
            "Error",
            "Kaizen Error",
            "Match"
        ]
        
        try:
            with open(errors_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in error_records:
                    # Swap nationalities if needed (same logic as main output)
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    priority_country = self._get_priority_country_for_record(record)
                    if priority_country:
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat) if secondary_nat else None
                        
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                primary_nat = secondary_nat
                                secondary_nat = record.primary_nationality
                    
                    output_row = [
                        record.transaction_ref,
                        record.person_code,
                        record.account_type,
                        record.id_value,
                        record.id_type,
                        record.first_name,
                        record.surname,
                        record.date_of_birth,
                        record.gender,
                        primary_nat,
                        secondary_nat,
                        record.correction_output or "",
                        record.correction_fields or "",
                        record.tracker_status or "",
                        f"Format: {record.format_status} | Logic: {record.logic_status}" if record.format_status else "",
                        record.failure_reason or "",
                        " | ".join(record.actions_taken) if record.actions_taken else "",
                        record.error or "",
                        record.kaizen_error or "",
                        record.match or ""
                    ]
                    writer.writerow(output_row)
            
            self.logger.info(f"Successfully wrote {len(error_records)} error records to {errors_file}")
        
        except Exception as e:
            self.logger.error(f"Error writing errors-only CSV: {e}", exc_info=True)
            raise
    
    def run(self):
        """Execute the validation workflow."""
        start_time = datetime.now()
        
        self.logger.log_header("BUYER ID VALIDATION v3.0")
        self.logger.info(f"Input file: {self.input_file}")
        self.logger.info(f"Output file: {self.output_file}")
        if self.dry_run:
            self.logger.info("*** DRY RUN MODE - No output file will be written ***")
        self.logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Read input
        records = self.read_input_csv()
        
        if not records:
            self.logger.error("No records to process")
            return
        
        # Step 2: Process each record
        self.logger.log_header("PROCESSING RECORDS")
        
        # Debug: Log sample of first record
        if records:
            first = records[0]
            self.logger.info(f"[DEBUG] Sample record 1:")
            self.logger.info(f"  id_value: '{first.id_value}'")
            self.logger.info(f"  id_type: '{first.id_type}'")
            self.logger.info(f"  person_code: '{first.person_code}'")
            self.logger.info(f"  first_name: '{first.first_name}'")
            self.logger.info(f"  surname: '{first.surname}'")
            self.logger.info(f"  dob: '{first.date_of_birth}'")
            self.logger.info(f"  primary_nationality: '{first.primary_nationality}'")
            self.logger.info(f"  secondary_nationality: '{first.secondary_nationality}'")
        
        processed_records = []
        
        # Setup progress bar if requested
        if self.show_progress:
            try:
                from tqdm import tqdm
                record_iter = tqdm(records, desc="Processing records", unit="rec")
            except ImportError:
                self.logger.warning("tqdm not installed - progress bar disabled. Install with: pip install tqdm")
                record_iter = records
        else:
            record_iter = records
        
        for record in record_iter:
            processed = self.processor.process_record(record)
            processed_records.append(processed)
        
        # Step 2.5: Aggregate joint accounts (JNT pairs)
        jnt_count = sum(1 for r in processed_records if r.account_type.upper() == "JNT")
        if jnt_count > 0:
            self.logger.info(f"Found {jnt_count} JNT account records - aggregating pairs...")
            processed_records = IDValidationProcessor.aggregate_jnt_accounts(processed_records)
            aggregated_count = sum(1 for r in processed_records if r.account_type.upper() == "JNT")
            jnt_removed = jnt_count - aggregated_count
            self.processor.stats.jnt_aggregated = jnt_removed
            self.logger.info(f"After aggregation: {aggregated_count} JNT records ({jnt_removed} duplicate rows removed)")
        
        # Step 3: Write output (skip if dry run)
        if self.dry_run:
            self.logger.info("Dry run mode - skipping output file write")
            self.logger.info(f"Would have written {len(processed_records)} records to: {self.output_file}")
            # Show sample of what would be written
            if processed_records:
                sample_record = processed_records[0]
                self.logger.info("Sample output (first record):")
                self.logger.info(f"  ID: {sample_record.id_value} ({sample_record.id_type})")
                self.logger.info(f"  Correction: {sample_record.correction_output or 'None'}")
                self.logger.info(f"  Actions: {' | '.join(sample_record.actions_taken) if sample_record.actions_taken else 'None'}")
                self.logger.info(f"  Status: Format={sample_record.format_status}, Logic={sample_record.logic_status}")
        else:
            self.write_output_csv(processed_records)
            
            # Write errors-only CSV if there are errors
            error_count = sum(1 for r in processed_records if not r.is_valid)
            if error_count > 0:
                self.logger.info(f"Writing errors-only CSV ({error_count} error records)...")
                self.write_errors_only_csv(processed_records)
        
        # Step 4: Summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.logger.log_header("PROCESSING COMPLETE")
        self.logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {duration}")
        
        # Print statistics
        self.processor.stats.print_summary(logger=self.logger)


def run_batch_validation(config: Dict, dry_run: bool = False, show_progress: bool = False):
    """
    Run validation for multiple incidents in batch mode.
    
    Args:
        config: Configuration dictionary with testing_period, incidents, and paths
        dry_run: If True, preview without writing
        show_progress: If True, show progress bars
    """
    # Extract batch configuration
    testing_period = config.get('testing_period', {})
    fiscal_year = testing_period.get('fiscal_year', 'FYXX')
    quarter = testing_period.get('quarter', 'QX')
    
    # Get batch mode configuration
    batch_config = config.get('batch', {})
    
    # Check for auto-discovery of incidents
    incidents_config = batch_config.get('incidents', [])
    if incidents_config == 'auto':
        # Auto-discover all standard buyer incidents (7_35, 7_37, 7_39)
        incidents = ['7_35', '7_37', '7_39']
        print(f"Auto-discovered {len(incidents)} standard buyer incidents: {', '.join(incidents)}")
    elif isinstance(incidents_config, list):
        incidents = incidents_config
    else:
        incidents = []
    
    # Get paths from batch configuration
    paths = batch_config.get('paths', {})
    extract_dir = Path(paths.get('extract_dir', 'data/extracts'))
    template_dir = Path(paths.get('template_dir', 'data/templates'))
    output_dir = Path(paths.get('output_dir', 'data/validated'))
    
    # Get filename patterns from batch configuration
    filename_patterns = batch_config.get('filename_patterns', {})
    extract_pattern = filename_patterns.get('extract', '{incident}_{fiscal_year}_{quarter}.csv')
    template_pattern = filename_patterns.get('template', '{fiscal_year} {quarter} {incident}.csv')
    output_pattern = filename_patterns.get('output', 'validated_{fiscal_year}_{quarter}_{incident}.csv')
    
    if not incidents:
        print("ERROR: No incidents specified in batch config")
        print("       Set batch.incidents to 'auto', 'all', or provide explicit list")
        return 1
    
    print(f"\n{'='*70}")
    print(f"BATCH BUYER ID VALIDATION - {fiscal_year} {quarter}")
    print(f"{'='*70}")
    print(f"Extract directory:  {extract_dir}")
    print(f"Template directory: {template_dir}")
    print(f"Output directory:   {output_dir}")
    print(f"Incidents:          {', '.join(incidents)}")
    print(f"{'='*70}\n")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_success = 0
    total_failed = 0
    
    for incident in incidents:
        print(f"\n{'─'*70}")
        print(f"Processing incident: {incident}")
        print(f"{'─'*70}")
        
        # Check validation type and route accordingly
        validation_type = get_validation_type(incident)
        if validation_type is None:
            print(f"⚠️  SKIPPING: Unknown incident code '{incident}'")
            print(f"   → Not found in incident code matrix")
            total_failed += 1
            continue
        elif validation_type == 'decision_maker':
            print(f"⚠️  SKIPPING: Decision maker incident requires different validation logic")
            print(f"   Description: {get_incident_description(incident)}")
            print(f"   (Requires chronological analysis by Person Code)")
            print(f"   → Not yet implemented in Python - see legacy VBA: InconsistentBuyerIDValidation")
            total_failed += 1
            continue
        elif validation_type != 'standard_id':
            print(f"⚠️  SKIPPING: Unexpected validation type '{validation_type}' for buyer validation")
            print(f"   Expected: 'standard_id', Got: '{validation_type}'")
            total_failed += 1
            continue
        
        # Build filenames using configured patterns
        extract_filename = extract_pattern.format(
            incident=incident, fiscal_year=fiscal_year, quarter=quarter
        )
        template_filename = template_pattern.format(
            incident=incident, fiscal_year=fiscal_year, quarter=quarter
        )
        extract_path = extract_dir / extract_filename
        template_path = template_dir / template_filename
        
        # Build output filename using configured pattern
        output_filename = output_pattern.format(
            incident=incident, fiscal_year=fiscal_year, quarter=quarter
        )
        output_path = output_dir / output_filename
        
        # Check if extract file exists (input data to validate)
        if not extract_path.exists():
            print(f"⚠️  Extract file not found: {extract_path}")
            print(f"   Skipping incident {incident}")
            total_failed += 1
            continue
        
        # Create modified config for this incident
        incident_config = config.copy()
        incident_config['paths'] = {
            **paths,
            'input_file': str(extract_path),
            'output_file': str(output_path),
            'template_file': str(template_path) if template_path.exists() else ''  # Optional Kaizen lookup
        }
        
        try:
            # Run validation for this incident
            validator = BuyerIDValidator(
                config_dict=incident_config,
                dry_run=dry_run,
                show_progress=show_progress
            )
            validator.run()
            
            print(f"✓ Completed: {incident}")
            total_success += 1
            
        except Exception as e:
            print(f"✗ Failed: {incident} - {e}")
            total_failed += 1
            continue
    
    # Print batch summary
    print(f"\n{'='*70}")
    print(f"BATCH VALIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"Successful: {total_success}/{len(incidents)}")
    print(f"Failed:     {total_failed}/{len(incidents)}")
    print(f"{'='*70}\n")
    
    return 0 if total_failed == 0 else 1


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Buyer ID Validation v3.0 - Validate buyer identification codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # With YAML configuration file
  python -m src.accuracy_testing.scripts.buyer_id_validation --config config/local/accuracy_testing/buyer_validation.yaml
  
  # With environment variables
  export TXR_PATHS_INPUT_FILE="data/buyer_input.csv"
  export TXR_PATHS_OUTPUT_FILE="data/buyer_output.csv"
  python -m src.accuracy_testing.scripts.buyer_id_validation --use-env
  
  # With direct CLI arguments (backward compatible)
  python -m src.accuracy_testing.scripts.buyer_id_validation input.csv output.csv
  
  # Override log level
  python -m src.accuracy_testing.scripts.buyer_id_validation --config config.yaml --log-level DEBUG
        """
    )
    
    parser.add_argument(
        'input_file',
        nargs='?',
        type=str,
        help='Path to input CSV file (backward compatible mode)'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        type=str,
        help='Path to output CSV file (backward compatible mode)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file'
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
        help='Override logging level from config'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without writing output file'
    )
    
    parser.add_argument(
        '--progress',
        action='store_true',
        help='Display progress bar for large files'
    )
    
    return parser.parse_args()


def main():
    """Main entry point with CLI support"""
    args = parse_args()
    
    try:
        # Determine configuration source
        if args.use_env:
            print("Loading configuration from environment variables...")
            config = AccuracyConfigManager.load_from_env("TXR_ACCURACY_")
        elif args.config:
            print(f"Loading configuration from {args.config}...")
            config = AccuracyConfigManager.load_from_yaml(args.config)
        elif args.input_file and args.output_file:
            # Backward compatible mode: build config from CLI args
            print("Running in backward compatible mode (CLI arguments)...")
            config = {
                'paths': {
                    'input_file': args.input_file,
                    'output_file': args.output_file,
                    'log_output': 'logs'
                },
                'processor': {
                    'log_level': args.log_level or 'INFO',
                    'verbose': False,
                    'batch_size': 1000
                }
            }
        else:
            # Default configuration path (same pattern as replay scripts)
            default_config = Path(__file__).parent.parent.parent.parent / "config" / "local" / "accuracy_testing" / "buyer_validation.yaml"
            if default_config.exists():
                print(f"Loading default configuration from {default_config}...")
                config = AccuracyConfigManager.load_from_yaml(str(default_config))
            else:
                print("Error: No configuration specified and default config not found")
                print("Use --config, --use-env, or provide input_file and output_file arguments")
                return 1
        
        # Check if this is batch mode (using mode field from config)
        mode = config.get('mode', 'single')  # Default to single if not specified
        is_batch_mode = mode == 'batch'
        
        if is_batch_mode:
            # Run batch validation for multiple incidents
            return run_batch_validation(
                config=config,
                dry_run=args.dry_run,
                show_progress=args.progress
            )
        else:
            # Single file mode (backward compatible)
            # Override log level if specified
            if args.log_level:
                if 'processor' not in config:
                    config['processor'] = {}
                config['processor']['log_level'] = args.log_level
            
            # Create and run validator
            validator = BuyerIDValidator(
                config_dict=config,
                dry_run=args.dry_run,
                show_progress=args.progress
            )
            validator.run()
            
            validator.logger.info("Buyer ID validation completed successfully")
            return 0
    
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
