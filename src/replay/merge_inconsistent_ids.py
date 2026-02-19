#!/usr/bin/env python3
"""
Merge Inconsistent IDs Summary
================================

Reads a Phase III Inconsistent IDs Summary CSV, groups rows by a key column
(default: "Reported Name & DOB"), and merges each group into a single row.

Merge behaviour:
- Where all rows in a group share the same value for a column, the merged cell
  contains that value once.
- Where rows differ, each unique value is stacked on a new line within the cell
  (duplicate values are suppressed; order of first appearance is preserved).
- Empty / NaN values are always suppressed when stacking.

Output is an Excel (.xlsx) file with text wrapping applied to every data cell
so that multi-line merged values display cleanly.

Version 1.0 Changes:
- Initial implementation

Usage:
    # Using a YAML config file
    merge-inconsistent-ids --config config/local/merge_inconsistent_ids.yaml

    # Using CLI arguments directly
    merge-inconsistent-ids --input path/to/summary.csv --output path/to/merged.xlsx

    # Dry run (no file written)
    merge-inconsistent-ids --input summary.csv --output merged.xlsx --dry-run
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from core import create_logger


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MergeConfig:
    """Configuration for the merge operation."""

    input_file: Path
    output_file: Path
    group_column: str = "Reported Name & DOB"
    separator: str = "\n"
    dry_run: bool = False
    verbose: bool = False
    log_level: str = "INFO"


@dataclass
class MergeStats:
    """Statistics produced during a merge run."""

    input_rows: int = 0
    output_rows: int = 0
    groups_merged: int = 0          # groups that had more than one row
    groups_single: int = 0          # groups that were already unique
    columns_stacked: int = 0        # individual cell values that were stacked


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

class MergeConfigManager:
    """Loads MergeConfig from a YAML file, with optional CLI overrides."""

    DEFAULT_GROUP_COLUMN: str = "Reported Name & DOB"
    DEFAULT_SEPARATOR: str = "\n"

    def load(
        self,
        config_file: Optional[str],
        cli_input: Optional[str],
        cli_output: Optional[str],
        cli_group_column: Optional[str],
        cli_separator: Optional[str],
        cli_dry_run: bool,
        cli_verbose: bool,
        cli_log_level: Optional[str],
    ) -> MergeConfig:
        """
        Resolve configuration from YAML and CLI overrides.

        Priority (highest to lowest): CLI args > YAML > defaults.

        Args:
            config_file: Path to YAML config file, or None.
            cli_input: --input CLI value.
            cli_output: --output CLI value.
            cli_group_column: --group-column CLI value.
            cli_separator: --separator CLI value.
            cli_dry_run: --dry-run flag.
            cli_verbose: --verbose flag.
            cli_log_level: --log-level CLI value.

        Returns:
            Populated MergeConfig instance.

        Raises:
            FileNotFoundError: If a config file path is specified but missing.
            ValueError: If required paths cannot be resolved.
        """
        yaml_data: Dict[str, Any] = {}

        if config_file:
            config_path = Path(config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")
            with open(config_path, encoding="utf-8") as fh:
                yaml_data = yaml.safe_load(fh) or {}

        paths = yaml_data.get("paths", {})
        merge = yaml_data.get("merge", {})
        options = yaml_data.get("options", {})
        processor = yaml_data.get("processor", {})

        # Resolve each value: CLI > YAML > default
        input_raw = cli_input or paths.get("input_file")
        output_raw = cli_output or paths.get("output_file")

        if not input_raw:
            raise ValueError(
                "input_file is required. Provide --input or set paths.input_file in config."
            )
        if not output_raw:
            raise ValueError(
                "output_file is required. Provide --output or set paths.output_file in config."
            )

        output_path = Path(output_raw)
        if output_path.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ValueError(
                f"output_file must be an Excel file (.xlsx): got '{output_raw}'"
            )

        return MergeConfig(
            input_file=Path(input_raw),
            output_file=output_path,
            group_column=cli_group_column or merge.get("group_column", self.DEFAULT_GROUP_COLUMN),
            separator=cli_separator or merge.get("separator", self.DEFAULT_SEPARATOR),
            dry_run=cli_dry_run or options.get("dry_run", False),
            verbose=cli_verbose or options.get("verbose", False),
            log_level=cli_log_level or processor.get("log_level", "INFO"),
        )


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

class RowMerger:
    """
    Merges groups of rows from a DataFrame into single rows.

    Within each group (keyed by group_column):
    - Unique values are collected from each column, preserving first-appearance order.
    - Duplicate or blank values are suppressed.
    - If only one unique value exists, it is used directly.
    - If multiple unique values exist, they are joined with the configured separator.
    """

    def __init__(self, group_column: str, separator: str = "\n") -> None:
        """
        Initialise the RowMerger.

        Args:
            group_column: Column name to group rows by.
            separator: String used to join stacked values (default: newline).
        """
        self.group_column = group_column
        self.separator = separator

    def _merge_group(
        self,
        group_df: pd.DataFrame,
        all_columns: List[str],
    ) -> Dict[str, Any]:
        """
        Merge a group of rows into a single dict.

        Args:
            group_df: Subset of the DataFrame sharing the same group_column value.
            all_columns: Ordered list of all column names.

        Returns:
            Dict mapping column name to merged cell value.
        """
        row: Dict[str, Any] = {}
        for col in all_columns:
            if col == self.group_column:
                # Always a single shared value by definition
                row[col] = group_df[col].iloc[0]
                continue

            # Collect non-empty string representations, preserving order
            seen: Dict[str, None] = {}
            for raw in group_df[col]:
                if pd.isna(raw):
                    continue
                value = str(raw).strip()
                if value:
                    seen[value] = None  # dict preserves insertion order (Python 3.7+)

            unique_values = list(seen.keys())
            if len(unique_values) == 0:
                row[col] = ""
            elif len(unique_values) == 1:
                row[col] = unique_values[0]
            else:
                row[col] = self.separator.join(unique_values)

        return row

    def process(self, df: pd.DataFrame) -> tuple[pd.DataFrame, MergeStats]:
        """
        Process the full DataFrame, merging groups sharing the same group_column value.

        Args:
            df: Raw input DataFrame.

        Returns:
            Tuple of (merged DataFrame, MergeStats).

        Raises:
            KeyError: If group_column is not present in the DataFrame.
        """
        if self.group_column not in df.columns:
            raise KeyError(
                f"Group column '{self.group_column}' not found in CSV. "
                f"Available columns: {list(df.columns)}"
            )

        stats = MergeStats(input_rows=len(df))
        columns: List[str] = list(df.columns)
        merged_rows: List[Dict[str, Any]] = []

        for key, group_df in df.groupby(self.group_column, sort=False, dropna=False):
            merged_row = self._merge_group(group_df, columns)
            merged_rows.append(merged_row)

            if len(group_df) > 1:
                stats.groups_merged += 1
                # Count columns where stacking occurred
                for col, value in merged_row.items():
                    if isinstance(value, str) and self.separator in value:
                        stats.columns_stacked += 1
            else:
                stats.groups_single += 1

        merged_df = pd.DataFrame(merged_rows, columns=columns)
        stats.output_rows = len(merged_df)
        return merged_df, stats


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

# Maximum column width (in Excel character units) to prevent excessively wide columns
_MAX_COL_WIDTH: int = 40
# RGB hex fill colour for the header row (light steel blue)
_HEADER_FILL_COLOUR: str = "D0E4F1"


class ExcelExporter:
    """
    Writes a merged DataFrame to an Excel (.xlsx) file using openpyxl.

    Formatting applied:
    - Header row: bold font, light blue background fill, top-aligned.
    - Data cells: wrap_text=True, vertical top alignment.
    - Column widths: auto-sized from content, capped at _MAX_COL_WIDTH characters.
    - Row 1 frozen so the header stays visible when scrolling.
    """

    def __init__(self, separator: str = "\n") -> None:
        """
        Args:
            separator: Value separator used in merged cells (used for width calculation).
        """
        self.separator = separator

    def _estimate_col_width(self, series: pd.Series, header: str) -> int:
        """
        Estimate a sensible column width based on the header and the widest value.

        For multi-line cells, only the longest individual segment is used.

        Args:
            series: Column data.
            header: Column header string.

        Returns:
            Width in Excel character units, capped at _MAX_COL_WIDTH.
        """
        max_len = len(header)
        for val in series:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            s = str(val)
            # If the cell has stacked lines, take the longest line
            segment_max = max((len(seg) for seg in s.split(self.separator)), default=0)
            if segment_max > max_len:
                max_len = segment_max
        return min(max_len + 2, _MAX_COL_WIDTH)  # +2 for padding

    def export(self, df: pd.DataFrame, output_path: Path) -> None:
        """
        Write the DataFrame to an Excel file.

        Args:
            df: Merged DataFrame to export.
            output_path: Destination .xlsx path (parent directory created if needed).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "Merged"

        header_font = Font(bold=True)
        header_fill = PatternFill(
            start_color=_HEADER_FILL_COLOUR,
            end_color=_HEADER_FILL_COLOUR,
            fill_type="solid",
        )
        header_alignment = Alignment(wrap_text=True, vertical="top")
        cell_alignment = Alignment(wrap_text=True, vertical="top")

        columns = list(df.columns)

        # --- Write and format the header row ---
        for col_idx, header in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # --- Write and format data rows ---
        for row_idx, row_data in enumerate(df.itertuples(index=False), start=2):
            for col_idx, value in enumerate(row_data, start=1):
                # Write empty string for NaN/None; preserve all other values as strings
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    cell_value: Any = ""
                elif isinstance(value, str):
                    cell_value = value
                else:
                    cell_value = str(value)
                cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
                cell.alignment = cell_alignment

        # --- Set column widths ---
        for col_idx, col_name in enumerate(columns, start=1):
            width = self._estimate_col_width(df[col_name], col_name)
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

        # --- Freeze the header row ---
        ws.freeze_panes = "A2"

        wb.save(output_path)


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for merge-inconsistent-ids.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Merge Phase III Inconsistent IDs Summary rows by name and DOB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using a YAML config file
  merge-inconsistent-ids --config config/local/merge_inconsistent_ids.yaml

  # Specifying paths directly
  merge-inconsistent-ids --input summary.csv --output merged.xlsx

  # Using a custom group column
  merge-inconsistent-ids --input summary.csv --output merged.xlsx --group-column "Client Name"

  # Dry run (shows what would be done, writes no file)
  merge-inconsistent-ids --input summary.csv --output merged.xlsx --dry-run
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        metavar="PATH",
        help="Path to YAML configuration file (default: config/local/replay/merge_inconsistent_ids.yaml).",
    )
    parser.add_argument(
        "--input",
        type=str,
        metavar="PATH",
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="PATH",
        help="Path for the merged Excel output file (.xlsx).",
    )
    parser.add_argument(
        "--group-column",
        type=str,
        metavar="COLUMN",
        default=None,
        help='Column to group/merge rows on (default: "Reported Name & DOB").',
    )
    parser.add_argument(
        "--separator",
        type=str,
        metavar="SEP",
        default=None,
        help="Separator for stacked values within a cell (default: newline).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging verbosity level (default: INFO).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and merge but do not write the output file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-group details during processing.",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Main entry point for the merge-inconsistent-ids console script.

    Raises:
        SystemExit: On configuration error or fatal processing failure.
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    # ---- Resolve config path (fall back to default local config if not specified) ----
    config_file = args.config
    if not config_file:
        default_config = (
            Path(__file__).parent.parent.parent
            / "config" / "local" / "replay" / "merge_inconsistent_ids.yaml"
        )
        if default_config.exists():
            print(f"Loading default configuration from {default_config}...")
            config_file = str(default_config)
        else:
            print(
                f"Error: No configuration specified and default config not found: {default_config}",
                file=sys.stderr,
            )
            sys.exit(1)

    # ---- Load config ----
    config_manager = MergeConfigManager()
    try:
        config = config_manager.load(
            config_file=config_file,
            cli_input=args.input,
            cli_output=args.output,
            cli_group_column=args.group_column,
            cli_separator=args.separator,
            cli_dry_run=args.dry_run,
            cli_verbose=args.verbose,
            cli_log_level=args.log_level,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ---- Configure logging ----
    logger = create_logger(__name__, log_dir="logs", log_level=config.log_level)
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)

    logger.info("merge-inconsistent-ids starting")
    logger.info(f"Input:        {config.input_file}")
    logger.info(f"Output:       {config.output_file}")
    logger.info(f"Group column: {config.group_column}")

    if config.dry_run:
        logger.info("Dry run mode — no output file will be written.")

    # ---- Read input CSV ----
    if not config.input_file.exists():
        logger.error(f"Input file not found: {config.input_file}")
        sys.exit(1)

    logger.info(f"Reading CSV: {config.input_file}")
    try:
        df = pd.read_csv(
            config.input_file,
            encoding="utf-8",
            dtype=str,          # Keep all values as strings; avoid type coercion
            keep_default_na=False,  # Treat empty cells as "" not NaN
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to read input CSV: {exc}")
        sys.exit(1)

    # Replace pandas NaN that might have crept in with empty string
    df = df.where(pd.notna(df), other="")

    logger.info(f"Read {len(df):,} rows, {len(df.columns)} columns.")

    # ---- Merge ----
    merger = RowMerger(group_column=config.group_column, separator=config.separator)
    try:
        merged_df, stats = merger.process(df)
    except KeyError as exc:
        logger.error(str(exc))
        sys.exit(1)

    if config.verbose:
        logger.debug(
            f"Merge details: "
            f"{stats.groups_merged} groups merged (multiple rows), "
            f"{stats.groups_single} groups had a single row."
        )

    # ---- Dry run: just report and exit ----
    if config.dry_run:
        logger.info("Dry run complete. No file written.")
        _print_summary(stats, config, written=False)
        return

    # ---- Export ----
    logger.info(f"Writing Excel output: {config.output_file}")
    exporter = ExcelExporter(separator=config.separator)
    try:
        exporter.export(merged_df, config.output_file)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to write Excel file: {exc}")
        sys.exit(1)

    _print_summary(stats, config, written=True)
    logger.info("Done.")


def _print_summary(stats: MergeStats, config: MergeConfig, *, written: bool) -> None:
    """
    Log a human-readable summary of the merge operation.

    Args:
        stats: Statistics from the merge run.
        config: Resolved configuration.
        written: Whether the output file was actually written.
    """
    logger = create_logger(__name__, log_dir="logs", log_level=config.log_level)
    logger.info(
        f"\n"
        f"  Merge Summary\n"
        f"  {'─' * 40}\n"
        f"  Input rows:          {stats.input_rows:>8,}\n"
        f"  Output rows:         {stats.output_rows:>8,}\n"
        f"  Rows removed:        {stats.input_rows - stats.output_rows:>8,}\n"
        f"  Groups merged (>1):  {stats.groups_merged:>8,}\n"
        f"  Single-row groups:   {stats.groups_single:>8,}\n"
        f"  Stacked cell values: {stats.columns_stacked:>8,}\n"
        f"  Output file:         {'(not written — dry run)' if not written else str(config.output_file)}"
    )


if __name__ == "__main__":
    main()
