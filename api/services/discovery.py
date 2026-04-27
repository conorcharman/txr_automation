"""
Incident Discovery Service
===========================

Scans a directory for CSV files matching known incident code patterns,
enabling the Run All orchestrator to preview which validations have
matching input data.
"""

import logging
import re
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
    "incorrect_net_amount_validation": ["35_3"],
    "non_zero_net_quantity": ["7_6"],
    "non_zero_net_amount": ["7_42"],
    "incorrect_time": ["7_30"],
}


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
