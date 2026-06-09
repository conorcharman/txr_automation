#!/usr/bin/env python3
"""
Non-Zero Net Quantity Validation Script
=========================================

Validates child transaction quantities against parent order quantities
for Incident Code 7_6 (NonZeroNetQuantity).

This script:
1. Reads the CSV extract from the NonZeroNetQuantity SQL query
2. Groups child records by parent_ref
3. Removes duplicate child_ref entries within each group (first occurrence kept)
4. Sums child_qty for each parent group
5. Compares the net sum against parent_qty
6. Outputs each record with error flag, net_qty, and difference columns

Only deduplicated records are written to the output (duplicate rows are excluded).

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.non_zero_net_quantity \\
        --config config/local/accuracy_testing/non_zero_net_quantity.yaml

    # With direct CLI arguments
    python -m src.accuracy_testing.scripts.non_zero_net_quantity \\
        input.csv output.csv --log-level DEBUG

Input CSV columns (exact order from SQL extract):
    - child_ref
    - child_qty
    - parent_ref
    - parent_qty
    - report_status
    - trade_date_time

Output CSV columns (all input columns + 3 appended):
    - child_ref
    - child_qty
    - parent_ref
    - parent_qty
    - report_status
    - trade_date_time
    - net_qty       (sum of child_qty for this parent group)
    - difference    (net_qty - parent_qty)
    - error         (N = match, Y = mismatch)
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

from src.accuracy_testing.models.net_quantity_record import NetQuantityRecord
from src.accuracy_testing.processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
)
from src.accuracy_testing.validators.net_quantity_validator import NetQuantityValidator

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


class NetQuantityStats:
    """Statistics for a non-zero net quantity validation run."""

    def __init__(self) -> None:
        self.total_input_records: int = 0
        self.output_records: int = 0
        self.duplicates_removed: int = 0
        self.parents_processed: int = 0
        self.match_groups: int = 0
        self.error_groups: int = 0
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
            f"Duplicate child refs removed:{self.duplicates_removed:>6}",
            f"Records written to output:   {self.output_records:>6}",
            f"Parent groups processed:     {self.parents_processed:>6}",
            f"  Matching (error = N):       {self.match_groups:>6}",
            f"  Mismatching (error = Y):    {self.error_groups:>6}",
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


class NonZeroNetQuantityScript:
    """Main application class for non-zero net quantity validation."""

    # Expected column headers in the input CSV
    INPUT_COLUMNS = [
        "child_ref",
        "child_qty",
        "parent_ref",
        "parent_qty",
        "report_status",
        "trade_date_time",
    ]

    # Output CSV column headers — input columns, then bulk_ref/bulk_qty after
    # parent_qty, then the three calculated columns.
    OUTPUT_COLUMNS = [
        "child_ref",
        "child_qty",
        "parent_ref",
        "parent_qty",
        "bulk_ref",
        "bulk_qty",
        "report_status",
        "trade_date_time",
        "net_qty",
        "difference",
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
            name="non_zero_net_quantity",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level,
        )

        self.validator = NetQuantityValidator(verbose=self.proc_config.verbose)
        self.input_file = Path(self.path_config.input_file)
        self.output_file = Path(self.path_config.output_file)
        self.stats = NetQuantityStats()

    def _log_header(self, title: str) -> None:
        """Emit a section header, using log_header() if available (StructuredLogger)
        or falling back to a plain info line.

        Args:
            title: Section title text
        """
        if hasattr(self.logger, "log_header"):
            self.logger.log_header(title)  # type: ignore[union-attr]
        else:
            self.logger.info("=" * 70)
            self.logger.info(title)
            self.logger.info("=" * 70)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def read_input_csv(self) -> List[NetQuantityRecord]:
        """
        Read and parse the input CSV file into NetQuantityRecord objects.

        Row order is preserved; this is critical because deduplication keeps
        the first occurrence by row order.

        Returns:
            List of NetQuantityRecord objects in CSV row order

        Raises:
            FileNotFoundError: If the input file does not exist
        """
        self.logger.info(f"Reading input file: {self.input_file}")

        if not self.input_file.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        records: List[NetQuantityRecord] = []
        f, encoding = safe_open_csv(self.input_file, "r", newline="")
        self.logger.info(f"Detected encoding: {encoding}")

        try:
            with f:
                reader = csv.reader(f)
                header = next(reader)  # consume header row
                self.logger.debug(f"Header: {header}")

                for row_idx, row in enumerate(reader, start=2):
                    if not any(cell.strip() for cell in row):
                        continue  # skip blank rows

                    try:
                        record = NetQuantityRecord.from_row(row, row_index=row_idx)
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

    def write_output_csv(self, records: List[NetQuantityRecord]) -> None:
        """
        Write validated records to the output CSV.

        Only records that were retained after deduplication should be passed
        here. The output contains all input columns plus net_qty, difference,
        and error.

        Args:
            records: Deduplicated list of validated NetQuantityRecord objects
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
                            str(record.child_qty),
                            record.parent_ref,
                            str(record.parent_qty),
                            record.bulk_ref,
                            str(record.bulk_qty),
                            record.report_status,
                            record.trade_date_time,
                            str(record.net_qty),
                            str(record.difference),
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

        self._log_header("NON-ZERO NET QUANTITY VALIDATION (7_6)")
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

        # Step 2: Validate all groups (dedup + sum + flag in place)
        self._log_header("VALIDATING QUANTITY GROUPS")
        validation_stats = self.validator.validate_all(all_records)

        self.stats.parents_processed = validation_stats["parents_processed"]
        self.stats.duplicates_removed = validation_stats["duplicates_removed"]
        self.stats.match_groups = validation_stats["match_groups"]
        self.stats.error_groups = validation_stats["error_groups"]

        # Step 3: Collect the deduplicated output records
        # Re-run deduplication per group to get the retained records only.
        # validate_all already mutated all records with correct error/net_qty/difference,
        # so we just need to collect the first-seen child_ref per parent.
        seen_child_refs: set = set()
        output_records: List[NetQuantityRecord] = []
        for record in all_records:
            if record.child_ref not in seen_child_refs:
                seen_child_refs.add(record.child_ref)
                output_records.append(record)

        self.stats.output_records = len(output_records)

        # Step 4: Write (or dry-run preview)
        if self.dry_run:
            self.logger.info(
                f"Dry run: would write {len(output_records)} records to {self.output_file}"
            )
            if output_records:
                sample = output_records[0]
                self.logger.info("Sample output (first record):")
                self.logger.info(f"  child_ref:   {sample.child_ref}")
                self.logger.info(f"  parent_ref:  {sample.parent_ref}")
                self.logger.info(f"  child_qty:   {sample.child_qty}")
                self.logger.info(f"  net_qty:     {sample.net_qty}")
                self.logger.info(f"  parent_qty:  {sample.parent_qty}")
                self.logger.info(f"  difference:  {sample.difference}")
                self.logger.info(f"  error:       {sample.error}")
        else:
            self.write_output_csv(output_records)

        # Step 5: Summary
        end_time = datetime.now()
        self._log_header("VALIDATION COMPLETE")
        self.logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {end_time - start_time}")
        self.stats.print_summary(logger=self.logger)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Create and parse the argument parser."""
    parser = argparse.ArgumentParser(
        description="Non-Zero Net Quantity Validation (Incident Code 7_6)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # With YAML configuration file (recommended)
  python -m src.accuracy_testing.scripts.non_zero_net_quantity \\
      --config config/local/accuracy_testing/non_zero_net_quantity.yaml

  # With direct CLI arguments
  python -m src.accuracy_testing.scripts.non_zero_net_quantity \\
      input.csv output.csv

  # Dry run to preview
  python -m src.accuracy_testing.scripts.non_zero_net_quantity \\
      --config config/local/accuracy_testing/non_zero_net_quantity.yaml --dry-run
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
    """Entry point for the non-zero net quantity validation script."""
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
                / "non_zero_net_quantity.yaml"
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

        script = NonZeroNetQuantityScript(
            config_dict=config,
            dry_run=args.dry_run,
        )
        script.run()
        return 0

    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return 1
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
