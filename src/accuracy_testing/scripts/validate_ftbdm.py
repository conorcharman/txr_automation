#!/usr/bin/env python3
"""
Buyer Decision Maker Validation Script v1.0
=============================================

Validates buyer decision maker codes for fund trade transaction reporting.
Migrated from VBA macro ValidateFTBDM3_0.vb.

Incident Code: 12_17

Business Rule:
    For discretionary accounts (Service Level = "D"):
    - Decision Maker Code MUST be populated
    - Decision Maker Code MUST be different from Buyer Code
    - If either condition fails, provide the correct LEI as correction

Exempt Accounts:
    - SIPP accounts: Always no error
    - Non-discretionary accounts (A/E service levels): Always no error

Usage:
    # With YAML configuration file
    python -m src.accuracy_testing.scripts.validate_ftbdm \\
        --config config/local/accuracy_testing/ftbdm_validation.yaml

    # With command-line arguments
    python -m src.accuracy_testing.scripts.validate_ftbdm \\
        --input data/input/ftbdm_data.csv \\
        --lei-data data/reference/lei_lookup.csv \\
        --output data/output/ftbdm_validated.csv

    # Preview without writing output
    python -m src.accuracy_testing.scripts.validate_ftbdm \\
        --config config.yaml --dry-run

Input CSV columns (7 columns minimum):
    1. Transaction Reference
    2. Account ID
    3. Buyer Code
    4. Buyer DM Code
    5. Account Type
    6. Service Level
    7. Branch Code

Output CSV columns (13 columns):
    1. Transaction Reference
    2. Account ID
    3. Buyer Code
    4. Type of Buyer ID (derived)
    5. Buyer DM Code
    6. Type of Buyer DM ID (derived)
    7. Product (derived from Account ID)
    8. Account Type
    9. Service Level
    10. Branch Code
    11. Error (Y/N/TBC)
    12. Correction (LEI:L format)
    13. Correction Field

Version: 1.0
Migrated from: ValidateFTBDM3_0.vb
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

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
    IDFormatValidator,
    ValidationStats,
)

# Import core utilities
try:
    from core import create_logger, StructuredLogger
    CORE_LOGGING = True
except ImportError:
    CORE_LOGGING = False
    create_logger = None


class BuyerDecisionMakerValidator:
    """Main application class for Buyer Decision Maker validation."""

    PARTY_TYPE = "Buyer"

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        input_file: Optional[str] = None,
        output_file: Optional[str] = None,
        lei_data_file: Optional[str] = None,
        id_formats_file: Optional[str] = None,
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
            id_formats_file: ID formats CSV file path (overrides config)
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
        if id_formats_file:
            paths["id_formats_file"] = id_formats_file
        if log_dir:
            paths["log_output"] = log_dir
        self.config["paths"] = paths

        processor_config = self.config.get("processor", {})
        processor_config["log_level"] = log_level
        
        # Get incident code from config
        self.incident_code = self.config.get("single", {}).get("incident_code")
        if not self.incident_code:
            raise ValueError("Configuration error: 'single.incident_code' is required in config file")
        processor_config["verbose"] = verbose
        self.config["processor"] = processor_config

        # Setup logging
        self._setup_logging()

        # Get file paths
        self.input_file = Path(paths.get("input_file", ""))
        self.output_file = Path(paths.get("output_file", ""))
        self.lei_data_file = Path(paths.get("lei_data_file", ""))
        # Only create Path for id_formats_file if it exists in config
        id_formats_str = paths.get("id_formats_file", "")
        self.id_formats_file = Path(id_formats_str) if id_formats_str else None

        # Initialize processor
        self.processor = DecisionMakerProcessor(
            party_type=self.PARTY_TYPE,
            logger=self.logger,
        )

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = self.config.get("processor", {}).get("log_level", "INFO")
        # Get log_output from single.paths or fallback to paths
        paths = self.config.get("single", {}).get("paths", {}) or self.config.get("paths", {})
        log_dir = paths.get("log_output", "logs")

        if CORE_LOGGING and create_logger:
            self.logger = create_logger(
                name="validate_ftbdm",
                log_dir=log_dir,
                log_level=log_level,
            )
        else:
            # Fallback to standard logging
            logging.basicConfig(
                level=getattr(logging, log_level.upper(), logging.INFO),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            self.logger = logging.getLogger("validate_ftbdm")

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

        # ID formats file is optional
        if self.id_formats_file and not self.id_formats_file.exists():
            self.logger.warning(f"ID formats file not found: {self.id_formats_file}")

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
        self.logger.info(f"Starting Buyer Decision Maker Validation (Incident {self.incident_code})")
        self.logger.info(f"Input file: {self.input_file}")
        self.logger.info(f"LEI data file: {self.lei_data_file}")
        self.logger.info(f"Output file: {self.output_file}")

        # Validate paths
        if not self.validate_paths():
            raise FileNotFoundError("Required files not found")

        # Load LEI reference data
        self.processor.load_lei_data(self.lei_data_file)

        # Load ID formats (optional)
        if self.id_formats_file and self.id_formats_file.exists():
            self.processor.load_id_formats(self.id_formats_file)

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
        print(f"Buyer Decision Maker Validation Complete (Incident {self.incident_code})")
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
        description="Validate Buyer Decision Maker codes for fund trades (Incident 12_17)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Using config file
    python -m src.accuracy_testing.scripts.validate_ftbdm --config config/ftbdm.yaml

    # Using CLI arguments
    python -m src.accuracy_testing.scripts.validate_ftbdm \\
        --input data/ftbdm_input.csv \\
        --lei-data data/lei_lookup.csv \\
        --output data/ftbdm_validated.csv

    # Dry run with verbose output
    python -m src.accuracy_testing.scripts.validate_ftbdm \\
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
        "--id-formats",
        type=str,
        dest="id_formats_file",
        help="Path to ID formats CSV file (optional)",
    )

    # Logging
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

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Determine config source
    config_path = args.config
    if not config_path and not args.input_file:
        # Default configuration path (same pattern as other validation scripts)
        from pathlib import Path
        default_config = Path(__file__).parent.parent.parent.parent / "config" / "local" / "accuracy_testing" / "ftbdm_validation.yaml"
        if default_config.exists():
            print(f"Loading default configuration from {default_config}...")
            config_path = str(default_config)
        else:
            parser.error("No configuration specified and default config not found. Use --config or provide --input and --lei-data")

    try:
        validator = BuyerDecisionMakerValidator(
            config_path=config_path,
            input_file=args.input_file,
            output_file=args.output_file,
            lei_data_file=args.lei_data_file,
            id_formats_file=args.id_formats_file,
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
