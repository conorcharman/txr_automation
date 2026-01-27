#!/usr/bin/env python3
"""
Inconsistent Seller ID Validation Script v1.3
==============================================

Validates seller identification codes for INCONSISTENT ID scenarios (incident 16_20).
Migrated from VBA macro InconsistentSellerIDValidation1_3.vb.

This script handles records where the same person has different IDs across multiple trades.
It applies a specialized algorithm that:
1. Groups records by Person Code
2. Sorts each group chronologically by Trade_Date_Time
3. Validates each ID using standard format + logic rules
4. Corrects INVALID IDs using the most recent PRIOR VALID ID

Key differences from standard validation:
- Groups by Person Code, not just individual record validation
- Uses Trade_Date_Time for chronological ordering
- Detects fallback IDs (CC_PersonCode pattern)
- Only corrects invalid IDs - valid-to-valid changes are preserved

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation --config config/local/accuracy_testing/inconsistent_seller.yaml
    
    # With environment variables
    export TXR_PATHS_INPUT_FILE="data/seller_input.csv"
    export TXR_PATHS_OUTPUT_FILE="data/seller_output.csv"
    export TXR_PATHS_LOG_OUTPUT="logs"
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation --use-env
    
    # With direct CLI arguments
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation input.csv output.csv --log-level DEBUG

Input CSV columns (minimum required):
    - Transaction Reference
    - Account ID
    - Trade_Date_Time (format: YYYY-MM-DD-HH-MM-SS-MSMS)
    - Person Code  
    - Account Type
    - Seller ID Code
    - Type of Seller ID Code
    - First Name
    - Surname
    - Date of Birth
    - Gender
    - Primary Nationality
    - Secondary Nationality (optional)

Output CSV adds:
    - Correction Output (ID:TYPE format from prior valid)
    - Correction Fields
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

# Import txr_replay_core utilities
from src.common.logger import create_logger, StructuredLogger
from src.common.utils import safe_open_csv
from src.txr_replay_core.incident_codes import (
    get_inconsistent_seller_incident_codes,
    is_inconsistent_id_incident,
    get_validation_type,
    get_incident_description
)


class InconsistentSellerIDValidator:
    """
    Main application class for inconsistent seller ID validation.
    
    This validator handles incident code 16_20 where the same person
    appears with different IDs across multiple trades.
    """
    
    # CSV column mapping (0-indexed) - extended for Trade_Date_Time
    COL_TRANSACTION_REF = 0
    COL_ACCOUNT_ID = 1
    COL_TRADE_DATE_TIME = 2  # New: YYYY-MM-DD-HH-MM-SS-MSMS format
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
            name="inconsistent_seller_id_validation",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Initialize STANDARD ID processor (used for format/logic validation)
        self.id_processor = IDValidationProcessor(
            client_type="seller",  # Key difference: seller instead of buyer
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
            client_type="seller",  # Key difference: seller instead of buyer
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
        
        # Define output columns (matching VBA output format with inconsistent-specific fields)
        output_columns = [
            "Transaction Reference",
            "Account ID",
            "Trade_Date_Time",  # Include for traceability
            "Person Code",
            "Account Type",
            "Seller ID Code",  # Key difference: Seller instead of Buyer
            "Type of Seller ID Code",  # Key difference: Seller instead of Buyer
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",  # ID:TYPE format (from prior valid or standard)
            "Correction Fields",  # "ID:IDT"
            "Correction Source",  # New: Where the correction came from
            "Tracker Status",
            "Pass/Fail",
            "Failure Reason",
            "Actions Taken",
            "Error",
            "Kaizen Error",
            "Match"
        ]
        
        try:
            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in records:
                    # Swap nationalities if priority country is in secondary position
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    priority_country = record.priority_country_code
                    if priority_country and secondary_nat:
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat)
                        
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                primary_nat = secondary_nat
                                secondary_nat = record.primary_nationality
                    
                    # Build output row from original data + validation results
                    output_row = [
                        record.transaction_ref,
                        record.account_id,
                        record.trade_date_time_raw,  # Include Trade_Date_Time
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
                        record.correction_source or "",  # New field
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
        
        errors_file.parent.mkdir(parents=True, exist_ok=True)
        
        output_columns = [
            "Transaction Reference",
            "Account ID",
            "Trade_Date_Time",
            "Person Code",
            "Account Type",
            "Seller ID Code",
            "Type of Seller ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",
            "Correction Fields",
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
                
                for record in error_records:
                    primary_nat = record.primary_nationality
                    secondary_nat = record.secondary_nationality
                    
                    priority_country = record.priority_country_code
                    if priority_country and secondary_nat:
                        from src.accuracy_testing.core import country_manager
                        priority_obj = country_manager.get_by_alpha2(priority_country)
                        secondary_obj = country_manager.get_by_alpha2(secondary_nat)
                        
                        if priority_obj and secondary_obj and priority_obj.alpha2 == secondary_obj.alpha2:
                            primary_obj = country_manager.get_by_alpha2(primary_nat) if primary_nat else None
                            if not primary_obj or primary_obj.alpha2 != priority_obj.alpha2:
                                primary_nat = secondary_nat
                                secondary_nat = record.primary_nationality
                    
                    output_row = [
                        record.transaction_ref,
                        record.account_id,
                        record.trade_date_time_raw,
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
        
        self.logger.log_header("INCONSISTENT SELLER ID VALIDATION v1.3")
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
                    self.id_processor.process_record(record)
                    record.correction_source = "Standard validation (no prior valid ID)"
        
        # Combine all records (maintain original order by row_index)
        all_records = sorted(records, key=lambda r: r.row_index)
        
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
        description="Inconsistent Seller ID Validation Script v1.3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation --config config/local/accuracy_testing/inconsistent_seller.yaml
    
    # With environment variables  
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation --use-env
    
    # Direct CLI arguments (backward compatible)
    python -m src.accuracy_testing.scripts.inconsistent_seller_id_validation input.csv output.csv --log-level DEBUG
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
            # Default configuration path
            default_config = (
                Path(__file__).parent.parent.parent.parent / 
                "config" / "local" / "accuracy_testing" / "inconsistent_seller.yaml"
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
        validator = InconsistentSellerIDValidator(
            config_dict=config,
            dry_run=args.dry_run,
            show_progress=args.progress
        )
        validator.run()
        
        validator.logger.info("Inconsistent Seller ID validation completed successfully")
        return 0
    
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
