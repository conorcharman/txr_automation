#!/usr/bin/env python3
"""
Data Push Script v1.1
=====================

Push validation results to master tracking files.

This script consolidates accuracy testing results back to centralised
tracking files after validation is complete. It matches records by
transaction reference and pushes all validation columns.

Migrated from: DataPush1_0.vb

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.data_push \\
        --config config/local/accuracy_testing/data_push.yaml

    # With command-line arguments
    python -m src.accuracy_testing.scripts.data_push \\
        --source data/output/buyer_id_validated.csv \\
        --target data/master/FY26_Q1_7_37.csv \\
        --incident 7_37

    # Dry run (preview without writing)
    python -m src.accuracy_testing.scripts.data_push \\
        --source source.csv --target target.csv --dry-run

    # Batch mode (process multiple incidents)
    python -m src.accuracy_testing.scripts.data_push \\
        --batch \\
        --source-dir data/output/validated \\
        --target-dir data/master \\
        --fiscal-year FY26 \\
        --quarter Q1

Business Logic:
    - Match records by Transaction Reference
    - Push ALL validation columns to template for QA purposes
    - Both validation outputs and templates use "Error" column
    - All records (with or without errors) are pushed
    - No match: Log as not found (no update)

Version: 1.1 (Push all records for QA)
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.models.data_push_record import (
    ColumnMapping,
    DataPushConfig,
    PushStats,
)
from src.accuracy_testing.validators.data_push_processor import (
    BatchDataPushProcessor,
    DataPushProcessor,
)

# Import core utilities
try:
    from core import create_logger

    CORE_LOGGING = True
except ImportError:
    CORE_LOGGING = False
    create_logger = None


class DataPushCLI:
    """Command-line interface for data push operations."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        source_file: Optional[str] = None,
        target_file: Optional[str] = None,
        output_file: Optional[str] = None,
        incident_code: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        quarter: Optional[str] = None,
        log_level: str = "INFO",
        dry_run: bool = False,
        backup: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize CLI handler.

        Args:
            config_path: Path to YAML configuration file
            source_file: Path to source CSV file
            target_file: Path to target CSV file
            output_file: Path for output file (defaults to target)
            incident_code: Incident code
            fiscal_year: Fiscal year
            quarter: Quarter
            log_level: Logging level
            dry_run: If True, preview changes without writing
            backup: If True, create backup before modifying
            verbose: Enable verbose output
        """
        self.dry_run = dry_run
        self.backup = backup
        self.verbose = verbose

        # Load configuration
        self.config: Dict[str, Any] = {}
        if config_path:
            self.config = self._load_yaml_config(config_path)

        # Override with CLI arguments
        paths = self.config.get("paths", {})
        if source_file:
            paths["source_file"] = source_file
        if target_file:
            paths["target_file"] = target_file
        if output_file:
            paths["output_file"] = output_file
        self.config["paths"] = paths

        period = self.config.get("testing_period", {})
        if fiscal_year:
            period["fiscal_year"] = fiscal_year
        if quarter:
            period["quarter"] = quarter
        self.config["testing_period"] = period

        incident = self.config.get("incident", {})
        if incident_code:
            incident["code"] = incident_code
        self.config["incident"] = incident

        # Setup logging
        self._setup_logging(log_level)

        # Get file paths
        self.source_file = (
            Path(paths.get("source_file", "")) if paths.get("source_file") else None
        )
        self.target_file = (
            Path(paths.get("target_file", "")) if paths.get("target_file") else None
        )
        self.output_file = (
            Path(paths.get("output_file", "")) if paths.get("output_file") else None
        )

    def _load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        """Load YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _setup_logging(self, log_level: str) -> None:
        """Setup logging configuration."""
        if CORE_LOGGING and create_logger:
            # Get log directory from config, default to "logs"
            log_dir = self.config.get("paths", {}).get("log_output", "logs")
            if self.config.get("mode") == "batch":
                log_dir = (
                    self.config.get("batch", {})
                    .get("paths", {})
                    .get("log_output", "logs")
                )
            elif self.config.get("mode") == "single":
                log_dir = (
                    self.config.get("single", {})
                    .get("paths", {})
                    .get("log_output", "logs")
                )

            self.logger = create_logger(
                name="data_push",
                log_dir=log_dir,
                log_level=log_level,
            )
        else:
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self.logger = logging.getLogger("data_push")

    def validate_paths(self) -> bool:
        """Validate that required files exist."""
        errors = []

        if not self.source_file or not self.source_file.exists():
            errors.append(f"Source file not found: {self.source_file}")

        if not self.target_file or not self.target_file.exists():
            errors.append(f"Target file not found: {self.target_file}")

        if errors:
            for error in errors:
                self.logger.error(error)
            return False

        return True

    def run(self) -> PushStats:
        """
        Run the data push operation.

        Returns:
            PushStats with results
        """
        self.logger.info("Starting Data Push operation")
        self.logger.info(f"Source: {self.source_file}")
        self.logger.info(f"Target: {self.target_file}")

        if not self.validate_paths():
            raise FileNotFoundError("Required files not found")

        # Build configuration
        push_config = DataPushConfig.from_dict(self.config)
        push_config.source_file = self.source_file
        push_config.target_file = self.target_file
        push_config.dry_run = self.dry_run
        push_config.backup = self.backup

        # Create processor
        processor = DataPushProcessor(config=push_config, logger=self.logger)

        # Determine output path
        output_path = self.output_file or self.target_file

        # Run push
        stats = processor.process(
            source_path=self.source_file,
            target_path=self.target_file,
            output_path=output_path,
            dry_run=self.dry_run,
            backup=self.backup,
        )

        # Print summary
        self._print_summary(stats, processor)

        return stats

    def _print_summary(self, stats: PushStats, processor: DataPushProcessor) -> None:
        """Print operation summary."""
        print("\n" + "=" * 60)
        print("Data Push Complete")
        print("=" * 60)
        print(f"Source records:             {stats.total_source:>8}")
        print(f"Matched in target:          {stats.matched:>8}")
        print(f"Not found:                  {stats.not_found:>8}")
        print("-" * 60)
        print(f"Updated (all columns):      {stats.updated_all:>8}")
        print(f"Updated (error only):       {stats.updated_error_only:>8}")
        print(f"Skipped:                    {stats.skipped:>8}")
        print(f"Errors:                     {stats.errors:>8}")
        print("-" * 60)
        print(f"Success rate:               {stats.success_rate:>7.1f}%")
        print("=" * 60)

        if self.dry_run:
            print("\n🔍 DRY RUN - No changes were written")

        if stats.not_found > 0:
            print(f"\n⚠️  {stats.not_found} records not found in target")
            if self.verbose:
                unmatched = processor.get_unmatched_records()[:10]
                print("  First 10 unmatched:")
                for record in unmatched:
                    print(f"    - {record.transaction_ref}")


class BatchDataPushCLI:
    """Command-line interface for batch data push operations."""

    def __init__(
        self,
        source_dir: str,
        target_dir: str,
        fiscal_year: str,
        quarter: str,
        incidents: Optional[str] = None,
        column_mappings: Optional[list] = None,
        backup_dir: Optional[str] = None,
        log_dir: str = "logs",
        log_level: str = "INFO",
        dry_run: bool = False,
        backup: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize batch CLI handler.

        Args:
            source_dir: Base directory for source files
            target_dir: Base directory for target files
            fiscal_year: Fiscal year (e.g., FY26)
            quarter: Quarter (e.g., Q1)
            incidents: Comma-separated incident codes (or None for auto-discovery)
            column_mappings: List of column mappings from config
            backup_dir: Optional directory for backup files
            log_dir: Directory for log files
            log_level: Logging level
            dry_run: If True, preview changes without writing
            backup: If True, create backups
            verbose: Enable verbose output
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.fiscal_year = fiscal_year
        self.quarter = quarter
        self.incidents = incidents.split(",") if incidents else None
        self.column_mappings = column_mappings
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self.dry_run = dry_run
        self.backup = backup
        self.verbose = verbose
        self.log_dir = Path(log_dir) if log_dir else Path("logs")

        # Setup logging
        self._setup_logging(log_level, str(self.log_dir))

    def _setup_logging(self, log_level: str, log_dir: str = "logs") -> None:
        """Setup logging configuration."""
        if CORE_LOGGING and create_logger:
            self.logger = create_logger(
                name="data_push_batch",
                log_dir=log_dir,
                log_level=log_level,
            )
        else:
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self.logger = logging.getLogger("data_push_batch")

    def run(self) -> Dict[str, PushStats]:
        """
        Run batch data push operation.

        Returns:
            Dictionary of incident_code -> PushStats
        """
        self.logger.info(f"Starting batch data push: {self.fiscal_year} {self.quarter}")
        self.logger.info(f"Source directory: {self.source_dir}")
        self.logger.info(f"Target directory: {self.target_dir}")

        # Create batch processor
        processor = BatchDataPushProcessor(
            base_source_dir=self.source_dir,
            base_target_dir=self.target_dir,
            fiscal_year=self.fiscal_year,
            quarter=self.quarter,
            column_mappings=self.column_mappings,
            backup_dir=self.backup_dir,
            logger=self.logger,
        )

        # Run batch
        results = processor.process_batch(
            incidents=self.incidents,
            dry_run=self.dry_run,
            backup=self.backup,
        )

        # Print summary
        self._print_summary(processor)

        return results

    def _print_summary(self, processor: BatchDataPushProcessor) -> None:
        """Print batch operation summary."""
        summary = processor.get_batch_summary()

        print("\n" + "=" * 60)
        print("Batch Data Push Complete")
        print("=" * 60)
        print(f"Incidents processed:        {summary['incidents_processed']:>8}")
        print(f"Total source records:       {summary['total_source_records']:>8}")
        print(f"Total matched:              {summary['total_matched']:>8}")
        print(f"Total updated:              {summary['total_updated']:>8}")
        print("-" * 60)

        if self.verbose:
            print("\nBy Incident:")
            for incident, stats in summary["by_incident"].items():
                print(
                    f"  {incident}: {stats['matched']}/{stats['total_source']} matched"
                )

        print("=" * 60)

        if self.dry_run:
            print("\n🔍 DRY RUN - No changes were written")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Push validation results to master tracking files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default config
    data-push

    # Single file push with config
    python -m src.accuracy_testing.scripts.data_push --config config/data_push.yaml

    # Single file push with CLI arguments
    python -m src.accuracy_testing.scripts.data_push \\
        --source data/output/buyer_id_validated.csv \\
        --target data/master/FY26_Q1_7_37.csv

    # Dry run (preview changes)
    python -m src.accuracy_testing.scripts.data_push \\
        --source source.csv --target target.csv --dry-run

    # Batch mode
    python -m src.accuracy_testing.scripts.data_push --batch \\
        --source-dir data/output/validated \\
        --target-dir data/master \\
        --fiscal-year FY26 --quarter Q1
        """,
    )

    # Mode selection
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run in batch mode (process multiple incidents)",
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        default="config/local/accuracy_testing/data_push.yaml",
        help="Path to YAML configuration file (default: config/local/accuracy_testing/data_push.yaml)",
    )

    # Single file mode arguments
    parser.add_argument(
        "--source",
        type=str,
        dest="source_file",
        help="Path to source CSV file (validation output)",
    )
    parser.add_argument(
        "--target",
        type=str,
        dest="target_file",
        help="Path to target CSV file (master tracking file)",
    )
    parser.add_argument(
        "--output",
        type=str,
        dest="output_file",
        help="Path for output file (defaults to target, overwriting)",
    )
    parser.add_argument(
        "--incident",
        type=str,
        dest="incident_code",
        help="Incident code (e.g., 7_37)",
    )

    # Batch mode arguments
    parser.add_argument(
        "--source-dir",
        type=str,
        help="Base directory for source files (batch mode)",
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        help="Base directory for target files (batch mode)",
    )
    parser.add_argument(
        "--incidents",
        type=str,
        help="Comma-separated incident codes (batch mode, optional)",
    )

    # Common arguments
    parser.add_argument(
        "--fiscal-year",
        type=str,
        help="Fiscal year (e.g., FY26)",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        help="Quarter (e.g., Q1)",
    )

    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to files",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup of target file before modifying",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--gui-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Load config to determine mode (if config provided)
        config = None
        config_mode = None
        if args.config and Path(args.config).exists():
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                config_mode = config.get("mode", "single")

        # Determine if we should run in batch mode
        # Priority: explicit --source/--target → single mode,
        #           --batch flag → batch mode,
        #           config mode → batch/single,
        #           default → single
        has_explicit_single = args.source_file and args.target_file
        batch_mode = (not has_explicit_single) and (
            args.batch or (config_mode == "batch")
        )

        if batch_mode:
            # Batch mode
            # Get parameters from args or config
            if config and config_mode == "batch":
                batch_config = config.get("batch", {})
                batch_paths = batch_config.get("paths", {})
                testing_period = config.get("testing_period", {})

                source_dir = (
                    args.source_dir
                    or batch_paths.get("source_dir")
                    or batch_paths.get("input_directory")
                )
                target_dir = (
                    args.target_dir
                    or batch_paths.get("target_dir")
                    or batch_paths.get("output_directory")
                )
                fiscal_year = args.fiscal_year or testing_period.get("fiscal_year")
                quarter = args.quarter or testing_period.get("quarter")

                # Handle incidents config value
                incidents_config = args.incidents or batch_config.get("incidents")
                if incidents_config == "all" or incidents_config is None:
                    incidents = None  # Auto-discover
                elif isinstance(incidents_config, str):
                    incidents = incidents_config  # Will be split by CLI class
                else:
                    incidents = (
                        ",".join(incidents_config)
                        if isinstance(incidents_config, list)
                        else incidents_config
                    )

                # Get column mappings from config
                column_mappings_raw = batch_config.get("column_mappings", [])
                column_mappings = [
                    ColumnMapping(
                        source_col=m.get("source", ""),
                        target_col=m.get("target", ""),
                        description=m.get("description", ""),
                    )
                    for m in column_mappings_raw
                ]

                log_dir = batch_paths.get("log_output", "logs")
                backup_dir = batch_paths.get("backup_dir")
            else:
                source_dir = args.source_dir
                target_dir = args.target_dir
                fiscal_year = args.fiscal_year
                quarter = args.quarter
                incidents = args.incidents
                column_mappings = []
                log_dir = "logs"
                backup_dir = None

            if not source_dir or not target_dir:
                parser.error(
                    "Batch mode requires --source-dir and --target-dir (or batch config)"
                )
            if not fiscal_year or not quarter:
                parser.error(
                    "Batch mode requires --fiscal-year and --quarter (or batch config)"
                )

            cli = BatchDataPushCLI(
                source_dir=source_dir,
                target_dir=target_dir,
                fiscal_year=fiscal_year,
                quarter=quarter,
                incidents=incidents,
                column_mappings=column_mappings,
                backup_dir=backup_dir,
                log_dir=log_dir,
                log_level=args.log_level,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                verbose=args.verbose,
            )

            results = cli.run()

            # Return error if any incident failed
            for stats in results.values():
                if stats.errors > 0:
                    return 1
            return 0

        else:
            # Single file mode
            # Check if config file exists (including default)
            config_path = args.config if args.config else None
            config_exists = config_path and Path(config_path).exists()

            if not config_exists and not (args.source_file and args.target_file):
                if config_path:
                    parser.error(
                        f"Config file not found: {config_path}. Either provide a valid --config or both --source and --target"
                    )
                else:
                    parser.error(
                        "Either --config or both --source and --target are required"
                    )

            cli = DataPushCLI(
                config_path=config_path if config_exists else None,
                source_file=args.source_file,
                target_file=args.target_file,
                output_file=args.output_file,
                incident_code=args.incident_code,
                fiscal_year=args.fiscal_year,
                quarter=args.quarter,
                log_level=args.log_level,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                verbose=args.verbose,
            )

            stats = cli.run()

            return 1 if stats.errors > 0 else 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
