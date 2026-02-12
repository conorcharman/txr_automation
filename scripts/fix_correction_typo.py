#!/usr/bin/env python3
"""
Fix Correction Typo
===================

Searches through CSV files and replaces "Corretion" with "Correction".

This utility script processes a batch of CSV files, searching for the
misspelled word "Corretion" and replacing it with the correct spelling
"Correction". It preserves file encoding and provides a dry-run mode
for previewing changes.

Usage:
    python scripts/fix_correction_typo.py --directory data/output
    python scripts/fix_correction_typo.py --directory . --pattern "**/*.csv" --dry-run
"""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def find_csv_files(directory: Path, pattern: str = "*.csv") -> List[Path]:
    """
    Find all CSV files matching the pattern in the directory.

    Args:
        directory: Directory to search in
        pattern: Glob pattern for matching files (default: "*.csv")

    Returns:
        List of Path objects for matching CSV files

    Example:
        >>> files = find_csv_files(Path("data"), "**/*.csv")
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")
    
    csv_files = list(directory.glob(pattern))
    logger.info(f"Found {len(csv_files)} CSV file(s) matching pattern '{pattern}'")
    
    return csv_files


def fix_typo_in_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, int]:
    """
    Replace "Corretion" with "Correction" in a CSV file.

    Reads the entire file content, performs the replacement,
    and writes it back. Preserves UTF-8 encoding.

    Args:
        file_path: Path to the CSV file to process
        dry_run: If True, only report changes without modifying files

    Returns:
        Tuple of (changes_made: bool, occurrences: int)

    Raises:
        IOError: If file cannot be read or written
    """
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            content = f.read()
        
        # Count occurrences
        occurrences = content.count('Corretion')
        
        if occurrences == 0:
            return False, 0
        
        # Perform replacement
        corrected_content = content.replace('Corretion', 'Correction')
        
        if dry_run:
            logger.info(
                f"[DRY RUN] Would fix {occurrences} occurrence(s) in: {file_path.name}"
            )
            return True, occurrences
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(corrected_content)
        
        logger.info(f"Fixed {occurrences} occurrence(s) in: {file_path.name}")
        return True, occurrences
        
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error in {file_path.name}: {e}")
        raise
    except IOError as e:
        logger.error(f"IO error processing {file_path.name}: {e}")
        raise


def process_batch(
    directory: Path,
    pattern: str = "*.csv",
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Process a batch of CSV files to fix the typo.

    Args:
        directory: Directory containing CSV files
        pattern: Glob pattern for matching files
        dry_run: If True, preview changes without modifying files

    Returns:
        Tuple of (files_modified: int, total_occurrences: int)
    """
    csv_files = find_csv_files(directory, pattern)
    
    if not csv_files:
        logger.warning("No CSV files found to process")
        return 0, 0
    
    files_modified = 0
    total_occurrences = 0
    
    for file_path in csv_files:
        try:
            changes_made, occurrences = fix_typo_in_file(file_path, dry_run)
            if changes_made:
                files_modified += 1
                total_occurrences += occurrences
        except Exception as e:
            logger.error(f"Failed to process {file_path.name}: {e}")
            continue
    
    return files_modified, total_occurrences


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Fix 'Corretion' typo in CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fix typo in all CSV files in current directory
  python scripts/fix_correction_typo.py --directory .

  # Search recursively in subdirectories (dry run)
  python scripts/fix_correction_typo.py --directory data/output --pattern "**/*.csv" --dry-run

  # Process specific directory with verbose output
  python scripts/fix_correction_typo.py -d data/test -v
        """
    )
    
    parser.add_argument(
        '-d', '--directory',
        type=str,
        required=True,
        help='Directory containing CSV files to process'
    )
    
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        default='*.csv',
        help='Glob pattern for matching CSV files (default: *.csv)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
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
    
    # Convert directory to Path
    directory = Path(args.directory)
    
    try:
        # Display configuration
        mode = "DRY RUN" if args.dry_run else "LIVE"
        logger.info(f"Starting typo fix in {mode} mode")
        logger.info(f"Directory: {directory.absolute()}")
        logger.info(f"Pattern: {args.pattern}")
        logger.info("-" * 60)
        
        # Process files
        files_modified, total_occurrences = process_batch(
            directory=directory,
            pattern=args.pattern,
            dry_run=args.dry_run
        )
        
        # Display summary
        logger.info("-" * 60)
        if args.dry_run:
            logger.info(
                f"Summary: Would fix {total_occurrences} occurrence(s) "
                f"in {files_modified} file(s)"
            )
        else:
            logger.info(
                f"Summary: Fixed {total_occurrences} occurrence(s) "
                f"in {files_modified} file(s)"
            )
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
