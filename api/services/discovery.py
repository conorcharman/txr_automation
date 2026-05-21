"""
Incident Discovery Service
===========================

Scans a directory for CSV files matching known incident code patterns,
enabling the Run All orchestrator to preview which validations have
matching input data.
"""

import logging
import re
import csv
from pathlib import Path

logger = logging.getLogger(__name__)

#: Maps validation group names to their incident code patterns.
#: Duplicated from ``src/gui/constants.py`` to avoid importing GUI code.
INCIDENT_CODE_PATTERNS: dict[str, list[str]] = {
    "buyer_id_validation": ["7_35", "7_37", "7_39"],
    "seller_id_validation": ["16_19", "16_21", "16_23"],
    "inconsistent_buyer_id_validation": ["7_66"],
    "inconsistent_seller_id_validation": ["16_20"],
    "validate_ftbdm": ["12_17"],
    "validate_ftsdm": ["21_17"],
    "incorrect_net_amount_validation": ["35_3", "35_10"],
    "non_zero_net_quantity": ["7_6"],
    "non_zero_net_amount": ["7_42"],
    "incorrect_time": ["7_30"],
}


def _iter_incident_rows(file_path: Path) -> list[tuple[list[str], list[str]]]:
    """Read INCIDENT_CODE/INCIDENT_DESCRIPTION pairs from a consolidated CSV.

    Args:
        file_path: Path to consolidated Errors/Queries CSV.

    Returns:
        List of tuples ``(codes, descriptions)`` where each list may contain
        multiple pipe-delimited entries from the same row.
    """
    rows: list[tuple[list[str], list[str]]] = []
    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return rows

        upper = [col.strip().upper() for col in header]
        code_idx = upper.index("INCIDENT_CODE") if "INCIDENT_CODE" in upper else -1
        desc_idx = upper.index("INCIDENT_DESCRIPTION") if "INCIDENT_DESCRIPTION" in upper else -1
        if code_idx < 0:
            return rows

        for record in reader:
            if code_idx >= len(record):
                continue
            raw_codes = record[code_idx].strip()
            raw_desc = record[desc_idx].strip() if 0 <= desc_idx < len(record) else ""

            codes = [c.strip() for c in raw_codes.split("|") if c.strip()]
            descriptions = [d.strip() for d in raw_desc.split("|") if d.strip()]
            if codes:
                rows.append((codes, descriptions))
    return rows


def detect_consolidated_incidents(
    errors_file: str | None,
    queries_file: str | None,
) -> dict[str, dict[str, int | str]]:
    """Detect incident counts across consolidated Errors/Queries files.

    Args:
        errors_file: Optional consolidated errors CSV absolute path.
        queries_file: Optional consolidated queries CSV absolute path.

    Returns:
        Mapping keyed by incident code with ``description``, ``errors_count``,
        and ``queries_count`` values.
    """
    pattern = re.compile(r"^\d+_\d+$")
    stats: dict[str, dict[str, int | str]] = {}

    def _merge(source_file: str | None, source_key: str) -> None:
        if not source_file:
            return
        path = Path(source_file)
        if not path.exists() or not path.is_file():
            return

        for codes, descriptions in _iter_incident_rows(path):
            for idx, code in enumerate(codes):
                if not pattern.match(code):
                    continue
                desc = descriptions[idx] if idx < len(descriptions) else (descriptions[0] if descriptions else "")
                if code not in stats:
                    stats[code] = {
                        "description": desc,
                        "errors_count": 0,
                        "queries_count": 0,
                    }
                if not stats[code]["description"] and desc:
                    stats[code]["description"] = desc
                count_key = "errors_count" if source_key == "errors" else "queries_count"
                stats[code][count_key] = int(stats[code][count_key]) + 1

    _merge(errors_file, "errors")
    _merge(queries_file, "queries")
    return stats


def discover_incidents(input_directory: str) -> dict[str, list[str]]:
    """Scan a directory for CSV files matching incident code patterns.

    Args:
        input_directory: Absolute path to the directory to scan.

    Returns:
        A mapping of validation script name to list of matched file paths.

    Raises:
        ValueError: If the directory does not exist or is not a directory.
    """
    dir_path = Path(input_directory)
    if not dir_path.is_dir():
        raise ValueError(f"'{input_directory}' is not a valid directory.")

    csv_files = sorted(str(f) for f in dir_path.glob("*.csv"))
    results: dict[str, list[str]] = {}

    for script_name, codes in INCIDENT_CODE_PATTERNS.items():
        matched: list[str] = []
        for code in codes:
            pattern = re.compile(re.escape(code))
            for csv_path in csv_files:
                filename = Path(csv_path).name
                if pattern.search(filename) and csv_path not in matched:
                    matched.append(csv_path)
        results[script_name] = matched

    logger.debug(
        "Discovered incidents in '%s': %s",
        input_directory,
        {k: len(v) for k, v in results.items()},
    )
    return results
