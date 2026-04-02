#!/usr/bin/env python3
"""
Period Extract Generator
========================

Generates DTF configuration files for period-based SQL extraction from
System i Data Transfer. Unlike the SQL extract generator (which uses a
list of transaction references), this script extracts ALL transactions
within a fiscal year quarter date range.

Usage:
    python -m src.accuracy_testing.scripts.period_extract_generator \\
        --validation-type buyer_id \\
        --fiscal-year FY26 \\
        --quarter Q2 \\
        --output-dir data/extracts/automated/

    python -m src.accuracy_testing.scripts.period_extract_generator \\
        --validation-type non_zero_net_qty \\
        --fiscal-year FY26 \\
        --quarter Q3 \\
        --output-dir data/extracts/automated/ \\
        --dry-run

Version 1.0 Changes:
- Initial implementation for Phase 4 period-based extraction
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Add project root to sys.path (same pattern as other scripts in this package).
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.gui.scheduler.file_naming import AutoFileNamer
from src.gui.scheduler.models import PeriodType, SchedulePeriod, ValidationType
from src.accuracy_testing.core.dtf_runner import DTFRunner

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

VALIDATION_TYPE_MAP: dict[str, ValidationType] = {
    "buyer_id": ValidationType.BUYER_ID,
    "seller_id": ValidationType.SELLER_ID,
    "inconsistent_buyer_id": ValidationType.INCONSISTENT_BUYER_ID,
    "inconsistent_seller_id": ValidationType.INCONSISTENT_SELLER_ID,
    "fund_trade_buyer_dm": ValidationType.FUND_TRADE_BUYER_DM,
    "fund_trade_seller_dm": ValidationType.FUND_TRADE_SELLER_DM,
    "non_zero_net_qty": ValidationType.NON_ZERO_NET_QTY,
    "non_zero_net_amt": ValidationType.NON_ZERO_NET_AMT,
    "incorrect_net_amount": ValidationType.INCORRECT_NET_AMOUNT,
}

SQL_TEMPLATE_MAP: dict[ValidationType, str] = {
    ValidationType.BUYER_ID: "BuyerID_period.sql",
    ValidationType.SELLER_ID: "SellerID_period.sql",
    ValidationType.INCONSISTENT_BUYER_ID: "InconsistentBuyerID_period.sql",
    ValidationType.INCONSISTENT_SELLER_ID: "InconsistentSellerID_period.sql",
    ValidationType.FUND_TRADE_BUYER_DM: "FTBDM_period.sql",
    ValidationType.FUND_TRADE_SELLER_DM: "FTSDM_period.sql",
    ValidationType.NON_ZERO_NET_QTY: "NonZeroNetQuantity_period.sql",
    ValidationType.NON_ZERO_NET_AMT: "NonZeroNetAmount_period.sql",
    ValidationType.INCORRECT_NET_AMOUNT: "IncorrectNetAmount_period.sql",
}

_SQL_TEMPLATES_DIR = Path(__file__).parent.parent / "sql_templates"


# ---------------------------------------------------------------------------
# Date range calculation
# ---------------------------------------------------------------------------

def fiscal_period_to_dates(fiscal_year: str, quarter: str) -> tuple[date, date]:
    """Convert a fiscal year + quarter label to a start/end date range.

    Fiscal year convention: FY26 starts April 2025.

    - Q1 = 1 Apr – 30 Jun (calendar year N-1)
    - Q2 = 1 Jul – 30 Sep (calendar year N-1)
    - Q3 = 1 Oct – 31 Dec (calendar year N-1)
    - Q4 = 1 Jan – 31 Mar (calendar year N)

    Args:
        fiscal_year: Fiscal year label, e.g. ``"FY26"``.
        quarter: Quarter label, e.g. ``"Q2"``.

    Returns:
        Tuple of ``(start_date, end_date)`` as :class:`datetime.date` objects.

    Raises:
        ValueError: If the quarter label is not Q1–Q4.

    Example:
        >>> fiscal_period_to_dates("FY26", "Q2")
        (datetime.date(2025, 7, 1), datetime.date(2025, 9, 30))
    """
    fy_num = int(fiscal_year.lstrip("FYfy"))
    fy_calendar_start = 2000 + fy_num - 1  # FY26 → 2025
    quarter_map: dict[str, tuple[date, date]] = {
        "Q1": (date(fy_calendar_start, 4, 1), date(fy_calendar_start, 6, 30)),
        "Q2": (date(fy_calendar_start, 7, 1), date(fy_calendar_start, 9, 30)),
        "Q3": (date(fy_calendar_start, 10, 1), date(fy_calendar_start, 12, 31)),
        "Q4": (date(fy_calendar_start + 1, 1, 1), date(fy_calendar_start + 1, 3, 31)),
    }
    q_upper = quarter.upper()
    if q_upper not in quarter_map:
        raise ValueError(f"Invalid quarter {quarter!r}. Expected one of: Q1, Q2, Q3, Q4.")
    return quarter_map[q_upper]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the period extract generator CLI."""
    parser = argparse.ArgumentParser(
        description="Generate period-based DTF extract files for System i Data Transfer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--validation-type",
        required=True,
        choices=list(VALIDATION_TYPE_MAP.keys()),
        help="Validation type to generate extract for",
    )
    parser.add_argument(
        "--fiscal-year",
        required=True,
        help="Fiscal year label, e.g. FY26",
    )
    parser.add_argument(
        "--quarter",
        required=True,
        help="Quarter label, e.g. Q2",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the DTF and CSV files",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview paths without writing any files",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    vtype = VALIDATION_TYPE_MAP[args.validation_type]
    period = SchedulePeriod(
        period_type=PeriodType.FISCAL_QUARTER,
        fiscal_year=args.fiscal_year,
        quarter=args.quarter,
    )
    start_date, end_date = period.to_date_range()

    timestamp = datetime.now()
    output_dir = Path(args.output_dir)
    csv_path = AutoFileNamer.generate_extract_path(vtype, period, output_dir, timestamp)
    dtf_path = csv_path.with_suffix(".dtf")

    sql_template_name = SQL_TEMPLATE_MAP[vtype]
    sql_template_path = _SQL_TEMPLATES_DIR / sql_template_name

    logger.info(
        "Generating period extract for %s %s %s",
        vtype.display_name,
        args.fiscal_year,
        args.quarter,
    )
    logger.info("Date range: %s to %s", start_date, end_date)
    logger.info("SQL template: %s", sql_template_path)
    logger.info("Output CSV:  %s", csv_path)
    logger.info("Output DTF:  %s", dtf_path)

    if args.dry_run:
        logger.info("Dry run — no files written")
        return

    runner = DTFRunner()
    generated = runner.generate_dtf_from_template(
        sql_template_path=sql_template_path,
        parameters={
            "START_DATE": str(start_date),
            "END_DATE": str(end_date),
        },
        output_csv_path=csv_path,
        dtf_output_path=dtf_path,
    )
    logger.info("DTF file written: %s", generated)


if __name__ == "__main__":
    main()
