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

    # Batch: one or more CSV files (trade date extracted from filename DD-MM-YYYY if absent in file)
    python -m firds.scripts.check_reportability --input trades_15-03-2026.csv
    python -m firds.scripts.check_reportability --input a.csv b.csv c.csv

    # Batch: all CSVs in a directory
    python -m firds.scripts.check_reportability --input-dir data/trades/ --pattern "*.csv"

    # Also write a single merged output collecting all files
    python -m firds.scripts.check_reportability --input-dir data/trades/ --output merged.csv

    # Drive entirely from config/local/firds_config.yaml (batch section):
    #
    #   batch:
    #     inputs:
    #       - data/trades/trades_15-03-2026.csv
    #       - data/trades/trades_16-03-2026.csv
    #     input_dir: data/trades/
    #     pattern: "*.csv"
    #     output: data/output/merged_reportability.csv
    python -m firds.scripts.check_reportability

    # Use a custom database location
    python -m firds.scripts.check_reportability --db /data/firds_cache.db --input-dir data/trades/
"""

import argparse
import csv
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from firds.cache import FirdsCacheManager
from firds.reportability import FirdsReportabilityChecker, ReportabilityResult, ReportabilityReason

# Regex to find DD-MM-YYYY anywhere in a filename stem
_DATE_PATTERN = re.compile(r"\b(\d{2}-\d{2}-\d{4})\b")

# Result column names appended to each output row
_COL_IS_REPORTABLE = "is_reportable"
_COL_REASON = "reportability_reason"
_COL_MATCHED_MICS = "matched_mics"


def _canonical_header(value: str) -> str:
    """Return a canonical header token for resilient column matching.

    Normalises casing, trims whitespace, strips UTF-8 BOM, and collapses
    internal spacing/underscores so variants like "Instrument ID",
    " instrument_id ", and "INSTRUMENT   ID" compare equally.

    Args:
        value: Raw CSV header value.

    Returns:
        Canonicalised header token.
    """
    token = (value or "").replace("\ufeff", "").strip().lower()
    token = " ".join(token.replace("_", " ").split())
    return token


def _resolve_column(fieldnames: List[str], aliases: List[str]) -> Optional[str]:
    """Resolve a CSV column by canonical aliases.

    Args:
        fieldnames: Raw header names from CSV.
        aliases: Accepted alias names for the same semantic column.

    Returns:
        The original matching header name, preserving exact token for DictReader.
    """
    canonical_map = {_canonical_header(name): name for name in fieldnames}
    for alias in aliases:
        match = canonical_map.get(_canonical_header(alias))
        if match:
            return match
    return None

logger = logging.getLogger(__name__)


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
        nargs="+",
        default=None,
        metavar="CSV_PATH",
        help=(
            "One or more input CSV files.  Each must contain an 'isin' column.  "
            "A 'trade_date' column is used when present; otherwise the date is "
            "extracted from the filename (DD-MM-YYYY pattern)."
        ),
    )
    batch.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory to scan for input CSV files (combined with --pattern).",
    )
    batch.add_argument(
        "--pattern",
        type=str,
        default="*.csv",
        metavar="GLOB",
        help="Glob pattern used with --input-dir (default: *.csv).",
    )
    batch.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help=(
            "Optional merged output CSV collecting results from all input files, "
            "with an added 'source_file' column.  Each input file also produces a "
            "per-file '_reportability' output automatically alongside the original."
        ),
    )

    # Common options
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the SQLite cache database.  Defaults to the path in "
            "config/local/firds_config.yaml, or data/firds_cache.db if no config is found."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a YAML config file.  Defaults to config/local/firds_config.yaml "
            "if that file exists."
        ),
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


def _extract_date_from_filename(path: Path) -> Optional[date]:
    """Extract a trade date from a filename containing a DD-MM-YYYY pattern.

    Args:
        path: Path whose stem is scanned for a date.

    Returns:
        Parsed :class:`~datetime.date`, or ``None`` if no match is found.
    """
    match = _DATE_PATTERN.search(path.stem)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d-%m-%Y").date()
    except ValueError:
        return None


def _collect_input_paths(
    explicit: Optional[List[Path]],
    input_dir: Optional[Path],
    pattern: str,
) -> List[Path]:
    """Build a deduplicated, sorted list of input CSV paths.

    Args:
        explicit: Files passed via ``--input``, or ``None``.
        input_dir: Directory passed via ``--input-dir``, or ``None``.
        pattern: Glob pattern for ``input_dir`` (e.g. ``*.csv``).

    Returns:
        Ordered list of :class:`~pathlib.Path` objects with no duplicates.
    """
    seen: set = set()
    paths: List[Path] = []

    def _add(p: Path) -> None:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            paths.append(p)

    if explicit:
        for p in explicit:
            _add(p)
    if input_dir:
        for p in sorted(input_dir.glob(pattern)):
            # Never re-process files that were produced by a previous run
            if not p.stem.endswith("_reportability"):
                _add(p)

    return paths


def _per_file_output_path(input_path: Path) -> Path:
    """Derive the per-file output path by inserting '_reportability' before the extension.

    For example, ``trades_15-03-2026.csv`` → ``trades_15-03-2026_reportability.csv``.

    Args:
        input_path: Path to the input CSV.

    Returns:
        Output path in the same directory as the input.
    """
    return input_path.with_name(f"{input_path.stem}_reportability{input_path.suffix}")


def main() -> None:
    """Entry point for the firds-check console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # --- Resolve config -------------------------------------------------
    _DEFAULT_CONFIG = _REPO_ROOT / "config" / "local" / "firds_config.yaml"
    config_path: Optional[Path] = args.config or (_DEFAULT_CONFIG if _DEFAULT_CONFIG.exists() else None)
    cfg: Dict[str, Any] = _load_yaml_config(config_path) if config_path else {}
    batch_cfg: Dict[str, Any] = cfg.get("batch", {})

    # --- Resolve DB path: CLI flag > config > default -------------------
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

    # --- If --isin is provided, skip batch resolution and run single ---
    if args.isin:
        if not args.date:
            print(
                "Error: --date is required for a single instrument check.",
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
        return

    # --- Resolve batch inputs: CLI flags take precedence over config ----
    explicit_inputs: Optional[List[Path]] = args.input
    if explicit_inputs is None and batch_cfg.get("inputs"):
        explicit_inputs = [
            Path(p) if Path(p).is_absolute() else _REPO_ROOT / p
            for p in batch_cfg["inputs"]
        ]

    input_dir: Optional[Path] = args.input_dir
    if input_dir is None and batch_cfg.get("input_dir"):
        raw = batch_cfg["input_dir"]
        input_dir = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    pattern: str = args.pattern
    if pattern == "*.csv" and batch_cfg.get("pattern"):
        pattern = batch_cfg["pattern"]

    merged_output: Optional[Path] = args.output
    if merged_output is None and batch_cfg.get("output"):
        raw = batch_cfg["output"]
        merged_output = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    input_paths = _collect_input_paths(explicit_inputs, input_dir, pattern)

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------
    if input_paths:
        all_rows: List[dict] = []
        total_files = len(input_paths)
        skipped_files = 0

        for input_path in input_paths:
            if not input_path.exists():
                print(f"Warning: Input file not found, skipping: {input_path}", file=sys.stderr)
                skipped_files += 1
                continue

            file_date = _extract_date_from_filename(input_path)
            per_file_out = _per_file_output_path(input_path)

            rows, row_count, error_count = _process_file(checker, input_path, file_date)

            if rows is None:
                skipped_files += 1
                continue

            _write_csv(rows, per_file_out)
            reportable = sum(1 for r in rows if r.get(_COL_IS_REPORTABLE) == "Y")
            print(
                f"{input_path.name}: {row_count} rows checked, "
                f"{reportable} reportable, "
                f"{row_count - reportable - error_count} not reportable, "
                f"{error_count} errors \u2192 {per_file_out.name}"
            )

            if merged_output is not None:
                for row in rows:
                    row["source_file"] = input_path.name
                all_rows.extend(rows)

        if merged_output is not None and all_rows:
            if merged_output.is_dir():
                print(
                    f"Error: --output path '{merged_output}' is a directory. "
                    "Please supply a full file path including a .csv filename "
                    "(e.g. data/output/results.csv).",
                    file=sys.stderr,
                )
            else:
                merged_output.parent.mkdir(parents=True, exist_ok=True)
                _write_csv(all_rows, merged_output)
                print(f"\nMerged output ({len(all_rows)} rows) written to: {merged_output}")

        if skipped_files:
            print(
                f"\n{skipped_files} of {total_files} file(s) were skipped due to errors.",
                file=sys.stderr,
            )
        return

    # No batch inputs and no --isin: nothing to do
    print(
        "Error: --isin and --date are required for a single instrument check.\n"
        "       Use --input or --input-dir for batch mode.",
        file=sys.stderr,
    )
    sys.exit(1)


def _process_file(
    checker: FirdsReportabilityChecker,
    input_path: Path,
    file_date: Optional[date],
) -> Tuple[Optional[List[dict]], int, int]:
    """Process a single CSV file and return annotated rows.

    The trade date for each row is resolved in this order:

    1. ``trade_date`` column in the CSV row.
    2. ``file_date`` extracted from the filename.

    If neither is available the file is skipped entirely.

    Args:
        checker: Configured reportability checker.
        input_path: Path to the input CSV.
        file_date: Trade date extracted from the filename, or ``None``.

    Returns:
        Tuple of ``(rows, row_count, error_count)``.  ``rows`` is ``None``
        if the file could not be read at all (e.g. missing required headers).
    """
    rows: List[dict] = []
    row_count = 0
    error_count = 0

    try:
        fh = input_path.open(encoding="utf-8", newline="")
    except OSError as exc:
        print(f"Error: Cannot open '{input_path}': {exc}", file=sys.stderr)
        return None, 0, 0

    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            print(f"Error: '{input_path.name}' has no headers — skipping.", file=sys.stderr)
            return None, 0, 0

        fieldnames = list(reader.fieldnames)

        isin_col = _resolve_column(
            fieldnames,
            ["isin", "instrument id", "instrument identifier", "instrumentid"],
        )
        date_col = _resolve_column(
            fieldnames,
            ["trade_date", "trade date", "transaction date"],
        )
        mic_col = _resolve_column(
            fieldnames,
            ["mic", "trading venue", "venue"],
        )

        if isin_col and _canonical_header(isin_col) != "isin":
            logger.info(
                "Resolved ISIN column alias %r in file %s.",
                isin_col,
                input_path.name,
            )
        if date_col and _canonical_header(date_col) != "trade date":
            logger.info(
                "Resolved trade date column alias %r in file %s.",
                date_col,
                input_path.name,
            )

        if not isin_col:
            print(
                f"Error: '{input_path.name}' has no recognised ISIN column — skipping. "
                "Accepted aliases: isin, instrument id, instrument identifier.",
                file=sys.stderr,
            )
            logger.error("Available headers for %s: %s", input_path.name, fieldnames)
            return None, 0, 0

        if date_col is None and file_date is None:
            print(
                f"Error: '{input_path.name}' has no recognised trade date column and no "
                "DD-MM-YYYY date could be found in the filename — skipping.",
                file=sys.stderr,
            )
            logger.error("Available headers for %s: %s", input_path.name, fieldnames)
            return None, 0, 0

        for row in reader:
            row_count += 1
            isin = row[isin_col].strip()
            mic = row[mic_col].strip() if mic_col else None

            # Resolve trade date: column in file takes priority over filename
            if date_col:
                trade_date_str = row[date_col].strip()
                try:
                    trade_date: Optional[date] = _parse_date(trade_date_str)
                except (argparse.ArgumentTypeError, ValueError):
                    row[_COL_IS_REPORTABLE] = "ERROR"
                    row[_COL_REASON] = f"Invalid trade_date: {trade_date_str}"
                    row[_COL_MATCHED_MICS] = ""
                    rows.append(row)
                    error_count += 1
                    continue
            else:
                trade_date = file_date  # guaranteed non-None by header check above

            result = checker.is_reportable(isin=isin, trade_date=trade_date, mic=mic)
            row[_COL_IS_REPORTABLE] = "Y" if result.is_reportable else "N"
            row[_COL_REASON] = result.reason
            row[_COL_MATCHED_MICS] = "|".join(result.matched_mics)
            rows.append(row)

    return rows, row_count, error_count


def _write_csv(rows: List[dict], output_path: Path) -> None:
    """Write a list of row dicts to a CSV file.

    Args:
        rows: Row dicts to write; fieldnames are taken from the first row.
        output_path: Destination path.
    """
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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
    """Parse a date string into a :class:`~datetime.date`.

    Accepts both ``YYYY-MM-DD`` and ``DD/MM/YYYY`` formats.

    Args:
        value: Date string in YYYY-MM-DD or DD/MM/YYYY format.

    Returns:
        Parsed :class:`~datetime.date`.

    Raises:
        argparse.ArgumentTypeError: If the string cannot be parsed.
    """
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM-DD or DD/MM/YYYY format."
        )


if __name__ == "__main__":
    main()
