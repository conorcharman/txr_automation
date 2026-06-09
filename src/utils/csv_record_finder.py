#!/usr/bin/env python3
"""
CSV Record Finder
=================

Searches a directory of CSV, Excel (.xlsx / .xls), or XML files for rows
where a specified column contains any of a set of search terms (substring
match, case-insensitive by default).

All matching rows are written to a single output CSV file with an extra
column recording the source filename.  For Excel files the source column
includes the sheet name (e.g. ``report.xlsx::Sheet1``).

Version 1.0 Changes:
- Initial implementation

Usage:
    # Search CSV files only
    python -m utils.csv_record_finder \\
        --input-dir /path/to/files \\
        --output results.csv \\
        --column TransactionDescription \\
        --terms "PPM MANAGER" "F/FLOW THE BANK OF"

    # Search all supported types recursively with a secondary sort column
    python -m utils.csv_record_finder \\
        --input-dir /path/to/files \\
        --output results.csv \\
        --column TransactionDescription \\
        --terms "PPM MANAGER" "F/FLOW THE BANK OF" \\
        --file-types csv xlsx xml \\
        --recursive \\
        --sort-by TransactionPostedDate
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_PROGRESS_INTERVAL = 100


@dataclass
class FinderResult:
    """Aggregate results from a :func:`find_records` run.

    Attributes:
        files_scanned: Number of files successfully opened and searched.
        files_with_matches: Number of files (or Excel sheets) containing
            at least one matching row.
        records_written: Total number of matching rows written to output.
        skipped_files: Source labels that were skipped due to a missing
            column or a read error.
    """

    files_scanned: int = 0
    files_with_matches: int = 0
    records_written: int = 0
    skipped_files: List[str] = field(default_factory=list)


def _read_file(
    path: Path,
    encoding: str,
) -> List[Tuple[pd.DataFrame, str]]:
    """Read a file into one or more ``(DataFrame, source_label)`` pairs.

    CSV and XML files yield a single pair.  Excel files yield one pair per
    sheet, with the source label formatted as ``filename.xlsx::SheetName``.

    Args:
        path: Path to the input file.
        encoding: Character encoding used for CSV and XML files.

    Returns:
        List of ``(DataFrame, source_label)`` tuples.  Returns an empty list
        if the file cannot be read (the error is logged as a warning).
    """
    suffix = path.suffix.lower()

    if suffix == ".csv":
        try:
            df = pd.read_csv(path, dtype=str, encoding=encoding, keep_default_na=False)
            return [(df, path.name)]
        except Exception as exc:
            logger.warning("Could not read CSV '%s': %s", path.name, exc)
            return []

    if suffix in (".xlsx", ".xls"):
        results: List[Tuple[pd.DataFrame, str]] = []
        try:
            xl = pd.ExcelFile(path)
            for sheet_name in xl.sheet_names:
                try:
                    df = xl.parse(sheet_name, dtype=str, keep_default_na=False)
                    results.append((df, f"{path.name}::{sheet_name}"))
                except Exception as exc:
                    logger.warning(
                        "Could not read sheet '%s' in '%s': %s",
                        sheet_name,
                        path.name,
                        exc,
                    )
            return results
        except Exception as exc:
            logger.warning("Could not open Excel file '%s': %s", path.name, exc)
            return []

    if suffix == ".xml":
        try:
            # Imported lazily to keep startup fast and avoid circularity.
            from utils.xml_csv_converter import XMLToCSVConverter  # noqa: PLC0415

            converter = XMLToCSVConverter()
            root, _ = converter._parse_xml_resilient(path)
            record_tag = converter.detect_record_element(root)
            rows = [converter.flatten_element(elem) for elem in root.iter(record_tag)]
            if not rows:
                logger.warning("No records found in XML file '%s'.", path.name)
                return []
            df = pd.DataFrame(rows).fillna("").astype(str)
            return [(df, path.name)]
        except Exception as exc:
            logger.warning("Could not read XML file '%s': %s", path.name, exc)
            return []

    return []


def _discover_files(
    input_dir: Path,
    file_types: List[str],
    recursive: bool,
) -> List[Path]:
    """Discover all files of the requested types in *input_dir*.

    Args:
        input_dir: Directory to search.
        file_types: Extension strings to match, e.g. ``['csv', 'xlsx', 'xml']``.
            ``'xlsx'`` automatically includes ``*.xls`` as well.
        recursive: If True, search subdirectories via ``rglob``.

    Returns:
        Sorted, deduplicated list of matching :class:`~pathlib.Path` objects.
    """
    match_fn = input_dir.rglob if recursive else input_dir.glob
    found: List[Path] = []
    for ft in file_types:
        if ft == "xlsx":
            found.extend(match_fn("*.xlsx"))
            found.extend(match_fn("*.xls"))
        else:
            found.extend(match_fn(f"*.{ft}"))
    return sorted(set(found))


def find_records(
    input_dir: str,
    output: str,
    column: str,
    terms: List[str],
    source_column: str = "SourceFile",
    sort_by: Optional[List[str]] = None,
    case_sensitive: bool = False,
    match_mode: str = "contains",
    recursive: bool = False,
    file_types: Optional[List[str]] = None,
    encoding: str = "utf-8",
) -> FinderResult:
    """Search files in *input_dir* for rows matching the given search terms.

    Args:
        input_dir: Directory containing the files to search.
        output: Destination CSV path for all matching records.
        column: Name of the column to perform the substring search on.
        terms: Search strings; rows matching *any* term are included.
        source_column: Name of the extra column appended to each output row
            that records the source filename (or ``filename::sheet``).
        sort_by: Additional sort columns applied after *column*. Date columns
            are detected automatically and sorted chronologically.
        case_sensitive: If False (default) the search ignores case.
        match_mode: ``'contains'`` (default) matches any row whose column
            value includes the term as a substring.  ``'equals'`` matches
            only rows whose column value is identical to the term (still
            respects *case_sensitive*).
        recursive: If True, search subdirectories recursively.
        file_types: Extension strings to scan — ``'csv'``, ``'xlsx'``, or
            ``'xml'``.  Defaults to ``['csv']``.
        encoding: Character encoding for CSV and XML files.

    Returns:
        :class:`FinderResult` with counts for the completed run.
    """
    if file_types is None:
        file_types = ["csv"]
    if sort_by is None:
        sort_by = []

    result = FinderResult()
    input_path = Path(input_dir)

    if not input_path.is_dir():
        print(
            f"ERROR: Input directory does not exist: {input_path}",
            file=sys.stderr,
        )
        return result

    files = _discover_files(input_path, file_types, recursive)
    total = len(files)
    print(f"Found {total} file(s) to scan in '{input_path}'.")

    accumulated: List[pd.DataFrame] = []

    for i, file_path in enumerate(files, start=1):
        if i % _PROGRESS_INTERVAL == 0 or i == total:
            print(f"  Scanned {i}/{total} files...")

        pairs = _read_file(file_path, encoding)
        if not pairs:
            result.skipped_files.append(file_path.name)
            continue

        result.files_scanned += 1
        file_had_matches = False

        for df, source_label in pairs:
            if column not in df.columns:
                print(
                    f"  WARNING: Column '{column}' not found in "
                    f"'{source_label}' — skipping."
                )
                result.skipped_files.append(source_label)
                continue

            mask = pd.Series([False] * len(df), index=df.index)
            col_series = df[column]
            if not case_sensitive:
                col_series = col_series.str.lower()
            for term in terms:
                cmp_term = term if case_sensitive else term.lower()
                if match_mode == "equals":
                    mask |= col_series.fillna("") == cmp_term
                else:
                    mask |= col_series.str.contains(
                        cmp_term,
                        case=True,  # already lowercased when needed
                        na=False,
                        regex=False,
                    )

            matches = df[mask].copy()
            if matches.empty:
                continue

            matches[source_column] = source_label
            # Ensure source_column is always the rightmost column.
            cols = [c for c in matches.columns if c != source_column] + [source_column]
            accumulated.append(matches[cols])
            file_had_matches = True

        if file_had_matches:
            result.files_with_matches += 1

    if not accumulated:
        print("No matching records found.")
        return result

    combined = pd.concat(accumulated, ignore_index=True)

    # Sort: primary by the lookup column, then any requested secondary columns.
    # For each sort column, attempt datetime coercion so that date-valued
    # columns sort chronologically rather than lexicographically.
    sort_columns = [c for c in ([column] + sort_by) if c in combined.columns]
    if sort_columns:
        sort_keys: List[str] = []
        temp_cols: List[str] = []
        for col in sort_columns:
            coerced = pd.to_datetime(combined[col], format="mixed", errors="coerce")
            if coerced.isna().all():
                # Column is not date-like; sort by the original string values.
                sort_keys.append(col)
            else:
                temp_col = f"__sort_{col}__"
                combined[temp_col] = coerced
                temp_cols.append(temp_col)
                sort_keys.append(temp_col)

        combined.sort_values(sort_keys, inplace=True, ignore_index=True)
        combined.drop(columns=temp_cols, inplace=True)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False, encoding="utf-8")

    result.records_written = len(combined)
    print(
        f"\nDone.\n"
        f"  Files scanned:             {result.files_scanned}\n"
        f"  Files with matches:        {result.files_with_matches}\n"
        f"  Records written:           {result.records_written}\n"
        f"  Output:                    {output_path}"
    )
    if result.skipped_files:
        print(f"  Skipped (no column/error): {len(result.skipped_files)}")
        for sf in result.skipped_files[:10]:
            print(f"    - {sf}")
        if len(result.skipped_files) > 10:
            print(f"    ... and {len(result.skipped_files) - 10} more")

    return result


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Build and parse the command-line argument parser.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed :class:`argparse.Namespace`.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Search a directory of CSV, Excel, or XML files for rows "
            "where a specific column contains any of a set of search terms."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the files to search.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the output CSV file containing all matching records.",
    )
    parser.add_argument(
        "--column",
        required=True,
        help="Name of the column to search.",
    )
    parser.add_argument(
        "--terms",
        required=True,
        nargs="+",
        help="One or more search strings. Rows matching any term are included.",
    )
    parser.add_argument(
        "--source-column",
        default="SourceFile",
        help=(
            "Name of the column appended to each output row recording the "
            "source filename (default: SourceFile)."
        ),
    )
    parser.add_argument(
        "--sort-by",
        nargs="+",
        default=[],
        metavar="COLUMN",
        help=(
            "Optional secondary sort column(s) applied after the lookup "
            "column. Date columns are detected automatically."
        ),
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        default=False,
        help="Enable case-sensitive matching (default: case-insensitive).",
    )
    parser.add_argument(
        "--match-mode",
        choices=["contains", "equals"],
        default="contains",
        help=(
            "How terms are matched against column values: "
            "'contains' (default) finds rows where the column includes the "
            "term as a substring; 'equals' requires an exact match."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=False,
        help="Search subdirectories recursively.",
    )
    parser.add_argument(
        "--file-types",
        nargs="+",
        default=["csv"],
        choices=["csv", "xlsx", "xml"],
        metavar="TYPE",
        help="File type(s) to search: csv xlsx xml (default: csv).",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Character encoding for CSV and XML files (default: utf-8).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the CSV record finder.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    args = parse_arguments(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    result = find_records(
        input_dir=args.input_dir,
        output=args.output,
        column=args.column,
        terms=args.terms,
        source_column=args.source_column,
        sort_by=args.sort_by,
        case_sensitive=args.case_sensitive,
        match_mode=args.match_mode,
        recursive=args.recursive,
        file_types=args.file_types,
        encoding=args.encoding,
    )

    sys.exit(0 if result.records_written >= 0 else 1)


if __name__ == "__main__":
    main()
