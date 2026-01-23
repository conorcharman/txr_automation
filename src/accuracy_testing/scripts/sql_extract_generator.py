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
from typing import List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.sql_extract_generator import SQLExtractGenerator


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
        verbose: bool = False
    ):
        """
        Initialize CLI.
        
        Args:
            template_path: Path to SQL template file
            input_csv: Path to CSV file with transaction references
            output_dir: Directory for output SQL files
            batch_size: Records per SQL file (default 900)
            placeholder: Custom placeholder pattern (auto-detects if None)
            transaction_column: CSV column name/index for transaction refs
            dry_run: Preview mode - don't write files
            verbose: Enable detailed output
        """
        self.template_path = template_path
        self.input_csv = input_csv
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.placeholder = placeholder
        self.transaction_column = transaction_column
        self.dry_run = dry_run
        self.verbose = verbose
    
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
        
        with open(input_path, 'r', encoding='utf-8') as f:
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
            print(f"Template:     {self.template_path}")
            print(f"Input CSV:    {self.input_csv}")
            print(f"Output Dir:   {self.output_dir}")
            print(f"Batch Size:   {self.batch_size}")
            if self.dry_run:
                print("Mode:         DRY RUN (preview only)")
            print("=" * 70)
            
            # Initialize generator
            if self.verbose:
                print("\n[1/4] Loading SQL template...")
            
            generator = SQLExtractGenerator(
                template_path=self.template_path,
                batch_size=self.batch_size,
                placeholder=self.placeholder
            )
            
            if self.verbose:
                print(f"  ✓ Template loaded: {generator.template_path.name}")
                print(f"  ✓ Placeholder detected: {generator.placeholder}")
            
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
                print(f"\nWould generate {summary['num_batches']} SQL file(s) in:")
                print(f"  {Path(self.output_dir).absolute()}")
                
                # Show what filenames would be
                base_filename = Path(self.template_path).stem
                for i in range(1, summary['num_batches'] + 1):
                    if summary['num_batches'] == 1:
                        filename = f"{base_filename}.sql"
                    else:
                        filename = f"{base_filename}_Extract{i}.sql"
                    print(f"    - {filename}")
            else:
                if self.verbose:
                    print("\n[4/4] Generating SQL files...")
                
                base_filename = Path(self.template_path).stem
                generated_files = generator.generate_extracts(
                    transaction_refs=transaction_refs,
                    output_dir=self.output_dir,
                    base_filename=base_filename
                )
                
                print(f"\n✓ Successfully generated {len(generated_files)} SQL file(s):")
                for file_path in generated_files:
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
        '--dry-run',
        action='store_true',
        help='Preview mode - show what would be generated without writing files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed output'
    )
    
    return parser.parse_args()


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
    
    # Get from config if available and not provided via CLI
    if config:
        paths = config.get('paths', {})
        processing = config.get('processing', {})
        
        if not template_path:
            template_path = paths.get('template_file')
        if not input_csv:
            input_csv = paths.get('input_file')
        if not output_dir:
            output_dir = paths.get('output_directory')
        if not placeholder:
            placeholder = processing.get('placeholder_pattern')
        if not transaction_column:
            transaction_column = processing.get('transaction_column')
        if args.batch_size == 900:  # default value
            batch_size = processing.get('batch_size', 900)
    
    # Validate required arguments
    if not template_path:
        print("ERROR: Template file (--template or via --config) is required")
        return 1
    if not input_csv:
        print("ERROR: Input CSV file (--input or via --config) is required")
        return 1
    if not output_dir:
        print("ERROR: Output directory (--output or via --config) is required")
        return 1
    
    cli = SQLExtractGeneratorCLI(
        template_path=template_path,
        input_csv=input_csv,
        output_dir=output_dir,
        batch_size=batch_size,
        placeholder=placeholder,
        transaction_column=transaction_column,
        dry_run=dry_run,
        verbose=verbose
    )
    
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
