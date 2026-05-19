#!/usr/bin/env python3
"""
Phase 2 Final Lookup v1.0
=========================

Validates Phase II replay corrections against UnaVista transaction data.

This is the second stage of Phase II replay processing:

- Stage 1 (Feedback):     phase_2_processor.py   — looks up corrections from incident
                                                    files and writes them into replay
                                                    output files.
- Stage 2 (Final Lookup): phase_2_final_lookup.py — reads Phase II output files, validates
                                                    each correction against UnaVista data,
                                                    and produces an annotated UnaVista CSV.

Key design decisions:
- Phase II output files are the SOURCE OF TRUTH for corrections. Incident files are used
  only for cross-reference; discrepancies are flagged but do not override the test result.
- UnaVista input is CSV only. XLSX conversion must be performed upstream.
- Transaction reference is used as the primary lookup key throughout (not client identity).

Version 1.0 - Initial implementation (April 2026)
Version 1.1 - Added XLSX support for Phase 2 output and UnaVista files (May 2026)
"""

import csv
import glob
import os
import re
import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False

# Core library imports
from core import (
    ConfigManager,
    DateParser,
    ProcessingStats,
    UnaVistaTransaction,
    create_logger,
    safe_open_csv,
    INCIDENT_CODE_MATRIX,
)
from core.data import Phase2SingleColumns, Phase2CombinedColumns

# Sibling module imports — reuse indexer and column mapper from the Feedback stage
from .phase_2_processor import IncidentColumnMapper, IncidentFileIndex

# Reuse UnaVista field mapping and test result structure from Phase 3 Final Lookup
from .phase_3_final_lookup import FieldMapper, TestResult


# ============================================================================
# File Reading Helper
# ============================================================================


def _read_rows(file_path: str) -> List[List[str]]:
    """Read a CSV or XLSX file and return all rows as lists of strings.

    Args:
        file_path: Absolute path to the file. Files ending ``.xlsx`` are read
            with ``openpyxl``; all other files are treated as CSV.

    Returns:
        List of rows (header as row 0, data rows following).

    Raises:
        ImportError: If the file is ``.xlsx`` but ``openpyxl`` is not installed.
    """
    if str(file_path).lower().endswith('.xlsx'):
        if not _OPENPYXL_AVAILABLE:
            raise ImportError(
                "openpyxl is required to read .xlsx files: pip install openpyxl"
            )
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows = [
            [str(cell) if cell is not None else "" for cell in row]
            for row in ws.iter_rows(values_only=True)
        ]
        wb.close()
        return rows
    else:
        f, _ = safe_open_csv(Path(file_path), 'r', newline='')
        with f:
            return list(csv.reader(f))


# ============================================================================
# Module-level helpers
# ============================================================================

def _split_correction_parts(raw: str) -> List[str]:
    """Split a correction value or field string on the appropriate delimiter.

    Supports two delimiters:
    - ``¬`` (negation sign) — takes precedence when present.
    - ``:`` (colon) — used when ``¬`` is absent.

    Args:
        raw: The raw correction or field string to split.

    Returns:
        List of stripped string parts.
    """
    if '\u00ac' in raw:  # ¬
        return [p.strip() for p in raw.split('\u00ac')]
    return [p.strip() for p in raw.split(':')]


def _parse_phase2_corrections(correction_value: str, correction_field: str) -> Dict[str, str]:
    """Parse Phase 2 output correction strings into a field -> value dict.

    The Phase 2 processor writes final corrections into the output CSV. This
    function reconstructs the structured corrections dict from those strings,
    applying the same delimiter and fan-out logic used by Phase 3 Final Lookup.

    Args:
        correction_value: Correction value string from Phase 2 output column.
        correction_field: Correction field string from Phase 2 output column.

    Returns:
        Dict of correction_field -> expected_value, or empty dict for No Change
        or unrecognised values.
    """
    value = correction_value.strip()
    field_str = correction_field.strip()

    if not value or value.lower() in ('no change', 'client not found'):
        return {}
    if re.search(r'\bre\s+accounts?\b', value, re.IGNORECASE):
        return {}
    if not field_str or field_str.lower() in ('no change', 'client not found'):
        return {}

    value_parts = _split_correction_parts(value)
    field_parts = _split_correction_parts(field_str)

    corrections: Dict[str, str] = {}
    for field_item, val in zip(field_parts, value_parts):
        if ' & ' in field_item:
            for sub_field in field_item.split(' & '):
                corrections[sub_field.strip()] = val
        else:
            corrections[field_item] = val

    return corrections


def _extract_incident_correction(
    row: List[str],
    column_mapper: IncidentColumnMapper,
) -> Tuple[str, str]:
    """Extract the effective correction from an incident file row.

    Applies the same decision logic as Phase2Processor._create_lookup_result():
    1. If Correction has a value and Agree is Y/P/empty → use Correction.
    2. If Correction has a value and Agree is N/F → use Suggested Correction if
       present, else No Change.
    3. If Correction is empty → use Suggested Correction if present, else No Change.
    4. RE Account corrections → No Change.

    Args:
        row: Data row from the incident file.
        column_mapper: Column mapper for the incident file.

    Returns:
        Tuple of (correction_value, correction_field). Both are "No Change" when
        no correction applies.
    """
    def _cell(col: Optional[int]) -> str:
        return row[col].strip() if col is not None and len(row) > col else ""

    correction_value = _cell(column_mapper.get('correction'))
    correction_field = _cell(column_mapper.get('correction_field'))
    suggested_value = _cell(column_mapper.get('suggested_correction'))
    suggested_field = _cell(column_mapper.get('suggested_correction_field'))
    agree = _cell(column_mapper.get('agree_with_correction')).upper()

    if correction_value:
        if agree in ('N', 'F'):
            if suggested_value:
                correction_value, correction_field = suggested_value, suggested_field
            else:
                return "No Change", "No Change"
        # Y / P / empty → keep correction_value as-is
    else:
        if suggested_value:
            correction_value, correction_field = suggested_value, suggested_field
        else:
            return "No Change", "No Change"

    if re.search(r'\bre\s+accounts?\b', correction_value, re.IGNORECASE):
        return "No Change", "No Change"

    return correction_value, correction_field


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Phase2ReplayRecord:
    """Represents a single row from a Phase 2 output (Feedback stage) CSV.

    The correction_value and correction_field here are the SOURCE OF TRUTH for
    Final Lookup testing. They reflect the analyst-agreed corrections as resolved
    by the Phase 2 Processor.
    """

    transaction_ref: str
    incident_codes: List[str]
    correction_value: str
    correction_field: str
    source_file: str
    file_type: str  # 'single' or 'combined'


@dataclass
class Phase2CrossRef:
    """Result of cross-referencing a Phase 2 output correction against the
    source incident file.

    match_state values:
    - 'both_agree':    Phase 2 output and incident file agree on correction.
    - 'both_disagree': Both have corrections but values/fields differ.
    - 'output_only':   Phase 2 output has a correction, incident file has none.
    - 'incident_only': Incident file has a correction, Phase 2 output has none.
    - 'not_found':     Transaction not found in the incident file.
    """

    match_state: str
    incident_correction_value: str
    incident_correction_field: str


# ============================================================================
# Phase 2 Replay Index
# ============================================================================

class Phase2ReplayIndex:
    """Builds a transaction_ref -> Phase2ReplayRecord index from Phase 2 output CSVs.

    Phase 2 output files use the same column layout as Phase 2 input files —
    Phase2SingleColumns or Phase2CombinedColumns from core — because the Feedback
    stage writes corrections back into the original column positions.
    """

    def __init__(self, logger) -> None:
        self.records: Dict[str, Phase2ReplayRecord] = {}
        self.logger = logger

    @staticmethod
    def _detect_file_type(filename: str) -> str:
        """Return 'combined' if '+' appears in the filename, else 'single'."""
        return 'combined' if '+' in filename else 'single'

    @staticmethod
    def _get_column_mapping(file_type: str) -> Dict[str, int]:
        """Return column index mapping for the given file type."""
        cols: type
        if file_type == 'single':
            cols = Phase2SingleColumns
        else:
            cols = Phase2CombinedColumns
        return {
            'incident_code': cols.INCIDENT_CODE,
            'agrees': cols.AGREES,
            'correction_field': cols.CORRECTION_FIELD,
            'correction_value': cols.CORRECTION_VALUE,
            'transaction_ref': cols.TRANSACTION_REF,
        }

    def load_file(self, file_path: str) -> None:
        """Load a Phase 2 output CSV and index its records by transaction reference.

        Args:
            file_path: Absolute path to the Phase 2 output CSV.
        """
        filename = os.path.basename(file_path)
        file_type = self._detect_file_type(filename)
        col_map = self._get_column_mapping(file_type)
        min_cols = max(col_map.values()) + 1

        try:
            rows = _read_rows(file_path)

            if len(rows) < 2:
                self.logger.warning(f"No data rows in {filename}")
                return

            data_rows = rows[1:]
            loaded = 0

            for row in data_rows:
                # Pad short rows to avoid index errors
                while len(row) < min_cols:
                    row.append("")

                txn_ref = row[col_map['transaction_ref']].strip()
                if not txn_ref:
                    continue

                codes_str = row[col_map['incident_code']].strip()
                codes = [c.strip() for c in codes_str.split('|') if c.strip()]

                self.records[txn_ref] = Phase2ReplayRecord(
                    transaction_ref=txn_ref,
                    incident_codes=codes,
                    correction_value=row[col_map['correction_value']].strip(),
                    correction_field=row[col_map['correction_field']].strip(),
                    source_file=filename,
                    file_type=file_type,
                )
                loaded += 1

            self.logger.info(f"Loaded {loaded} records from {filename}")

        except Exception as e:
            self.logger.error(f"Error loading replay file {filename}: {e}")


# ============================================================================
# UnaVista Transaction Index
# ============================================================================

class UnaVistaTransactionIndex:
    """Loads UnaVista CSV files and builds a transaction_ref -> row_index dict.

    Unlike the Phase 3 Final Lookup's UnaVistaIndex (which uses identity-based
    indexes), this class uses transaction reference as the sole lookup key.
    The row index maps to the flat list of all transactions loaded across all
    input files.
    """

    def __init__(self, logger) -> None:
        self.transactions: List[List[str]] = []
        self.header: List[str] = []
        self.transaction_ref_index: Dict[str, int] = {}
        self.logger = logger

    def load_files(self, file_paths: List[str]) -> None:
        """Load one or more UnaVista CSV files into the index.

        Files are loaded in the order supplied (caller should sort by mtime).
        Only the first occurrence of a transaction reference is indexed; later
        duplicates are stored in the row list but not indexed.

        Args:
            file_paths: List of absolute paths to UnaVista CSV files.
        """
        global_idx = 0
        for file_path in file_paths:
            try:
                rows = _read_rows(file_path)

                if len(rows) < 2:
                    self.logger.warning(
                        f"UnaVista file empty or has no data rows: {os.path.basename(file_path)}"
                    )
                    continue

                if not self.header:
                    self.header = rows[0]

                data_rows = rows[1:]
                self.logger.info(
                    f"Loading {len(data_rows)} rows from {os.path.basename(file_path)}"
                )

                for row in data_rows:
                    txn_ref = row[1].strip() if len(row) > 1 else ""
                    if txn_ref and txn_ref not in self.transaction_ref_index:
                        self.transaction_ref_index[txn_ref] = global_idx
                    self.transactions.append(row)
                    global_idx += 1

            except Exception as e:
                self.logger.error(
                    f"Error loading UnaVista file {os.path.basename(file_path)}: {e}"
                )

        self.logger.info(
            f"Indexed {len(self.transactions)} UnaVista rows, "
            f"{len(self.transaction_ref_index)} unique transaction references"
        )

    def lookup(self, transaction_ref: str) -> Optional[int]:
        """Return the row index for a transaction reference, or None.

        Args:
            transaction_ref: Transaction reference to look up.

        Returns:
            Row index into self.transactions, or None if not found.
        """
        return self.transaction_ref_index.get(transaction_ref.strip())


# ============================================================================
# Main Processor
# ============================================================================

class Phase2FinalLookup:
    """Main processor for Phase 2 Final Lookup.

    Orchestrates:
    1. Discovery of Phase 2 output files and UnaVista files.
    2. Loading of all indexes (replay records, UnaVista rows, incident files).
    3. Per-transaction validation: test corrections against UnaVista data.
    4. Cross-referencing of Phase 2 output corrections against incident files
       (discrepancies are annotated in the output but do not override the test).
    5. Output generation: annotated UnaVista CSV with test_result at column 2.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[Dict] = None,
    ) -> None:
        """Initialise from a YAML config file or a config dict.

        Args:
            config_path: Path to YAML configuration file.
            config_dict: Configuration dictionary (takes precedence over config_path).

        Raises:
            ValueError: If neither config_path nor config_dict is provided.
        """
        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = ConfigManager.load_from_yaml(config_path)
        else:
            raise ValueError("Must provide either config_path or config_dict")

        # Paths
        paths = self.config.get('paths', {})
        self.replay_output_path: str = paths.get('replay_output', '')
        self.incident_files_path: str = paths.get('incident_files', '')
        self.unavista_files_path: str = paths.get('unavista_files', '')
        self.output_path: str = paths.get('output', self.replay_output_path)
        self.log_output_path: str = paths.get('log_output', self.output_path)

        # File patterns
        files = self.config.get('files', {})
        self.replay_patterns: List[str] = files.get('replay_patterns', ['*.csv'])
        self.incident_pattern: str = files.get('incident_pattern', '*.csv')
        self.unavista_pattern: str = files.get(
            'unavista_pattern', 'UnaVista_MiFIR_Manual_Corrections_*.csv'
        )

        # Column config for incident file cross-reference
        self.incident_columns: Dict[str, str] = self.config.get('incident_columns', {})

        # Logging
        log_level = self.config.get('processor', {}).get('log_level', 'INFO')
        self.logger = create_logger(
            name="phase2_final_lookup",
            log_dir=self.log_output_path,
            log_level=log_level,
        )

        # Stats
        self.stats = ProcessingStats()
        for key in ('processed_records', 'not_found', 'no_change',
                    'full_pass', 'full_fail', 'partial_pass',
                    'inconsistent', 'cross_ref_discrepancies'):
            self.stats.increment(key, 0)

        # Indexes
        self.replay_index = Phase2ReplayIndex(self.logger)
        self.unavista_index = UnaVistaTransactionIndex(self.logger)
        self.incident_indexes: Dict[str, IncidentFileIndex] = {}

        # File paths (populated by find_files)
        self.replay_file_paths: List[str] = []
        self.unavista_paths: List[str] = []

    # ------------------------------------------------------------------ #
    # File discovery
    # ------------------------------------------------------------------ #

    def find_files(self) -> None:
        """Discover Phase 2 output files and UnaVista files using glob patterns.

        Raises:
            FileNotFoundError: If no replay output files or no UnaVista files
                are found.
        """
        self.logger.info("Discovering input files...")

        for pattern in self.replay_patterns:
            matches = sorted(
                glob.glob(os.path.join(self.replay_output_path, pattern)),
                key=os.path.getmtime,
            )
            self.replay_file_paths.extend(matches)

        if not self.replay_file_paths:
            raise FileNotFoundError(
                f"No Phase 2 output files found matching {self.replay_patterns} "
                f"in {self.replay_output_path}"
            )
        self.logger.info(f"Found {len(self.replay_file_paths)} Phase 2 output file(s):")
        for p in self.replay_file_paths:
            self.logger.info(f"  {os.path.basename(p)}")

        self.unavista_paths = sorted(
            glob.glob(os.path.join(self.unavista_files_path, self.unavista_pattern)),
            key=os.path.getmtime,
        )
        if not self.unavista_paths:
            raise FileNotFoundError(
                f"No UnaVista files found matching {self.unavista_pattern} "
                f"in {self.unavista_files_path}"
            )
        self.logger.info(f"Found {len(self.unavista_paths)} UnaVista file(s):")
        for p in self.unavista_paths:
            self.logger.info(f"  {os.path.basename(p)}")

    # ------------------------------------------------------------------ #
    # Index loading
    # ------------------------------------------------------------------ #

    def load_indexes(self) -> None:
        """Load all indexes: replay records, UnaVista rows, and incident files."""
        self.logger.info("Loading indexes...")

        for file_path in self.replay_file_paths:
            self.replay_index.load_file(file_path)
        self.logger.info(
            f"Total replay records indexed: {len(self.replay_index.records)}"
        )

        self.unavista_index.load_files(self.unavista_paths)

        if self.incident_files_path and self.incident_columns:
            self._preload_incident_indexes()
        else:
            self.logger.info(
                "incident_files path or incident_columns not configured — "
                "cross-reference will be skipped"
            )

    def _preload_incident_indexes(self) -> None:
        """Load and index all incident files referenced by the replay records."""
        self.logger.info("Preloading incident files for cross-reference...")

        codes: Set[str] = set()
        for record in self.replay_index.records.values():
            codes.update(record.incident_codes)

        loaded = 0
        for code in codes:
            path = self.find_incident_file(code)
            if path:
                self.incident_indexes[code] = IncidentFileIndex(
                    path, self.incident_columns, self.logger
                )
                loaded += 1
            else:
                self.logger.warning(f"Incident file not found for code: {code}")

        self.logger.info(f"Loaded {loaded} incident files for cross-reference")

    # ------------------------------------------------------------------ #
    # Incident file discovery
    # ------------------------------------------------------------------ #

    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find the incident file for a given code using a four-tier glob strategy.

        Tier 1: Exact match using pattern prefix + space + code.
        Tier 2: Dash-separated variant for backwards compatibility.
        Tier 3: Space-anchored glob with exact code (avoids substring collisions,
                e.g. ``9_1`` matching ``19_1``).
        Tier 4: Space-anchored glob with suffix (handles filenames such as
                ``FY26 Q1 7_39_batch.csv``); regex-filtered for collision safety.

        Args:
            incident_code: Incident code string, e.g. ``"7_39"``.

        Returns:
            Absolute path to the incident file, or None if not found.
        """
        pattern_prefix = self.incident_pattern.replace('*.csv', '').strip()

        # Tier 1: "FY25 Q4 7_39.csv"
        path = os.path.join(self.incident_files_path, f"{pattern_prefix} {incident_code}.csv")
        if os.path.exists(path):
            return path

        # Tier 2: "FY25 Q4 - 7_39.csv"
        path_dash = os.path.join(
            self.incident_files_path, f"{pattern_prefix} - {incident_code}.csv"
        )
        if os.path.exists(path_dash):
            return path_dash

        # Tier 3: "* 7_39.csv" (exact, space-anchored)
        matches = glob.glob(os.path.join(self.incident_files_path, f"* {incident_code}.csv"))
        if matches:
            return matches[0]

        # Tier 4: "* 7_39*.csv" with regex collision guard
        # Regex: code must be preceded by whitespace and followed by whitespace,
        # underscore, or dot — prevents "9_1" matching "9_10" or "9_12".
        code_re = re.compile(rf'\s{re.escape(incident_code)}(?=[\s_.])')
        wider = glob.glob(os.path.join(self.incident_files_path, f"* {incident_code}*.csv"))
        for match in sorted(wider, key=os.path.getmtime):
            if code_re.search(os.path.basename(match)):
                return match

        return None

    # ------------------------------------------------------------------ #
    # Cross-reference
    # ------------------------------------------------------------------ #

    def cross_reference(
        self, record: Phase2ReplayRecord, incident_code: str
    ) -> Phase2CrossRef:
        """Cross-reference a Phase 2 output correction against the source incident file.

        The Phase 2 output correction is the source of truth; the incident file
        value is used only to detect discrepancies for annotation.

        Args:
            record: Phase 2 replay record (source of truth).
            incident_code: Incident code identifying which incident file to check.

        Returns:
            Phase2CrossRef describing the agreement/disagreement state.
        """
        if incident_code not in self.incident_indexes:
            return Phase2CrossRef(
                match_state='not_found',
                incident_correction_value='',
                incident_correction_field='',
            )

        index = self.incident_indexes[incident_code]
        row_idx = index.lookup_by_transaction_ref(record.transaction_ref)

        if row_idx is None:
            return Phase2CrossRef(
                match_state='not_found',
                incident_correction_value='',
                incident_correction_field='',
            )

        inc_value, inc_field = _extract_incident_correction(
            index.data_rows[row_idx], index.column_mapper
        )

        output_value = record.correction_value.strip()
        output_is_no_change = output_value.lower() in ('no change', 'client not found', '')
        incident_is_no_change = inc_value.lower() == 'no change'

        if output_is_no_change and incident_is_no_change:
            state = 'both_agree'
        elif not output_is_no_change and not incident_is_no_change:
            if (output_value.lower() == inc_value.lower() and
                    record.correction_field.strip().lower() == inc_field.lower()):
                state = 'both_agree'
            else:
                state = 'both_disagree'
        elif output_is_no_change:
            state = 'incident_only'
        else:
            state = 'output_only'

        return Phase2CrossRef(
            match_state=state,
            incident_correction_value=inc_value,
            incident_correction_field=inc_field,
        )

    def _format_discrepancy(self, cross_ref: Phase2CrossRef, incident_code: str) -> str:
        """Format a cross-reference discrepancy as a compact annotation string.

        Args:
            cross_ref: Cross-reference result for a single incident code.
            incident_code: Incident code (used in the annotation for clarity).

        Returns:
            Annotation string, or empty string when there is no discrepancy.
        """
        if cross_ref.match_state == 'both_agree':
            return ''
        if cross_ref.match_state == 'not_found':
            return f'[⚠ {incident_code}: txn not in incident file]'
        if cross_ref.match_state == 'output_only':
            return f'[⚠ {incident_code}: incident has no correction]'
        if cross_ref.match_state == 'incident_only':
            return (
                f'[⚠ {incident_code}: incident has '
                f'{cross_ref.incident_correction_field}='
                f'\'{cross_ref.incident_correction_value}\' but output has none]'
            )
        # both_disagree
        return (
            f'[⚠ {incident_code}: incident '
            f'{cross_ref.incident_correction_field}='
            f'\'{cross_ref.incident_correction_value}\']'
        )

    # ------------------------------------------------------------------ #
    # Client type resolution
    # ------------------------------------------------------------------ #

    def _get_client_types(self, incident_codes: List[str]) -> Set[str]:
        """Determine buyer/seller sides from incident codes via INCIDENT_CODE_MATRIX.

        Args:
            incident_codes: List of incident code strings.

        Returns:
            Set containing 'buyer' and/or 'seller'. Falls back to {'buyer'} when
            no codes are recognised.
        """
        types: Set[str] = set()
        for code in incident_codes:
            entry = INCIDENT_CODE_MATRIX.get(code)
            if entry:
                types.update(entry.get('sides', set()))
        return types or {'buyer'}

    # ------------------------------------------------------------------ #
    # Field testing
    # ------------------------------------------------------------------ #

    def _test_corrections(
        self,
        row_data: List[str],
        corrections: Dict[str, str],
        client_type: str,
    ) -> List[TestResult]:
        """Test a set of corrections against a UnaVista row for one client type.

        Args:
            row_data: UnaVista row data (list of cell strings).
            corrections: Dict of correction_field -> expected_value.
            client_type: 'buyer' or 'seller'.

        Returns:
            List of TestResult objects, one per correction field.
        """
        results: List[TestResult] = []

        for field_name, expected_value in corrections.items():
            col_idx = FieldMapper.get_unavista_index(field_name, client_type)

            if col_idx is None:
                self.logger.warning(
                    f"Unknown field mapping: '{field_name}' for {client_type}"
                )
                results.append(TestResult(
                    field_name=field_name,
                    expected=expected_value,
                    actual='UNKNOWN_FIELD',
                    passed=False,
                    source='',
                ))
                continue

            actual_value = row_data[col_idx].strip() if col_idx < len(row_data) else ''

            if expected_value.strip().upper() == 'NULL':
                passed = (actual_value == '')
            else:
                expected_norm = expected_value.strip().lower()
                actual_norm = actual_value.strip().lower()

                if 'date' in field_name.lower() or field_name.upper() == 'DOB':
                    expected_norm = DateParser.parse_date(expected_value) or expected_norm
                    actual_norm = DateParser.parse_date(actual_value) or actual_norm

                passed = (expected_norm == actual_norm)

            results.append(TestResult(
                field_name=field_name,
                expected=expected_value,
                actual=actual_value,
                passed=passed,
                source='',
            ))

        return results

    # ------------------------------------------------------------------ #
    # Per-transaction processing
    # ------------------------------------------------------------------ #

    def process_transaction(
        self,
        record: Phase2ReplayRecord,
        row_data: List[str],
    ) -> str:
        """Generate a test_result string for one UnaVista row.

        Uses the Phase 2 output correction as the source of truth. If cross-
        reference is enabled and the incident file disagrees, a discrepancy
        annotation is appended to the result string.

        Args:
            record: Replay record containing the Phase 2 output correction.
            row_data: UnaVista row to test against.

        Returns:
            Formatted test_result string.
        """
        value = record.correction_value.strip()
        is_no_change = value.lower() in ('no change', '')
        is_client_not_found = value.lower() == 'client not found'

        if is_client_not_found:
            return 'Transaction not found in incident file'

        # Detect multi-code inconsistencies written by the Feedback stage.
        # The Phase 2 processor joins inconsistent corrections with '|' (and no ¬).
        # A legitimate multi-field correction uses ¬ as the delimiter.
        if '|' in value and '\u00ac' not in value:
            self.stats.increment('inconsistent')
            return f'Inconsistent corrections from Phase 2: {value}'

        # Parse corrections from Phase 2 output (source of truth)
        corrections = _parse_phase2_corrections(value, record.correction_field)

        # Determine buyer/seller sides
        client_types = self._get_client_types(record.incident_codes)

        # Cross-reference against incident files (annotation only)
        discrepancy_parts: List[str] = []
        if self.incident_indexes:
            seen_codes: Set[str] = set()
            for code in record.incident_codes:
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                cross_ref = self.cross_reference(record, code)
                annotation = self._format_discrepancy(cross_ref, code)
                if annotation:
                    discrepancy_parts.append(annotation)
                    self.stats.increment('cross_ref_discrepancies')

        discrepancy_note = ' '.join(discrepancy_parts)

        if is_no_change or not corrections:
            self.stats.increment('no_change')
            result = 'No change'
            return f'{result} {discrepancy_note}'.strip()

        # Test each correction field per client type
        output_parts: List[str] = []
        all_passed = True
        any_tested = False

        for client_type in sorted(client_types):
            test_results = self._test_corrections(row_data, corrections, client_type)
            if not test_results:
                continue

            any_tested = True
            passed = [r for r in test_results if r.passed]
            failed = [r for r in test_results if not r.passed]

            if failed:
                all_passed = False

            parts: List[str] = []
            if passed:
                pass_str = ', '.join(f'{r.field_name}={r.expected}' for r in passed)
                parts.append(f'PASS ({client_type}): {pass_str}')
            if failed:
                fail_str = ' | '.join(
                    f"{r.field_name} expected '{r.expected}' got '{r.actual}'"
                    for r in failed
                )
                parts.append(f'FAIL ({client_type}): {fail_str}')

            if parts:
                output_parts.append(' | '.join(parts))

        if not any_tested:
            result = 'No testable corrections'
        else:
            result = ' || '.join(output_parts) if output_parts else 'No change'
            if all_passed:
                self.stats.increment('full_pass')
            else:
                self.stats.increment('full_fail')

        return f'{result} {discrepancy_note}'.strip()

    # ------------------------------------------------------------------ #
    # Output generation
    # ------------------------------------------------------------------ #

    def generate_output(self) -> str:
        """Generate the annotated UnaVista output CSV.

        Iterates all UnaVista rows, looks up each transaction reference against
        the Phase 2 replay index, runs the correction test, and inserts a
        ``test_result`` column at position 2.

        Returns:
            Filename of the generated output CSV.
        """
        self.logger.info("Generating output file...")
        not_found_count = 0

        os.makedirs(self.output_path, exist_ok=True)

        header = list(self.unavista_index.header)
        header.insert(2, 'test_result')

        output_rows: List[List[str]] = [header]

        for row_idx, row_data in enumerate(self.unavista_index.transactions):
            txn_ref = row_data[1].strip() if len(row_data) > 1 else ''
            record = self.replay_index.records.get(txn_ref)

            if record is None:
                test_result = 'Transaction not found'
                not_found_count += 1
                self.stats.increment('not_found')
            else:
                test_result = self.process_transaction(record, row_data)
                self.stats.increment('processed_records')

            row = list(row_data)
            row.insert(2, test_result)
            output_rows.append(row)

        if not_found_count:
            self.logger.info(
                f"{not_found_count} UnaVista transactions had no matching "
                "Phase 2 replay record"
            )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'output_Phase2_final_lookup_{timestamp}.csv'
        output_filepath = os.path.join(self.output_path, output_filename)

        with open(output_filepath, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.writer(f_out)
            writer.writerows(output_rows)

        self.logger.info(f"Output written to: {output_filename}")
        return output_filename

    # ------------------------------------------------------------------ #
    # Main execution
    # ------------------------------------------------------------------ #

    def run(self) -> int:
        """Main execution method.

        Returns:
            0 on success, 1 on fatal error.
        """
        start_time = datetime.now()

        try:
            self.logger.log_header("PHASE 2 FINAL LOOKUP v1.0")
            self.logger.info(f"Phase 2 output path: {self.replay_output_path}")
            self.logger.info(f"UnaVista files path: {self.unavista_files_path}")
            self.logger.info(f"Incident files path: {self.incident_files_path or '(not configured)'}")
            self.logger.info(f"Output path:         {self.output_path}")

            self.find_files()
            self.load_indexes()
            self.generate_output()

            elapsed = datetime.now() - start_time
            self.logger.info(f"Total processing time: {elapsed}")
            self.logger.log_header("PROCESSING SUMMARY")
            self.logger.log_stats(self.stats)

            if self.incident_indexes:
                cross_ref_pct = (
                    self.stats.custom_stats.get('cross_ref_discrepancies', 0)
                    / max(self.stats.custom_stats.get('processed_records', 1), 1)
                    * 100
                )
                self.logger.info(
                    f"Cross-reference discrepancies: "
                    f"{self.stats.custom_stats.get('cross_ref_discrepancies', 0)} "
                    f"({cross_ref_pct:.1f}% of processed records)"
                )

            self.logger.info("Phase 2 Final Lookup v1.0 completed successfully")
            return 0

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            return 1


# ============================================================================
# CLI Entry Point
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Phase 2 Final Lookup v1.0 — Validate Phase II corrections against UnaVista data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with configuration file
  python -m replay.phase_2_final_lookup --config config/local/replay/phase2_final.yaml

  # Override log level
  python -m replay.phase_2_final_lookup --config config/phase2_final.yaml --log-level DEBUG
        """,
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file',
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Override log level from configuration',
    )
    parser.add_argument(
        '--gui-mode',
        action='store_true',
        help=argparse.SUPPRESS,
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point with CLI support."""
    args = parse_args()

    try:
        if args.config:
            config = ConfigManager.load_from_yaml(args.config)
        elif not getattr(args, 'gui_mode', False):
            default_config = (
                Path(__file__).parent.parent.parent
                / 'config' / 'local' / 'replay' / 'phase2_final.yaml'
            )
            if default_config.exists():
                print(f"Loading default configuration from {default_config}...")
                config = ConfigManager.load_from_yaml(str(default_config))
            else:
                print("Error: No configuration specified and default config not found.")
                print("Use --config to specify a configuration file.")
                return 1
        else:
            # gui_mode without config — caller is responsible for providing config_dict
            return 1

        if args.log_level:
            if 'processor' not in config:
                config['processor'] = {}
            config['processor']['log_level'] = args.log_level

        processor = Phase2FinalLookup(config_dict=config)
        return processor.run()

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
