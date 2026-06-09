#!/usr/bin/env python3
"""
GLEIF Historic Backfill CLI
============================

Loads the GLEIF LEI reference data and annotates every counterparty record in
an input CSV with LEI validation results and entity name enrichment.

The script auto-detects whether the input is an FCA incident file or a generic
trade CSV, and processes buyer and/or seller LEI columns where present.

Supported input formats
-----------------------
**Incident file** (FCA regulatory reporting output)
    Column names used automatically where present:

    - ``Buyer identifier value`` — buyer LEI
    - ``Seller identifier value`` — seller LEI
    - ``Trading date time_Date`` — trade date (``YYYY-MM-DD``)

    If both buyer and seller LEI columns are found, both are validated and
    results are written to separate column sets prefixed ``buyer_`` and
    ``seller_``.

**Generic trade CSV**
    Must contain at least one column named ``lei`` (case-insensitive).
    A ``trade_date`` column, if present, is used to assess LAPSED status.

Output columns added per LEI column
-------------------------------------
For a generic ``lei`` column:
    ``lei_valid``, ``lei_status``, ``legal_name``, ``lei_reason``,
    ``entity_category``, ``legal_address_country``

For incident-format ``buyer``/``seller`` columns:
    ``buyer_lei_valid``, ``buyer_lei_status``, ``buyer_legal_name``,
    ``buyer_lei_reason``, ``buyer_entity_category``, ``buyer_legal_address_country``
    (and the equivalent set prefixed ``seller_``)

Usage:
    gleif-backfill --input incidents.csv --output results.csv
    gleif-backfill --input trades.csv --output results.csv --skip-refresh
    gleif-backfill --input incidents.csv --db /data/gleif_cache.db --output results.csv
"""

import argparse
import csv
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from gleif.cache import GleifCacheManager
from gleif.client import GleifApiClient
from gleif.lookup import GleifLookup, LeiLookupResult
from gleif.refresher import GleifRefresher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name constants
# ---------------------------------------------------------------------------

# FCA incident file column names
_INCIDENT_BUYER_LEI_COL = "Buyer identifier value"
_INCIDENT_SELLER_LEI_COL = "Seller identifier value"
_INCIDENT_DATE_COL = "Trading date time_Date"

# Generic CSV column names
_GENERIC_LEI_COL = "lei"
_GENERIC_DATE_COL = "trade_date"


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
            "Annotate a trade CSV with GLEIF LEI validation results and "
            "entity name enrichment."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        metavar="CSV_PATH",
        help=(
            "Input CSV file — either an FCA incident file (with Buyer/Seller "
            "identifier columns) or a generic trade CSV with a 'lei' column."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="CSV_PATH",
        help=(
            "Output CSV path.  All original columns are preserved; "
            "LEI validation columns are appended."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["auto", "incident", "generic"],
        default="auto",
        help=(
            "Input CSV format.  'incident' = FCA Consolidated Errors/Queries file; "
            "'generic' = CSV with a 'lei' column; 'auto' = detect from headers (default)."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_REPO_ROOT / "data" / "gleif_cache.db",
        metavar="PATH",
        help="Path to the SQLite cache database (default: data/gleif_cache.db).",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help=(
            "Skip downloading the GLEIF Golden Copy; use the existing cache as-is.  "
            "Ensures the cache is present before running."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CSV loading and format detection
# ---------------------------------------------------------------------------


def _detect_format(fieldnames: List[str]) -> str:
    """Detect input CSV format from header names.

    Returns:
        ``'incident'`` if FCA incident file buyer/seller columns are present,
        ``'generic'`` otherwise.
    """
    lower = {f.lower() for f in fieldnames}
    has_incident = (
        _INCIDENT_BUYER_LEI_COL.lower() in lower
        or _INCIDENT_SELLER_LEI_COL.lower() in lower
    )
    return "incident" if has_incident else "generic"


def _resolve_column(fieldnames: List[str], target: str) -> Optional[str]:
    """Find a column name in ``fieldnames`` by case-insensitive match.

    Args:
        fieldnames: List of CSV header names.
        target: Target column name (case-insensitive).

    Returns:
        The matched fieldname as it appears in the CSV, or ``None``.
    """
    for name in fieldnames:
        if name.strip().lower() == target.lower():
            return name
    return None


def _load_trades(
    csv_path: Path,
    fmt: str = "auto",
) -> Tuple[List[Dict[str, Any]], List[str], str]:
    """Read a trade CSV and return (rows, original_fieldnames, detected_format).

    Args:
        csv_path: Path to the input CSV.
        fmt: ``'incident'``, ``'generic'``, or ``'auto'``.

    Returns:
        Tuple of (list of row dicts, list of original fieldnames, format string).
    """
    rows: List[Dict[str, Any]] = []

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            print("Error: Input CSV has no header row.", file=sys.stderr)
            sys.exit(1)

        fieldnames = list(reader.fieldnames)
        detected = fmt if fmt != "auto" else _detect_format(fieldnames)

        for row in reader:
            rows.append(dict(row))

    return rows, fieldnames, detected


# ---------------------------------------------------------------------------
# LEI validation helpers
# ---------------------------------------------------------------------------


def _make_empty_result_cols(prefix: str) -> Dict[str, str]:
    """Return an empty result column dict for a given prefix."""
    return {
        f"{prefix}lei_valid": "",
        f"{prefix}lei_status": "",
        f"{prefix}legal_name": "",
        f"{prefix}lei_reason": "",
        f"{prefix}entity_category": "",
        f"{prefix}legal_address_country": "",
    }


def _result_to_cols(result: LeiLookupResult, prefix: str) -> Dict[str, str]:
    """Convert a :class:`~gleif.lookup.LeiLookupResult` to output column dict."""
    return {
        f"{prefix}lei_valid": "Y" if result.is_valid else "N",
        f"{prefix}lei_status": result.registration_status,
        f"{prefix}legal_name": result.legal_name,
        f"{prefix}lei_reason": result.reason,
        f"{prefix}entity_category": result.entity_category,
        f"{prefix}legal_address_country": result.legal_address_country,
    }


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def _process_incident(
    rows: List[Dict[str, Any]],
    fieldnames: List[str],
    lookup: GleifLookup,
    output_path: Path,
) -> None:
    """Validate buyer and seller LEIs in an FCA incident format file.

    Args:
        rows: All CSV rows as dicts.
        fieldnames: Original CSV fieldnames.
        lookup: Initialised :class:`~gleif.lookup.GleifLookup`.
        output_path: Destination CSV path.
    """
    buyer_col = _resolve_column(fieldnames, _INCIDENT_BUYER_LEI_COL)
    seller_col = _resolve_column(fieldnames, _INCIDENT_SELLER_LEI_COL)
    date_col = _resolve_column(fieldnames, _INCIDENT_DATE_COL)

    extra_cols: List[str] = []
    if buyer_col:
        extra_cols += [
            "buyer_lei_valid",
            "buyer_lei_status",
            "buyer_legal_name",
            "buyer_lei_reason",
            "buyer_entity_category",
            "buyer_legal_address_country",
        ]
    if seller_col:
        extra_cols += [
            "seller_lei_valid",
            "seller_lei_status",
            "seller_legal_name",
            "seller_lei_reason",
            "seller_entity_category",
            "seller_legal_address_country",
        ]

    out_fieldnames = fieldnames + extra_cols
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fieldnames)
        writer.writeheader()

        for row in rows:
            trade_date: Optional[date] = None
            if date_col and row.get(date_col, "").strip():
                raw = row[date_col].strip()[:10]
                try:
                    trade_date = date.fromisoformat(raw)
                except ValueError:
                    pass

            out_row = dict(row)

            if buyer_col:
                buyer_lei = row.get(buyer_col, "").strip()
                if buyer_lei:
                    result = lookup.lookup_lei(buyer_lei, trade_date)
                    out_row.update(_result_to_cols(result, "buyer_"))
                else:
                    out_row.update(_make_empty_result_cols("buyer_"))

            if seller_col:
                seller_lei = row.get(seller_col, "").strip()
                if seller_lei:
                    result = lookup.lookup_lei(seller_lei, trade_date)
                    out_row.update(_result_to_cols(result, "seller_"))
                else:
                    out_row.update(_make_empty_result_cols("seller_"))

            writer.writerow(out_row)


def _process_generic(
    rows: List[Dict[str, Any]],
    fieldnames: List[str],
    lookup: GleifLookup,
    output_path: Path,
) -> None:
    """Validate a single 'lei' column in a generic trade format file.

    Args:
        rows: All CSV rows as dicts.
        fieldnames: Original CSV fieldnames.
        lookup: Initialised :class:`~gleif.lookup.GleifLookup`.
        output_path: Destination CSV path.
    """
    lei_col = _resolve_column(fieldnames, _GENERIC_LEI_COL)
    date_col = _resolve_column(fieldnames, _GENERIC_DATE_COL)

    if lei_col is None:
        print(
            f"Error: No 'lei' column found in input CSV.\n"
            f"Available columns: {', '.join(fieldnames)}",
            file=sys.stderr,
        )
        sys.exit(1)

    extra_cols = [
        "lei_valid",
        "lei_status",
        "legal_name",
        "lei_reason",
        "entity_category",
        "legal_address_country",
    ]
    out_fieldnames = fieldnames + extra_cols
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fieldnames)
        writer.writeheader()

        for row in rows:
            trade_date: Optional[date] = None
            if date_col and row.get(date_col, "").strip():
                raw = row[date_col].strip()[:10]
                try:
                    trade_date = date.fromisoformat(raw)
                except ValueError:
                    pass

            lei_value = row.get(lei_col, "").strip()
            out_row = dict(row)

            if lei_value:
                result = lookup.lookup_lei(lei_value, trade_date)
                out_row.update(_result_to_cols(result, ""))
            else:
                out_row.update(_make_empty_result_cols(""))

            writer.writerow(out_row)


def main() -> None:
    """Entry point for the gleif-backfill console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # --- Optional cache refresh -----------------------------------------
    if not args.skip_refresh:
        if not args.db.exists():
            print(
                f"Cache not found at '{args.db}'. Running full GLEIF refresh first..."
            )
            cache_for_refresh = GleifCacheManager(db_path=args.db)
            cache_for_refresh.initialise_db()
            refresher = GleifRefresher(cache=cache_for_refresh)
            result = refresher.run_full_refresh()
            print(f"Refresh complete: {result.total_records:,} records loaded.")
        else:
            print(
                f"Cache exists at '{args.db}'. "
                "Use --skip-refresh to suppress this message and run without refresh."
            )
    else:
        if not args.db.exists():
            print(
                f"Error: GLEIF cache not found at '{args.db}' and --skip-refresh was set.\n"
                "Run 'gleif-refresh --type full' first.",
                file=sys.stderr,
            )
            sys.exit(1)

    # --- Load trades and detect format ----------------------------------
    print(f"Loading trades from: {args.input}")
    rows, fieldnames, detected_fmt = _load_trades(args.input, fmt=args.format)
    print(f"Format detected: {detected_fmt} ({len(rows)} rows)")

    # --- Build lookup ---------------------------------------------------
    cache = GleifCacheManager(db_path=args.db)
    cache.initialise_db()
    lookup = GleifLookup(cache=cache)

    # --- Process and write output ---------------------------------------
    print(f"Validating LEIs and writing output to: {args.output}")
    if detected_fmt == "incident":
        _process_incident(rows, fieldnames, lookup, args.output)
    else:
        _process_generic(rows, fieldnames, lookup, args.output)

    print(f"Done. Output: {args.output}")


if __name__ == "__main__":
    main()
