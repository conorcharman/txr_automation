#!/usr/bin/env python3
"""
Setup Directories Utility v1.0
================================

Creates the standard directory hierarchy for accuracy testing and replay
for a given fiscal year and quarter.  Running the script is idempotent —
directories that already exist are skipped and reported in the log.

Directories created under ``{data_dir}/{fiscal_year}/{quarter}/``:

    accuracy_testing/
        extracts/
            csv/
            dtf/
            sql/
        kaizen/
        logs/
        output/
        templates/
    replay/
        phase_2/
            feedback/
                kaizen/
                output/
            final_lookup/
                output/
                unavista/
            logs/
        phase_3/
            feedback/
                kaizen/
                output/
            final_lookup/
                merged/
                output/
                unavista/
            logs/

Usage:
    python -m src.utils.setup_directories --fiscal-year FY26 --quarter Q1
    python -m src.utils.setup_directories --config /path/to/config.yaml
"""

import argparse
import sys
from pathlib import Path
from typing import List

from core import ConfigManager, create_logger

# ---------------------------------------------------------------------------
# Directory tree
# ---------------------------------------------------------------------------

#: All paths to create, relative to ``{data_dir}/{fiscal_year}/{quarter}/``.
DIRECTORY_TREE: List[str] = [
    # Accuracy Testing
    "accuracy_testing/extracts/csv",
    "accuracy_testing/extracts/dtf",
    "accuracy_testing/extracts/sql",
    "accuracy_testing/kaizen",
    "accuracy_testing/logs",
    "accuracy_testing/output",
    "accuracy_testing/templates",
    # Replay — Phase 2
    "replay/phase_2/feedback/kaizen",
    "replay/phase_2/feedback/output",
    "replay/phase_2/final_lookup/output",
    "replay/phase_2/final_lookup/unavista",
    "replay/phase_2/logs",
    # Replay — Phase 3
    "replay/phase_3/feedback/kaizen",
    "replay/phase_3/feedback/output",
    "replay/phase_3/feedback/merged",
    "replay/phase_3/final_lookup/output",
    "replay/phase_3/final_lookup/unavista",
    "replay/phase_3/logs",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Create the standard directory structure for a fiscal year/quarter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a YAML configuration file.",
    )
    parser.add_argument(
        "--fiscal-year",
        dest="fiscal_year",
        type=str,
        help="Fiscal year identifier, e.g. FY26.",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        help="Quarter identifier, e.g. Q1.",
    )
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        type=str,
        help="Root data directory (default: /app/data).",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity level.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point.

    Returns:
        Exit code — ``0`` on success, ``1`` if any directory could not be created.
    """
    args = _parse_arguments()

    # Load config from YAML when provided; explicit CLI args override each field.
    config: dict = {}
    if args.config:
        config = ConfigManager.load_from_yaml(args.config)

    setup = config.get("setup", {})
    fiscal_year: str = args.fiscal_year or setup.get("fiscal_year", "")
    quarter: str = args.quarter or setup.get("quarter", "")
    data_dir: str = args.data_dir or setup.get("data_dir", "/app/data")
    log_level: str = args.log_level or config.get("processor", {}).get(
        "log_level", "INFO"
    )
    log_dir: str = config.get("paths", {}).get("log_output", "/app/data/logs")

    logger = create_logger("setup_directories", log_dir, log_level)

    if not fiscal_year or not quarter:
        logger.error(
            "fiscal_year and quarter are required — use --fiscal-year / --quarter or a config YAML."
        )
        return 1

    base = Path(data_dir) / fiscal_year / quarter

    logger.log_header("SETUP DIRECTORIES v1.0")
    logger.info(f"Base path   : {base}")
    logger.info(f"Fiscal year : {fiscal_year}")
    logger.info(f"Quarter     : {quarter}")
    logger.info(f"Directories : {len(DIRECTORY_TREE)}")

    created = 0
    existing = 0
    errors = 0

    for rel_path in DIRECTORY_TREE:
        full_path = base / rel_path
        try:
            if full_path.exists():
                logger.debug(f"  Already exists : {rel_path}")
                existing += 1
            else:
                full_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"  Created        : {rel_path}")
                created += 1
        except OSError as exc:
            logger.error(f"  Failed         : {rel_path} — {exc}")
            errors += 1

    logger.info(
        f"Complete — {created} created, {existing} already existed"
        + (f", {errors} error(s)." if errors else ".")
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
