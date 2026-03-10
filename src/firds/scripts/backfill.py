#!/usr/bin/env python3
"""
FIRDS Historic Backfill CLI
============================

Loads the FIRDS instrument reference data required to check reportability
for a historic incident file (or any trade record CSV), then writes
reportability results for every trade record in the file.

The script determines the date range of trades in the input file, downloads
the appropriate FULINS baseline (the most recent Saturday on or before the
earliest trade date) and all subsequent DLTINS delta files through the latest
trade date.  Any files already present in the sync log are skipped so the
command is safe to run multiple times.

Supported input formats
-----------------------
**Incident file** (FCA regulatory reporting output)
    Column names used automatically:

    - ``Instrument identification code`` — ISIN
    - ``Venue`` — MIC (trading venue)
    - ``Trading date time_Date`` — trade date (YYYY-MM-DD)

**Generic trade CSV**
    Must contain columns ``isin`` and ``trade_date`` (and optionally ``mic``).
    Pass ``--format generic`` to force this mode, or the script will auto-detect
    based on header names.

Usage
-----
::

    firds-backfill --input incidents.csv --output results.csv
    firds-backfill --input trades.csv --format generic --output results.csv
    firds-backfill --input incidents.csv --db /data/firds_cache.db --output results.csv
    firds-backfill --input incidents.csv --skip-refresh --output results.csv

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

from firds.cache import FirdsCacheManager
from firds.client import FirdsApiClient
from firds.refresher import FirdsRefresher, _most_recent_saturday
from firds.reportability import FirdsReportabilityChecker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name mappings
# ---------------------------------------------------------------------------

# Column names used in FCA incident files (Consolidated Errors / Queries Data)
_INCIDENT_ISIN_COL = "Instrument identification code"
_INCIDENT_MIC_COL = "Venue"
_INCIDENT_DATE_COL = "Trading date time_Date"

# Output column names written to the results CSV
_COL_IS_REPORTABLE = "is_reportable"
_COL_REASON = "reportability_reason"
_COL_MATCHED_MICS = "matched_mics"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse YYYY-MM-DD string to date."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}' — expected YYYY-MM-DD format."
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the FIRDS cache for a historic incident file and "
            "annotate each trade record with a reportability result."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        metavar="CSV_PATH",
        help="Input CSV file — either an FCA incident file or a generic trade CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="CSV_PATH",
        help="Output CSV path.  All original columns are preserved; "
             "is_reportable, reportability_reason, and matched_mics columns are appended.",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "incident", "generic"],
        default="auto",
        help=(
            "Input CSV format.  'incident' = FCA Consolidated Errors/Queries file; "
            "'generic' = CSV with isin/trade_date[/mic] columns; "
            "'auto' = detect from headers (default)."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_REPO_ROOT / "data" / "firds_cache.db",
        metavar="PATH",
        help="Path to the SQLite cache database (default: data/firds_cache.db).",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help=(
            "Skip downloading FIRDS files; use the existing cache as-is.  "
            "Useful if the cache is already known to be up-to-date for the "
            "period covered by the input file."
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
# CSV loading
# ---------------------------------------------------------------------------


def _detect_format(fieldnames: List[str]) -> str:
    """Detect input CSV format from header names.

    Returns:
        ``'incident'`` if FCA incident file headers are present,
        ``'generic'`` otherwise.
    """
    has_incident_headers = all(
        any(col.lower() == h.lower() for h in fieldnames)
        for col in [_INCIDENT_ISIN_COL, _INCIDENT_DATE_COL]
    )
    return "incident" if has_incident_headers else "generic"


def _load_trades(
    csv_path: Path,
    fmt: str = "auto",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Read a trade CSV and return (trade_rows, original_fieldnames).

    Each trade row is a dict containing the original CSV row plus normalised
    ``_isin``, ``_mic``, ``_trade_date`` keys (prefixed with underscore to
    avoid collisions).  Rows with no ISIN or trade date are skipped.

    Args:
        csv_path: Path to the input CSV.
        fmt: ``'incident'``, ``'generic'``, or ``'auto'``.

    Returns:
        Tuple of (list of dicts, list of original fieldnames).

    Raises:
        SystemExit: If required columns are missing.
    """
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            print("Error: Input CSV has no header row.", file=sys.stderr)
            sys.exit(1)

        fieldnames = list(reader.fieldnames)
        detected = fmt if fmt != "auto" else _detect_format(fieldnames)

        if detected == "incident":
            isin_col, mic_col, date_col = _resolve_incident_cols(fieldnames)
        else:
            isin_col, mic_col, date_col = _resolve_generic_cols(fieldnames)

        rows = []
        skipped = 0
        for row in reader:
            isin = row.get(isin_col, "").strip().upper()
            mic = row.get(mic_col, "").strip().upper() if mic_col else ""
            date_str = row.get(date_col, "").strip()

            if not isin or not date_str:
                skipped += 1
                continue

            try:
                trade_date = _parse_date(date_str)
            except argparse.ArgumentTypeError:
                skipped += 1
                continue

            row["_isin"] = isin
            row["_mic"] = mic or None
            row["_trade_date"] = trade_date
            rows.append(row)

        if skipped:
            logger.info("Skipped %d rows with missing ISIN or trade date.", skipped)

        return rows, fieldnames


def _resolve_incident_cols(
    fieldnames: List[str],
) -> Tuple[str, Optional[str], str]:
    """Map incident file headers to (isin_col, mic_col, date_col).

    Args:
        fieldnames: List of CSV header names.

    Returns:
        Tuple of column name strings (mic_col may be ``None``).

    Raises:
        SystemExit: If required columns are absent.
    """
    lower_map = {f.lower(): f for f in fieldnames}

    isin_col = lower_map.get(_INCIDENT_ISIN_COL.lower())
    mic_col = lower_map.get(_INCIDENT_MIC_COL.lower())
    date_col = lower_map.get(_INCIDENT_DATE_COL.lower())

    missing = []
    if not isin_col:
        missing.append(f"'{_INCIDENT_ISIN_COL}'")
    if not date_col:
        missing.append(f"'{_INCIDENT_DATE_COL}'")
    if missing:
        print(
            f"Error: incident file is missing required column(s): {', '.join(missing)}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return isin_col, mic_col, date_col


def _resolve_generic_cols(
    fieldnames: List[str],
) -> Tuple[str, Optional[str], str]:
    """Map generic CSV headers to (isin_col, mic_col, date_col).

    Args:
        fieldnames: List of CSV header names.

    Returns:
        Tuple of column name strings (mic_col may be ``None``).

    Raises:
        SystemExit: If required columns are absent.
    """
    lower_map = {f.lower(): f for f in fieldnames}

    isin_col = lower_map.get("isin")
    mic_col = lower_map.get("mic")
    date_col = lower_map.get("trade_date")

    if not isin_col or not date_col:
        print(
            "Error: generic trade CSV must contain 'isin' and 'trade_date' columns.",
            file=sys.stderr,
        )
        sys.exit(1)

    return isin_col, mic_col, date_col


# ---------------------------------------------------------------------------
# FIRDS cache refresh
# ---------------------------------------------------------------------------


def _refresh_for_period(
    cache: FirdsCacheManager,
    min_date: date,
    max_date: date,
) -> None:
    """Download and ingest FULINS + FULCAN files for the Saturday preceding ``min_date``.

    Runs a full refresh for the most recent Saturday on or before ``min_date``.
    Only in-scope FULINS categories are ingested:
    C = Collective Investment Vehicles, D = Debt, E = Equities.
    DLTINS delta files are not used — the weekly full refresh is the sole
    source of truth.

    Files already in the sync log are skipped automatically.

    Args:
        cache: Initialised :class:`~firds.cache.FirdsCacheManager`.
        min_date: Earliest trade date in the dataset.
        max_date: Latest trade date in the dataset (informational only).
    """
    api_client = FirdsApiClient()
    refresher = FirdsRefresher(cache=cache, api_client=api_client)

    fulins_date = _most_recent_saturday(min_date)
    logger.info(
        "FULINS baseline date: %s (Saturday on or before earliest trade date %s)",
        fulins_date,
        min_date,
    )

    print(f"  Loading FULINS baseline for {fulins_date} …")
    full_result = refresher.run_full_refresh(target_date=fulins_date)
    print(
        f"  FULINS: {full_result.files_processed} file(s) processed, "
        f"{full_result.files_skipped} skipped, "
        f"{full_result.total_records:,} records."
    )


# ---------------------------------------------------------------------------
# Reportability annotation
# ---------------------------------------------------------------------------


def _annotate_trades(
    checker: FirdsReportabilityChecker,
    trades: List[Dict[str, Any]],
    fieldnames: List[str],
    output_path: Path,
) -> None:
    """Run reportability checks and write annotated rows to ``output_path``.

    Appends ``is_reportable``, ``reportability_reason``, and ``matched_mics``
    columns to the output CSV.

    Args:
        checker: Configured reportability checker.
        trades: List of trade row dicts (with ``_isin``, ``_mic``, ``_trade_date``).
        fieldnames: Original CSV field names (for output column ordering).
        output_path: Destination CSV path.
    """
    out_fieldnames = list(fieldnames) + [
        _COL_IS_REPORTABLE,
        _COL_REASON,
        _COL_MATCHED_MICS,
    ]

    reportable_count = 0
    not_reportable_count = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=out_fieldnames, extrasaction="ignore"
        )
        writer.writeheader()

        for row in trades:
            result = checker.is_reportable(
                isin=row["_isin"],
                trade_date=row["_trade_date"],
                mic=row.get("_mic"),
            )
            row[_COL_IS_REPORTABLE] = "Y" if result.is_reportable else "N"
            row[_COL_REASON] = result.reason
            row[_COL_MATCHED_MICS] = "|".join(result.matched_mics)
            writer.writerow(row)

            if result.is_reportable:
                reportable_count += 1
            else:
                not_reportable_count += 1

    print(
        f"\n  Results written to: {output_path}\n"
        f"  Reportable:     {reportable_count:>6,}\n"
        f"  Not reportable: {not_reportable_count:>6,}\n"
        f"  Total:          {reportable_count + not_reportable_count:>6,}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the firds-backfill console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Load trade records from incident/generic CSV
    print(f"\n[1/3] Reading trade records from '{args.input.name}' …")
    trades, fieldnames = _load_trades(args.input, fmt=args.format)

    if not trades:
        print("No valid trade records found in the input file.")
        sys.exit(0)

    trade_dates = [t["_trade_date"] for t in trades]
    min_date = min(trade_dates)
    max_date = max(trade_dates)
    unique_isins = len({t["_isin"] for t in trades})

    print(
        f"  {len(trades):,} trade records loaded.\n"
        f"  Date range:    {min_date}  →  {max_date}\n"
        f"  Unique ISINs:  {unique_isins:,}"
    )

    # Step 2: Refresh FIRDS cache for the required period
    cache = FirdsCacheManager(db_path=args.db)
    cache.initialise_db()

    if args.skip_refresh:
        print("\n[2/3] Skipping FIRDS cache refresh (--skip-refresh specified).")
    else:
        print("\n[2/3] Refreshing FIRDS cache …")
        _refresh_for_period(cache, min_date, max_date)

    # Step 3: Annotate trades with reportability results
    print("\n[3/3] Checking reportability …")
    checker = FirdsReportabilityChecker(cache=cache)
    _annotate_trades(checker, trades, fieldnames, args.output)


if __name__ == "__main__":
    main()
