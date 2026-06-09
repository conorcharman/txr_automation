#!/usr/bin/env python3
"""
CSV Extract Collation Tool
==========================

Merges split CSV extract files back into single files for validation.

When the SQL extract generator splits large datasets into multiple batches
(e.g., 7_37_Extract1.csv, 7_37_Extract2.csv), this tool collates them back
into a single file ready for the validation scripts.

Features:
- Auto-discovers split files by incident code pattern
- Merges while removing duplicate headers
- Validates row counts against expected totals
- Supports batch mode for multiple incidents
- Integrates with YAML configuration

Author: Transaction Reporting Team
Date: January 2026
Version: 1.0

Usage:
    # Single incident
    collate-csv-extracts --input-dir data/csv --incident 7_37 --output data/collated/7_37.csv

    # Batch mode with config
    collate-csv-extracts --config config/local/collate_extracts.yaml

    # Batch mode with all incidents
    collate-csv-extracts --input-dir data/csv --output-dir data/collated --all-incidents
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from core import ConfigManager, create_logger
from core.data.incident_codes import INCIDENT_CODE_MATRIX, get_all_incident_codes


@dataclass
class CollationStats:
    """Statistics for CSV collation operations."""

    incident_code: str = ""
    input_files: int = 0
    total_rows: int = 0
    header_rows_skipped: int = 0
    output_file: str = ""
    success: bool = False
    error_message: str = ""
    files_deleted: int = 0
    source_files: List[Path] = field(default_factory=list)


@dataclass
class CollationResult:
    """Result of a collation operation."""

    incidents_processed: int = 0
    incidents_successful: int = 0
    incidents_failed: int = 0
    incidents_skipped: int = 0
    stats: List[CollationStats] = field(default_factory=list)

    def print_summary(self, logger=None) -> None:
        """Print summary of collation results."""
        summary = (
            f"\nCollation Summary:\n"
            f"  Incidents processed: {self.incidents_processed}\n"
            f"  Successful:          {self.incidents_successful}\n"
            f"  Failed:              {self.incidents_failed}\n"
            f"  Skipped (no files):  {self.incidents_skipped}\n"
        )
        if logger:
            logger.info(summary)
        else:
            print(summary)


class CSVExtractCollator:
    """
    Collates split CSV extract files into single files.

    Handles the merging of files like:
        7_37_Extract1.csv, 7_37_Extract2.csv, 7_37_Extract3.csv
    Into:
        7_37.csv
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        logger=None,
        dry_run: bool = False,
        force: bool = False,
        delete_originals: bool = False,
        reconcile_existing: bool = False,
        fiscal_year: Optional[str] = None,
        quarter: Optional[str] = None,
        has_header: bool = True,
    ):
        """
        Initialize the CSV collator.

        Args:
            input_dir: Directory containing split CSV files
            output_dir: Directory for collated output (defaults to input_dir)
            logger: StructuredLogger instance
            dry_run: Preview mode - don't write files
            force: Overwrite existing output files
            delete_originals: Delete original split files after successful merge
            reconcile_existing: If output exists, safely delete stale split files
                after compatibility checks
            fiscal_year: Fiscal year for filename pattern (e.g., 'FY26')
            quarter: Quarter for filename pattern (e.g., 'Q1')
            has_header: When True (default), treat the first row of each CSV as a
                header; skip and deduplicate it across files.  Set to False for
                headerless SQL-extract CSVs produced by AS/400 System i Data
                Transfer — every row is data and must not be skipped.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir) if output_dir else input_path

        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_path}")

        # Check if a 'csv' subdirectory exists
        csv_subdir = input_path / "csv"
        has_csv_subdir = csv_subdir.exists() and csv_subdir.is_dir()

        # Resolve input directory
        if has_csv_subdir:
            self.input_dir = csv_subdir
            if logger:
                logger.debug(f"Using CSV subdirectory for input: {self.input_dir}")
        else:
            self.input_dir = input_path

        # Resolve output directory
        # If output and input point to the same directory and we found a csv subdirectory, use it for output too
        if output_path == input_path and has_csv_subdir:
            self.output_dir = csv_subdir
            if logger:
                logger.debug(f"Using CSV subdirectory for output: {self.output_dir}")
        else:
            self.output_dir = output_path

        self.logger = logger
        self.dry_run = dry_run
        self.force = force
        self.delete_originals = delete_originals
        self.reconcile_existing = reconcile_existing
        self.fiscal_year = fiscal_year
        self.quarter = quarter
        self.has_header = has_header

    @staticmethod
    def _canonical_header_token(token: str) -> str:
        """Normalize a single header token for resilient comparisons."""
        clean = (token or "").replace("\ufeff", "").strip().lower()
        return " ".join(clean.split())

    @classmethod
    def _canonicalize_header(cls, header_row: List[str]) -> List[str]:
        """Normalize a CSV header row for compatibility checks."""
        return [cls._canonical_header_token(col) for col in header_row]

    def _headers_compatible(self, expected: List[str], observed: List[str]) -> bool:
        """Return True when two headers are equivalent after normalization."""
        if len(expected) != len(observed):
            return False
        return self._canonicalize_header(expected) == self._canonicalize_header(
            observed
        )

    def _read_header(self, file_path: Path) -> List[str]:
        """Read and return the first CSV row (header) as a list of strings."""
        with open(file_path, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            return next(reader, [])

    def _reconcile_existing_output(
        self, out_path: Path, input_files: List[Path], stats: CollationStats
    ) -> bool:
        """Safely remove stale split files when a collated output already exists."""
        if not self.reconcile_existing or not self.delete_originals:
            return False

        if self.dry_run:
            if self.logger:
                self.logger.info(
                    f"  [DRY RUN] Would reconcile existing output and delete {len(input_files)} split files"
                )
            return True

        try:
            output_mtime = out_path.stat().st_mtime
            if any(p.stat().st_mtime > output_mtime for p in input_files):
                if self.logger:
                    self.logger.warning(
                        "  Reconcile skipped: one or more split files are newer than output"
                    )
                return False

            output_header = self._read_header(out_path)
            if not output_header:
                if self.logger:
                    self.logger.warning(
                        "  Reconcile skipped: output file has no header"
                    )
                return False

            for src in input_files:
                src_header = self._read_header(src)
                if not self._headers_compatible(output_header, src_header):
                    if self.logger:
                        self.logger.warning(
                            f"  Reconcile skipped: header mismatch between {out_path.name} and {src.name}"
                        )
                    return False

            self._delete_source_files(stats, input_files)
            if self.logger:
                self.logger.info(
                    f"  ✓ Reconciled existing output: deleted {stats.files_deleted} split file(s)"
                )
            return True
        except OSError as exc:
            if self.logger:
                self.logger.warning(f"  Reconcile skipped due to file error: {exc}")
            return False

    def _build_file_pattern(self, incident_code: str) -> str:
        """
        Build the glob pattern for finding split extract files.

        Supports patterns like:
        - 7_37_Extract*.csv
        - FY26_Q1_7_37_Extract*.csv
        - 7_37_FY26_Q1_Extract*.csv
        """
        if self.fiscal_year and self.quarter:
            # Try multiple patterns
            return f"*{incident_code}*Extract*.csv"
        return f"{incident_code}_Extract*.csv"

    def _find_extract_files(self, incident_code: str) -> List[Path]:
        """
        Find all split extract files for an incident code.

        Returns files sorted by extract number.
        """
        pattern = self._build_file_pattern(incident_code)
        candidate_files = list(self.input_dir.glob(pattern))
        incident_re = re.compile(
            rf"(?<!\d){re.escape(incident_code)}(?!\d)", re.IGNORECASE
        )
        split_re = re.compile(r"extract\d+", re.IGNORECASE)

        # Filter out loosely matched incidents (e.g. 7_6 matching 7_66)
        # and ignore collated outputs that only contain "extract" without
        # an extract batch number.
        files = [
            p
            for p in candidate_files
            if incident_re.search(p.stem) and split_re.search(p.stem)
        ]

        # Also check for single file (no split)
        if not files:
            # Try various single-file patterns
            single_patterns = [
                f"{incident_code}.csv",
                f"*{incident_code}.csv",
            ]
            if self.fiscal_year and self.quarter:
                single_patterns.extend(
                    [
                        f"{self.fiscal_year}_{self.quarter}_{incident_code}.csv",
                        f"{incident_code}_{self.fiscal_year}_{self.quarter}.csv",
                    ]
                )

            for sp in single_patterns:
                matches = list(self.input_dir.glob(sp))
                if matches:
                    files = matches[:1]  # Take first match
                    break

        # Sort by extract number
        def extract_number(path: Path) -> int:
            """Extract the number from Extract{N} in filename."""
            name = path.stem
            if "_Extract" in name:
                try:
                    num_part = name.split("_Extract")[-1]
                    return int(num_part.split("_")[0])
                except (ValueError, IndexError):
                    return 0
            return 0

        return sorted(files, key=extract_number)

    def _build_output_filename(self, incident_code: str) -> str:
        """Build the output filename for a collated file."""
        if self.fiscal_year and self.quarter:
            return f"{incident_code}_{self.fiscal_year}_{self.quarter}_extract.csv"
        return f"{incident_code}_extract.csv"

    def collate_incident(
        self, incident_code: str, output_file: Optional[Path] = None
    ) -> CollationStats:
        """
        Collate all extract files for a single incident code.

        Args:
            incident_code: Incident code (e.g., '7_37')
            output_file: Optional specific output path

        Returns:
            CollationStats with results
        """
        stats = CollationStats(incident_code=incident_code)

        # Find input files
        input_files = self._find_extract_files(incident_code)
        stats.input_files = len(input_files)

        if not input_files:
            stats.error_message = "No extract files found"
            if self.logger:
                self.logger.warning(f"  No files found for incident {incident_code}")
            return stats

        # Determine output path
        if output_file:
            out_path = Path(output_file)
        else:
            out_path = self.output_dir / self._build_output_filename(incident_code)

        stats.output_file = str(out_path)

        # Store source files for potential deletion/reconciliation.
        stats.source_files = input_files.copy()

        # Check if output exists
        if out_path.exists() and not self.force:
            stats.error_message = "Output file exists (use --force to overwrite)"
            reconciled = self._reconcile_existing_output(out_path, input_files, stats)
            if reconciled:
                stats.success = True
                stats.error_message = ""
            if self.logger:
                if reconciled:
                    self.logger.info(f"  Output exists: {out_path.name} (reconciled)")
                else:
                    self.logger.warning(f"  Output exists: {out_path.name} (skipping)")
            return stats

        # Single file - just copy/rename
        if len(input_files) == 1:
            if self.dry_run:
                if self.logger:
                    self.logger.info(
                        f"  [DRY RUN] Would copy: {input_files[0].name} → {out_path.name}"
                    )
                    if self.delete_originals:
                        self.logger.info(
                            f"  [DRY RUN] Would delete: {input_files[0].name}"
                        )
                stats.success = True
                stats.total_rows = self._count_rows(input_files[0])
                return stats

            # Copy single file
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with open(input_files[0], "r", encoding="utf-8-sig", newline="") as src:
                content = src.read()
            with open(out_path, "w", encoding="utf-8", newline="") as dst:
                dst.write(content)

            stats.total_rows = self._count_rows(out_path)
            stats.success = True

            # Delete original if requested
            if self.delete_originals:
                self._delete_source_files(stats, input_files)

            if self.logger:
                self.logger.info(
                    f"  ✓ Copied: {input_files[0].name} → {out_path.name} ({stats.total_rows} rows)"
                )

            return stats

        # Multiple files - merge
        if self.dry_run:
            if self.logger:
                self.logger.info(
                    f"  [DRY RUN] Would merge {len(input_files)} files → {out_path.name}"
                )
                for f in input_files:
                    self.logger.info(f"    - {f.name}")
                if self.delete_originals:
                    self.logger.info(
                        f"  [DRY RUN] Would delete {len(input_files)} original files"
                    )

            # Count rows for preview
            total = 0
            for i, f in enumerate(input_files):
                rows = self._count_rows(f)
                if self.has_header and i > 0:
                    rows -= 1  # Subtract duplicate header row
                total += rows

            stats.total_rows = total
            stats.header_rows_skipped = (len(input_files) - 1) if self.has_header else 0
            stats.success = True
            return stats

        # Perform merge
        self.output_dir.mkdir(parents=True, exist_ok=True)

        total_rows = 0
        headers_skipped = 0
        header = None

        with open(out_path, "w", encoding="utf-8", newline="") as out_file:
            writer = None

            for i, input_file in enumerate(input_files):
                with open(input_file, "r", encoding="utf-8-sig", newline="") as in_file:
                    reader = csv.reader(in_file)

                    for row_idx, row in enumerate(reader):
                        if self.has_header and row_idx == 0:
                            if i == 0:
                                # First file - write header
                                header = row
                                writer = csv.writer(out_file)
                                writer.writerow(row)
                            else:
                                # Subsequent files - skip duplicate header
                                headers_skipped += 1
                                # Validate header matches
                                if not self._headers_compatible(header or [], row):
                                    if self.logger:
                                        mismatch_details = []
                                        if len(row) != len(header or []):
                                            mismatch_details.append(
                                                f"column count differs ({len(row)} vs {len(header or [])})"
                                            )
                                        for idx, (left, right) in enumerate(
                                            zip(header or [], row)
                                        ):
                                            if self._canonical_header_token(
                                                left
                                            ) != self._canonical_header_token(right):
                                                mismatch_details.append(
                                                    f"col[{idx}] '{left}' != '{right}'"
                                                )
                                            if len(mismatch_details) >= 3:
                                                break
                                        details = (
                                            "; ".join(mismatch_details)
                                            if mismatch_details
                                            else "schema differs"
                                        )
                                        self.logger.warning(
                                            f"  ⚠ Header mismatch in {input_file.name}: {details}"
                                        )
                        else:
                            if writer is None:
                                writer = csv.writer(out_file)
                            writer.writerow(row)
                            total_rows += 1

        stats.total_rows = total_rows
        stats.header_rows_skipped = headers_skipped
        stats.success = True

        # Delete original files if requested
        if self.delete_originals:
            self._delete_source_files(stats, input_files)

        if self.logger:
            delete_msg = (
                f", {stats.files_deleted} files deleted"
                if stats.files_deleted > 0
                else ""
            )
            self.logger.info(
                f"  ✓ Merged {len(input_files)} files → {out_path.name} "
                f"({total_rows} data rows, {headers_skipped} headers skipped{delete_msg})"
            )

        return stats

    def _delete_source_files(self, stats: CollationStats, files: List[Path]) -> None:
        """Delete source files after successful collation."""
        for f in files:
            try:
                f.unlink()
                stats.files_deleted += 1
                if self.logger:
                    self.logger.debug(f"    Deleted: {f.name}")
            except OSError as e:
                if self.logger:
                    self.logger.warning(f"    Failed to delete {f.name}: {e}")

    def _count_rows(self, file_path: Path) -> int:
        """Count rows in a CSV file (excluding header if has_header=True)."""
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            return sum(1 for _ in f) - (1 if self.has_header else 0)

    def collate_all(self, incident_codes: List[str]) -> CollationResult:
        """
        Collate extract files for multiple incident codes.

        Args:
            incident_codes: List of incident codes to process

        Returns:
            CollationResult with summary statistics
        """
        result = CollationResult()

        for incident_code in incident_codes:
            if self.logger:
                self.logger.info(f"Processing incident: {incident_code}")

            stats = self.collate_incident(incident_code)
            result.stats.append(stats)
            result.incidents_processed += 1

            if stats.input_files == 0:
                result.incidents_skipped += 1
            elif stats.success:
                result.incidents_successful += 1
            else:
                result.incidents_failed += 1

        return result


def create_argument_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="CSV Extract Collation Tool - Merge split extract files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single incident with explicit output
  collate-csv-extracts --input-dir data/csv --incident 7_37 --output data/collated/7_37.csv

  # Multiple incidents
  collate-csv-extracts --input-dir data/csv --output-dir data/collated --incidents 7_37,7_39,16_21

  # All known incidents
  collate-csv-extracts --input-dir data/csv --output-dir data/collated --all-incidents

  # Using config file
  collate-csv-extracts --config config/local/collate_extracts.yaml

  # Dry run preview
  collate-csv-extracts --input-dir data/csv --all-incidents --dry-run
        """,
    )

    parser.add_argument("--config", type=str, help="Path to YAML configuration file")

    parser.add_argument(
        "--input-dir", type=str, help="Directory containing split CSV extract files"
    )

    parser.add_argument(
        "--output-dir", type=str, help="Directory for collated output files"
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Specific output file path (single incident mode only)",
    )

    parser.add_argument(
        "--incident", type=str, help="Single incident code to collate (e.g., 7_37)"
    )

    parser.add_argument(
        "--incidents", type=str, help="Comma-separated list of incident codes"
    )

    parser.add_argument(
        "--all-incidents",
        action="store_true",
        help="Process all known incident codes from INCIDENT_CODE_MATRIX",
    )

    parser.add_argument(
        "--fiscal-year", type=str, help="Fiscal year for filename patterns (e.g., FY26)"
    )

    parser.add_argument(
        "--quarter", type=str, help="Quarter for filename patterns (e.g., Q1)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - show what would be done without writing files",
    )

    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing output files"
    )

    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete original split files after successful merge",
    )

    parser.add_argument(
        "--reconcile-existing",
        action="store_true",
        help="When output exists, safely reconcile by deleting stale split files",
    )

    parser.add_argument(
        "--no-header",
        action="store_false",
        dest="has_header",
        default=True,
        help=(
            "Treat extract files as headerless (no column-name row). "
            "Use for SQL extract CSVs produced by AS/400 System i Data Transfer."
        ),
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument(
        "--gui-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Default config file location
    default_config_path = Path(
        "config/local/accuracy_testing/collate_csv_extracts.yaml"
    )

    # Load config - automatically use default if it exists
    config = {}
    config_path = None

    if args.config:
        # Explicit config file specified
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Config file not found: {args.config}")
            return 1
    elif default_config_path.exists():
        # Auto-load default config
        config_path = default_config_path

    if config_path:
        config = load_config(str(config_path))
        print(f"Loading default configuration from {config_path}...")

    # Merge config with command line args (CLI takes precedence)
    paths = config.get("paths", {})
    processing = config.get("processing", {})
    testing_period = config.get("testing_period", {})

    input_dir = args.input_dir or paths.get("input_dir")
    output_dir = args.output_dir or paths.get("output_dir")
    fiscal_year = args.fiscal_year or testing_period.get("fiscal_year")
    quarter = args.quarter or testing_period.get("quarter")
    dry_run = args.dry_run or processing.get("dry_run", False)
    force = args.force or processing.get("force", False)
    delete_originals = args.delete_originals or processing.get(
        "delete_originals", False
    )
    reconcile_existing = args.reconcile_existing or processing.get(
        "reconcile_existing", False
    )
    # CLI --no-header flag stores False in args.has_header; config key has_header defaults to True.
    # CLI wins when it was explicitly set (args.has_header is False); otherwise defer to config.
    has_header: bool = args.has_header and processing.get("has_header", True)

    # Determine incident codes
    incidents = []
    if args.incident:
        incidents = [args.incident]
    elif args.incidents:
        incidents = [i.strip() for i in args.incidents.split(",")]
    elif args.all_incidents:
        incidents = sorted(get_all_incident_codes())
    elif "incidents" in config:
        incidents = config["incidents"]

    # Validate required parameters
    if not input_dir:
        print("Error: --input-dir or config paths.input_dir required")
        return 1

    if not incidents:
        print(
            "Error: Specify --incident, --incidents, --all-incidents, or config incidents list"
        )
        return 1

    # Default output_dir to input_dir if not specified
    if not output_dir:
        output_dir = input_dir

    # Setup logging
    log_dir = paths.get("log_output", str(output_dir))
    logger = create_logger("collate_csv_extracts", log_dir, args.log_level)

    # Print startup info
    logger.info("=" * 70)
    logger.info("CSV Extract Collation Tool v1.0")
    logger.info("=" * 70)
    logger.info(f"Input directory:  {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Incidents:        {len(incidents)}")
    if fiscal_year:
        logger.info(f"Fiscal year:      {fiscal_year}")
    if quarter:
        logger.info(f"Quarter:          {quarter}")
    if dry_run:
        logger.info("Mode:             DRY RUN (preview only)")
    if force:
        logger.info("Force overwrite:  ENABLED")
    if delete_originals:
        logger.info("Delete originals: ENABLED")
    if reconcile_existing:
        logger.info("Reconcile existing: ENABLED")
    if not has_header:
        logger.info("Header mode:        HEADERLESS (no column-name row)")
    logger.info("-" * 70)

    # Create collator
    try:
        collator = CSVExtractCollator(
            input_dir=Path(input_dir),
            output_dir=Path(output_dir) if output_dir else None,
            logger=logger,
            dry_run=dry_run,
            force=force,
            delete_originals=delete_originals,
            reconcile_existing=reconcile_existing,
            fiscal_year=fiscal_year,
            quarter=quarter,
            has_header=has_header,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Log the actual directories being used (after collator resolves csv subdirectory)
    if str(collator.input_dir) != input_dir:
        logger.info(f"Resolved input directory:  {collator.input_dir}")
    if str(collator.output_dir) != output_dir:
        logger.info(f"Resolved output directory: {collator.output_dir}")

    # Single incident with specific output file
    if args.incident and args.output:
        logger.info(f"Processing single incident: {args.incident}")
        stats = collator.collate_incident(args.incident, Path(args.output))

        if stats.success:
            logger.info(f"✓ Collation complete: {stats.total_rows} rows")
            return 0
        else:
            logger.error(f"✗ Collation failed: {stats.error_message}")
            return 1

    # Batch mode
    logger.info(f"Processing {len(incidents)} incidents...")
    result = collator.collate_all(incidents)

    # Print summary
    logger.info("=" * 70)
    result.print_summary(logger)

    # Detailed stats
    if args.verbose or args.dry_run:
        logger.info("\nDetailed Results:")
        for stats in result.stats:
            status = "✓" if stats.success else "✗" if stats.error_message else "○"
            if stats.input_files == 0:
                logger.info(f"  {status} {stats.incident_code}: No files found")
            elif stats.success:
                logger.info(
                    f"  {status} {stats.incident_code}: {stats.input_files} file(s) → "
                    f"{stats.total_rows} rows"
                )
            else:
                logger.info(f"  {status} {stats.incident_code}: {stats.error_message}")

    return 0 if result.incidents_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
