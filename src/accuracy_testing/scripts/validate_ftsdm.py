#!/usr/bin/env python3
"""
Seller Decision Maker Validation Script v1.0
=============================================

Validates seller decision maker codes for fund trade transaction reporting.
Migrated from VBA macro ValidateFTSDM3_0.vb.

Incident Code: 21_17

Business Rule:
    For discretionary accounts (Service Level = "D"):
    - Decision Maker Code MUST be populated
    - Decision Maker Code MUST be different from Seller Code
    - If either condition fails, provide the correct LEI as correction

Exempt Accounts:
    - SIPP accounts: Always no error
    - Non-discretionary accounts (A/E service levels): Always no error

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.validate_ftsdm \\
        --config config/local/accuracy_testing/ftsdm_validation.yaml

    # With command-line arguments
    python -m src.accuracy_testing.scripts.validate_ftsdm \\
        --input data/input/ftsdm_data.csv \\
        --lei-data data/reference/lei_lookup.csv \\
        --output data/output/ftsdm_validated.csv

    # Preview without writing output
    python -m src.accuracy_testing.scripts.validate_ftsdm \\
        --config config.yaml --dry-run

Input CSV columns (7 columns minimum):
    1. Transaction Reference
    2. Account ID
    3. Seller ID Code
    4. Seller DM ID Code
    5. Account Type
    6. Service Level
    7. Branch Code

Output CSV columns (13 columns):
    1. Transaction Reference
    2. Account ID
    3. Seller ID Code
    4. Type of Seller ID Code (derived)
    5. Seller DM ID Code
    6. Type of Seller DM ID Code (derived)
    7. Product (derived from Account ID)
    8. Account Type
    9. Service Level
    10. Branch Code
    11. Error (Y/N/TBC)
    12. Correction (LEI:L format)
    13. Correction Field

Version: 1.0
Migrated from: ValidateFTSDM3_0.vb
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.accuracy_testing.processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
)
from src.accuracy_testing.validators.decision_maker_validator import (
    DecisionMakerProcessor,
    LEILookupManager,
    ValidationStats,
)

# Import core utilities
try:
    from core import StructuredLogger, create_logger

    CORE_LOGGING = True
except ImportError:
    CORE_LOGGING = False
    create_logger = None


class SellerDecisionMakerValidator:
    """Main application class for Seller Decision Maker validation."""

    PARTY_TYPE = "Seller"

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
        lei_data_file: Optional[str] = None,
        log_dir: Optional[str] = None,
        log_level: str = "INFO",
        dry_run: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize validator.

        Args:
            config_path: Path to YAML configuration file
            config_dict: Configuration dictionary (overrides config_path)
            input_file: Input CSV file path (overrides config)
            output_file: Output CSV file path (overrides config)
            lei_data_file: LEI lookup CSV file path (overrides config)
            log_dir: Log output directory
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            dry_run: If True, preview changes without writing output
            verbose: Enable verbose console output
        """
        self.dry_run = dry_run
        self.verbose = verbose

        # Load configuration
        self.config: Dict[str, Any] = {}
        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = AccuracyConfigManager.load_from_yaml(config_path)

        # Get paths from single.paths (like buyer/seller validation)
        paths = self.config.get("single", {}).get("paths", {})
        if not paths:
            # Fallback to root paths if single.paths doesn't exist
            paths = self.config.get("paths", {})

        # Override with CLI arguments
        if input_file:
            paths["input_file"] = input_file
        if output_file:
            paths["output_file"] = output_file
        if lei_data_file:
            paths["lei_data_file"] = lei_data_file
        if log_dir:
            paths["log_output"] = log_dir
        self.config["paths"] = paths

        processor_config = self.config.get("processor", {})
        processor_config["log_level"] = log_level
        processor_config["verbose"] = verbose
        self.config["processor"] = processor_config

        # Get incident code from config
        self.incident_code = self.config.get("single", {}).get("incident_code")
        if not self.incident_code:
            raise ValueError(
                "Configuration error: 'single.incident_code' is required in config file"
            )

        # Setup logging
        self._setup_logging()

        # Get file paths
        self.input_file = Path(paths.get("input_file", ""))
        self.output_file = Path(paths.get("output_file", ""))
        self.lei_data_file = Path(paths.get("lei_data_file", ""))

        # Initialize processor
        self.processor = DecisionMakerProcessor(
            party_type=self.PARTY_TYPE,
            logger=self.logger,
        )

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = self.config.get("processor", {}).get("log_level", "INFO")
        # Get log_output from single.paths or fallback to paths
        paths = self.config.get("single", {}).get("paths", {}) or self.config.get(
            "paths", {}
        )
        log_dir = paths.get("log_output", "logs")

        if CORE_LOGGING and create_logger:
            self.logger = create_logger(
                name="validate_ftsdm",
                log_dir=log_dir,
                log_level=log_level,
            )
        else:
            # Fallback to standard logging
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self.logger = logging.getLogger("validate_ftsdm")

    def validate_paths(self) -> bool:
        """
        Validate that required files exist.

        Returns:
            True if all required files exist, False otherwise
        """
        errors = []

        if not self.input_file or not self.input_file.exists():
            errors.append(f"Input file not found: {self.input_file}")

        if not self.lei_data_file or not self.lei_data_file.exists():
            errors.append(f"LEI data file not found: {self.lei_data_file}")

        if errors:
            for error in errors:
                self.logger.error(error)
            return False

        return True

    def run(self) -> ValidationStats:
        """
        Run the validation process.

        Returns:
            ValidationStats with results

        Raises:
            FileNotFoundError: If required files are missing
            ValueError: If configuration is invalid
        """
        self.logger.info(
            f"Starting Seller Decision Maker Validation (Incident {self.incident_code})"
        )
        self.logger.info(f"Input file: {self.input_file}")
        self.logger.info(f"LEI data file: {self.lei_data_file}")
        self.logger.info(f"Output file: {self.output_file}")

        # Validate paths
        if not self.validate_paths():
            raise FileNotFoundError("Required files not found")

        # Load LEI reference data
        self.processor.load_lei_data(self.lei_data_file)

        # Load input data
        record_count = self.processor.load_input_csv(self.input_file)
        self.logger.info(f"Loaded {record_count} records")

        # Run validation
        stats = self.processor.process()

        # Write output
        if not self.dry_run:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self.processor.write_output_csv(self.output_file)
            self.logger.info(f"Results written to {self.output_file}")
        else:
            self.logger.info("Dry run - no output written")

        # Print summary
        self._print_summary(stats)

        return stats

    def _print_summary(self, stats: ValidationStats) -> None:
        """Print validation summary."""
        print("\n" + "=" * 60)
        print(
            f"Seller Decision Maker Validation Complete (Incident {self.incident_code})"
        )
        print("=" * 60)
        print(f"Total records:              {stats.total:>8}")
        print(f"No error:                   {stats.no_error:>8}")
        print(f"Error (with correction):    {stats.error:>8}")
        print(f"TBC (needs investigation):  {stats.tbc:>8}")
        print("-" * 60)
        print(f"Skipped (SIPP accounts):    {stats.skipped_sipp:>8}")
        print(f"Skipped (non-discretionary):{stats.skipped_non_discretionary:>8}")
        print("=" * 60)

        if stats.error > 0:
            print(f"\n⚠️  {stats.error} records require correction")
        if stats.tbc > 0:
            print(f"\n🔍 {stats.tbc} records require manual investigation")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate Seller Decision Maker codes for fund trades (Incident 21_17)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Using config file
    python -m src.accuracy_testing.scripts.validate_ftsdm --config config/ftsdm.yaml

    # Using CLI arguments
    python -m src.accuracy_testing.scripts.validate_ftsdm \\
        --input data/ftsdm_input.csv \\
        --lei-data data/lei_lookup.csv \\
        --output data/ftsdm_validated.csv

    # Dry run with verbose output
    python -m src.accuracy_testing.scripts.validate_ftsdm \\
        --config config.yaml --dry-run --verbose
        """,
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )

    # File paths
    parser.add_argument(
        "--input",
        type=str,
        dest="input_file",
        help="Path to input CSV file",
    )
    parser.add_argument(
        "--output",
        type=str,
        dest="output_file",
        help="Path to output CSV file",
    )
    parser.add_argument(
        "--lei-data",
        type=str,
        dest="lei_data_file",
        help="Path to LEI lookup CSV file",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        help="Directory for log files",
    )
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
        help="Preview without writing output",
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

    # Determine config source
    config_path = args.config
    if not config_path and not args.input_file and not getattr(args, "gui_mode", False):
        # Default configuration path (same pattern as other validation scripts)
        from pathlib import Path

        default_config = (
            Path(__file__).parent.parent.parent.parent
            / "config"
            / "local"
            / "accuracy_testing"
            / "ftsdm_validation.yaml"
        )
        if default_config.exists():
            print(f"Loading default configuration from {default_config}...")
            config_path = str(default_config)
        else:
            parser.error(
                "No configuration specified and default config not found. Use --config or provide --input and --lei-data"
            )

    try:
        validator = SellerDecisionMakerValidator(
            config_path=config_path,
            input_file=args.input_file,
            output_file=args.output_file,
            lei_data_file=args.lei_data_file,
            log_dir=args.log_dir,
            log_level=args.log_level,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        stats = validator.run()

        # Return exit code based on results
        if stats.error > 0 or stats.tbc > 0:
            return 1  # Errors or TBC found
        return 0  # Success

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
