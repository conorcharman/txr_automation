#!/usr/bin/env python3
"""
Run All Validations
===================

Orchestrates execution of all validation scripts for accuracy testing.

This script provides a unified interface to run multiple validation scripts
in sequence, monitor their execution, and report results.

Version 1.0 Features:
- Run all validation scripts or select specific ones
- YAML config-driven validation selection
- Progress tracking and status reporting
- Aggregated execution summary
- Error handling and logging

Usage:
    # Run all validations with default configs
    python -m src.accuracy_testing.scripts.run_all_validations

    # Run specific validations
    python -m src.accuracy_testing.scripts.run_all_validations --validations buyer seller

    # Use custom config file
    python -m src.accuracy_testing.scripts.run_all_validations --config config/local/accuracy_testing/run_all_validations.yaml

    # Run with verbose output
    python -m src.accuracy_testing.scripts.run_all_validations --verbose
"""

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class ValidationConfig:
    """Configuration for a single validation script."""

    name: str
    script_module: str
    config_file: Optional[str] = None
    enabled: bool = True
    description: str = ""


@dataclass
class ValidationResult:
    """Result of running a single validation."""

    name: str
    success: bool
    duration: float = 0.0
    error_message: str = ""
    return_code: int = 0


class ValidationOrchestrator:
    """Orchestrates execution of multiple validation scripts."""

    # Default validation configurations
    DEFAULT_VALIDATIONS = [
        ValidationConfig(
            name="buyer",
            script_module="src.accuracy_testing.scripts.buyer_id_validation",
            config_file="config/local/accuracy_testing/buyer_validation.yaml",
            description="Buyer ID Validation (7_5, 7_6)",
        ),
        ValidationConfig(
            name="seller",
            script_module="src.accuracy_testing.scripts.seller_id_validation",
            config_file="config/local/accuracy_testing/seller_validation.yaml",
            description="Seller ID Validation (7_7, 7_8)",
        ),
        ValidationConfig(
            name="inconsistent-buyer",
            script_module="src.accuracy_testing.scripts.inconsistent_buyer_id_validation",
            config_file="config/local/accuracy_testing/inconsistent_buyer_validation.yaml",
            description="Inconsistent Buyer ID Validation (7_37, 7_38)",
        ),
        ValidationConfig(
            name="inconsistent-seller",
            script_module="src.accuracy_testing.scripts.inconsistent_seller_id_validation",
            config_file="config/local/accuracy_testing/inconsistent_seller_validation.yaml",
            description="Inconsistent Seller ID Validation (7_39, 7_40)",
        ),
        ValidationConfig(
            name="ftbdm",
            script_module="src.accuracy_testing.scripts.validate_ftbdm",
            config_file="config/local/accuracy_testing/ftbdm_validation.yaml",
            description="Field 27 Buyer Decision Maker Validation",
        ),
        ValidationConfig(
            name="ftsdm",
            script_module="src.accuracy_testing.scripts.validate_ftsdm",
            config_file="config/local/accuracy_testing/ftsdm_validation.yaml",
            description="Field 28 Seller Decision Maker Validation",
        ),
        ValidationConfig(
            name="pricing",
            script_module="src.accuracy_testing.scripts.pricing_validation",
            config_file="config/local/accuracy_testing/pricing_validation.yaml",
            description="Pricing Validation",
        ),
        ValidationConfig(
            name="non-zero-net-qty",
            script_module="src.accuracy_testing.scripts.non_zero_net_quantity",
            config_file="config/local/accuracy_testing/non_zero_net_quantity.yaml",
            description="Non-Zero Net Quantity Validation (7_6)",
        ),
    ]

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        config_file: Optional[str] = None,
    ):
        """
        Initialize validation orchestrator.

        Args:
            logger: Optional logger instance
            config_file: Optional YAML config file path
        """
        self.logger = logger or logging.getLogger(__name__)
        self.validations = self._load_validations(config_file)
        self.results: List[ValidationResult] = []

    def _load_validations(self, config_file: Optional[str]) -> List[ValidationConfig]:
        """
        Load validation configurations.

        Args:
            config_file: Optional YAML config file path

        Returns:
            List of validation configurations
        """
        if not config_file or not Path(config_file).exists():
            self.logger.info("Using default validation configurations")
            return self.DEFAULT_VALIDATIONS.copy()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            validations = []
            for val_config in config_data.get("validations", []):
                validations.append(
                    ValidationConfig(
                        name=val_config["name"],
                        script_module=val_config["script_module"],
                        config_file=val_config.get("config_file"),
                        enabled=val_config.get("enabled", True),
                        description=val_config.get("description", ""),
                    )
                )

            self.logger.info(
                f"Loaded {len(validations)} validation configurations from {config_file}"
            )
            return validations

        except Exception as e:
            self.logger.warning(
                f"Failed to load config from {config_file}: {e}. Using defaults."
            )
            return self.DEFAULT_VALIDATIONS.copy()

    def run_validation(self, validation: ValidationConfig) -> ValidationResult:
        """
        Run a single validation script.

        Args:
            validation: Validation configuration

        Returns:
            Validation result
        """
        self.logger.info(
            f"Starting validation: {validation.name}",
            extra={
                "validation": validation.name,
                "description": validation.description,
            },
        )

        start_time = datetime.now()

        try:
            # Build command to run the validation script
            cmd = [sys.executable, "-m", validation.script_module]

            # Add config file if specified
            if validation.config_file and Path(validation.config_file).exists():
                cmd.extend(["--config", validation.config_file])

            # Run the validation script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                self.logger.info(
                    f"✓ Validation completed: {validation.name}",
                    extra={"validation": validation.name, "duration": duration},
                )
                return ValidationResult(
                    name=validation.name,
                    success=True,
                    duration=duration,
                    return_code=result.returncode,
                )
            else:
                error_msg = result.stderr or "Unknown error"
                self.logger.error(
                    f"✗ Validation failed: {validation.name}",
                    extra={
                        "validation": validation.name,
                        "duration": duration,
                        "error": error_msg,
                    },
                )
                # Print full error to console for debugging
                if error_msg:
                    print(f"\nFull error output for {validation.name}:")
                    print("-" * 80)
                    print(error_msg)
                    print("-" * 80)

                return ValidationResult(
                    name=validation.name,
                    success=False,
                    duration=duration,
                    error_message=error_msg,
                    return_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(
                f"✗ Validation timed out: {validation.name}",
                extra={"validation": validation.name, "duration": duration},
            )
            return ValidationResult(
                name=validation.name,
                success=False,
                duration=duration,
                error_message="Timeout after 600 seconds",
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(
                f"✗ Validation error: {validation.name}: {e}",
                extra={
                    "validation": validation.name,
                    "duration": duration,
                    "error": str(e),
                },
            )
            return ValidationResult(
                name=validation.name,
                success=False,
                duration=duration,
                error_message=str(e),
            )

    def run_all(
        self,
        selected_names: Optional[List[str]] = None,
        continue_on_error: bool = True,
    ) -> bool:
        """
        Run all validations or selected validations.

        Args:
            selected_names: Optional list of validation names to run
            continue_on_error: Continue running validations if one fails

        Returns:
            True if all validations succeeded, False otherwise
        """
        # Filter validations
        validations_to_run = [
            v
            for v in self.validations
            if v.enabled and (not selected_names or v.name in selected_names)
        ]

        if not validations_to_run:
            self.logger.warning("No validations selected to run")
            return False

        self.logger.info(
            f"Running {len(validations_to_run)} validation(s)",
            extra={"count": len(validations_to_run)},
        )

        # Print validation list
        print("\n" + "=" * 80)
        print("VALIDATION EXECUTION PLAN")
        print("=" * 80)
        for i, validation in enumerate(validations_to_run, 1):
            print(f"{i}. {validation.name}: {validation.description}")
            if validation.config_file:
                print(f"   Config: {validation.config_file}")
        print("=" * 80 + "\n")

        # Run each validation
        self.results = []
        for i, validation in enumerate(validations_to_run, 1):
            print(f"\n[{i}/{len(validations_to_run)}] Running: {validation.name}")
            print("-" * 80)

            result = self.run_validation(validation)
            self.results.append(result)

            if not result.success and not continue_on_error:
                self.logger.error("Stopping execution due to validation failure")
                break

        # Print summary
        self._print_summary()

        # Return overall success
        return all(r.success for r in self.results)

    def _print_summary(self):
        """Print execution summary."""
        print("\n" + "=" * 80)
        print("VALIDATION EXECUTION SUMMARY")
        print("=" * 80)

        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful
        total_duration = sum(r.duration for r in self.results)

        print(f"\nTotal Validations: {total}")
        print(f"Successful: {successful} ✓")
        print(f"Failed: {failed} ✗")
        print(f"Total Duration: {total_duration:.2f}s\n")

        # Print individual results
        print("Individual Results:")
        print("-" * 80)
        for result in self.results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            print(f"{status:8} | {result.name:25} | {result.duration:6.2f}s")
            if not result.success and result.error_message:
                print(f"         | Error: {result.error_message[:70]}")

        print("=" * 80 + "\n")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for run_all_validations."""
    parser = argparse.ArgumentParser(
        description="Run all validation scripts for accuracy testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all validations
    %(prog)s
    
    # Run specific validations
    %(prog)s --validations buyer seller
    
    # Use custom config file
    %(prog)s --config config/local/accuracy_testing/run_all_validations.yaml
    
    # Stop on first failure
    %(prog)s --stop-on-error
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )

    parser.add_argument(
        "--validations",
        nargs="+",
        help="Specific validations to run (e.g., buyer seller)",
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop execution on first validation failure",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available validations and exit",
    )

    parser.add_argument(
        "--gui-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def main():
    """Main entry point for run_all_validations script."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    # Create orchestrator
    orchestrator = ValidationOrchestrator(logger=logger, config_file=args.config)

    # List validations if requested
    if args.list:
        print("\nAvailable Validations:")
        print("=" * 80)
        for validation in orchestrator.validations:
            status = "✓" if validation.enabled else "✗"
            print(f"{status} {validation.name:25} | {validation.description}")
            if validation.config_file:
                print(f"  Config: {validation.config_file}")
        print("=" * 80)
        return 0

    try:
        # Run validations
        success = orchestrator.run_all(
            selected_names=args.validations,
            continue_on_error=not args.stop_on_error,
        )

        return 0 if success else 1

    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
