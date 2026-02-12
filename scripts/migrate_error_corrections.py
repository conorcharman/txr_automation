#!/usr/bin/env python3
"""
Migrate Error and Correction Data
==================================

Migrates error and correction data from old template CSV files to new template CSV files.

This script reads source CSV files, looks up records by Transaction Reference,
and copies error/correction columns to matching records in target files using
dynamic column header mapping.

Version 1.0:
- Dynamic column mapping by header names
- Transaction Reference matching
- Dry-run mode for preview
- Detailed statistics and logging
- Backup creation option

Usage:
    python scripts/migrate_error_corrections.py --source-dir old_templates/ --target-dir new_templates/
    python scripts/migrate_error_corrections.py --source-dir old/ --target-dir new/ --dry-run
    python scripts/migrate_error_corrections.py --source old.csv --target new.csv  # Single file mode
"""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Column mapping: source -> target
COLUMN_MAPPING = {
    "Error (Y/N)": "Error",
    "Correction": "Correction",
    "Correction Field (Select Dropdown)": "Correction Field",
    "Checked": "Agree With Correction",
    "Checked Correction": "Suggested Correction",
    "Checked Correction Field": "Suggested Correction Field",
}


@dataclass
class MigrationStats:
    """Statistics for migration operation."""
    
    source_records: int = 0
    target_records: int = 0
    matched_records: int = 0
    unmatched_source: int = 0
    unmatched_target: int = 0
    columns_migrated: int = 0
    errors: List[str] = field(default_factory=list)
    
    def print_summary(self, dry_run: bool = False) -> None:
        """Print migration statistics summary."""
        mode = "DRY RUN - " if dry_run else ""
        logger.info("=" * 70)
        logger.info(f"{mode}MIGRATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Source records:           {self.source_records}")
        logger.info(f"Target records:           {self.target_records}")
        logger.info(f"Matched and migrated:     {self.matched_records}")
        logger.info(f"Columns migrated:         {self.columns_migrated}")
        logger.info(f"Unmatched in source:      {self.unmatched_source}")
        logger.info(f"Unmatched in target:      {self.unmatched_target}")
        
        if self.errors:
            logger.warning(f"Errors encountered:       {len(self.errors)}")
            for error in self.errors[:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
            if len(self.errors) > 5:
                logger.warning(f"  ... and {len(self.errors) - 5} more")
        
        logger.info("=" * 70)


@dataclass
class BatchMigrationStats:
    """Statistics for batch migration operation."""
    
    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    total_records_migrated: int = 0
    file_stats: List[Tuple[str, MigrationStats]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def print_batch_summary(batch_stats: BatchMigrationStats, dry_run: bool = False) -> None:
    """Print batch migration statistics summary."""
    mode = "DRY RUN - " if dry_run else ""
    logger.info("")
    logger.info("#" * 70)
    logger.info(f"{mode}BATCH MIGRATION SUMMARY")
    logger.info("#" * 70)
    logger.info(f"Total files processed:    {batch_stats.files_processed}")
    logger.info(f"Files succeeded:          {batch_stats.files_succeeded}")
    logger.info(f"Files failed:             {batch_stats.files_failed}")
    logger.info(f"Total records migrated:   {batch_stats.total_records_migrated}")
    logger.info("")
    
    if batch_stats.files_succeeded > 0:
        logger.info("Successfully processed files:")
        for filename, stats in batch_stats.file_stats:
            if not stats.errors:
                logger.info(f"  ✓ {filename}: {stats.matched_records} records migrated")
    
    if batch_stats.files_failed > 0:
        logger.info("")
        logger.warning("Failed files:")
        for filename, stats in batch_stats.file_stats:
            if stats.errors:
                logger.warning(f"  ✗ {filename}: {stats.errors[0] if stats.errors else 'Unknown error'}")
    
    if batch_stats.errors:
        logger.info("")
        logger.warning(f"General errors: {len(batch_stats.errors)}")
        for error in batch_stats.errors[:5]:
            logger.warning(f"  - {error}")
    
    logger.info("#" * 70)


def validate_file_exists(file_path: Path, file_type: str) -> None:
    """
    Validate that a file exists and is readable.
    
    Args:
        file_path: Path to the file
        file_type: Description of file type (for error messages)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If path is not a file
    """
    if not file_path.exists():
        raise FileNotFoundError(f"{file_type} file not found: {file_path}")
    
    if not file_path.is_file():
        raise ValueError(f"{file_type} path is not a file: {file_path}")


def find_transaction_ref_column(headers: List[str]) -> Optional[str]:
    """
    Find the Transaction Reference column in CSV headers.
    
    Searches for common variations of the transaction reference column name.
    
    Args:
        headers: List of column headers
        
    Returns:
        Column name if found, None otherwise
    """
    possible_names = [
        "Transaction Reference",
        "Transaction Ref",
        "TransactionReference",
        "Txn Reference",
        "Txn Ref",
        "Reference",
    ]
    
    for col in headers:
        col_normalized = col.strip()
        if col_normalized in possible_names:
            return col
    
    return None


def validate_columns(
    headers: List[str],
    required_columns: List[str],
    file_type: str
) -> Tuple[List[str], List[str]]:
    """
    Validate that required columns exist in CSV headers.
    
    Args:
        headers: List of column headers
        required_columns: List of required column names
        file_type: Description of file type (for error messages)
        
    Returns:
        Tuple of (found_columns, missing_columns)
    """
    header_set = set(headers)
    found = []
    missing = []
    
    for col in required_columns:
        if col in header_set:
            found.append(col)
        else:
            missing.append(col)
    
    if missing:
        logger.warning(f"{file_type}: Missing columns: {missing}")
    
    return found, missing


def load_csv_file(file_path: Path, file_type: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Load CSV file into list of dictionaries.
    
    Args:
        file_path: Path to CSV file
        file_type: Description of file type (for logging)
        
    Returns:
        Tuple of (headers, records) where records is a list of dictionaries
        
    Raises:
        ValueError: If file cannot be loaded or validated
    """
    try:
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames) if reader.fieldnames else []
            records = list(reader)
        
        logger.info(f"Loaded {file_type}: {file_path.name} ({len(records)} records)")
        return headers, records
    except Exception as e:
        raise ValueError(f"Failed to load {file_type} file {file_path.name}: {e}")


def migrate_data(
    source_headers: List[str],
    source_records: List[Dict[str, str]],
    target_headers: List[str],
    target_records: List[Dict[str, str]],
    column_mapping: Dict[str, str],
    txn_ref_col_source: str,
    txn_ref_col_target: str,
    stats: MigrationStats
) -> List[Dict[str, str]]:
    """
    Migrate error and correction data from source to target records.
    
    Args:
        source_headers: Source file column headers
        source_records: Source file records as list of dictionaries
        target_headers: Target file column headers
        target_records: Target file records as list of dictionaries
        column_mapping: Dictionary mapping source columns to target columns
        txn_ref_col_source: Transaction Reference column name in source
        txn_ref_col_target: Transaction Reference column name in target
        stats: MigrationStats object to update
        
    Returns:
        Modified target records
    """
    # Validate columns exist
    source_cols, missing_source = validate_columns(
        source_headers,
        list(column_mapping.keys()),
        "Source"
    )
    
    target_cols, missing_target = validate_columns(
        target_headers,
        list(column_mapping.values()),
        "Target"
    )
    
    # Filter mapping to only include columns present in both files
    active_mapping = {}
    for src_col, tgt_col in column_mapping.items():
        if src_col in source_cols and tgt_col in target_cols:
            active_mapping[src_col] = tgt_col
    
    if not active_mapping:
        raise ValueError(
            "No valid column mappings found. Check that both source and target "
            "files contain the expected columns."
        )
    
    stats.columns_migrated = len(active_mapping)
    logger.info(f"Active column mappings: {len(active_mapping)}")
    for src, tgt in active_mapping.items():
        logger.debug(f"  {src} -> {tgt}")
    
    # Create lookup dictionary from source data
    source_lookup = {}
    for row in source_records:
        txn_ref = row.get(txn_ref_col_source, '')
        if txn_ref and txn_ref.strip():
            txn_ref_key = str(txn_ref).strip()
            source_lookup[txn_ref_key] = row
    
    stats.source_records = len(source_records)
    logger.info(f"Source lookup created: {len(source_lookup)} unique transaction refs")
    
    # Track matches
    matched_refs = set()
    target_refs = set()
    
    # Migrate data - work on target records in place
    for row in target_records:
        txn_ref = row.get(txn_ref_col_target, '')
        
        if txn_ref and txn_ref.strip():
            txn_ref_key = str(txn_ref).strip()
            target_refs.add(txn_ref_key)
            
            if txn_ref_key in source_lookup:
                source_row = source_lookup[txn_ref_key]
                matched_refs.add(txn_ref_key)
                
                # Copy mapped columns
                for src_col, tgt_col in active_mapping.items():
                    value = source_row.get(src_col, '')
                    row[tgt_col] = value
                
                logger.debug(f"Migrated data for Transaction Ref: {txn_ref_key}")
    
    # Calculate statistics
    stats.target_records = len(target_records)
    stats.matched_records = len(matched_refs)
    stats.unmatched_source = len(source_lookup) - len(matched_refs)
    stats.unmatched_target = len(target_refs) - len(matched_refs)
    
    # Log unmatched references
    if stats.unmatched_source > 0:
        unmatched_src = set(source_lookup.keys()) - matched_refs
        logger.warning(
            f"Found {stats.unmatched_source} transaction refs in source "
            f"that don't exist in target"
        )
        for ref in list(unmatched_src)[:5]:
            logger.debug(f"  Unmatched source ref: {ref}")
    
    if stats.unmatched_target > 0:
        unmatched_tgt = target_refs - matched_refs
        logger.info(
            f"Found {stats.unmatched_target} transaction refs in target "
            f"that don't exist in source (these will keep original values)"
        )
        for ref in list(unmatched_tgt)[:5]:
            logger.debug(f"  Unmatched target ref: {ref}")
    
    return target_records


def create_backup(file_path: Path) -> Path:
    """
    Create a backup of the target file before modification.
    
    Args:
        file_path: Path to file to backup
        
    Returns:
        Path to backup file
    """
    backup_path = file_path.with_suffix('.backup' + file_path.suffix)
    counter = 1
    
    # Avoid overwriting existing backups
    while backup_path.exists():
        backup_path = file_path.with_suffix(f'.backup{counter}{file_path.suffix}')
        counter += 1
    
    # Copy file
    import shutil
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path.name}")
    
    return backup_path


def find_csv_files_in_directory(directory: Path) -> List[Path]:
    """
    Find all CSV files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        List of CSV file paths
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    
    csv_files = sorted(directory.glob('*.csv'))
    logger.info(f"Found {len(csv_files)} CSV file(s) in {directory.name}")
    
    return csv_files


def match_target_file(source_file: Path, target_dir: Path) -> Optional[Path]:
    """
    Find corresponding target file for a source file.
    
    Handles filename pattern transformation:
    - Source pattern: "FY** Q* - *_*" (with hyphen)
    - Target pattern: "FY** Q* *_*" (without hyphen)
    
    Args:
        source_file: Source file path
        target_dir: Target directory
        
    Returns:
        Path to matching target file, or None if not found
    """
    # First try exact match
    target_file = target_dir / source_file.name
    if target_file.exists():
        return target_file
    
    # Try removing " - " pattern (space-hyphen-space) for FY** Q* pattern
    # Example: "FY25 Q4 - 7_1.csv" -> "FY25 Q4 7_1.csv"
    if " - " in source_file.name:
        target_filename = source_file.name.replace(" - ", " ")
        target_file = target_dir / target_filename
        if target_file.exists():
            logger.debug(f"Matched {source_file.name} -> {target_filename}")
            return target_file
    
    return None


def process_single_migration(
    source_path: Path,
    target_path: Path,
    output_path: Optional[Path] = None,
    dry_run: bool = False,
    create_backup_flag: bool = True
) -> MigrationStats:
    """
    Process the migration from source to target file.
    
    Args:
        source_path: Path to source CSV file
        target_path: Path to target CSV file
        output_path: Optional output path (defaults to overwriting target)
        dry_run: If True, preview changes without saving
        create_backup_flag: If True, create backup before modifying target
        
    Returns:
        MigrationStats object with operation statistics
        
    Raises:
        ValueError: If validation fails or processing errors occur
    """
    stats = MigrationStats()
    
    # Validate files exist
    validate_file_exists(source_path, "Source")
    validate_file_exists(target_path, "Target")
    
    # Load files
    logger.info("-" * 70)
    source_headers, source_records = load_csv_file(source_path, "source file")
    target_headers, target_records = load_csv_file(target_path, "target file")
    
    # Find Transaction Reference columns
    logger.info("-" * 70)
    txn_ref_col_source = find_transaction_ref_column(source_headers)
    txn_ref_col_target = find_transaction_ref_column(target_headers)
    
    if not txn_ref_col_source:
        raise ValueError(
            f"Could not find Transaction Reference column in source file. "
            f"Available columns: {source_headers}"
        )
    
    if not txn_ref_col_target:
        raise ValueError(
            f"Could not find Transaction Reference column in target file. "
            f"Available columns: {target_headers}"
        )
    
    logger.info(f"Source Transaction Ref column: '{txn_ref_col_source}'")
    logger.info(f"Target Transaction Ref column: '{txn_ref_col_target}'")
    
    # Perform migration
    logger.info("-" * 70)
    logger.info("Starting data migration...")
    
    try:
        result_records = migrate_data(
            source_headers=source_headers,
            source_records=source_records,
            target_headers=target_headers,
            target_records=target_records,
            column_mapping=COLUMN_MAPPING,
            txn_ref_col_source=txn_ref_col_source,
            txn_ref_col_target=txn_ref_col_target,
            stats=stats
        )
    except Exception as e:
        stats.errors.append(str(e))
        raise
    
    # Save results
    if not dry_run:
        output_file = output_path if output_path else target_path
        
        # Create backup if modifying target file
        if output_file == target_path and create_backup_flag:
            create_backup(target_path)
        
        logger.info(f"Writing results to: {output_file.name}")
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=target_headers)
            writer.writeheader()
            writer.writerows(result_records)
        logger.info("Migration completed successfully")
    else:
        logger.info("DRY RUN - No files were modified")
        # Show sample of changes
        logger.info("\nSample of migrated data (first 3 matched records):")
        logger.info("-" * 70)
        
        sample_count = 0
        for row in result_records:
            txn_ref = row.get(txn_ref_col_target, '')
            if txn_ref and txn_ref.strip():
                logger.info(f"Transaction Ref: {txn_ref}")
                for tgt_col in COLUMN_MAPPING.values():
                    if tgt_col in target_headers:
                        logger.info(f"  {tgt_col}: {row.get(tgt_col, '')}")
                sample_count += 1
                if sample_count >= 3:
                    break
    
    return stats


def process_batch_migration(
    source_dir: Path,
    target_dir: Path,
    output_dir: Optional[Path] = None,
    dry_run: bool = False,
    create_backup_flag: bool = True
) -> BatchMigrationStats:
    """Process batch migration for all CSV files in directories.
    
    Args:
        source_dir: Directory containing source CSV files
        target_dir: Directory containing target CSV files
        output_dir: Optional output directory (defaults to target_dir)
        dry_run: If True, preview changes without saving
        create_backup_flag: If True, create backups before modifying targets
        
    Returns:
        BatchMigrationStats object with operation statistics
    """
    batch_stats = BatchMigrationStats()
    
    # Find all CSV files in source directory
    try:
        source_files = find_csv_files_in_directory(source_dir)
    except Exception as e:
        batch_stats.errors.append(f"Failed to read source directory: {e}")
        return batch_stats
    
    if not source_files:
        logger.warning("No CSV files found in source directory")
        return batch_stats
    
    # Process each source file
    for source_file in source_files:
        batch_stats.files_processed += 1
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"Processing file {batch_stats.files_processed}/{len(source_files)}: {source_file.name}")
        logger.info("=" * 70)
        
        # Find matching target file
        target_file = match_target_file(source_file, target_dir)
        
        if not target_file:
            error_msg = f"No matching target file found for {source_file.name}"
            logger.error(error_msg)
            stats = MigrationStats()
            stats.errors.append(error_msg)
            batch_stats.file_stats.append((source_file.name, stats))
            batch_stats.files_failed += 1
            batch_stats.errors.append(error_msg)
            continue
        
        # Determine output path
        if output_dir:
            output_file = output_dir / source_file.name
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_file = target_file
        
        # Process migration for this file pair
        try:
            stats = process_single_migration(
                source_path=source_file,
                target_path=target_file,
                output_path=output_file,
                dry_run=dry_run,
                create_backup_flag=create_backup_flag
            )
            
            if stats.errors:
                batch_stats.files_failed += 1
            else:
                batch_stats.files_succeeded += 1
                batch_stats.total_records_migrated += stats.matched_records
            
            batch_stats.file_stats.append((source_file.name, stats))
            
        except Exception as e:
            error_msg = f"Failed to process {source_file.name}: {e}"
            logger.error(error_msg)
            stats = MigrationStats()
            stats.errors.append(str(e))
            batch_stats.file_stats.append((source_file.name, stats))
            batch_stats.files_failed += 1
            batch_stats.errors.append(error_msg)
    
    return batch_stats


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Migrate error and correction data between CSV template files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Column Mapping (source -> target):
  Error (Y/N)                         -> Error
  Correction                          -> Correction
  Correction Field (Select Dropdown)  -> Correction Field
  Checked                             -> Agree With Correction
  Checked Correction                  -> Suggested Correction
  Checked Correction Field            -> Suggested Correction Field

Batch Processing Examples:
  # Preview migration for all files (dry run)
  python scripts/migrate_error_corrections.py --source-dir old_templates/ --target-dir new_templates/ --dry-run

  # Perform batch migration (overwrites target files, creates backups)
  python scripts/migrate_error_corrections.py --source-dir old_templates/ --target-dir new_templates/

  # Save results to separate output directory
  python scripts/migrate_error_corrections.py --source-dir old/ --target-dir new/ --output-dir migrated/

Single File Examples:
  # Preview single file migration
  python scripts/migrate_error_corrections.py --source old.csv --target new.csv --dry-run

  # Perform single file migration
  python scripts/migrate_error_corrections.py --source old.csv --target new.csv
        """
    )
    
    # Batch processing (directory) arguments
    parser.add_argument(
        '--source-dir',
        type=str,
        help='Directory containing source CSV files (old templates) - for batch processing'
    )
    
    parser.add_argument(
        '--target-dir',
        type=str,
        help='Directory containing target CSV files (new templates) - for batch processing'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Output directory for migrated files (batch mode, default: overwrites target files)'
    )
    
    # Single file processing arguments
    parser.add_argument(
        '-s', '--source',
        type=str,
        help='Path to source CSV file (old template) - for single file processing'
    )
    
    parser.add_argument(
        '-t', '--target',
        type=str,
        help='Path to target CSV file (new template) - for single file processing'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path (single file mode, default: overwrites target file)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup of target file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser


def main() -> int:
    """
    Main entry point for the script.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate arguments
    is_batch_mode = bool(args.source_dir and args.target_dir)
    is_single_mode = bool(args.source and args.target)
    
    if not is_batch_mode and not is_single_mode:
        logger.error("Error: Must specify either --source-dir/--target-dir (batch mode) or --source/--target (single file mode)")
        return 1
    
    if is_batch_mode and is_single_mode:
        logger.error("Error: Cannot use both batch mode and single file mode arguments together")
        return 1
    
    if args.output_dir and not is_batch_mode:
        logger.error("Error: --output-dir can only be used with --source-dir/--target-dir (batch mode)")
        return 1
    
    if args.output and not is_single_mode:
        logger.error("Error: --output can only be used with --source/--target (single file mode)")
        return 1
    
    try:
        logger.info("=" * 70)
        logger.info("ERROR/CORRECTION DATA MIGRATION")
        logger.info("=" * 70)
        logger.info(f"Mode: {'BATCH' if is_batch_mode else 'SINGLE FILE'} | {'DRY RUN' if args.dry_run else 'LIVE'}")
        logger.info(f"Backup: {'No' if args.no_backup else 'Yes'}")
        
        if is_batch_mode:
            # Batch processing mode
            source_dir = Path(args.source_dir)
            target_dir = Path(args.target_dir)
            output_dir = Path(args.output_dir) if args.output_dir else None
            
            logger.info(f"Source directory: {source_dir}")
            logger.info(f"Target directory: {target_dir}")
            if output_dir:
                logger.info(f"Output directory: {output_dir}")
            else:
                logger.info("Output: (will overwrite target files)")
            
            # Process batch
            batch_stats = process_batch_migration(
                source_dir=source_dir,
                target_dir=target_dir,
                output_dir=output_dir,
                dry_run=args.dry_run,
                create_backup_flag=not args.no_backup
            )
            
            # Print batch summary
            print_batch_summary(batch_stats, dry_run=args.dry_run)
            
            if batch_stats.files_failed > 0:
                return 1
            
        else:
            # Single file processing mode
            source_path = Path(args.source)
            target_path = Path(args.target)
            output_path = Path(args.output) if args.output else None
            
            logger.info(f"Source file: {source_path}")
            logger.info(f"Target file: {target_path}")
            if output_path:
                logger.info(f"Output file: {output_path}")
            else:
                logger.info("Output: (will overwrite target)")
            
            # Process single migration
            stats = process_single_migration(
                source_path=source_path,
                target_path=target_path,
                output_path=output_path,
                dry_run=args.dry_run,
                create_backup_flag=not args.no_backup
            )
            
            # Print summary
            logger.info("")
            stats.print_summary(dry_run=args.dry_run)
            
            if stats.errors:
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
