#!/usr/bin/env python3
"""
FIRDS Reportability Check CLI
==============================

Command-line tool for ad-hoc instrument reportability lookups against the
local FCA FIRDS SQLite cache.

Usage:
    # Check a single instrument with MIC
    python -m firds.scripts.check_reportability --isin GB00B3RBWM25 --mic XLON --date 2025-06-15

    # Check without a specific venue (any active venue)
    python -m firds.scripts.check_reportability --isin GB00B3RBWM25 --date 2025-06-15

    # Batch check from a CSV file (columns: isin, mic, trade_date)
    python -m firds.scripts.check_reportability --input trades.csv --output results.csv

    # Use a custom database location
    python -m firds.scripts.check_reportability --isin US0378331005 --date 2025-01-10 --db /data/firds_cache.db
"""

import argparse
import csv
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from firds.cache import FirdsCacheManager
from firds.reportability import FirdsReportabilityChecker, ReportabilityResult


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether financial instruments are reportable using the local FIRDS cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Single instrument mode
    single = parser.add_argument_group("Single instrument check")
    single.add_argument("--isin", type=str, help="Instrument ISIN code.")
    single.add_argument(
        "--mic",
        type=str,
        default=None,
        help="ISO 10383 Market Identifier Code (MIC) of the trading venue. "
             "If omitted, checks across all venues.",
    )
    single.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Trade date for the reportability check.",
    )

    # Batch mode
    batch = parser.add_argument_group("Batch check (CSV)")
    batch.add_argument(
        "--input",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help="Input CSV file with columns: isin, trade_date[, mic].",
    )
    batch.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help="Output CSV file path for batch results.",
    )

    # Common options
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the SQLite cache database. Defaults to the path in "
             "config/local/firds_config.yaml, or data/firds_cache.db if no config is found.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a YAML config file. Defaults to config/local/firds_config.yaml "
             "if that file exists.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Logging verbosity (default: WARNING).",
    )
    return parser.parse_args()


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load a YAML config file and return its contents as a dict.

    Args:
        config_path: Path to the YAML file.

    Returns:
        Parsed configuration dictionary, or an empty dict if loading fails.
    """
    if not _YAML_AVAILABLE:
        return {}
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def main() -> None:
    """Entry point for the firds-check console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # --- Resolve DB path: explicit flag > config file > hardcoded default ---
    _DEFAULT_CONFIG = _REPO_ROOT / "config" / "local" / "firds_config.yaml"
    config_path: Optional[Path] = args.config or (_DEFAULT_CONFIG if _DEFAULT_CONFIG.exists() else None)
    cfg: Dict[str, Any] = _load_yaml_config(config_path) if config_path else {}

    db_path: Path = args.db or _REPO_ROOT / "data" / "firds_cache.db"
    if args.db is None and cfg.get("database", {}).get("path"):
        db_path = Path(cfg["database"]["path"])
        if not db_path.is_absolute():
            db_path = _REPO_ROOT / db_path

    if not db_path.exists():
        print(
            f"Error: FIRDS cache database not found at '{db_path}'.\n"
            "Run 'firds-refresh --type full' to build the cache first.",
            file=sys.stderr,
        )
        sys.exit(1)

    cache = FirdsCacheManager(db_path=db_path)
    cache.initialise_db()
    checker = FirdsReportabilityChecker(cache=cache)

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------
    if args.input:
        if args.output is None:
            print("Error: --output is required when using --input.", file=sys.stderr)
            sys.exit(1)
        _run_batch(checker, args.input, args.output)
        return

    # ------------------------------------------------------------------
    # Single mode
    # ------------------------------------------------------------------
    if not args.isin or not args.date:
        print(
            "Error: --isin and --date are required for a single instrument check.\n"
            "       Use --input for batch mode.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = checker.is_reportable(
        isin=args.isin,
        trade_date=args.date,
        mic=args.mic,
    )
    _print_result(result)

    if not result.is_reportable:
        sys.exit(2)


def _run_batch(
    checker: FirdsReportabilityChecker,
    input_path: Path,
    output_path: Path,
) -> None:
    """Run reportability checks for every row in a CSV file.

    Expected CSV columns (case-insensitive header): ``isin``, ``trade_date``,
    and optionally ``mic``.  All other columns are passed through to the output.

    Args:
        checker: Configured :class:`~firds.reportability.FirdsReportabilityChecker`.
        input_path: Path to the input CSV.
        output_path: Path where the results CSV will be written.
    """
    results: List[dict] = []
    row_count = 0
    error_count = 0

    with input_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            print("Error: Input CSV has no headers.", file=sys.stderr)
            sys.exit(1)

        # Normalise column names to lowercase for lookup
        fieldnames_lower = {name.lower(): name for name in reader.fieldnames}

        isin_col = fieldnames_lower.get("isin")
        date_col = fieldnames_lower.get("trade_date")
        mic_col = fieldnames_lower.get("mic")

        if not isin_col or not date_col:
            print(
                "Error: Input CSV must contain 'isin' and 'trade_date' columns.",
                file=sys.stderr,
            )
            sys.exit(1)

        for row in reader:
            row_count += 1
            isin = row[isin_col].strip()
            mic = row[mic_col].strip() if mic_col else None
            trade_date_str = row[date_col].strip()

            try:
                trade_date = _parse_date(trade_date_str)
            except (argparse.ArgumentTypeError, ValueError):
                row["is_reportable"] = "ERROR"
                row["reportability_reason"] = f"Invalid trade_date: {trade_date_str}"
                row["matched_mics"] = ""
                results.append(row)
                error_count += 1
                continue

            result = checker.is_reportable(isin=isin, trade_date=trade_date, mic=mic)
            row["is_reportable"] = "Y" if result.is_reportable else "N"
            row["reportability_reason"] = result.reason
            row["matched_mics"] = "|".join(result.matched_mics)
            results.append(row)

    if not results:
        print("No rows found in input file.")
        return

    output_fieldnames = list(results[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(results)

    reportable = sum(1 for r in results if r["is_reportable"] == "Y")
    print(
        f"Batch complete: {row_count} rows checked, "
        f"{reportable} reportable, "
        f"{row_count - reportable - error_count} not reportable, "
        f"{error_count} errors. "
        f"Output written to: {output_path}"
    )


def _print_result(result: ReportabilityResult) -> None:
    """Print a single reportability result to stdout.

    Args:
        result: :class:`~firds.reportability.ReportabilityResult` to display.
    """
    from firds.reportability import ReportabilityReason

    if result.reason == ReportabilityReason.ACTIVE_OTHER_VENUE:
        alternatives = ", ".join(result.matched_mics)
        status = f"REPORTABLE \u2014 {result.mic} not active, try: {alternatives}"
    elif result.is_reportable:
        status = "REPORTABLE"
    else:
        status = "NOT REPORTABLE"
    print(f"\nResult:       {status}")
    print(f"ISIN:         {result.isin}")
    print(f"Trade date:   {result.trade_date}")
    if result.mic:
        print(f"MIC:          {result.mic}")
    print(f"Reason:       {result.reason}")
    if result.matched_mics:
        print(f"Active MICs:  {', '.join(result.matched_mics)}")
    print()


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a :class:`~datetime.date`.

    Args:
        value: Date string in YYYY-MM-DD format.

    Returns:
        Parsed :class:`~datetime.date`.

    Raises:
        argparse.ArgumentTypeError: If the string cannot be parsed.
    """
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM-DD format."
        )


if __name__ == "__main__":
    main()
