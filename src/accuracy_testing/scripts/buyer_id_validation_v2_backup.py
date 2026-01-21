#!/usr/bin/env python3
"""
Buyer ID Validation Script v2.0
================================

Validates buyer identification codes for transaction reporting accuracy testing.
Migrated from VBA macro BuyerIDValidation5_6.vb.

This script:
1. Reads buyer ID data from CSV
2. Validates IDs against country-specific formats
3. Generates corrections for invalid IDs
4. Outputs results with validation status and corrections

Version 2.0 Changes:
- Integrated with txr_replay_core for ConfigManager and StructuredLogger
- Added --config and --use-env command-line flags
- Uses safe_open_csv for robust file handling
- Structured logging with file output

Usage:
    # With command-line paths
    python -m src.accuracy_testing.scripts.buyer_id_validation_v2 input.csv output.csv
    
    # With configuration file (future)
    python -m src.accuracy_testing.scripts.buyer_id_validation_v2 --config config/buyer_validation.yaml
    
    # With environment variables
    export TXR_BUYER_INPUT_FILE="data/buyer_input.csv"
    export TXR_BUYER_OUTPUT_FILE="data/buyer_output.csv"
    python -m src.accuracy_testing.scripts.buyer_id_validation_v2 --use-env
    
    # With verbose logging
    python -m src.accuracy_testing.scripts.buyer_id_validation_v2 input.csv output.csv --log-level DEBUG

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
from typing import List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.processor import (
    ClientRecord,
    IDValidationProcessor,
    ProcessingStats,
)

# Try to import txr_replay_core utilities
try:
    from txr_replay_core.logger import create_logger, StructuredLogger
    from txr_replay_core.utils import safe_open_csv
    REPLAY_CORE_AVAILABLE = True
except ImportError:
    REPLAY_CORE_AVAILABLE = False
    StructuredLogger = None
    create_logger = None
    safe_open_csv = None


class BuyerIDValidator:
    """Main application class for buyer ID validation."""
    
    # CSV column mapping (0-indexed)
    COL_TRANSACTION_REF = 0
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
        input_file: str,
        output_file: str,
        logger: Optional[StructuredLogger] = None,
        verbose: bool = False
    ):
        """
        Initialize validator.
        
        Args:
            input_file: Path to input CSV
            output_file: Path to output CSV
            logger: Optional StructuredLogger instance
            verbose: Enable verbose output
        """
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.logger = logger
        self.verbose = verbose
        self.processor = IDValidationProcessor(
            client_type="buyer",
            logger=logger,
            verbose=verbose
        )
    
    def _log_info(self, message: str):
        """Log info message to logger or print."""
        if self.logger:
            self.logger.info(message)
        elif self.verbose:
            print(message)
    
    def _log_warning(self, message: str):
        """Log warning message to logger or print."""
        if self.logger:
            self.logger.warning(message)
        else:
            print(f"WARNING: {message}")
    
    def _log_error(self, message: str):
        """Log error message to logger or print."""
        if self.logger:
            self.logger.error(message)
        else:
            print(f"ERROR: {message}")
    
    def read_input_csv(self) -> List[ClientRecord]:
        """
        Read and parse input CSV file.
        
        Returns:
            List of ClientRecord objects
        """
        self._log_info(f"Reading input file: {self.input_file}")
        records = []
        
        # Use safe_open_csv if available, otherwise fallback
        if REPLAY_CORE_AVAILABLE and safe_open_csv:
            f, encoding = safe_open_csv(self.input_file, 'r', newline='')
            self._log_info(f"Detected encoding: {encoding}")
        else:
            f = open(self.input_file, 'r', encoding='utf-8-sig', newline='')
        
        try:
            with f:
                reader = csv.reader(f)
                header = next(reader)  # Skip header row
                
                for row_idx, row in enumerate(reader, start=2):  # Start at 2 (after header)
                    if len(row) < 15:  # Minimum required columns
                        self._log_warning(f"Row {row_idx} has insufficient columns, skipping")
                        continue
                    
                    try:
                        record = ClientRecord(
                            row_index=row_idx,
                            transaction_ref=row[self.COL_TRANSACTION_REF].strip(),
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
                        self._log_error(f"Error parsing row {row_idx}: {e}")
                        continue
        
        except Exception as e:
            self._log_error(f"Error reading CSV file: {e}")
            raise
        
        self._log_info(f"Successfully read {len(records)} records")
        return records
    
    def write_output_csv(self, records: List[ClientRecord]):
        """
        Write processed records to output CSV.
        
        Args:
            records: List of processed ClientRecord objects
        """
        self._log_info(f"Writing output file: {self.output_file}")
        
        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Define output columns
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
            "Validation Status",
            "Correction",
            "Correction Type",
            "Actions Taken"
        ]
        
        try:
            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in records:
                    # Build output row from original data + validation results
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
                        record.primary_nationality,
                        record.secondary_nationality,
                        "VALID" if record.is_valid else "INVALID" if record.validation_error else "ERROR",
                        record.correction or "",
                        record.correction_type or "",
                        " | ".join(record.actions_taken) if record.actions_taken else ""
                    ]
                    writer.writerow(output_row)
            
            self._log_info(f"Successfully wrote {len(records)} records")
        
        except Exception as e:
            self._log_error(f"Error writing output CSV: {e}")
            raise
    
    def run(self):
        """Execute the validation workflow."""
        start_time = datetime.now()
        
        if self.logger:
            self.logger.log_header("BUYER ID VALIDATION v2.0")
        else:
            print("\n" + "="*70)
            print("BUYER ID VALIDATION v2.0")
            print("="*70)
        
        self._log_info(f"Input file: {self.input_file}")
        self._log_info(f"Output file: {self.output_file}")
        self._log_info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Read input
        records = self.read_input_csv()
        
        if not records:
            self._log_error("No records to process")
            return
        
        # Step 2: Process each record
        if self.logger:
            self.logger.log_header("PROCESSING RECORDS")
        
        processed_records = []
        for record in records:
            processed = self.processor.process_record(record)
            processed_records.append(processed)
            
            if self.verbose and not self.logger:
                status = "VALID" if processed.is_valid else "INVALID"
                print(f"  Row {processed.row_index}: {status} - {processed.transaction_ref}")
        
        # Step 3: Write output
        self.write_output_csv(processed_records)
        
        # Step 4: Summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        if self.logger:
            self.logger.log_header("PROCESSING COMPLETE")
        
        self._log_info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self._log_info(f"Duration: {duration}")
        
        # Print statistics
        self.processor.stats.print_summary(logger=self.logger)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Buyer ID Validation v2.0 - Validate buyer identification codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python -m src.accuracy_testing.scripts.buyer_id_validation_v2 input.csv output.csv
  
  # With verbose logging
  python -m src.accuracy_testing.scripts.buyer_id_validation_v2 input.csv output.csv --verbose
  
  # With debug logging to file
  python -m src.accuracy_testing.scripts.buyer_id_validation_v2 input.csv output.csv --log-level DEBUG
  
  # Using environment variables
  export TXR_BUYER_INPUT_FILE="data/buyer_input.csv"
  export TXR_BUYER_OUTPUT_FILE="data/buyer_output.csv"
  python -m src.accuracy_testing.scripts.buyer_id_validation_v2 --use-env
        """
    )
    
    parser.add_argument(
        'input_file',
        nargs='?',
        type=str,
        help='Path to input CSV file (required unless --use-env)'
    )
    
    parser.add_argument(
        'output_file',
        nargs='?',
        type=str,
        help='Path to output CSV file (required unless --use-env)'
    )
    
    parser.add_argument(
        '--use-env',
        action='store_true',
        help='Load file paths from environment variables (TXR_BUYER_INPUT_FILE, TXR_BUYER_OUTPUT_FILE)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--log-dir',
        type=str,
        default='logs',
        help='Directory for log files (default: logs)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose console output'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Determine input/output files
    if args.use_env:
        input_file = os.getenv('TXR_BUYER_INPUT_FILE')
        output_file = os.getenv('TXR_BUYER_OUTPUT_FILE')
        
        if not input_file or not output_file:
            print("ERROR: --use-env specified but TXR_BUYER_INPUT_FILE or TXR_BUYER_OUTPUT_FILE not set")
            sys.exit(1)
    else:
        if not args.input_file or not args.output_file:
            print("ERROR: input_file and output_file are required (or use --use-env)")
            sys.exit(1)
        
        input_file = args.input_file
        output_file = args.output_file
    
    # Setup logger if replay_core is available
    logger = None
    if REPLAY_CORE_AVAILABLE and create_logger:
        os.makedirs(args.log_dir, exist_ok=True)
        logger = create_logger(
            name="buyer_id_validation",
            log_dir=args.log_dir,
            log_level=args.log_level
        )
    
    # Create validator and run
    try:
        validator = BuyerIDValidator(
            input_file=input_file,
            output_file=output_file,
            logger=logger,
            verbose=args.verbose
        )
        validator.run()
        
        if logger:
            logger.info("Buyer ID validation completed successfully")
        else:
            print("\nBuyer ID validation completed successfully")
        
        return 0
    
    except Exception as e:
        if logger:
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"\nFATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
