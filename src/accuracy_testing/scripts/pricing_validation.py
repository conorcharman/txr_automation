#!/usr/bin/env python3
"""
Pricing Data Validation Script v1.0
====================================

Validates transaction pricing data for accuracy testing (Incident Code 35_3).
Migrated from VBA macro pricing_data_validation_v1.0.vb.

This script:
1. Reads pricing data from CSV (Transaction Reference, Net Amount, Consideration, Interest)
2. Calculates derived fields (Total, Expected Interest, Net Difference)
3. Validates pricing using formula: Net Amount = Consideration + Interest
4. Outputs results with error flag ("N" or "TBC")

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.pricing_validation --config config/local/accuracy_testing/pricing_validation.yaml
    
    # With environment variables
    export TXR_ACCURACY_PATHS_INPUT_FILE="data/pricing_input.csv"
    export TXR_ACCURACY_PATHS_OUTPUT_FILE="data/pricing_output.csv"
    python -m src.accuracy_testing.scripts.pricing_validation --use-env
    
    # With direct CLI arguments (backward compatible)
    python -m src.accuracy_testing.scripts.pricing_validation input.csv output.csv --log-level DEBUG

Input CSV columns (minimum required):
    - Transaction Reference
    - Net Amount
    - Consideration  
    - Interest

Output CSV adds:
    - Error (N or TBC)
    - Total (Consideration + Interest)
    - Expected Interest (Consideration - Net Amount)
    - Net Difference (Total - Net Amount)
"""

import sys
import csv
import argparse
from pathlib import Path
from typing import List
from datetime import datetime
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.pricing_record import PricingRecord
from src.accuracy_testing.validators.pricing_validator import PricingValidator
from src.accuracy_testing.processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig
)

# Import txr_replay_core utilities
try:
    from common.logger import create_logger, StructuredLogger
    from common.utils import safe_open_csv
except ImportError:
    # Fallback if txr_replay_core not available
    import logging
    def create_logger(name, log_dir, log_level='INFO'):
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level))
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        return logger
    
    def safe_open_csv(file_path, mode, newline=''):
        return open(file_path, mode, encoding='utf-8', newline=newline), 'utf-8'


class PricingStats:
    """Statistics for pricing validation runs."""
    
    def __init__(self):
        self.total_records = 0
        self.valid_records = 0
        self.invalid_records = 0
        self.errors = 0
    
    def print_summary(self, logger=None):
        """
        Print processing summary to logger or console.
        
        Args:
            logger: Optional StructuredLogger instance
        """
        try:
            if logger and hasattr(logger, 'info'):
                logger.info("=" * 70)
                logger.info("PROCESSING SUMMARY")
                logger.info("=" * 70)
                logger.info(f"Total records processed:     {self.total_records:>6}")
                logger.info(f"Valid records (correct):     {self.valid_records:>6}")
                logger.info(f"Invalid records (TBC):       {self.invalid_records:>6}")
                logger.info(f"Processing errors:           {self.errors:>6}")
                logger.info("=" * 70)
            else:
                # Fallback to print
                print(f"\n{'='*70}")
                print(f"PROCESSING SUMMARY")
                print(f"{'='*70}")
                print(f"Total records processed:     {self.total_records:>6}")
                print(f"Valid records (correct):     {self.valid_records:>6}")
                print(f"Invalid records (TBC):       {self.invalid_records:>6}")
                print(f"Processing errors:           {self.errors:>6}")
                print(f"{'='*70}\n")
        except Exception:
            # Final fallback
            print(f"\n{'='*70}")
            print(f"PROCESSING SUMMARY")
            print(f"{'='*70}")
            print(f"Total records processed:     {self.total_records:>6}")
            print(f"Valid records (correct):     {self.valid_records:>6}")
            print(f"Invalid records (TBC):       {self.invalid_records:>6}")
            print(f"Processing errors:           {self.errors:>6}")
            print(f"{'='*70}\n")


class PricingValidationScript:
    """Main application class for pricing data validation."""
    
    # Input CSV column mapping (0-indexed)
    # Input file has: Transaction Reference, Net Amount, Consideration, Interest
    COL_TRANSACTION_REF = 0
    COL_NET_AMOUNT = 1
    COL_CONSIDERATION = 2
    COL_INTEREST = 3
    
    # Output CSV will have additional columns:
    # Error (N or TBC), Total, Expected Interest, Net Difference, Correction, Correction Field, Comments
    
    def __init__(
        self,
        config_path: str = None,
        config_dict: dict = None,
        dry_run: bool = False,
        show_progress: bool = False
    ):
        """
        Initialize pricing validation script.
        
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
            name="pricing_validation",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Initialize validator
        self.validator = PricingValidator(
            tolerance=Decimal('0.01'),
            verbose=self.proc_config.verbose
        )
        
        # Get input/output files from path config
        self.input_file = Path(self.path_config.input_file)
        self.output_file = Path(self.path_config.output_file)
        
        # Statistics
        self.stats = PricingStats()
    
    def read_input_csv(self) -> List[PricingRecord]:
        """
        Read and parse input CSV file.
        
        Returns:
            List of PricingRecord objects
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
                    if len(row) < 4:  # Minimum required columns
                        self.logger.warning(f"Row {row_idx} has insufficient columns, skipping")
                        continue
                    
                    try:
                        # Create record from row data (input only has 4 columns)
                        record = PricingRecord(
                            transaction_ref=row[self.COL_TRANSACTION_REF].strip() if row[self.COL_TRANSACTION_REF] else "",
                            net_amount=Decimal(row[self.COL_NET_AMOUNT]) if row[self.COL_NET_AMOUNT] else Decimal('0'),
                            consideration=Decimal(row[self.COL_CONSIDERATION]) if row[self.COL_CONSIDERATION] else Decimal('0'),
                            interest=Decimal(row[self.COL_INTEREST]) if row[self.COL_INTEREST] else Decimal('0'),
                            correction=None,
                            correction_field=None,
                            comments=None
                        )
                        records.append(record)
                    
                    except (ValueError, IndexError) as e:
                        self.logger.error(f"Error parsing row {row_idx}: {e}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error reading CSV file: {e}", exc_info=True)
            raise
        
        self.logger.info(f"Successfully read {len(records)} records")
        return records
    
    def write_output_csv(self, records: List[PricingRecord]):
        """
        Write processed records to output CSV.
        
        Args:
            records: List of processed PricingRecord objects
        """
        self.logger.info(f"Writing output file: {self.output_file}")
        
        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Define output columns (10 columns)
        output_columns = [
            "Transaction Reference",  # Col 0
            "Net Amount",             # Col 1
            "Consideration",          # Col 2
            "Interest",               # Col 3
            "Total",                  # Col 4
            "Expected Interest",      # Col 5
            "Net Difference",         # Col 6
            "Correction",             # Col 7
            "Correction Field",       # Col 8
            "Error"                   # Col 9
        ]
        
        try:
            with open(self.output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(output_columns)
                
                for record in records:
                    output_row = [
                        record.transaction_ref,
                        f"{record.net_amount:.2f}",
                        f"{record.consideration:.2f}",
                        f"{record.interest:.2f}",
                        f"{record.total:.2f}",
                        f"{record.expected_interest:.2f}",
                        f"{record.net_difference:.2f}",
                        record.correction or "",
                        record.correction_field or "",
                        record.error
                    ]
                    writer.writerow(output_row)
            
            self.logger.info(f"Successfully wrote {len(records)} records")
        
        except Exception as e:
            self.logger.error(f"Error writing output CSV: {e}", exc_info=True)
            raise
    
    def run(self):
        """Execute the validation workflow."""
        start_time = datetime.now()
        
        self.logger.log_header("PRICING DATA VALIDATION v1.0")
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
        
        # Step 2: Validate records
        self.logger.log_header("VALIDATING PRICING DATA")
        
        # Setup progress bar if requested
        if self.show_progress:
            try:
                from tqdm import tqdm
                record_iter = tqdm(records, desc="Validating records", unit="rec")
            except ImportError:
                self.logger.warning("tqdm not installed - progress bar disabled. Install with: pip install tqdm")
                record_iter = records
        else:
            record_iter = records
        
        # Validate each record
        for record in record_iter:
            self.validator.validate_record_safe(record)
        
        # Step 3: Calculate statistics
        stats = self.validator.validate_batch(records)
        self.stats.total_records = stats['total']
        self.stats.valid_records = stats['valid']
        self.stats.invalid_records = stats['invalid']
        self.stats.errors = stats['errors']
        
        # Step 4: Write output (skip if dry run)
        if self.dry_run:
            self.logger.info("Dry run mode - skipping output file write")
            self.logger.info(f"Would have written {len(records)} records to: {self.output_file}")
            # Show sample of what would be written
            if records:
                sample_record = records[0]
                self.logger.info("Sample output (first record):")
                self.logger.info(f"  Transaction Ref: {sample_record.transaction_ref}")
                self.logger.info(f"  Net Amount: {sample_record.net_amount}")
                self.logger.info(f"  Total: {sample_record.total}")
                self.logger.info(f"  Net Difference: {sample_record.net_difference}")
                self.logger.info(f"  Error: {sample_record.error}")
        else:
            self.write_output_csv(records)
        
        # Step 5: Summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.logger.log_header("VALIDATION COMPLETE")
        self.logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {duration}")
        
        # Print statistics
        self.stats.print_summary(logger=self.logger)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pricing Data Validation v1.0 - Validate transaction pricing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # With YAML configuration file
  python -m src.accuracy_testing.scripts.pricing_validation --config config/local/accuracy_testing/pricing_validation.yaml
  
  # With environment variables
  export TXR_ACCURACY_PATHS_INPUT_FILE="data/pricing_input.csv"
  export TXR_ACCURACY_PATHS_OUTPUT_FILE="data/pricing_output.csv"
  python -m src.accuracy_testing.scripts.pricing_validation --use-env
  
  # With direct CLI arguments (backward compatible)
  python -m src.accuracy_testing.scripts.pricing_validation input.csv output.csv
  
  # Override log level
  python -m src.accuracy_testing.scripts.pricing_validation --config config.yaml --log-level DEBUG
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
        help='Load configuration from environment variables (TXR_ACCURACY_* prefix)'
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
            # Default configuration path (same pattern as other validation scripts)
            default_config = Path(__file__).parent.parent.parent.parent / "config" / "local" / "accuracy_testing" / "pricing_validation.yaml"
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
        script = PricingValidationScript(
            config_dict=config,
            dry_run=args.dry_run,
            show_progress=args.progress
        )
        script.run()
        
        script.logger.info("Pricing data validation completed successfully")
        return 0
    
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
