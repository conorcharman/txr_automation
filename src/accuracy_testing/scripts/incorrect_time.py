#!/usr/bin/env python3
"""
Incorrect Time Validation Script
==================================

Validates child transaction trade datetimes against parent block trade
datetimes for Incident Code 7_30 (IncorrectTime).

This script:
1. Reads the CSV extract from the IncorrectTime SQL query
2. Compares each child's trade datetime against its parent's at second precision
3. Flags mismatches with error = 'Y' and records the human-readable time gap
4. Outputs all input records with bulk_ref, time_difference, and error columns

Microseconds are ignored in the comparison. A child whose parent has no
TXNREPESMA row (empty parent_datetime) is flagged with
time_difference = 'parent datetime missing'.

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.incorrect_time \\
        --config config/local/accuracy_testing/incorrect_time.yaml

    # With direct CLI arguments
    python -m src.accuracy_testing.scripts.incorrect_time \\
        input.csv output.csv --log-level DEBUG

Input CSV columns (exact order from SQL extract):
    - child_ref
    - child_datetime
    - parent_ref
    - parent_datetime

Output CSV columns (all input columns + 3 appended):
    - child_ref
    - child_datetime
    - parent_ref
    - parent_datetime
    - bulk_ref
    - time_difference   (empty on match; human-readable gap or 'parent datetime missing' on error)
    - error             (N = datetimes match to the second, Y = mismatch or missing)
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.incorrect_time_record import IncorrectTimeRecord
from src.accuracy_testing.processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
)
from src.accuracy_testing.validators.incorrect_time_validator import (
    IncorrectTimeValidator,
)

try:
    from core import create_logger, safe_open_csv  # type: ignore[assignment]
except ImportError:
    import logging

    def create_logger(name, log_dir=None, log_level="INFO"):  # type: ignore[assignment]
        _logger = logging.getLogger(name)
        _logger.setLevel(getattr(logging, log_level))
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            _logger.addHandler(handler)
        return _logger

    def safe_open_csv(file_path, mode, newline=""):  # type: ignore[assignment]
        return open(file_path, mode, encoding="utf-8", newline=newline), "utf-8"


class IncorrectTimeStats:
    """Statistics for an incorrect time validation run."""

    def __init__(self) -> None:
        self.total_input_records: int = 0
        self.output_records: int = 0
        self.match_records: int = 0
        self.error_records: int = 0
        self.missing_parent: int = 0
        self.parse_errors: int = 0
        self.processing_errors: int = 0

    def print_summary(self, logger=None) -> None:
        """
        Print a processing summary.

        Args:
            logger: Optional logger instance
        """
        lines = [
            "=" * 70,
            "PROCESSING SUMMARY",
            "=" * 70,
            f"Total input records:         {self.total_input_records:>6}",
            f"Records written to output:   {self.output_records:>6}",
            f"  Matching (error = N):       {self.match_records:>6}",
            f"  Mismatching (error = Y):    {self.error_records:>6}",
            f"    of which missing parent:  {self.missing_parent:>6}",
            f"    of which parse errors:    {self.parse_errors:>6}",
            f"Processing errors:           {self.processing_errors:>6}",
            "=" * 70,
        ]
        try:
            if logger and hasattr(logger, "info"):
                for line in lines:
                    logger.info(line)
            else:
                for line in lines:
                    print(line)
        except Exception:
            for line in lines:
                print(line)


class IncorrectTimeScript:
    """Main application class for incorrect time validation."""

    # Expected column headers in the input CSV
    INPUT_COLUMNS = [
        "child_ref",
        "child_datetime",
        "parent_ref",
        "parent_datetime",
    ]

    # Output CSV column headers
    OUTPUT_COLUMNS = [
        "child_ref",
        "child_datetime",
        "parent_ref",
        "parent_datetime",
        "bulk_ref",
        "time_difference",
        "error",
    ]

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        dry_run: bool = False,
    ) -> None:
        """
        Initialise the validation script.

        Args:
            config_path: Path to YAML configuration file
            config_dict: Configuration dictionary (overrides config_path)
            dry_run: If True, preview without writing output

        Raises:
            ValueError: If neither config_path nor config_dict is provided
        """
        self.dry_run = dry_run

        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = AccuracyConfigManager.load_from_yaml(config_path)
        else:
            raise ValueError("Must provide either config_path or config_dict")

        self.path_config: AccuracyPathConfig = AccuracyConfigManager.get_path_config(
            self.config
        )
        self.proc_config: AccuracyProcessorConfig = (
            AccuracyConfigManager.get_processor_config(self.config)
        )

        self.logger = create_logger(
            name="incorrect_time",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level,
        )

        self.validator = IncorrectTimeValidator(verbose=self.proc_config.verbose)
        self.input_file = Path(self.path_config.input_file)
        self.output_file = Path(self.path_config.output_file)
        self.stats = IncorrectTimeStats()

    def _log_header(self, title: str) -> None:
        """Emit a section header."""
        if hasattr(self.logger, "log_header"):
            self.logger.log_header(title)  # type: ignore[union-attr]
        else:
            self.logger.info("=" * 70)
            self.logger.info(title)
            self.logger.info("=" * 70)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def read_input_csv(self) -> List[IncorrectTimeRecord]:
        """
        Read and parse the input CSV file into IncorrectTimeRecord objects.

        Returns:
            List of IncorrectTimeRecord objects in CSV row order

        Raises:
            FileNotFoundError: If the input file does not exist
        """
        self.logger.info(f"Reading input file: {self.input_file}")

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        records: List[IncorrectTimeRecord] = []
        f, encoding = safe_open_csv(self.input_file, "r", newline="")
        self.logger.info(f"Detected encoding: {encoding}")

        try:
            with f:
                reader = csv.reader(f)
                header = next(reader)
                self.logger.debug(f"Header: {header}")

                for row_idx, row in enumerate(reader, start=2):
                    if not any(cell.strip() for cell in row):
                        continue

                    try:
                        record = IncorrectTimeRecord.from_row(row, row_index=row_idx)
                        records.append(record)
                    except ValueError as e:
                        self.logger.error(f"Row {row_idx}: {e} — skipping")
                        self.stats.processing_errors += 1
                    except Exception as e:
                        self.logger.error(
                            f"Unexpected error on row {row_idx}: {e} — skipping"
                        )
                        self.stats.processing_errors += 1

        except Exception as e:
            self.logger.error(f"Error reading CSV: {e}", exc_info=True)
            raise

        self.logger.info(f"Read {len(records)} records successfully")
        return records

    def write_output_csv(self, records: List[IncorrectTimeRecord]) -> None:
        """
        Write validated records to the output CSV.

        All input records are written (no deduplication for this validation).

        Args:
            records: List of validated IncorrectTimeRecord objects
        """
        self.logger.info(f"Writing output file: {self.output_file}")
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.OUTPUT_COLUMNS)

                for record in records:
                    writer.writerow(
                        [
                            record.child_ref,
                            record.child_datetime,
                            record.parent_ref,
                            record.parent_datetime,
                            record.bulk_ref,
                            record.time_difference,
                            record.error,
                        ]
                    )

            self.logger.info(f"Wrote {len(records)} records to output")

        except Exception as e:
            self.logger.error(f"Error writing output CSV: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the full validation workflow."""
        start_time = datetime.now()

        self._log_header("INCORRECT TIME VALIDATION (7_30)")
        self.logger.info(f"Input file:  {self.input_file}")
        self.logger.info(f"Output file: {self.output_file}")
        if self.dry_run:
            self.logger.info("*** DRY RUN MODE — no output file will be written ***")
        self.logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Step 1: Read
        all_records = self.read_input_csv()
        if not all_records:
            self.logger.error("No records to process — aborting")
            return

        self.stats.total_input_records = len(all_records)

        # Step 2: Validate all records (mutated in place)
        self._log_header("VALIDATING TRADE DATETIMES")
        validation_stats = self.validator.validate_all(all_records)

        self.stats.match_records = validation_stats["matches"]
        self.stats.error_records = validation_stats["errors"]
        self.stats.missing_parent = validation_stats["missing"]
        self.stats.parse_errors = validation_stats["parse_errors"]
        self.stats.output_records = len(all_records)

        # Step 3: Write (or dry-run preview)
        if self.dry_run:
            self.logger.info(
                f"Dry run: would write {len(all_records)} records to {self.output_file}"
            )
            if all_records:
                sample = all_records[0]
                self.logger.info("Sample output (first record):")
                self.logger.info(f"  child_ref:        {sample.child_ref}")
                self.logger.info(f"  child_datetime:   {sample.child_datetime}")
                self.logger.info(f"  parent_ref:       {sample.parent_ref}")
                self.logger.info(f"  parent_datetime:  {sample.parent_datetime}")
                self.logger.info(f"  bulk_ref:         {sample.bulk_ref}")
                self.logger.info(f"  time_difference:  {sample.time_difference}")
                self.logger.info(f"  error:            {sample.error}")
        else:
            self.write_output_csv(all_records)

        # Step 4: Summary
        end_time = datetime.now()
        self._log_header("VALIDATION COMPLETE")
        self.logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {end_time - start_time}")
        self.stats.print_summary(logger=self.logger)


# ------------------------------------------------------------------
# Batch mode
# ------------------------------------------------------------------


def run_batch_validation(config: dict, dry_run: bool = False) -> int:
    """
    Run validation for multiple incidents in batch mode.

    Args:
        config: Configuration dictionary with testing_period, batch, and paths.
        dry_run: If True, preview without writing output.

    Returns:
        0 on full success, 1 if any incident failed.
    """
    testing_period = config.get("testing_period", {})
    fiscal_year = testing_period.get("fiscal_year", "FYXX")
    quarter = testing_period.get("quarter", "QX")

    batch_config = config.get("batch", {})
    incidents = batch_config.get("incidents", [])
    paths = batch_config.get("paths", {})
    extract_dir = Path(paths.get("extract_dir", "data/extracts"))
    output_dir = Path(paths.get("output_dir", "data/validated"))

    filename_patterns = batch_config.get("filename_patterns", {})
    extract_pattern = filename_patterns.get(
        "extract", "{incident}_{fiscal_year}_{quarter}_extract.csv"
    )
    output_pattern = filename_patterns.get(
        "output", "validated_{fiscal_year}_{quarter}_{incident}.csv"
    )

    if not incidents:
        print("ERROR: No incidents specified in batch config")
        return 1

    print(f"\n{'='*70}")
    print(f"BATCH INCORRECT TIME VALIDATION - {fiscal_year} {quarter}")
    print(f"{'='*70}")
    print(f"Extract directory: {extract_dir}")
    print(f"Output directory:  {output_dir}")
    print(f"Incidents:         {', '.join(incidents)}")
    print(f"{'='*70}\n")

    output_dir.mkdir(parents=True, exist_ok=True)

    total_success = 0
    total_failed = 0

    for incident in incidents:
        print(f"\n{'-'*70}")
        print(f"Processing incident: {incident}")
        print(f"{'-'*70}")

        extract_filename = extract_pattern.format(
            incident=incident, fiscal_year=fiscal_year, quarter=quarter
        )
        output_filename = output_pattern.format(
            incident=incident, fiscal_year=fiscal_year, quarter=quarter
        )
        extract_path = extract_dir / extract_filename
        output_path = output_dir / output_filename

        if not extract_path.exists():
            print(f"[!] Extract file not found: {extract_path}")
            print(f"   Skipping incident {incident}")
            total_failed += 1
            continue

        incident_config = {
            "paths": {
                "input_file": str(extract_path),
                "output_file": str(output_path),
                "log_output": paths.get("log_output", "logs"),
            },
            "processor": config.get("processor", {}),
        }

        try:
            script = IncorrectTimeScript(config_dict=incident_config, dry_run=dry_run)
            script.run()
            print(f"[PASS] Completed: {incident}")
            total_success += 1
        except Exception as exc:
            print(f"[FAIL] Failed: {incident} - {exc}")
            total_failed += 1

    print(f"\n{'='*70}")
    print(f"BATCH VALIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"Successful: {total_success}/{len(incidents)}")
    print(f"Failed:     {total_failed}/{len(incidents)}")
    print(f"{'='*70}\n")

    return 0 if total_failed == 0 else 1


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Create and parse the argument parser."""
    parser = argparse.ArgumentParser(
        description="Incorrect Time Validation (Incident Code 7_30)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # With YAML configuration file (recommended)
  python -m src.accuracy_testing.scripts.incorrect_time \\
      --config config/local/accuracy_testing/incorrect_time.yaml

  # With direct CLI arguments
  python -m src.accuracy_testing.scripts.incorrect_time \\
      input.csv output.csv

  # Dry run to preview
  python -m src.accuracy_testing.scripts.incorrect_time \\
      --config config/local/accuracy_testing/incorrect_time.yaml --dry-run
        """,
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        type=str,
        help="Path to input CSV file (positional, backward compatible)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        type=str,
        help="Path to output CSV file (positional, backward compatible)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override logging level from config",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing output file",
    )
    parser.add_argument(
        "--gui-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser.parse_args()


def main() -> int:
    """Entry point for the incorrect time validation script."""
    args = parse_args()

    try:
        if args.config:
            config = AccuracyConfigManager.load_from_yaml(args.config)
        elif args.input_file and args.output_file:
            config = {
                "paths": {
                    "input_file": args.input_file,
                    "output_file": args.output_file,
                    "log_output": "logs",
                },
                "processor": {
                    "log_level": args.log_level or "INFO",
                    "verbose": args.verbose,
                    "batch_size": 1000,
                },
            }
        elif not getattr(args, "gui_mode", False):
            default_config = (
                Path(__file__).parent.parent.parent.parent
                / "config"
                / "local"
                / "accuracy_testing"
                / "incorrect_time.yaml"
            )
            if default_config.exists():
                config = AccuracyConfigManager.load_from_yaml(str(default_config))
            else:
                print(
                    "Error: No configuration specified and default config not found.\n"
                    "Use --config <path>, or provide input_file and output_file arguments."
                )
                return 1

        # CLI overrides
        if args.log_level:
            config.setdefault("processor", {})["log_level"] = args.log_level
        if args.verbose:
            config.setdefault("processor", {})["verbose"] = True

        if config.get("mode") == "batch":
            return run_batch_validation(config, dry_run=args.dry_run)

        script = IncorrectTimeScript(
            config_dict=config,
            dry_run=args.dry_run,
        )
        script.run()
        return 0

    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
