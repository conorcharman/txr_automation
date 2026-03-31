#!/usr/bin/env python3
"""
SQL Extract Generator CLI
==========================

Command-line tool for generating SQL extract files from transaction references.
Replaces VBA scripts: ExtractBuyerID, ExtractInconsistentBuyerID, SCR_extract_generator.

Usage:
    # Basic usage with defaults
    python -m src.accuracy_testing.scripts.sql_extract_generator \\
        --template legacy/sql/ExtractBuyerID4_1.sql \\
        --input data/incident_7_39_transactions.csv \\
        --output extracts/

    # Custom batch size and placeholder
    python -m src.accuracy_testing.scripts.sql_extract_generator \\
        --template legacy/sql/SCR_pricing_data_v1.0.sql \\
        --input data/pricing_refs.csv \\
        --output extracts/ \\
        --batch-size 500 \\
        --placeholder "--<TRADE REFERENCES>--"
    
    # Dry run to preview
    python -m src.accuracy_testing.scripts.sql_extract_generator \\
        --template legacy/sql/ExtractInconsistentBuyerID1_0.sql \\
        --input data/inconsistent_refs.csv \\
        --output extracts/ \\
        --dry-run

Features:
- Auto-detects placeholder patterns in templates
- Batch splitting (default 900 records per file)
- Multiple output files for large datasets
- Dry run mode for testing
- Progress reporting
"""

import sys
import csv
import yaml
import argparse
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.sql_extract_generator import SQLExtractGenerator
from core import (
    is_buyer_incident,
    is_seller_incident,
    get_client_types,
)


class SQLExtractGeneratorCLI:
    """CLI wrapper for SQL Extract Generator."""
    
    def __init__(
        self,
        template_path: str,
        input_csv: str,
        output_dir: str,
        batch_size: int = 900,
        placeholder: str = None,
        transaction_column: str = None,
        dry_run: bool = False,
        verbose: bool = False,
        output_format: str = 'both',
        incident_code: str = None,
        dtf_template_path: str = None,
        values_mode: bool = False
    ):
        """
        Initialize CLI.
        
        Args:
            template_path: Path to SQL template file
            input_csv: Path to CSV file with transaction references
            output_dir: Parent directory for output files (creates /csv and /dtf subdirs)
            batch_size: Records per SQL file (default 900)
            placeholder: Custom placeholder pattern (auto-detects if None)
            transaction_column: CSV column name/index for transaction refs
            dry_run: Preview mode - don't write files
            verbose: Enable detailed output
            output_format: Output format - 'sql', 'dtf', or 'both' (default: 'both')
            incident_code: Incident code for CSV naming in DTF files
            dtf_template_path: Path to DTF template (uses default if None)
            values_mode: If True, format refs as a DB2 VALUES block (used for 7_6)
        """
        self.template_path = template_path
        self.input_csv = input_csv
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.placeholder = placeholder
        self.transaction_column = transaction_column
        self.dry_run = dry_run
        self.verbose = verbose
        self.output_format = output_format
        self.incident_code = incident_code
        self.dtf_template_path = dtf_template_path
        self.values_mode = values_mode
    
    def read_transaction_refs(self) -> List[str]:
        """
        Read transaction references from CSV file.
        
        Returns:
            List of transaction reference strings
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If specified column not found
        """
        input_path = Path(self.input_csv)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input CSV not found: {self.input_csv}")
        
        refs = []
        
        with open(input_path, 'r', encoding='cp1252') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header
            
            # Determine column index
            if self.transaction_column is None:
                # Default: try "Transaction reference number" (template format)
                # Fall back to first column if not found
                if 'Transaction reference number' in header:
                    col_idx = header.index('Transaction reference number')
                else:
                    col_idx = 0
            elif self.transaction_column.isdigit():
                # Column specified by index
                col_idx = int(self.transaction_column)
            else:
                # Column specified by name
                try:
                    col_idx = header.index(self.transaction_column)
                except ValueError:
                    raise ValueError(
                        f"Column '{self.transaction_column}' not found in CSV. "
                        f"Available columns: {', '.join(header)}"
                    )
            
            # Read transaction refs from specified column
            for row in reader:
                if len(row) > col_idx:
                    ref = row[col_idx].strip()
                    if ref:  # Skip empty refs
                        refs.append(ref)
        
        return refs
    
    def run(self) -> int:
        """
        Execute SQL extract generation.
        
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            print("=" * 70)
            print("SQL EXTRACT GENERATOR")
            print("=" * 70)
            print(f"Template:      {self.template_path}")
            print(f"Input CSV:     {self.input_csv}")
            print(f"Output Dir:    {self.output_dir}")
            print(f"Batch Size:    {self.batch_size}")
            print(f"Output Format: {self.output_format}")
            if self.dry_run:
                print("Mode:          DRY RUN (preview only)")
            print("=" * 70)
            
            # Initialize generator
            if self.verbose:
                print("\n[1/4] Loading SQL template...")
            
            generator = SQLExtractGenerator(
                template_path=self.template_path,
                batch_size=self.batch_size,
                placeholder=self.placeholder,
                output_format=self.output_format,
                dtf_template_path=self.dtf_template_path,
                values_mode=self.values_mode
            )
            
            if self.verbose and self.values_mode:
                print("  ✓ VALUES mode: enabled (CA references will be excluded)")
            
            if self.verbose:
                print(f"  ✓ Template loaded: {generator.template_path.name}")
                print(f"  ✓ Placeholder detected: {generator.placeholder}")
                if self.output_format in ['dtf', 'both']:
                    print(f"  ✓ DTF template loaded: {generator.dtf_template_path.name}")
            
            # Read transaction references
            if self.verbose:
                print("\n[2/4] Reading transaction references...")
            
            transaction_refs = self.read_transaction_refs()
            
            print(f"  ✓ Read {len(transaction_refs)} transaction references")
            
            # Get generation summary
            if self.verbose:
                print("\n[3/4] Planning batches...")
            
            summary = generator.get_summary(transaction_refs)
            
            print(f"  ✓ Total transactions: {summary['total_transactions']}")
            print(f"  ✓ Batch size: {summary['batch_size']}")
            print(f"  ✓ Number of batches: {summary['num_batches']}")
            
            # Generate SQL files
            if self.dry_run:
                print("\n[4/4] DRY RUN - Skipping file generation")
                print(f"\nWould generate {summary['num_batches']} file(s) in:")
                print(f"  {Path(self.output_dir).absolute()}")
                
                # Show what filenames would be
                base_filename = self.incident_code or Path(self.template_path).stem
                
                if self.output_format in ['sql', 'both']:
                    print(f"\n  SQL files (in /csv or /sql subdir):")
                    for i in range(1, summary['num_batches'] + 1):
                        if summary['num_batches'] == 1:
                            filename = f"{base_filename}.sql"
                        else:
                            filename = f"{base_filename}_Extract{i}.sql"
                        print(f"    - {filename}")
                
                if self.output_format in ['dtf', 'both']:
                    print(f"\n  DTF files (in /dtf subdir):")
                    for i in range(1, summary['num_batches'] + 1):
                        if summary['num_batches'] == 1:
                            filename = f"{base_filename}.dtf"
                        else:
                            filename = f"{base_filename}_Extract{i}.dtf"
                        print(f"    - {filename}")
            else:
                if self.verbose:
                    print("\n[4/4] Generating files...")
                
                base_filename = self.incident_code or Path(self.template_path).stem
                incident_code = self.incident_code or base_filename
                
                generated_files = generator.generate_extracts(
                    transaction_refs=transaction_refs,
                    output_dir=self.output_dir,
                    base_filename=base_filename,
                    incident_code=incident_code
                )
                
                # Report generated files
                if generated_files['sql_files']:
                    print(f"\n✓ Successfully generated {len(generated_files['sql_files'])} SQL file(s):")
                    for file_path in generated_files['sql_files']:
                        print(f"    - {file_path}")
                
                if generated_files['dtf_files']:
                    print(f"\n✓ Successfully generated {len(generated_files['dtf_files'])} DTF file(s):")
                    for file_path in generated_files['dtf_files']:
                        print(f"    - {file_path}")
            
            print("\n" + "=" * 70)
            print("GENERATION COMPLETE")
            print("=" * 70)
            
            return 0
        
        except Exception as e:
            print(f"\n✗ ERROR: {e}", file=sys.stderr)
            if self.verbose:
                import traceback
                traceback.print_exc()
            return 1


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='SQL Extract Generator v1.0 - Generate SQL extracts from transaction references',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use configuration file
  python -m src.accuracy_testing.scripts.sql_extract_generator \\
      --config config/templates/sql_extract_generator_template.yaml
  
  # Basic usage with command line arguments
  python -m src.accuracy_testing.scripts.sql_extract_generator \\
      --template legacy/sql/ExtractBuyerID4_1.sql \\
      --input data/transactions.csv \\
      --output extracts/
  
  # Custom batch size
  python -m src.accuracy_testing.scripts.sql_extract_generator \\
      --template legacy/sql/SCR_pricing_data_v1.0.sql \\
      --input data/pricing_refs.csv \\
      --output extracts/ \\
      --batch-size 500
  
  # Specify transaction column by name
  python -m src.accuracy_testing.scripts.sql_extract_generator \\
      --template legacy/sql/ExtractSellerID4_1.sql \\
      --input data/seller_transactions.csv \\
      --output extracts/ \\
      --column "Transaction Reference"
  
  # Dry run to preview
  python -m src.accuracy_testing.scripts.sql_extract_generator \\
      --template legacy/sql/ExtractInconsistentBuyerID1_0.sql \\
      --input data/inconsistent_refs.csv \\
      --output extracts/ \\
      --dry-run
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file (default: config/templates/sql_extract_generator_template.yaml)'
    )
    
    parser.add_argument(
        '--template',
        type=str,
        help='Path to SQL template file'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='Path to input CSV file with transaction references'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Directory for output SQL files'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=900,
        help='Number of transaction references per SQL file (default: 900)'
    )
    
    parser.add_argument(
        '--placeholder',
        type=str,
        default=None,
        help='Custom placeholder pattern in template (auto-detects if not specified)'
    )
    
    parser.add_argument(
        '--column',
        type=str,
        default=None,
        help='CSV column name or index for transaction references (default: first column)'
    )
    
    parser.add_argument(
        '--output-format',
        type=str,
        choices=['sql', 'dtf', 'both'],
        default='both',
        help='Output format: sql (SQL files only), dtf (DTF files only), or both (default: both)'
    )
    
    parser.add_argument(
        '--incident-code',
        type=str,
        default=None,
        help='Incident code for CSV naming in DTF files (defaults to template basename)'
    )
    
    parser.add_argument(
        '--dtf-template',
        type=str,
        default=None,
        help='Path to DTF template file (uses default if not specified)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview mode - show what would be generated without writing files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed output'
    )
    
    parser.add_argument(
        '--gui-mode',
        action='store_true',
        help=argparse.SUPPRESS,
    )
    
    return parser.parse_args()


def get_sql_template_for_incident(incident_code: str, sql_template_dir: Path) -> Path:
    """
    Determine the appropriate SQL template for an incident code.
    
    Args:
        incident_code: Incident code (e.g., '7_37', '16_21', '35_3')
        sql_template_dir: Directory containing SQL templates
        
    Returns:
        Path to the appropriate SQL template file
        
    Raises:
        FileNotFoundError: If template not found
    """
    # Map incident types to SQL templates (based on INCIDENT_CODE_MATRIX)
    # Standard buyer (7_35, 7_37, 7_39) → BuyerID.sql
    # Standard seller (16_19, 16_21, 16_23) → SellerID.sql  
    # Pricing (35_3) → SCR_pricing_data_v1.0.sql
    # Inconsistent buyer (7_66) → InconsistentBuyerID.sql
    # Inconsistent seller (16_20) → InconsistentSellerID.sql
    # Decision maker buyer (12_17) → FTBDM.sql
    # Decision maker seller (21_17) → FTSDM.sql
    
    # Pricing incidents
    if incident_code == '35_3':
        template_path = sql_template_dir / "SCR_pricing_data_v1.0.sql"
    # Non-zero net quantity — uses VALUES block CTE, not an IN-clause
    elif incident_code == '7_6':
        template_path = sql_template_dir / "NonZeroNetQuantity.sql"
    # Non-zero net amount — uses VALUES block CTE, not an IN-clause
    elif incident_code == '7_42':
        template_path = sql_template_dir / "NonZeroNetAmount.sql"
    # Inconsistent buyer
    elif incident_code == '7_66':
        template_path = sql_template_dir / "InconsistentBuyerID.sql"
    # Inconsistent seller
    elif incident_code == '16_20':
        template_path = sql_template_dir / "InconsistentSellerID.sql"
    # Decision maker buyer
    elif incident_code.startswith('12_'):
        template_path = sql_template_dir / "FTBDM.sql"
    # Decision maker seller
    elif incident_code.startswith('21_'):
        template_path = sql_template_dir / "FTSDM.sql"
    # Regular buyer incidents
    elif is_buyer_incident(incident_code):
        template_path = sql_template_dir / "BuyerID.sql"
    # Regular seller incidents
    elif is_seller_incident(incident_code):
        template_path = sql_template_dir / "SellerID.sql"
    else:
        raise ValueError(f"Unknown incident code: {incident_code}. Cannot determine SQL template.")
    
    if not template_path.exists():
        raise FileNotFoundError(f"SQL template not found: {template_path}")
    
    return template_path


# Incidents that require a DB2 VALUES block instead of a SQL IN-clause.
# The corresponding SQL templates use {VALUES} as their placeholder.
VALUES_MODE_INCIDENTS: set = {'7_6', '7_42'}


def requires_values_mode(incident_code: str) -> bool:
    """
    Return True if the incident uses a DB2 VALUES block rather than a SQL IN-clause.

    Args:
        incident_code: Incident code string (e.g. '7_6')

    Returns:
        True when the SQL template for this incident uses {VALUES} formatting
        (reference fields are split into component columns and CA references
        are excluded).
    """
    return incident_code in VALUES_MODE_INCIDENTS


def run_batch_sql_generation(config: Dict, dry_run: bool = False, verbose: bool = False) -> int:
    """
    Run SQL generation for multiple incidents in batch mode.
    
    Args:
        config: Configuration dictionary with testing_period, incidents, and paths
        dry_run: If True, preview without writing files
        verbose: If True, show detailed output
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Extract batch configuration
    testing_period = config.get('testing_period', {})
    fiscal_year = testing_period.get('fiscal_year', 'FYXX')
    quarter = testing_period.get('quarter', 'QX')
    
    # Get batch mode configuration
    batch_config = config.get('batch', {})
    
    # Check for incidents configuration
    incidents_config = batch_config.get('incidents', [])
    if incidents_config == 'all':
        # Get all automated incidents list from config
        incidents = batch_config.get('all_incidents', [])
        if not incidents:
            raise ValueError("Configuration error: 'batch.all_incidents' is required when incidents: 'all' is specified")
        print(f"Processing all {len(incidents)} automated incidents")
    elif isinstance(incidents_config, list):
        incidents = incidents_config
    else:
        incidents = []
    
    # Get paths from batch configuration
    paths = batch_config.get('paths', {})
    template_dir = Path(paths.get('template_dir', 'data/templates'))
    output_dir = Path(paths.get('output_dir', 'data/sql_extracts'))
    sql_template_dir = Path(paths.get('sql_template_dir', 'src/accuracy_testing/sql_templates'))
    dtf_template_path = paths.get('dtf_template_file')
    
    # Get filename patterns from batch configuration
    filename_patterns = batch_config.get('filename_patterns', {})
    template_pattern = filename_patterns.get('template', '{fiscal_year} {quarter} {incident}.csv')
    output_sql_pattern = filename_patterns.get('output_sql', '{incident}_{fiscal_year}_{quarter}.sql')
    output_sql_batch_pattern = filename_patterns.get('output_sql_batch', '{incident}_{fiscal_year}_{quarter}_Extract{batch_num}.sql')
    output_dtf_pattern = filename_patterns.get('output_dtf', '{incident}_{fiscal_year}_{quarter}.dtf')
    output_dtf_batch_pattern = filename_patterns.get('output_dtf_batch', '{incident}_{fiscal_year}_{quarter}_Extract{batch_num}.dtf')
    output_csv_pattern = filename_patterns.get('output_csv', '{incident}_{fiscal_year}_{quarter}.csv')
    output_csv_batch_pattern = filename_patterns.get('output_csv_batch', '{incident}_{fiscal_year}_{quarter}_Extract{batch_num}.csv')
    
    # Get processing options
    processing = config.get('processing', {})
    batch_size = processing.get('batch_size', 900)
    placeholder = processing.get('placeholder_pattern', '-- TRANSACTION REFERENCES --')
    transaction_column = processing.get('transaction_column', 'Transaction reference number')
    output_format = processing.get('output_format', 'both')
    
    if not incidents:
        print("ERROR: No incidents specified in config")
        return 1
    
    print(f"\n{'='*70}")
    print(f"BATCH SQL EXTRACT GENERATION - {fiscal_year} {quarter}")
    print(f"{'='*70}")
    print(f"Template directory:       {template_dir}")
    print(f"SQL template directory:   {sql_template_dir}")
    print(f"Output directory:         {output_dir}")
    print(f"Output format:            {output_format}")
    print(f"Incidents:                {', '.join(incidents)}")
    print(f"Batch size:               {batch_size} records per file")
    print(f"{'='*70}\n")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_success = 0
    total_failed = 0
    total_sql_files = 0
    total_dtf_files = 0
    
    for incident in incidents:
        print(f"\n{'─'*70}")
        print(f"Processing incident: {incident}")
        print(f"{'─'*70}")
        
        try:
            # Determine SQL template for this incident
            sql_template = get_sql_template_for_incident(incident, sql_template_dir)
            print(f"SQL template: {sql_template.name}")
            
            # Build template CSV filename using configured pattern
            template_filename = template_pattern.format(
                incident=incident, fiscal_year=fiscal_year, quarter=quarter
            )
            template_path = template_dir / template_filename
            
            # Check if template CSV exists
            if not template_path.exists():
                print(f"⚠️  Template not found: {template_path}")
                print(f"   Skipping incident {incident}")
                total_failed += 1
                continue
            
            # Read transaction refs from template CSV
            refs = []
            with open(template_path, 'r', encoding='cp1252') as f:
                reader = csv.DictReader(f)
                if transaction_column not in reader.fieldnames:
                    print(f"⚠️  Column '{transaction_column}' not found in {template_filename}")
                    print(f"   Available columns: {', '.join(reader.fieldnames)}")
                    total_failed += 1
                    continue
                
                for row in reader:
                    ref = row[transaction_column].strip()
                    if ref:
                        refs.append(ref)
            
            if not refs:
                print(f"⚠️  No transaction references found in {template_filename}")
                total_failed += 1
                continue
            
            print(f"Transaction refs: {len(refs)}")
            
            # Generate SQL extracts.
            # Always pass placeholder=None so the generator auto-detects the token
            # in the template (whether {VALUES} or a comment-style marker).
            # values_mode is likewise auto-derived from the detected placeholder.
            generator = SQLExtractGenerator(
                template_path=str(sql_template),
                batch_size=batch_size,
                placeholder=None,
                output_format=output_format,
                dtf_template_path=dtf_template_path,
            )

            if generator.values_mode and verbose:
                print("  VALUES mode: enabled (CA references will be excluded)")
            
            summary = generator.get_summary(refs)
            num_batches = summary['num_batches']
            
            if dry_run:
                if output_format in ['sql', 'both']:
                    print(f"DRY RUN - Would generate {num_batches} SQL file(s)")
                    for i in range(1, num_batches + 1):
                        if num_batches == 1:
                            filename = f"{incident}_{fiscal_year}_{quarter}.sql"
                        else:
                            filename = f"{incident}_{fiscal_year}_{quarter}_Extract{i}.sql"
                        print(f"  - {filename}")
                
                if output_format in ['dtf', 'both']:
                    print(f"DRY RUN - Would generate {num_batches} DTF file(s)")
                    for i in range(1, num_batches + 1):
                        if num_batches == 1:
                            filename = f"{incident}_{fiscal_year}_{quarter}.dtf"
                        else:
                            filename = f"{incident}_{fiscal_year}_{quarter}_Extract{i}.dtf"
                        print(f"  - {filename}")
                
                total_success += 1
                if output_format in ['sql', 'both']:
                    total_sql_files += num_batches
                if output_format in ['dtf', 'both']:
                    total_dtf_files += num_batches
            else:
                # Generate with custom base filename
                base_filename = f"{incident}_{fiscal_year}_{quarter}"
                generated_files = generator.generate_extracts(
                    transaction_refs=refs,
                    output_dir=str(output_dir),
                    base_filename=base_filename,
                    incident_code=incident
                )
                
                if generated_files['sql_files']:
                    print(f"✓ Generated {len(generated_files['sql_files'])} SQL file(s)")
                    if verbose:
                        for file_path in generated_files['sql_files']:
                            print(f"  - {Path(file_path).name}")
                    total_sql_files += len(generated_files['sql_files'])
                
                if generated_files['dtf_files']:
                    print(f"✓ Generated {len(generated_files['dtf_files'])} DTF file(s)")
                    if verbose:
                        for file_path in generated_files['dtf_files']:
                            print(f"  - {Path(file_path).name}")
                    total_dtf_files += len(generated_files['dtf_files'])
                
                total_success += 1
        
        except Exception as e:
            print(f"✗ Failed: {incident} - {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            total_failed += 1
            continue
    
    # Print batch summary
    print(f"\n{'='*70}")
    print(f"BATCH SQL GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"Incidents processed:  {total_success}/{len(incidents)}")
    print(f"Incidents failed:     {total_failed}/{len(incidents)}")
    if output_format in ['sql', 'both']:
        print(f"Total SQL files:      {total_sql_files}")
    if output_format in ['dtf', 'both']:
        print(f"Total DTF files:      {total_dtf_files}")
    print(f"{'='*70}\n")
    
    return 0 if total_failed == 0 else 1


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Load configuration if provided or use default
    config = {}
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        # Try default configuration path
        default_config = Path(__file__).parent.parent.parent.parent / "config" / "local" / "accuracy_testing" / "sql_extract_generator.yaml"
        if default_config.exists():
            print(f"Loading default configuration from {default_config}...")
            with open(default_config, 'r') as f:
                config = yaml.safe_load(f)
    
    # Determine paths (CLI args override config)
    template_path = args.template
    input_csv = args.input
    output_dir = args.output
    batch_size = args.batch_size or 900
    placeholder = args.placeholder
    transaction_column = args.column
    dry_run = args.dry_run
    verbose = args.verbose
    output_format = args.output_format
    incident_code = args.incident_code
    dtf_template_path = args.dtf_template
    
    # Get from config if available and not provided via CLI
    if config:
        # Single mode paths are nested under 'single.paths' in the config YAML,
        # mirroring how batch mode uses 'batch.paths'
        single_config = config.get('single', {})
        paths = single_config.get('paths', config.get('paths', {}))
        processing = config.get('processing', {})
        options = config.get('options', config.get('output_options', {}))
        
        if not template_path:
            template_path = paths.get('sql_template_file')
        if not input_csv:
            input_csv = paths.get('template_file')
        if not output_dir:
            output_dir = paths.get('output_dir', paths.get('output_directory'))
        if not placeholder:
            placeholder = processing.get('placeholder_pattern')
        if not transaction_column:
            transaction_column = processing.get('transaction_column')
        if args.batch_size == 900:  # default value
            batch_size = processing.get('batch_size', 900)
        if args.output_format == 'both':  # default value
            output_format = processing.get('output_format', 'both')
        if not incident_code:
            incident_code = single_config.get('incident_code')
        if not dtf_template_path:
            dtf_template_path = paths.get('dtf_template_file')
    
    # Check if batch mode (using mode field from config)
    mode = config.get('mode', 'single')  # Default to single if not specified
    is_batch_mode = mode == 'batch'
    
    if is_batch_mode:
        # Run batch SQL generation
        return run_batch_sql_generation(
            config=config,
            dry_run=dry_run,
            verbose=verbose
        )
    
    # Single mode - validate required arguments
    if not template_path:
        print("ERROR: Template file (--template or via --config) is required")
        return 1
    if not input_csv:
        print("ERROR: Input CSV file (--input or via --config) is required")
        return 1
    if not output_dir:
        print("ERROR: Output directory (--output or via --config) is required")
        return 1
    
    # Auto-detect placeholder from the template; values_mode is derived in
    # SQLExtractGenerator from the detected placeholder, so no incident-code
    # look-up is required here.
    effective_placeholder = placeholder

    cli = SQLExtractGeneratorCLI(
        template_path=template_path,
        input_csv=input_csv,
        output_dir=output_dir,
        batch_size=batch_size,
        placeholder=effective_placeholder,
        transaction_column=transaction_column,
        dry_run=dry_run,
        verbose=verbose,
        output_format=output_format,
        incident_code=incident_code,
        dtf_template_path=dtf_template_path,
        values_mode=False,  # Auto-derived by SQLExtractGenerator from the detected placeholder
    )
    
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
