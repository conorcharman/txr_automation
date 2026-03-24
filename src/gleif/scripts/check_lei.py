#!/usr/bin/env python3
"""
GLEIF LEI Check CLI
===================

Command-line tool for LEI validation and entity name lookups against the
local GLEIF Golden Copy SQLite cache.

Usage:
    # Validate a single LEI
    gleif-check --lei 5493001KJTIIGC8Y1R12

    # Validate a LEI with a trade date (LAPSED LEIs are valid before their renewal date)
    gleif-check --lei 5493001KJTIIGC8Y1R12 --date 2024-01-15

    # Search by entity name
    gleif-check --name "citibank" [--limit 10]

    # Batch: one or more CSV files (auto-detects 'lei' column)
    gleif-check --input trades.csv
    gleif-check --input a.csv b.csv c.csv

    # Batch: all CSVs in a directory
    gleif-check --input-dir data/trades/ [--pattern "*.csv"]

    # Also produce a merged output file with a 'source_file' column
    gleif-check --input-dir data/trades/ --output merged_lei_check.csv

    # Use a custom database location
    gleif-check --db /data/gleif_cache.db --input-dir data/trades/

    # Drive entirely from config/local/gleif_config.yaml (batch section):
    #
    #   batch:
    #     inputs:
    #       - data/trades/trades_2025-06-15.csv
    #     input_dir: data/trades/
    #     pattern: "*.csv"
    #     output: data/output/merged_lei_check.csv
    gleif-check
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
    yaml = None  # type: ignore[assignment]
    _YAML_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from gleif.cache import GleifCacheManager
from gleif.lookup import GleifLookup, LeiLookupResult

# Regex to extract YYYY-MM-DD from a filename
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Result column names appended to each output row
_COL_LEI_VALID = "lei_valid"
_COL_LEI_STATUS = "lei_status"
_COL_LEGAL_NAME = "legal_name"
_COL_LEI_REASON = "lei_reason"
_COL_ENTITY_CATEGORY = "entity_category"
_COL_LEGAL_ADDR_COUNTRY = "legal_address_country"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse YYYY-MM-DD string to a date object."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}' — expected YYYY-MM-DD format."
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate LEI codes and look up entity names using the local "
            "GLEIF Golden Copy cache."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    single = parser.add_argument_group("Single LEI / name check")
    single.add_argument(
        "--lei",
        type=str,
        default=None,
        help="20-character LEI code to validate.",
    )
    single.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Trade date for the validity check.  When provided, a LAPSED LEI is "
            "treated as valid if the trade occurred before the renewal deadline."
        ),
    )
    single.add_argument(
        "--name",
        type=str,
        default=None,
        help="Search for legal entities by name (full-text search).",
    )
    single.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results to return for --name search (default: 20).",
    )

    batch = parser.add_argument_group("Batch check (CSV)")
    batch.add_argument(
        "--input",
        type=Path,
        nargs="+",
        default=None,
        metavar="CSV_PATH",
        help=(
            "One or more input CSV files.  Each must contain a 'lei' column.  "
            "A 'trade_date' column is used when present; otherwise the date is "
            "extracted from the filename (YYYY-MM-DD pattern)."
        ),
    )
    batch.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory to scan for input CSV files.",
    )
    batch.add_argument(
        "--pattern",
        type=str,
        default="*.csv",
        metavar="GLOB",
        help="Glob pattern when using --input-dir (default: *.csv).",
    )
    batch.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help=(
            "Optional merged output CSV collecting results from all input files, "
            "with an added 'source_file' column."
        ),
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the SQLite cache database (default: data/gleif_cache.db).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a YAML config file.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Logging verbosity (default: WARNING).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    if not _YAML_AVAILABLE or not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _extract_date_from_filename(path: Path) -> Optional[date]:
    """Extract a trade date from a filename containing a YYYY-MM-DD pattern."""
    match = _DATE_PATTERN.search(path.stem)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _collect_input_paths(
    explicit: Optional[List[Path]],
    input_dir: Optional[Path],
    pattern: str,
) -> List[Path]:
    """Build a deduplicated, sorted list of input CSV paths."""
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
            if not p.stem.endswith("_lei_check"):
                _add(p)

    return paths


def _per_file_output_path(input_path: Path) -> Path:
    """Derive the per-file output path by inserting '_lei_check' before the extension."""
    return input_path.with_name(f"{input_path.stem}_lei_check{input_path.suffix}")


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def _detect_lei_column(fieldnames: List[str]) -> Optional[str]:
    """Find the LEI column name from a list of CSV field names.

    Accepts exact ``lei`` (case-insensitive) or common variations found in
    FCA incident file exports.

    Args:
        fieldnames: List of CSV header names.

    Returns:
        Matched column name, or ``None`` if not found.
    """
    priority = [
        "lei",
        "LEI",
        "Lei",
        "legal entity identifier",
        "Legal Entity Identifier",
    ]
    for candidate in priority:
        for name in fieldnames:
            if name.strip().lower() == candidate.lower():
                return name
    return None


def _detect_trade_date_column(fieldnames: List[str]) -> Optional[str]:
    """Find the trade date column name from a list of CSV field names."""
    for name in fieldnames:
        if name.strip().lower() in ("trade_date", "tradedate", "trading date"):
            return name
    return None


def _process_batch_file(
    input_path: Path,
    lookup: GleifLookup,
    output_path: Path,
    fallback_date: Optional[date] = None,
) -> Tuple[int, int]:
    """Read an input CSV, validate each LEI, write results to output CSV.

    Args:
        input_path: Path to the input CSV file.
        lookup: Initialised :class:`~gleif.lookup.GleifLookup`.
        output_path: Destination CSV path for the enriched results.
        fallback_date: Trade date to use when no ``trade_date`` column is
            found and no date was extracted from the filename.

    Returns:
        Tuple of ``(rows_processed, rows_skipped)``.
    """
    rows_processed = 0
    rows_skipped = 0

    with input_path.open(encoding="utf-8", newline="") as in_fh:
        reader = csv.DictReader(in_fh)
        if not reader.fieldnames:
            logger.warning("Input CSV has no headers: %s", input_path)
            return 0, 0

        lei_col = _detect_lei_column(list(reader.fieldnames))
        date_col = _detect_trade_date_column(list(reader.fieldnames))
        filename_date = _extract_date_from_filename(input_path)

        if lei_col is None:
            logger.warning(
                "No 'lei' column found in %s — skipping file", input_path.name
            )
            return 0, 0

        out_fieldnames = list(reader.fieldnames) + [
            _COL_LEI_VALID,
            _COL_LEI_STATUS,
            _COL_LEGAL_NAME,
            _COL_LEI_REASON,
            _COL_ENTITY_CATEGORY,
            _COL_LEGAL_ADDR_COUNTRY,
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8", newline="") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=out_fieldnames)
            writer.writeheader()

            for row in reader:
                lei_value = row.get(lei_col, "").strip()
                if not lei_value:
                    rows_skipped += 1
                    out_row = dict(row)
                    out_row.update({
                        _COL_LEI_VALID: "",
                        _COL_LEI_STATUS: "",
                        _COL_LEGAL_NAME: "",
                        _COL_LEI_REASON: "",
                        _COL_ENTITY_CATEGORY: "",
                        _COL_LEGAL_ADDR_COUNTRY: "",
                    })
                    writer.writerow(out_row)
                    continue

                # Resolve trade date: column > filename > fallback
                trade_date: Optional[date] = None
                if date_col and row.get(date_col, "").strip():
                    raw_date = row[date_col].strip()[:10]
                    try:
                        trade_date = date.fromisoformat(raw_date)
                    except ValueError:
                        pass
                if trade_date is None:
                    trade_date = filename_date or fallback_date

                result: LeiLookupResult = lookup.lookup_lei(lei_value, trade_date)

                out_row = dict(row)
                out_row.update({
                    _COL_LEI_VALID: "Y" if result.is_valid else "N",
                    _COL_LEI_STATUS: result.registration_status,
                    _COL_LEGAL_NAME: result.legal_name,
                    _COL_LEI_REASON: result.reason,
                    _COL_ENTITY_CATEGORY: result.entity_category,
                    _COL_LEGAL_ADDR_COUNTRY: result.legal_address_country,
                })
                writer.writerow(out_row)
                rows_processed += 1

    return rows_processed, rows_skipped


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the gleif-check console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # --- Resolve config -------------------------------------------------
    _DEFAULT_CONFIG = _REPO_ROOT / "config" / "local" / "gleif_config.yaml"
    config_path: Optional[Path] = args.config or (
        _DEFAULT_CONFIG if _DEFAULT_CONFIG.exists() else None
    )
    cfg: Dict[str, Any] = _load_yaml_config(config_path) if config_path else {}
    batch_cfg: Dict[str, Any] = cfg.get("batch", {})

    # --- Resolve DB path ------------------------------------------------
    db_path: Path = args.db or _REPO_ROOT / "data" / "gleif_cache.db"
    if args.db is None and (cfg.get("database") or {}).get("path"):
        raw = cfg["database"]["path"]
        db_path = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    if not db_path.exists():
        print(
            f"Error: GLEIF cache database not found at '{db_path}'.\n"
            "Run 'gleif-refresh --type full' to build the cache first.",
            file=sys.stderr,
        )
        sys.exit(1)

    cache = GleifCacheManager(db_path=db_path)
    cache.initialise_db()
    lookup = GleifLookup(cache=cache)

    # ====================================================================
    # Single LEI check
    # ====================================================================
    if args.lei:
        result = lookup.lookup_lei(args.lei.strip().upper(), args.date)
        print(f"\nLEI Validation Result")
        print(f"{'─' * 40}")
        print(f"  LEI              : {result.lei}")
        print(f"  Valid            : {'Yes' if result.is_valid else 'No'}")
        print(f"  Reason           : {result.reason}")
        print(f"  Legal name       : {result.legal_name or '(not found)'}")
        print(f"  Reg. status      : {result.registration_status or '─'}")
        print(f"  Entity status    : {result.entity_status or '─'}")
        print(f"  Entity category  : {result.entity_category or '─'}")
        print(f"  Country          : {result.legal_address_country or '─'}")
        print(f"  Next renewal     : {result.next_renewal_date or '─'}")
        if result.successor_lei:
            print(f"  Successor LEI    : {result.successor_lei}")
        if args.date:
            print(f"  Trade date       : {args.date}")
        print()
        sys.exit(0 if result.is_valid else 1)

    # ====================================================================
    # Name search
    # ====================================================================
    if args.name:
        results = lookup.search_by_name(args.name, limit=args.limit)
        if not results:
            print(f"No results found for name: {args.name!r}")
            sys.exit(0)
        print(f"\nName search results for {args.name!r} ({len(results)} found):")
        print(f"{'LEI':<22} {'Status':<10} {'Country':<8} Name")
        print("─" * 80)
        for row in results:
            print(
                f"{row.get('lei', ''):<22} "
                f"{row.get('registration_status', ''):<10} "
                f"{row.get('legal_address_country', ''):<8} "
                f"{row.get('legal_name', '')}"
            )
        print()
        sys.exit(0)

    # ====================================================================
    # Batch check
    # ====================================================================
    # Resolve batch inputs: CLI flags > config
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

    pattern: str = args.pattern or batch_cfg.get("pattern", "*.csv")

    output: Optional[Path] = args.output
    if output is None and batch_cfg.get("output"):
        raw = batch_cfg["output"]
        output = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    input_paths = _collect_input_paths(explicit_inputs, input_dir, pattern)

    if not input_paths:
        parser_ref = argparse.ArgumentParser()
        parser_ref.error(
            "No input files found.  Provide --lei, --name, --input, or --input-dir."
        )
        sys.exit(1)

    # Per-file processing
    merged_rows: List[Dict[str, Any]] = []
    total_processed = 0
    total_skipped = 0

    for input_path in input_paths:
        if not input_path.exists():
            print(f"WARNING: Input file not found: {input_path}", file=sys.stderr)
            continue

        per_file_out = _per_file_output_path(input_path)
        rows_p, rows_s = _process_batch_file(
            input_path=input_path,
            lookup=lookup,
            output_path=per_file_out,
        )
        total_processed += rows_p
        total_skipped += rows_s
        print(
            f"  {input_path.name}: {rows_p} rows processed -> {per_file_out.name}"
        )

        # Collect for merged output
        if output:
            with per_file_out.open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    row["source_file"] = input_path.name
                    merged_rows.append(row)

    print(f"\nTotal: {total_processed} rows processed, {total_skipped} skipped")

    # Write merged output if requested
    if output and merged_rows:
        output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(merged_rows[0].keys())
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merged_rows)
        print(f"Merged output written to: {output}")


if __name__ == "__main__":
    main()
