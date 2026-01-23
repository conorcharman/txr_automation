#!/usr/bin/env python3
"""
Accuracy Testing Template Generator CLI
========================================

Command-line interface for generating accuracy testing template files.

Usage:
    generate-accuracy-template \\
        --errors data/consolidated_errors.csv \\
        --queries data/consolidated_queries.csv \\
        --output templates/
    
    # With only errors file
    generate-accuracy-template \\
        --errors data/consolidated_errors.csv \\
        --output templates/
    
    # Dry run to see what would be generated
    generate-accuracy-template \\
        --errors data/consolidated_errors.csv \\
        --queries data/consolidated_queries.csv \\
        --output templates/ \\
        --dry-run
"""

import argparse
import sys
import yaml
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.accuracy_template_generator import (
    AccuracyTemplateGenerator,
    TemplateFormat
)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate accuracy testing template files from consolidated data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate using config file
  %(prog)s --config config/environments/local.yaml
  
  # Generate templates from both errors and queries
  %(prog)s --errors errors.csv --queries queries.csv --output templates/
  
  # Generate from errors only
  %(prog)s --errors errors.csv --output templates/
  
  # Preview without generating files
  %(prog)s --config config/environments/local.yaml --dry-run

Template Formats:
  Buyer validation:   7_35, 7_37, 7_39, 7_66
  Seller validation:  16_19, 16_21, 16_23, 16_20
  Pricing validation: 35_3
  Default format:     All other incident codes
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--errors',
        type=str,
        help='Path to consolidated errors CSV file (overrides config)'
    )
    
    parser.add_argument(
        '--queries',
        type=str,
        help='Path to consolidated queries CSV file (overrides config)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output directory for template files (overrides config)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview generation without creating files'
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)


def print_header():
    """Print script header."""
    print("=" * 70)
    print("ACCURACY TESTING TEMPLATE GENERATOR")
    print("=" * 70)


def print_summary(generator: AccuracyTemplateGenerator, output_dir: str, dry_run: bool = False):
    """Print generation summary."""
    summary = generator.get_summary()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total incident codes:      {summary['total_incidents']}")
    print(f"Total records:             {summary['total_records']}")
    print(f"  - Buyer validation:      {summary['buyer_records']}")
    print(f"  - Seller validation:     {summary['seller_records']}")
    print(f"  - Pricing validation:    {summary['pricing_records']}")
    print(f"  - Default format:        {summary['default_records']}")
    
    if dry_run:
        print(f"\nDRY RUN - No files generated")
        print(f"Would generate {summary['total_incidents']} template files in:")
        print(f"  {output_dir}")
    else:
        print(f"\n✓ Generated {summary['total_incidents']} template files in:")
        print(f"  {output_dir}")
    
    print("=" * 70)


def main():
    """Main entry point."""
    args = parse_args()
    
    print_header()
    
    # Load configuration if provided
    config = {}
    if args.config:
        config = load_config(args.config)
    
    # Determine paths (CLI args override config)
    errors_path = None
    queries_path = None
    output_dir = None
    
    # Get from config if available
    if config:
        paths = config.get('paths', {})
        input_paths = paths.get('input', {})
        output_paths = paths.get('output', {})
        
        errors_path = input_paths.get('errors_file')
        queries_path = input_paths.get('queries_file')
        output_dir = output_paths.get('directory')
    
    # CLI args override config
    if args.errors:
        errors_path = args.errors
    if args.queries:
        queries_path = args.queries
    if args.output:
        output_dir = args.output
    
    # Validate inputs
    if not errors_path and not queries_path:
        print("ERROR: At least one input file (--errors, --queries, or via --config) is required")
        sys.exit(1)
    
    if not output_dir:
        print("ERROR: Output directory (--output or via --config) is required")
        sys.exit(1)
    
    errors_path = Path(errors_path) if errors_path else None
    queries_path = Path(queries_path) if queries_path else None
    output_dir = Path(output_dir)
    
    # Check input files exist
    if errors_path and not errors_path.exists():
        print(f"ERROR: Errors file not found: {errors_path}")
        sys.exit(1)
    
    if queries_path and not queries_path.exists():
        print(f"ERROR: Queries file not found: {queries_path}")
        sys.exit(1)
    
    # Display configuration
    if args.config:
        print(f"Config file:   {args.config}")
    print(f"Errors file:   {errors_path if errors_path else 'Not provided'}")
    print(f"Queries file:  {queries_path if queries_path else 'Not provided'}")
    print(f"Output dir:    {output_dir}")
    print(f"Mode:          {'DRY RUN (preview only)' if args.dry_run else 'Generate files'}")
    print("=" * 70)
    
    try:
        # Initialize generator
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(errors_path) if errors_path else None,
            consolidated_queries=str(queries_path) if queries_path else None
        )
        
        # Load data
        generator.load_consolidated_data()
        
        if args.dry_run:
            # Preview mode
            print("\nDRY RUN - Preview of templates that would be generated:")
            print()
            
            for incident_code in sorted(generator.incident_records.keys()):
                record_count = len(generator.incident_records[incident_code])
                template_type = TemplateFormat.get_template_type(incident_code)
                print(f"  template_{incident_code}.csv ({template_type} format, {record_count} records)")
            
            print_summary(generator, str(output_dir), dry_run=True)
        else:
            # Generate templates
            generated_files = generator.generate_templates(str(output_dir))
            
            print_summary(generator, str(output_dir))
        
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
