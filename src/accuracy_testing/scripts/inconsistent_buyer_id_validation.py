#!/usr/bin/env python3
"""
Inconsistent Buyer ID Validation Script v1.4
=============================================

Validates buyer identification codes for INCONSISTENT ID scenarios (incident 7_66).
Migrated from VBA macro InconsistentBuyerIDValidation1_3.vb.

This script handles records where the same person has different IDs across multiple trades.
It applies a specialized algorithm that:
1. Groups records by Person Code
2. Sorts each group chronologically by Trade_Date_Time
3. Validates each ID using standard format + logic rules
4. For each (Person Code, ID Type, Nationality Prefix) group:
   - Finds the MOST RECENT (latest datetime) VALID ID
   - Corrects ALL records with DIFFERENT ID values to the most recent valid one
   - This includes both INVALID and VALID IDs with different values

Key differences from standard validation:
- Groups by Person Code, not just individual record validation
- Uses Trade_Date_Time for chronological ordering
- Detects fallback IDs (CC_PersonCode pattern)
- Standardizes ALL IDs to most recent valid (both invalid and valid-but-different)
- Only IDs matching most recent valid are left unchanged

Version 1.4 Changes (2026-02-11):
- Now corrects VALID IDs that differ from most recent valid (standardization)
- Previous versions only corrected invalid IDs to closest valid
- Example: If person has GBNZ283821B (valid, 2024-01-01), GBNZG283821B (invalid, 2024-02-01),
  and GBNZ283821A (valid, 2024-03-01), now ALL are corrected to GBNZ283821A

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation --config config/local/accuracy_testing/inconsistent_buyer.yaml
    
    # With environment variables
    export TXR_PATHS_INPUT_FILE="data/buyer_input.csv"
    export TXR_PATHS_OUTPUT_FILE="data/buyer_output.csv"
    export TXR_PATHS_LOG_OUTPUT="logs"
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation --use-env
    
    # With direct CLI arguments
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation input.csv output.csv --log-level DEBUG

Input CSV columns (minimum required):
    - Transaction Reference
    - Account ID
    - Trade_Date_Time (format: YYYY-MM-DD-HH-MM-SS-MSMS)
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
    - Correction (ID:TYPE format from prior valid)
    - Correction Field
    - Correction Source (where the correction came from)
    - Tracker Status
    - Pass/Fail
    - Failure Reason
    - Actions Taken
    - Error
    - Kaizen Error
    - Match
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
    InconsistentIDProcessor,
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
    get_inconsistent_buyer_incident_codes,
    is_inconsistent_id_incident,
    get_validation_type,
    get_incident_description,
)


class InconsistentBuyerIDValidator:
    """
    Main application class for inconsistent buyer ID validation.
    
    This validator handles incident code 7_66 where the same person
    appears with different IDs across multiple trades.
    """
    
    # CSV column mapping (0-indexed) - extended for Trade_Date_Time
    COL_TRANSACTION_REF = 0
    COL_ACCOUNT_ID = 1
    # COL 2 = BEN_Link (unused)
    # COL 3 = OWN_Link (unused)
    COL_PERSON_CODE = 4
    COL_ACCOUNT_TYPE = 5
    COL_ID_VALUE = 6
    COL_ID_TYPE = 7
    COL_FNAME = 8
    COL_SNAME = 9
    COL_DOB = 10
    COL_GENDER = 11
    COL_PRIMARY_NAT = 12
    COL_SECONDARY_NAT = 13
    COL_TRADE_DATE_TIME = 14  # YYYY-MM-DD-HH-MM-SS-MSMS format
    
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
            name="inconsistent_buyer_id_validation",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Initialize STANDARD ID processor (used for format/logic validation)
        self.id_processor = IDValidationProcessor(
            client_type="buyer",
            logger=self.logger,
            verbose=self.proc_config.verbose,
            italian_tracker_path=self.path_config.italian_tracker,
            main_tracker_path=self.path_config.main_tracker,
            template_path=self.path_config.template_file,
            template_id_column=self.path_config.template_id_column,
            template_type_column=self.path_config.template_type_column
        )
        
        # Initialize INCONSISTENT ID preprocessor
        self.inconsistent_processor = InconsistentIDProcessor(
            client_type="buyer",
            logger=self.logger,
            verbose=self.proc_config.verbose
        )
        
        # Get input/output files from path config
        self.input_file = Path(self.path_config.input_file)
        self.output_file = Path(self.path_config.output_file)
    
    def read_input_csv(self) -> List[ClientRecord]:
        """
        Read and parse input CSV file.
        
        Returns:
            List of ClientRecord objects with Trade_Date_Time populated
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
                    if len(row) < 14:  # Minimum required columns (up to Trade_Date_Time)
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
                            original_row=row,
                            # New: Capture Trade_Date_Time for chronological sorting
                            trade_date_time_raw=row[self.COL_TRADE_DATE_TIME].strip() if len(row) > self.COL_TRADE_DATE_TIME else ""
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
        
        # Define output columns (matching inconsistent ID validation format)
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
            "Prefixed Nationality",
            "Primary Nationality",
            "Secondary Nationality",
            "Trade_Date_Time",
            "Correction",
            "Correction Field",
            "Correction Source",
            "Tracker Status",
            "Pass/Fail",
            "Failure Reason",
            "Actions Taken",
            "Error",
            "Kaizen Error",
            "Match"
        ]
        
        # Sort records before writing: Surname (A-Z), First Name (A-Z), Person Code (A-Z), Trade_Date_Time (oldest to newest)
        from datetime import datetime
        sorted_records = sorted(
            records,
            key=lambda r: (
                r.surname.upper() if r.surname else "",
                r.first_name.upper() if r.first_name else "",
                r.person_code.upper() if r.person_code else "",
                r.trade_date_time_parsed if r.trade_date_time_parsed else datetime.max
            )
        )
        
        try:
            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in sorted_records:
                    # Swap nationalities if priority country is in secondary position
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    priority_country = record.priority_country_code
                    if priority_country and secondary_nat:
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat)
                        
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            # Priority country is in secondary position, check if primary differs
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                # Swap them so priority country is first
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
                        record.prefixed_nationality or "",
                        primary_nat,
                        secondary_nat,
                        record.trade_date_time_raw,
                        record.correction_output or "",
                        record.correction_fields or "",
                        record.correction_source or "",
                        record.tracker_status or "",
                        f"Format: {record.format_status} | Logic: {record.logic_status}" if record.format_status else "",
                        record.failure_reason or "",
                        " | ".join(record.actions_taken) if record.actions_taken else "",
                        record.error or "",
                        record.kaizen_error or "",
                        record.match or ""
                    ]
                    writer.writerow(output_row)
            
            self.logger.info(f"Successfully wrote {len(records)} records")
        
        except Exception as e:
            self.logger.error(f"Error writing output CSV: {e}", exc_info=True)
            raise
    
    def write_errors_only_csv(self, records: List[ClientRecord]):
        """
        Write only records with errors to a separate CSV file.
        
        Args:
            records: List of processed ClientRecord objects
        """
        errors_file = self.output_file.parent / f"{self.output_file.stem}_errors_only{self.output_file.suffix}"
        self.logger.info(f"Writing errors-only file: {errors_file}")
        
        # Filter to only invalid records (corrected or still needing attention)
        error_records = [r for r in records if not r.is_valid or r.correction_output]
        
        if not error_records:
            self.logger.info("No errors to write - all records passed validation")
            return
        
        # Sort error records before writing
        from datetime import datetime
        sorted_error_records = sorted(
            error_records,
            key=lambda r: (
                r.surname.upper() if r.surname else "",
                r.first_name.upper() if r.first_name else "",
                r.person_code.upper() if r.person_code else "",
                r.trade_date_time_parsed if r.trade_date_time_parsed else datetime.max
            )
        )
        
        errors_file.parent.mkdir(parents=True, exist_ok=True)
        
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
            "Prefixed Nationality",
            "Primary Nationality",
            "Secondary Nationality",
            "Trade_Date_Time",
            "Correction",
            "Correction Field",
            "Correction Source",
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
                
                for record in sorted_error_records:
                    # Swap nationalities if priority country is in secondary position
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    priority_country = record.priority_country_code
                    if priority_country and secondary_nat:
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat)
                        
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            # Priority country is in secondary position, check if primary differs
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                # Swap them so priority country is first
                                primary_nat = secondary_nat
                                secondary_nat = record.primary_nationality
                    
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
                        record.prefixed_nationality or "",
                        primary_nat,
                        secondary_nat,
                        record.trade_date_time_raw,
                        record.correction_output or "",
                        record.correction_fields or "",
                        record.correction_source or "",
                        record.tracker_status or "",
                        f"Format: {record.format_status} | Logic: {record.logic_status}" if record.format_status else "",
                        record.failure_reason or "",
                        " | ".join(record.actions_taken) if record.actions_taken else "",
                        record.error or "",
                        record.kaizen_error or "",
                        record.match or ""
                    ]
                    writer.writerow(output_row)
            
            self.logger.info(f"Successfully wrote {len(error_records)} error records")
        
        except Exception as e:
            self.logger.error(f"Error writing errors-only CSV: {e}", exc_info=True)
            raise
    
    def run(self):
        """
        Execute the inconsistent ID validation workflow.
        
        This uses a two-phase approach:
        1. PREPROCESSING: InconsistentIDProcessor groups by person code, 
           sorts chronologically, and applies prior-valid corrections
        2. STANDARD VALIDATION: Records that couldn't be corrected from prior
           valid go through standard IDValidationProcessor
        """
        start_time = datetime.now()
        
        self.logger.log_header("INCONSISTENT BUYER ID VALIDATION v1.3")
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
        
        # Step 2: PREPROCESSING - Apply inconsistent ID logic
        self.logger.log_header("PHASE 1: INCONSISTENT ID PREPROCESSING")
        self.logger.info("Grouping by Person Code, sorting chronologically, applying prior-valid corrections...")
        
        records = self.inconsistent_processor.preprocess_for_inconsistent_validation(
            records,
            self.id_processor
        )
        
        # Print preprocessing statistics
        self.inconsistent_processor.print_stats(logger=self.logger)
        
        # Step 3: STANDARD VALIDATION for remaining records
        self.logger.log_header("PHASE 2: STANDARD VALIDATION FOR REMAINING RECORDS")
        
        records_needing_standard = [r for r in records if r.requires_standard_validation]
        records_already_corrected = [r for r in records if not r.requires_standard_validation]
        
        self.logger.info(f"Records corrected from prior valid: {len(records_already_corrected)}")
        self.logger.info(f"Records needing standard validation: {len(records_needing_standard)}")
        
        # Process records that need standard validation
        if records_needing_standard:
            if self.show_progress:
                try:
                    from tqdm import tqdm
                    record_iter = tqdm(records_needing_standard, desc="Standard validation", unit="rec")
                except ImportError:
                    self.logger.warning("tqdm not installed - progress bar disabled")
                    record_iter = records_needing_standard
            else:
                record_iter = records_needing_standard
            
            for record in record_iter:
                # Only process if not already corrected
                if record.requires_standard_validation:
                    # Preserve existing failure_reason before standard validation
                    existing_failure_reason = record.failure_reason
                    self.id_processor.process_record(record)
                    # If failure_reason was set during preprocessing and still relevant, preserve it
                    if existing_failure_reason and not record.failure_reason:
                        record.failure_reason = existing_failure_reason
                    record.correction_source = "Standard validation (no prior valid ID)"
        
        # Step 3.5: KAIZEN TEMPLATE VALIDATION for preprocessed records
        # Records corrected by preprocessing didn't go through process_record(), so they missed Kaizen validation
        self.logger.log_header("PHASE 3: KAIZEN TEMPLATE VALIDATION FOR PREPROCESSED RECORDS")
        if records_already_corrected and self.id_processor.template_data:
            self.logger.info(f"Performing Kaizen validation on {len(records_already_corrected)} preprocessed records...")
            for record in records_already_corrected:
                self.id_processor._perform_template_validation(record)
        else:
            if not self.id_processor.template_data:
                self.logger.info("No template file loaded - skipping Kaizen validation")
            else:
                self.logger.info("No preprocessed records to validate against template")
        
        # Combine all records, sorted by Person Code (primary) and Trade_Date_Time (secondary)
        all_records = sorted(
            records, 
            key=lambda r: (
                r.person_code or "",
                r.trade_date_time_parsed or datetime.min
            )
        )
        
        # Step 4: Write output (skip if dry run)
        if self.dry_run:
            self.logger.info("Dry run mode - skipping output file write")
            self.logger.info(f"Would have written {len(all_records)} records to: {self.output_file}")
            
            # Show sample statistics
            corrected_prior = sum(1 for r in all_records if "prior valid" in (r.correction_source or "").lower())
            corrected_standard = sum(1 for r in all_records if "standard" in (r.correction_source or "").lower())
            self.logger.info(f"Corrected from prior valid: {corrected_prior}")
            self.logger.info(f"Corrected via standard validation: {corrected_standard}")
        else:
            self.write_output_csv(all_records)
            
            # Write errors-only CSV if there are errors
            error_count = sum(1 for r in all_records if not r.is_valid or r.correction_output)
            if error_count > 0:
                self.logger.info(f"Writing errors-only CSV ({error_count} records with corrections)...")
                self.write_errors_only_csv(all_records)
        
        # Step 5: Summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.logger.log_header("PROCESSING COMPLETE")
        self.logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {duration}")
        
        # Print standard validation statistics
        self.id_processor.stats.print_summary(logger=self.logger)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Inconsistent Buyer ID Validation Script v1.3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation --config config/local/accuracy_testing/inconsistent_buyer.yaml
    
    # With environment variables  
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation --use-env
    
    # Direct CLI arguments (backward compatible)
    python -m src.accuracy_testing.scripts.inconsistent_buyer_id_validation input.csv output.csv --log-level DEBUG
        """
    )
    
    # Configuration source (mutually exclusive)
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        '--config', '-c',
        type=str,
        help='Path to YAML configuration file'
    )
    config_group.add_argument(
        '--use-env',
        action='store_true',
        help='Load configuration from environment variables (TXR_ACCURACY_*)'
    )
    
    # Backward compatible positional arguments
    parser.add_argument(
        'input_file',
        nargs='?',
        help='Input CSV file (positional, backward compatible)'
    )
    parser.add_argument(
        'output_file',
        nargs='?',
        help='Output CSV file (positional, backward compatible)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
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
    """Main entry point with CLI support."""
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
                'single': {
                    'paths': {
                        'input_file': args.input_file,
                        'output_file': args.output_file,
                        'log_output': 'logs'
                    }
                },
                'processor': {
                    'log_level': args.log_level or 'INFO',
                    'verbose': False,
                    'batch_size': 1000
                }
            }
        else:
            # Default configuration path
            default_config = (
                Path(__file__).parent.parent.parent.parent / 
                "config" / "local" / "accuracy_testing" / "inconsistent_buyer_validation.yaml"
            )
            if default_config.exists():
                print(f"Loading default configuration from {default_config}...")
                config = AccuracyConfigManager.load_from_yaml(str(default_config))
            else:
                print("Error: No configuration specified and default config not found")
                print("Use --config, --use-env, or provide input_file and output_file arguments")
                return 1
        
        # Override log level if specified
        if args.log_level:
            if 'processor' not in config:
                config['processor'] = {}
            config['processor']['log_level'] = args.log_level
        
        # Create and run validator
        validator = InconsistentBuyerIDValidator(
            config_dict=config,
            dry_run=args.dry_run,
            show_progress=args.progress
        )
        validator.run()
        
        validator.logger.info("Inconsistent Buyer ID validation completed successfully")
        return 0
    
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
