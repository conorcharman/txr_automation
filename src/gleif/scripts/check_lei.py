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

# Strips characters that are special in FTS5 syntax (parentheses, colons, etc.)
# so they cannot corrupt a prefix query built from user-supplied name strings.
_FTS5_SPECIAL_CHARS = re.compile(r"[^\w\s]", re.UNICODE)

# Common company-suffix abbreviations and their full registered-name equivalents.
# Patterns are word-boundary anchored and treat a trailing period as optional so
# that both "Ltd" and "Ltd." are expanded.  Applied in _normalise_company_suffixes.
_SUFFIX_EXPANSIONS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bLtd\.?(?!\w)",   re.IGNORECASE), "Limited"),
    (re.compile(r"\bCorp\.?(?!\w)",  re.IGNORECASE), "Corporation"),
    (re.compile(r"\bInc\.?(?!\w)",   re.IGNORECASE), "Incorporated"),
    (re.compile(r"\bBros\.?(?!\w)",  re.IGNORECASE), "Brothers"),
    (re.compile(r"\bIntl\.?(?!\w)",  re.IGNORECASE), "International"),
    (re.compile(r"\bMgmt\.?(?!\w)",  re.IGNORECASE), "Management"),
    (re.compile(r"\bSvcs\.?(?!\w)",  re.IGNORECASE), "Services"),
    (re.compile(r"\bSvc\.?(?!\w)",   re.IGNORECASE), "Services"),
    (re.compile(r"\bGrp\.?(?!\w)",   re.IGNORECASE), "Group"),
    (re.compile(r"\bHldgs\.?(?!\w)", re.IGNORECASE), "Holdings"),
    (re.compile(r"\bHldg\.?(?!\w)",  re.IGNORECASE), "Holding"),
    (re.compile(r"\bMfg\.?(?!\w)",   re.IGNORECASE), "Manufacturing"),
    (re.compile(r"\bAssoc\.?(?!\w)", re.IGNORECASE), "Association"),
    (re.compile(r"\bAssn\.?(?!\w)",  re.IGNORECASE), "Association"),
]

# Result column names appended to each output row — LEI validation mode
_COL_LEI_VALID = "lei_valid"
_COL_LEI_STATUS = "lei_status"
_COL_LEGAL_NAME = "legal_name"
_COL_LEI_REASON = "lei_reason"
_COL_ENTITY_CATEGORY = "entity_category"
_COL_LEGAL_ADDR_COUNTRY = "legal_address_country"

# Result column names appended in name-match mode
_COL_NAME_MATCH_LEI = "name_match_lei"
_COL_NAME_MATCH_LEGAL_NAME = "name_match_legal_name"
_COL_NAME_MATCH_STATUS = "name_match_status"
_COL_NAME_MATCH_COUNTRY = "name_match_country"
_COL_NAME_MATCH_SCORE = "name_match_score"

_PRIORITY_COUNTRY = "GB"


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
    batch.add_argument(
        "--name-column",
        type=str,
        default=None,
        metavar="COLUMN",
        help=(
            "Name of the column containing entity names for name-based matching. "
            "When set, the script uses name-match mode instead of LEI validation. "
            "Without this flag, auto-detection is attempted on common column names: "
            "legal_name, entity_name, name, company_name, counterparty_name."
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


def _detect_name_column(fieldnames: List[str]) -> Optional[str]:
    """Find the entity name column from a list of CSV field names.

    Accepts common column names used in counterparty and transaction files.

    Args:
        fieldnames: List of CSV header names.

    Returns:
        Matched column name, or ``None`` if not found.
    """
    candidates = {
        "legal_name",
        "entity_name",
        "name",
        "company_name",
        "counterparty_name",
    }
    for field in fieldnames:
        if field.strip().lower() in candidates:
            return field
    return None


def _normalise_company_suffixes(name: str) -> str:
    """Expand common company suffix abbreviations to their full registered forms.

    For example ``"Retail Book Ltd"`` becomes ``"Retail Book Limited"`` so that
    a subsequent phrase or prefix FTS5 search can match official GLEIF records
    that use the full legal-name spelling.

    Args:
        name: Raw entity name string from the input CSV.

    Returns:
        Name with known abbreviations replaced by their full equivalents.
        Returns the original string unchanged when no abbreviations are found.
    """
    result = name
    for pattern, replacement in _SUFFIX_EXPANSIONS:
        result = pattern.sub(replacement, result)
    return result.strip()


def _search_name_with_fallback(
    lookup: GleifLookup,
    name_value: str,
    limit: int = 1,
) -> Tuple[List[Dict], str]:
    """Search the GLEIF cache by entity name with a phrase-to-prefix fallback.

    Normalises company suffix abbreviations first (e.g. ``Ltd`` → ``Limited``)
    so that the primary searches are performed against the full registered-name
    spelling stored in GLEIF.  This ensures that a query for "Zeus Capital Ltd"
    reaches "ZEUS CAPITAL LIMITED" before a lower-quality prefix match on the
    abbreviation "Ltd." in an unrelated record.

    Search order:
    1. Phrase search on the normalised form (GB results promoted).
    2. Prefix search on the normalised form (GB results promoted).
    3. If normalisation changed the query: phrase search on the original form.
    4. If normalisation changed the query: prefix search on the original form.

    Args:
        lookup: Initialised :class:`~gleif.lookup.GleifLookup`.
        name_value: Entity name string to search for.
        limit: Maximum number of results to return (default: 1).

    Returns:
        Tuple of ``(results_list, score_string)`` where *score_string* is one
        of ``"1_PHRASE"``, ``"1_PREFIX"``, ``"1_PHRASE_NORM"``,
        ``"1_PREFIX_NORM"``, or ``"NO_MATCH"``.  *results_list* is empty when
        no match is found.
    """
    if not name_value.strip():
        return [], "NO_MATCH"

    normalised = _normalise_company_suffixes(name_value)
    is_normalised = normalised != name_value
    phrase_score = "1_PHRASE_NORM" if is_normalised else "1_PHRASE"
    prefix_score = "1_PREFIX_NORM" if is_normalised else "1_PREFIX"

    # Step 1: phrase search on normalised form (GB results promoted first)
    results = lookup.search_by_name(normalised, limit=limit, priority_country=_PRIORITY_COUNTRY)
    if results:
        return results, phrase_score

    # Step 2: prefix search on normalised form
    safe = _FTS5_SPECIAL_CHARS.sub(" ", normalised).strip()
    words = safe.split()
    if not words:
        return [], "NO_MATCH"
    prefix_query = " ".join(w + "*" for w in words)
    results = lookup.search_by_name(prefix_query, limit=limit, raw_query=True, priority_country=_PRIORITY_COUNTRY)
    if results:
        return results, prefix_score

    # Steps 3 & 4: retry with the original (un-normalised) form when the query
    # was changed by suffix expansion — catches entities whose official registered
    # name itself uses abbreviations (e.g. "Smith Consulting Ltd." in GLEIF).
    if is_normalised:
        results = lookup.search_by_name(name_value, limit=limit, priority_country=_PRIORITY_COUNTRY)
        if results:
            return results, "1_PHRASE"

        safe_raw = _FTS5_SPECIAL_CHARS.sub(" ", name_value).strip()
        words_raw = safe_raw.split()
        if words_raw:
            prefix_raw = " ".join(w + "*" for w in words_raw)
            results = lookup.search_by_name(prefix_raw, limit=limit, raw_query=True, priority_country=_PRIORITY_COUNTRY)
            if results:
                return results, "1_PREFIX"

    return [], "NO_MATCH"


def _process_batch_file(
    input_path: Path,
    lookup: GleifLookup,
    output_path: Path,
    fallback_date: Optional[date] = None,
    name_column: Optional[str] = None,
) -> Tuple[int, int]:
    """Read an input CSV, validate each LEI or match entity names, and write results.

    When the CSV has a LEI column, each row is validated against the GLEIF
    cache (existing behaviour).  When the CSV has a name column instead,
    each row is matched by name using FTS5 phrase search with a prefix
    fallback.  If both columns are present, LEI validation takes precedence
    and a warning is printed.

    Args:
        input_path: Path to the input CSV file.
        lookup: Initialised :class:`~gleif.lookup.GleifLookup`.
        output_path: Destination CSV path for the enriched results.
        fallback_date: Trade date to use when no ``trade_date`` column is
            found and no date was extracted from the filename.
        name_column: Override for the entity name column.  When ``None``,
            auto-detection via :func:`_detect_name_column` is attempted.

    Returns:
        Tuple of ``(rows_processed, rows_skipped)``.
    """
    rows_processed = 0
    rows_skipped = 0

    with input_path.open(encoding="utf-8-sig", newline="") as in_fh:
        reader = csv.DictReader(in_fh)
        if not reader.fieldnames:
            logger.warning("Input CSV has no headers: %s", input_path)
            return 0, 0

        fieldnames = list(reader.fieldnames)
        lei_col = _detect_lei_column(fieldnames)
        date_col = _detect_trade_date_column(fieldnames)
        filename_date = _extract_date_from_filename(input_path)

        # Resolve name column: explicit override → auto-detect
        resolved_name_col: Optional[str] = None
        if name_column:
            if name_column in fieldnames:
                resolved_name_col = name_column
            else:
                print(
                    f"WARNING: Specified --name-column '{name_column}' not found "
                    f"in {input_path.name} — attempting auto-detection.",
                    file=sys.stderr,
                )
                resolved_name_col = _detect_name_column(fieldnames)
        else:
            resolved_name_col = _detect_name_column(fieldnames)

        # Determine processing mode
        if lei_col is not None and resolved_name_col is not None:
            print(
                f"INFO: Both LEI column ('{lei_col}') and name column "
                f"('{resolved_name_col}') found in {input_path.name}. "
                f"Using LEI validation mode; name column will be ignored.",
                file=sys.stderr,
            )
            resolved_name_col = None  # force LEI mode

        if lei_col is None and resolved_name_col is None:
            available = ", ".join(fieldnames[:10])
            print(
                f"WARNING: No LEI or name column found in {input_path.name} — skipping.\n"
                f"  Detected columns: {available}\n"
                f"  LEI mode expects a column named 'lei', 'LEI', or "
                f"'Legal Entity Identifier'.\n"
                f"  Name mode expects a column named 'legal_name', 'entity_name', "
                f"'name', 'company_name', or 'counterparty_name'.\n"
                f"  Use --name-column <COLUMN> to specify a custom name column.",
                file=sys.stderr,
            )
            return 0, 0

        # ----------------------------------------------------------------
        # LEI validation mode
        # ----------------------------------------------------------------
        if lei_col is not None:
            out_fieldnames = fieldnames + [
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

        # ----------------------------------------------------------------
        # Name-match mode
        # ----------------------------------------------------------------
        out_fieldnames = fieldnames + [
            _COL_NAME_MATCH_LEI,
            _COL_NAME_MATCH_LEGAL_NAME,
            _COL_NAME_MATCH_STATUS,
            _COL_NAME_MATCH_COUNTRY,
            _COL_NAME_MATCH_SCORE,
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8", newline="") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=out_fieldnames)
            writer.writeheader()

            for row in reader:
                name_value = row.get(resolved_name_col, "").strip()  # type: ignore[arg-type]
                if not name_value:
                    rows_skipped += 1
                    out_row = dict(row)
                    out_row.update({
                        _COL_NAME_MATCH_LEI: "",
                        _COL_NAME_MATCH_LEGAL_NAME: "",
                        _COL_NAME_MATCH_STATUS: "",
                        _COL_NAME_MATCH_COUNTRY: "",
                        _COL_NAME_MATCH_SCORE: "",
                    })
                    writer.writerow(out_row)
                    continue

                matches, score = _search_name_with_fallback(lookup, name_value)

                out_row = dict(row)
                if matches:
                    match = matches[0]
                    out_row.update({
                        _COL_NAME_MATCH_LEI: match.get("lei", ""),
                        _COL_NAME_MATCH_LEGAL_NAME: match.get("legal_name", ""),
                        _COL_NAME_MATCH_STATUS: match.get("registration_status", ""),
                        _COL_NAME_MATCH_COUNTRY: match.get("legal_address_country", ""),
                        _COL_NAME_MATCH_SCORE: score,
                    })
                else:
                    out_row.update({
                        _COL_NAME_MATCH_LEI: "",
                        _COL_NAME_MATCH_LEGAL_NAME: "",
                        _COL_NAME_MATCH_STATUS: "",
                        _COL_NAME_MATCH_COUNTRY: "",
                        _COL_NAME_MATCH_SCORE: score,
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
    batch_cfg: Dict[str, Any] = cfg.get("batch") or {}

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
        results, _ = _search_name_with_fallback(lookup, args.name, limit=args.limit)
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
            name_column=args.name_column,
        )
        total_processed += rows_p
        total_skipped += rows_s
        print(
            f"  {input_path.name}: {rows_p} rows processed -> {per_file_out.name}"
        )

        # Collect for merged output — only if the file was actually written
        if output and per_file_out.exists():
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
