#!/usr/bin/env python3
"""
Phase 3 Final Lookup Script v2.0
Refactored version using shared txr_replay_core library.

Author: GitHub Copilot
Date: December 23, 2025
Version: 2.0 - Refactored to use txr_replay_core library
"""

import csv
import os
import glob
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import argparse
import re
from pathlib import Path

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False

# Import from core library
from core import (
    ProcessingStats,
    UnaVistaTransaction,
    ConfigManager,
    create_logger,
    DateParser,
    safe_open_csv,
    INCIDENT_CODE_MATRIX,
    get_client_types,
)

# Import identity-based incident file indexer from the Feedback stage for
# cross-reference. IncidentFileIndex from phase_3_processor uses buyer/seller/DM
# identity indexes (not transaction-reference based).
from .phase_3_processor import (
    IncidentFileIndex as IncidentIdentityIndex,
    IncidentColumnMapper as IncidentIdentityColumnMapper,
)

# ============================================================================
# File Reading Helper
# ============================================================================


def _read_rows(file_path: str) -> List[List[str]]:
    """Read a CSV or XLSX file and return all rows as lists of strings.

    Args:
        file_path: Absolute path to the file. Files ending ``.xlsx`` are read
            with ``openpyxl``; all other files are treated as CSV.

    Returns:
        List of rows, where each row is a list of cell values converted to
        strings.  The first row is the header; subsequent rows are data.

    Raises:
        ImportError: If the file is ``.xlsx`` but ``openpyxl`` is not installed.
        FileNotFoundError: If the file does not exist.
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
# Data Classes
# ============================================================================

@dataclass
class ReplayRecord:
    """Represents a client correction record from Replay files"""
    client_id: str
    first_name: str
    surname: str
    date_of_birth: str
    corrections: Dict[str, str]  # field_name -> expected_value
    incident_codes: List[str]
    source_file: str  # 'IDs' or 'Names'
    original_row: List[str]
    row_index: int
    
@dataclass
class ClientKey:
    """Unique identifier for a client"""
    id: str
    first_name: str
    surname: str
    dob: str
    
    def __hash__(self):
        return hash((self.id.lower(), self.first_name.lower(), self.surname.lower(), self.dob))
    
    def __eq__(self, other):
        if not isinstance(other, ClientKey):
            return False
        return (self.id.lower() == other.id.lower() and 
                self.first_name.lower() == other.first_name.lower() and
                self.surname.lower() == other.surname.lower() and
                self.dob == other.dob)

@dataclass
class TestResult:
    """Represents the result of testing a field"""
    field_name: str
    expected: str
    actual: str
    passed: bool
    source: str  # 'IDs' or 'Names'


# ============================================================================
# Date Parser (from phase_3_processor_v4_2.py)
# ============================================================================



class FieldMapper:
    """Maps correction field names to UnaVista column indices"""
    
    # Short code mappings (for both buyer and seller)
    SHORT_CODE_FIELDS = {
        'DOB': 'Date of Birth',
        'FN': 'First Name',
        'SN': 'Surname',
        'ID': 'ID',
        'IDT': 'ID Sub Type'
    }
    
    # Long name mappings (specific decision maker fields)
    LONG_NAME_FIELDS = {
        'Buyer decision maker code': ('buyer_dm', 'ID'),
        'Type of buyer decision maker code': ('buyer_dm', 'ID Sub Type'),
        'Buy decision maker - First name(s)': ('buyer_dm', 'First Name'),
        'Buy decision maker - Surname(s)': ('buyer_dm', 'Surname'),
        'Buy decision maker - Date of birth': ('buyer_dm', 'Date of Birth'),
        'Seller decision maker code': ('seller_dm', 'ID'),
        'Type of Seller decision maker code': ('seller_dm', 'ID Sub Type'),
        'Sell decision maker - First name(s)': ('seller_dm', 'First Name'),
        'Sell decision maker - Surname(s)': ('seller_dm', 'Surname'),
        'Sell decision maker - Date of birth': ('seller_dm', 'Date of Birth'),
    }
    
    # UnaVista column indices
    UNAVISTA_INDICES = {
        'buyer': {
            'ID Type': 6,
            'ID Sub Type': 7,
            'ID': 8,
            'Country of Branch': 9,
            'First Name': 10,
            'Surname': 11,
            'Date of Birth': 12,
        },
        'buyer_dm': {
            'ID Type': 13,
            'ID Sub Type': 14,
            'ID': 15,
            'First Name': 16,
            'Surname': 17,
            'Date of Birth': 18,
        },
        'seller': {
            'ID Type': 19,
            'ID Sub Type': 20,
            'ID': 21,
            'Country of Branch': 22,
            'First Name': 23,
            'Surname': 24,
            'Date of Birth': 25,
        },
        'seller_dm': {
            'ID Type': 26,
            'ID Sub Type': 27,
            'ID': 28,
            'First Name': 29,
            'Surname': 30,
            'Date of Birth': 31,
        }
    }
    
    @classmethod
    def get_unavista_index(cls, correction_field: str, client_type: str) -> Optional[int]:
        """
        Get UnaVista column index for a correction field.
        
        Args:
            correction_field: Field name from correction (e.g., 'ID', 'FN', 'Buyer decision maker code')
            client_type: 'buyer' or 'seller'
        
        Returns:
            Column index or None if not found
        """
        # Check if it's a long name (decision maker field)
        if correction_field in cls.LONG_NAME_FIELDS:
            entity_type, field_type = cls.LONG_NAME_FIELDS[correction_field]
            return cls.UNAVISTA_INDICES.get(entity_type, {}).get(field_type)
        
        # Check if it's a short code
        if correction_field in cls.SHORT_CODE_FIELDS:
            field_type = cls.SHORT_CODE_FIELDS[correction_field]
            return cls.UNAVISTA_INDICES.get(client_type, {}).get(field_type)
        
        return None

# ============================================================================
# UnaVista Index
# ============================================================================

class UnaVistaIndex:
    """Optimized UnaVista index built from one or more UnaVista files."""
    
    def __init__(self, file_paths: List[str], logger: logging.Logger):
        # Accept a single path string for backwards compatibility
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        self.file_paths = file_paths
        self.logger = logger
        self.transactions = []  # List of UnaVistaTransaction objects
        
        # Pre-built indexes for O(1) lookups
        self.buyer_id_index = defaultdict(list)      # id -> transaction_indices
        self.seller_id_index = defaultdict(list)     # id -> transaction_indices
        self.buyer_name_index = defaultdict(list)    # (first, last, dob) -> transaction_indices
        self.seller_name_index = defaultdict(list)   # (first, last, dob) -> transaction_indices
        
        # Decision maker indexes
        self.buyer_dm_id_index = defaultdict(list)
        self.seller_dm_id_index = defaultdict(list)
        self.buyer_dm_name_index = defaultdict(list)
        self.seller_dm_name_index = defaultdict(list)

        # Counter incremented each time a decision maker index provides the match
        self.dm_match_count: int = 0

        self.header: List[str] = []
        self.load_and_index()
    
    def load_and_index(self):
        """Load all UnaVista files and build combined indexes."""
        global_idx = 0
        for file_path in self.file_paths:
            try:
                rows = _read_rows(file_path)
                
                if len(rows) < 2:
                    self.logger.warning(f"UnaVista file is empty or has no data rows: {os.path.basename(file_path)}")
                    continue
                
                # Use the first file's header; validate subsequent files match
                if not self.header:
                    self.header = rows[0]
                
                data_rows = rows[1:]
                self.logger.info(f"Loading {len(data_rows)} UnaVista transactions from {os.path.basename(file_path)}...")
                
                for row in data_rows:
                    if len(row) < 32:
                        global_idx += 1
                        continue
                    
                    transaction_ref = row[1].strip() if len(row) > 1 else ""
                    transaction = UnaVistaTransaction(
                        transaction_ref=transaction_ref,
                        row_data=row,
                        row_index=global_idx
                    )
                    self.transactions.append(transaction)
                    
                    # Index buyer data
                    self._index_buyer(row, global_idx)
                    # Index seller data
                    self._index_seller(row, global_idx)
                    # Index decision makers
                    self._index_decision_makers(row, global_idx)
                    global_idx += 1
                
            except Exception as e:
                self.logger.error(f"Error loading UnaVista file {os.path.basename(file_path)}: {e}")
        
        self.logger.info(f"Indexed {len(self.transactions)} UnaVista transactions total")
    
    def _index_buyer(self, row: List[str], idx: int):
        """Index buyer fields"""
        # Joint account rows may carry pipe- or semicolon-delimited IDs/names.
        # Each individual member is indexed separately so replay records with a
        # single ID match.
        buyer_id_raw = row[8].strip() if len(row) > 8 else ""
        for buyer_id in buyer_id_raw.replace(';', '|').split('|'):
            buyer_id = buyer_id.strip().lower()
            if buyer_id:
                self.buyer_id_index[buyer_id].append(idx)
        
        buyer_first_raw = row[10].strip() if len(row) > 10 else ""
        buyer_last_raw = row[11].strip() if len(row) > 11 else ""
        buyer_dob_raw = row[12].strip() if len(row) > 12 else ""
        first_parts = [p.strip().lower() for p in buyer_first_raw.split('|')] if buyer_first_raw else []
        last_parts = [p.strip().lower() for p in buyer_last_raw.split('|')] if buyer_last_raw else []
        dob_parts = [DateParser.parse_date(p.strip()) or "" for p in buyer_dob_raw.split('|')] if buyer_dob_raw else []
        for buyer_first, buyer_last, buyer_dob in zip(first_parts, last_parts, dob_parts):
            if buyer_first and buyer_last:
                name_key = (buyer_first, buyer_last, buyer_dob)
                self.buyer_name_index[name_key].append(idx)
    
    def _index_seller(self, row: List[str], idx: int):
        """Index seller fields"""
        # Seller IDs may be pipe- or semicolon-delimited for joint accounts.
        seller_id_raw = row[21].strip() if len(row) > 21 else ""
        for seller_id in seller_id_raw.replace(';', '|').split('|'):
            seller_id = seller_id.strip().lower()
            if seller_id:
                self.seller_id_index[seller_id].append(idx)
        
        seller_first_raw = row[23].strip() if len(row) > 23 else ""
        seller_last_raw = row[24].strip() if len(row) > 24 else ""
        seller_dob_raw = row[25].strip() if len(row) > 25 else ""
        first_parts = [p.strip().lower() for p in seller_first_raw.split('|')] if seller_first_raw else []
        last_parts = [p.strip().lower() for p in seller_last_raw.split('|')] if seller_last_raw else []
        dob_parts = [DateParser.parse_date(p.strip()) or "" for p in seller_dob_raw.split('|')] if seller_dob_raw else []
        for seller_first, seller_last, seller_dob in zip(first_parts, last_parts, dob_parts):
            if seller_first and seller_last:
                name_key = (seller_first, seller_last, seller_dob)
                self.seller_name_index[name_key].append(idx)
    
    def _index_decision_makers(self, row: List[str], idx: int):
        """Index decision maker fields"""
        # Buyer decision maker
        buyer_dm_id_raw = row[15].strip() if len(row) > 15 else ""
        for buyer_dm_id in buyer_dm_id_raw.split('|'):
            buyer_dm_id = buyer_dm_id.strip().lower()
            if buyer_dm_id:
                self.buyer_dm_id_index[buyer_dm_id].append(idx)
        
        buyer_dm_first_raw = row[16].strip() if len(row) > 16 else ""
        buyer_dm_last_raw = row[17].strip() if len(row) > 17 else ""
        buyer_dm_dob_raw = row[18].strip() if len(row) > 18 else ""
        dm_first_parts = [p.strip().lower() for p in buyer_dm_first_raw.split('|')] if buyer_dm_first_raw else []
        dm_last_parts = [p.strip().lower() for p in buyer_dm_last_raw.split('|')] if buyer_dm_last_raw else []
        dm_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in buyer_dm_dob_raw.split('|')] if buyer_dm_dob_raw else []
        for buyer_dm_first, buyer_dm_last, buyer_dm_dob in zip(dm_first_parts, dm_last_parts, dm_dob_parts):
            if buyer_dm_first and buyer_dm_last:
                name_key = (buyer_dm_first, buyer_dm_last, buyer_dm_dob)
                self.buyer_dm_name_index[name_key].append(idx)
        
        # Seller decision maker
        seller_dm_id_raw = row[28].strip() if len(row) > 28 else ""
        for seller_dm_id in seller_dm_id_raw.split('|'):
            seller_dm_id = seller_dm_id.strip().lower()
            if seller_dm_id:
                self.seller_dm_id_index[seller_dm_id].append(idx)
        
        seller_dm_first_raw = row[29].strip() if len(row) > 29 else ""
        seller_dm_last_raw = row[30].strip() if len(row) > 30 else ""
        seller_dm_dob_raw = row[31].strip() if len(row) > 31 else ""
        dm_first_parts = [p.strip().lower() for p in seller_dm_first_raw.split('|')] if seller_dm_first_raw else []
        dm_last_parts = [p.strip().lower() for p in seller_dm_last_raw.split('|')] if seller_dm_last_raw else []
        dm_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in seller_dm_dob_raw.split('|')] if seller_dm_dob_raw else []
        for seller_dm_first, seller_dm_last, seller_dm_dob in zip(dm_first_parts, dm_last_parts, dm_dob_parts):
            if seller_dm_first and seller_dm_last:
                name_key = (seller_dm_first, seller_dm_last, seller_dm_dob)
                self.seller_dm_name_index[name_key].append(idx)
    
    def lookup_by_id(self, client_id: str, client_type: str) -> List[UnaVistaTransaction]:
        """
        Fast O(1) ID lookup using indexes
        
        Args:
            client_id: Client ID to search for
            client_type: 'buyer' or 'seller'
        
        Returns:
            List of matching transactions
        """
        if not client_id:
            return []
        
        client_id_lower = client_id.lower()
        
        if client_type == 'buyer':
            indices = self.buyer_id_index.get(client_id_lower, [])
        else:
            indices = self.seller_id_index.get(client_id_lower, [])

        if indices:
            return [self.transactions[i] for i in indices]

        # Fallback: check decision maker indexes when no match in buyer/seller fields
        if client_type == 'buyer':
            dm_indices = self.buyer_dm_id_index.get(client_id_lower, [])
        else:
            dm_indices = self.seller_dm_id_index.get(client_id_lower, [])

        if dm_indices:
            self.dm_match_count += 1
            return [self.transactions[i] for i in dm_indices]

        return []
    
    def lookup_by_name(self, first_name: str, surname: str, dob: str, client_type: str) -> List[UnaVistaTransaction]:
        """
        Fast O(1) name lookup using indexes
        
        Args:
            first_name: Client first name
            surname: Client surname
            dob: Client date of birth
            client_type: 'buyer' or 'seller'
        
        Returns:
            List of matching transactions
        """
        first_lower = first_name.lower().strip()
        surname_lower = surname.lower().strip()
        dob_parsed = DateParser.parse_date(dob) if dob else ""
        
        name_key = (first_lower, surname_lower, dob_parsed or "")
        
        if client_type == 'buyer':
            indices = self.buyer_name_index.get(name_key, [])
        else:
            indices = self.seller_name_index.get(name_key, [])
        
        # Try without DOB if no exact match
        if not indices and dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            if client_type == 'buyer':
                indices = self.buyer_name_index.get(name_key_no_dob, [])
            else:
                indices = self.seller_name_index.get(name_key_no_dob, [])

        if indices:
            return [self.transactions[i] for i in indices]

        # Fallback: check decision maker name indexes when no match in buyer/seller fields
        if client_type == 'buyer':
            dm_indices = self.buyer_dm_name_index.get(name_key, [])
        else:
            dm_indices = self.seller_dm_name_index.get(name_key, [])

        if not dm_indices and dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            if client_type == 'buyer':
                dm_indices = self.buyer_dm_name_index.get(name_key_no_dob, [])
            else:
                dm_indices = self.seller_dm_name_index.get(name_key_no_dob, [])

        if dm_indices:
            self.dm_match_count += 1
            return [self.transactions[i] for i in dm_indices]

        return []

# ============================================================================
# Replay Record Index
# ============================================================================

class ReplayRecordIndex:
    """Index of client correction records from Replay files"""
    
    # Fallback hardcoded indices used when a column name cannot be found in the header.
    # These match the positions written by the Phase 3 Processor.
    _FALLBACK_INDICES = {
        'incident_codes':    4,
        'correction':        6,
        'correction_field':  7,
    }
    # Optional columns — resolved by name only, no positional fallback.
    _OPTIONAL_COLUMNS = (
        'agree_with_correction',
        'suggested_correction',
        'suggested_correction_field',
    )
    
    def __init__(self, logger: logging.Logger, incident_columns: Optional[Dict[str, str]] = None):
        self.logger = logger
        self.incident_columns = incident_columns or {}
        self.records = []  # List of ReplayRecord objects
        self.client_records = defaultdict(list)  # ClientKey -> List[ReplayRecord]
        # Use incident matrix from core library
        self.incident_matrix = INCIDENT_CODE_MATRIX
        self.logger.info(f"Loaded {len(self.incident_matrix)} incident code mappings from core library")
    
    def load_replay_file(self, file_path: str, file_type: str):
        """
        Load and index a Replay file
        
        Args:
            file_path: Path to replay file
            file_type: 'IDs' or 'Names'
        """
        try:
            rows = _read_rows(file_path)
            
            if len(rows) < 2:
                self.logger.warning(f"Replay file {file_type} is empty")
                return
            
            header = rows[0]
            col_map = self._build_col_map(header, os.path.basename(file_path))
            data_rows = rows[1:]
            self.logger.info(f"Processing {len(data_rows)} records from {file_type} file...")
            
            for i, row in enumerate(data_rows):
                # Ensure row has enough columns
                while len(row) < 9:
                    row.append("")
                
                # Parse record based on file type
                if file_type == 'IDs':
                    record = self._parse_ids_record(row, i, file_type, col_map)
                else:
                    record = self._parse_names_record(row, i, file_type, col_map)
                
                if record:  # Add all records (including 'No change')
                    self.records.append(record)
                    
                    # Create client key for duplicate detection
                    client_key = ClientKey(
                        id=record.client_id,
                        first_name=record.first_name,
                        surname=record.surname,
                        dob=record.date_of_birth
                    )
                    self.client_records[client_key].append(record)
            
            self.logger.info(f"Indexed {len([r for r in self.records if r.source_file == file_type])} records from {file_type}")
            
        except Exception as e:
            self.logger.error(f"Error loading replay file {file_type}: {e}")
    
    def _build_col_map(self, header: List[str], filename: str) -> Dict[str, int]:
        """
        Build a mapping from logical column names to their indices in the file header.

        For each key in _FALLBACK_INDICES the method first looks for the column name
        specified in the incident_columns config, then falls back to the hardcoded
        default index with a warning.

        Args:
            header: List of column name strings from the CSV header row.
            filename: File name used in log messages.

        Returns:
            Dict mapping logical name (e.g. 'correction') to column index.
        """
        col_map: Dict[str, Optional[int]] = {}
        for logical_name, fallback_idx in self._FALLBACK_INDICES.items():
            col_name = self.incident_columns.get(logical_name)
            if col_name and col_name in header:
                col_map[logical_name] = header.index(col_name)
                self.logger.debug(
                    f"{filename}: '{logical_name}' mapped to column "
                    f"'{col_name}' (index {col_map[logical_name]})"
                )
            else:
                col_map[logical_name] = fallback_idx
                if col_name:
                    self.logger.warning(
                        f"{filename}: column '{col_name}' for '{logical_name}' not found "
                        f"in header — falling back to index {fallback_idx}. "
                        f"Available columns: {header}"
                    )
                else:
                    self.logger.debug(
                        f"{filename}: no config entry for '{logical_name}' "
                        f"— using default index {fallback_idx}"
                    )
        # Optional columns: resolve by name only; set to None if absent
        for logical_name in self._OPTIONAL_COLUMNS:
            col_name = self.incident_columns.get(logical_name)
            if col_name and col_name in header:
                col_map[logical_name] = header.index(col_name)
                self.logger.debug(
                    f"{filename}: '{logical_name}' mapped to column "
                    f"'{col_name}' (index {col_map[logical_name]})"
                )
            else:
                col_map[logical_name] = None
                if col_name:
                    self.logger.debug(
                        f"{filename}: optional column '{col_name}' for '{logical_name}' "
                        f"not found in header — will not be used"
                    )
        return col_map

    def _parse_ids_record(self, row: List[str], row_index: int, file_type: str, col_map: Dict[str, Optional[int]]) -> Optional[ReplayRecord]:
        """Parse Inconsistent_IDs format record"""
        try:
            # Index 0: Reported Name & DOB (FN~SN~CCYY-MM-DD)
            name_dob_parts = row[0].split('~')
            if len(name_dob_parts) >= 3:
                first_name = name_dob_parts[0].strip()
                surname = name_dob_parts[1].strip()
                raw_dob = name_dob_parts[2].strip()
                parsed_dob = DateParser.parse_date(raw_dob) or raw_dob
            else:
                first_name = surname = parsed_dob = ""
            
            # Index 1: Reported IDs
            id_data = row[1].strip()
            ids = id_data.split('\n') if '\n' in id_data else [id_data]
            client_id = ""
            for id_entry in ids:
                if ':' in id_entry:
                    parts = id_entry.split(':', 1)
                    client_id = parts[1].strip()
                    break
            
            # Incident Codes — column resolved from config or fallback index 4
            incident_codes_idx = col_map['incident_codes']
            incident_codes_str = row[incident_codes_idx].strip() if len(row) > incident_codes_idx else ""
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            # Correction value, field, and agreement columns — resolved from config
            correction_idx       = col_map['correction']
            correction_field_idx = col_map['correction_field']
            agree_idx            = col_map.get('agree_with_correction')
            suggested_idx        = col_map.get('suggested_correction')
            suggested_field_idx  = col_map.get('suggested_correction_field')

            correction_str       = row[correction_idx].strip()       if len(row) > correction_idx else ""
            field_str            = row[correction_field_idx].strip()  if len(row) > correction_field_idx else ""
            agree_str            = row[agree_idx].strip()             if agree_idx is not None and len(row) > agree_idx else ""
            suggested_str        = row[suggested_idx].strip()         if suggested_idx is not None and len(row) > suggested_idx else ""
            suggested_field_str  = row[suggested_field_idx].strip()   if suggested_field_idx is not None and len(row) > suggested_field_idx else ""

            corrections = self._parse_corrections(
                correction_str, field_str,
                agree_str, suggested_str, suggested_field_str,
            )
            
            # Skip rows where both correction_str and field_str are empty/unparseable.
            # "No Change" rows are NOT skipped — _parse_corrections returns a sentinel
            # entry for them so they are annotated in the output.
            if not corrections:
                return None
            
            return ReplayRecord(
                client_id=client_id,
                first_name=first_name,
                surname=surname,
                date_of_birth=parsed_dob,
                corrections=corrections,
                incident_codes=incident_codes,
                source_file=file_type,
                original_row=row,
                row_index=row_index
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing IDs record at row {row_index + 1}: {e}")
            return None
    
    def _parse_names_record(self, row: List[str], row_index: int, file_type: str, col_map: Dict[str, Optional[int]]) -> Optional[ReplayRecord]:
        """Parse Inconsistent_Names format record"""
        try:
            # Index 0: Reported ID
            id_data = row[0].strip()
            if '~' in id_data:
                client_id = id_data.split('~', 1)[0].strip()
            else:
                client_id = id_data
            
            # Index 1: Reported Names & DOBs (FN:SN:CCYY-MM-DD)
            name_dob_data = row[1].strip()
            name_dob_parts = name_dob_data.split(':')
            if len(name_dob_parts) >= 3:
                first_name = name_dob_parts[0].strip()
                surname = name_dob_parts[1].strip()
                raw_dob = name_dob_parts[2].strip()
                parsed_dob = DateParser.parse_date(raw_dob) or raw_dob
            else:
                first_name = surname = parsed_dob = ""
            
            # Incident Codes — column resolved from config or fallback index 4
            incident_codes_idx = col_map['incident_codes']
            incident_codes_str = row[incident_codes_idx].strip() if len(row) > incident_codes_idx else ""
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            # Correction value, field, and agreement columns — resolved from config
            correction_idx       = col_map['correction']
            correction_field_idx = col_map['correction_field']
            agree_idx            = col_map.get('agree_with_correction')
            suggested_idx        = col_map.get('suggested_correction')
            suggested_field_idx  = col_map.get('suggested_correction_field')

            correction_str       = row[correction_idx].strip()       if len(row) > correction_idx else ""
            field_str            = row[correction_field_idx].strip()  if len(row) > correction_field_idx else ""
            agree_str            = row[agree_idx].strip()             if agree_idx is not None and len(row) > agree_idx else ""
            suggested_str        = row[suggested_idx].strip()         if suggested_idx is not None and len(row) > suggested_idx else ""
            suggested_field_str  = row[suggested_field_idx].strip()   if suggested_field_idx is not None and len(row) > suggested_field_idx else ""

            corrections = self._parse_corrections(
                correction_str, field_str,
                agree_str, suggested_str, suggested_field_str,
            )

            # Skip rows where both correction_str and field_str are empty/unparseable.
            # "No Change" rows are NOT skipped — _parse_corrections returns a sentinel
            # entry for them so they are annotated in the output.
            if not corrections:
                return None

            return ReplayRecord(
                client_id=client_id,
                first_name=first_name,
                surname=surname,
                date_of_birth=parsed_dob,
                corrections=corrections,
                incident_codes=incident_codes,
                source_file=file_type,
                original_row=row,
                row_index=row_index
            )

        except Exception as e:
            self.logger.error(f"Error parsing Names record at row {row_index + 1}: {e}")
            return None

    @staticmethod
    def _split_correction_parts(raw: str) -> List[str]:
        """
        Split a correction value or field string on the appropriate delimiter.

        Supports two delimiters:
        - ``¬`` (negation sign) — takes precedence when present
        - ``:`` (colon) — used when ``¬`` is absent

        Leading/trailing whitespace is stripped from each part.

        Args:
            raw: The raw correction or field string to split.

        Returns:
            List of stripped string parts.
        """
        if '\u00ac' in raw:  # ¬
            return [p.strip() for p in raw.split('\u00ac')]
        return [p.strip() for p in raw.split(':')]

    def _parse_corrections(
        self,
        correction_str: str,
        field_str: str,
        agree_str: str = "",
        suggested_str: str = "",
        suggested_field_str: str = "",
    ) -> Dict[str, str]:
        """
        Parse corrections and fields with support for ampersand-combined fields.

        Applies correction fallback logic before parsing:
        - If Correction is empty, falls back to Suggested Correction if present; otherwise
          treats the record as No Change so it still reaches generate_output and is annotated.
        - If Agree With Correction is N/No/F (only relevant when that column exists in the
          source file), Suggested Correction overrides Correction if present; otherwise the
          record is treated as No Change.
        - If Correction is "No Change" (or resolves to No Change after fallback), returns the
          sentinel {"No Change": "No Change"} so the record is annotated rather than dropped.

        Two delimiters are accepted for both the correction and field strings:
        - ``:`` (colon) — the standard delimiter inherited from the original VBA macros
        - ``¬`` (negation sign) — an alternative delimiter that may appear in exported CSVs;
          takes precedence over ``:`` when present in the correction string

        Args:
            correction_str: e.g., ``"Val1:Val2:Val3:Val4"`` or ``"Val1¬Val2¬Val3"`` or
                ``"No Change"``
            field_str: e.g., ``"Field1:Field2:Field3 & Field4"`` or
                ``"Field1¬Field2¬Field3 & Field4"``; empty string for No Change
            agree_str: Contents of the Agree With Correction column (Y/N/P/F/empty)
            suggested_str: Contents of the Suggested Correction column
            suggested_field_str: Contents of the Suggested Correction Field column

        Returns:
            Dictionary of field -> expected_value

        Note: When a delimiter-separated field item contains ' & ', it means that item
              represents multiple fields that all receive the same correction value.
        """
        # Apply agree/suggested override before anything else
        agree_normalised = agree_str.strip().upper()
        if agree_normalised in ('N', 'NO', 'F'):
            if suggested_str.strip():
                correction_str = suggested_str.strip()
                field_str = suggested_field_str.strip()
            else:
                return {"No Change": "No Change"}

        corrections: Dict[str, str] = {}

        if not correction_str:
            # No client correction — fall back to suggested correction if available,
            # otherwise treat as No Change so the record is still annotated.
            if suggested_str.strip():
                correction_str = suggested_str.strip()
                field_str = suggested_field_str.strip()
            else:
                return {"No Change": "No Change"}

        # Phase 3 processor writes "No Change" with an empty field string.
        # Preserve as a sentinel so the record reaches process_client and is
        # annotated as "No change" in the output rather than being dropped.
        if correction_str.strip().lower() == "no change":
            return {"No Change": "No Change"}

        # Corrections referring to RE Account(s) are not client data changes.
        if re.search(r'\bre\s+accounts?\b', correction_str, re.IGNORECASE):
            self.logger.debug("RE Account correction detected, treating as No Change")
            return {"No Change": "No Change"}

        if not field_str:
            return corrections

        # Split using whichever delimiter is present (¬ takes precedence over :)
        if '\u00ac' in correction_str:
            self.logger.debug(
                "\u00ac delimiter detected in correction field, normalising to parts"
            )
        correction_parts = self._split_correction_parts(correction_str)
        field_parts = self._split_correction_parts(field_str)

        # Pair them up
        for field, value in zip(field_parts, correction_parts):
            # Check if this field item contains ' & ' (multiple fields with same value)
            if ' & ' in field:
                # Split on ampersand and apply same value to each field
                sub_fields = [f.strip() for f in field.split(' & ')]
                for sub_field in sub_fields:
                    corrections[sub_field] = value
            else:
                corrections[field] = value

        return corrections

    def get_client_types(self, incident_codes: List[str]) -> Set[str]:
        """
        Determine if client is buyer, seller, or both based on incident codes
        
        Returns:
            Set containing 'buyer' and/or 'seller'
        """
        types = set()
        for code in incident_codes:
            if code in self.incident_matrix:
                types.update(self.incident_matrix[code]['sides'])
            else:
                # Log unknown incident codes for debugging
                self.logger.debug(f"Unknown incident code: {code}")
        return types

# ============================================================================
# Main Processor
# ============================================================================

class Phase3FinalLookup:
    """Main processor for Phase 3 Final Lookup with configuration management"""
    
    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize Phase 3 Final Lookup
        
        Args:
            config_path: Path to YAML configuration file
            config_dict: Configuration dictionary (overrides config_path)
        """
        # Load configuration
        if config_dict:
            self.config = config_dict
        elif config_path:
            self.config = ConfigManager.load_from_yaml(config_path)
        else:
            raise ValueError("Must provide either config_path or config_dict")
        
        # Get paths from config using standardized names
        self.replay_input_path = self.config.get('paths', {}).get('replay_input', '')
        self.data_reference_path = self.config.get('paths', {}).get('unavista_files', '')
        self.output_path = self.config.get('paths', {}).get('replay_output', '')
        self.log_output_path = self.config.get('paths', {}).get('log_output', self.output_path)

        # Optional: incident files for cross-reference
        # If not configured, cross-reference is silently skipped.
        self.incident_files_path: str = self.config.get('paths', {}).get('incident_files', '')
        
        # File patterns from config
        files_config = self.config.get('files', {})
        self.unavista_pattern = files_config.get('unavista_pattern', 'UnaVista_MiFIR_Manual_Corrections_*.csv')
        self.replay_ids_pattern = files_config.get('replay_ids_pattern', 'Replay_*_Inconsistent_IDs_Summary_FINAL*.csv')
        self.replay_names_pattern = files_config.get('replay_names_pattern', 'Replay_*_Inconsistent_Names_Summary_FINAL*.csv')
        self.incident_pattern: str = files_config.get('incident_pattern', '*.csv')
        # Note: incident_matrix no longer loaded from file - in core library

        # Column config for incident file cross-reference (identity columns).
        # Uses 'source_incident_columns' if present; falls back to 'incident_columns'.
        self.source_incident_columns: Dict[str, str] = (
            self.config.get('source_incident_columns')
            or self.config.get('incident_columns', {})
        )

        # Incident identity indexes for cross-reference (populated by load_indexes)
        self.incident_indexes: Dict[str, IncidentIdentityIndex] = {}
        
        # Actual file paths (will be set by find_files)
        self.unavista_paths: List[str] = []
        self.replay_ids_path = None
        self.replay_names_path = None
        self.incident_files_path_confirmed: bool = False
        
        # Setup logging using core library
        log_level = self.config.get('processor', {}).get('log_level', 'INFO')
        self.logger = create_logger(
            name="phase3_final_lookup",
            log_dir=self.log_output_path,
            log_level=log_level
        )
        
        # Statistics using ProcessingStats from core library
        self.stats = ProcessingStats()
        # Add custom stats
        self.stats.increment('skipped_duplicates', 0)
        self.stats.increment('full_pass', 0)
        self.stats.increment('partial_pass', 0)
        self.stats.increment('full_fail', 0)
        self.stats.increment('inconsistent_corrections', 0)
        self.stats.increment('cross_ref_discrepancies', 0)

        # Additional detailed stats (will use dict for complex nested stats)
        self.field_stats = defaultdict(lambda: {'pass': 0, 'fail': 0})
        self.buyer_stats = {'tested': 0, 'pass': 0, 'fail': 0}
        self.seller_stats = {'tested': 0, 'pass': 0, 'fail': 0}
        
        # Indexes
        self.replay_index = None
        self.unavista_index = None
    
    def find_files(self):
        """Find required files using glob patterns"""
        self.logger.info("Discovering input files...")
        
        # Helper function to find a single file (most recent if multiple)
        def find_file(search_path, pattern, description):
            matches = glob.glob(os.path.join(search_path, pattern))
            if matches:
                file_path = max(matches, key=os.path.getmtime)
                self.logger.info(f"Found {description}: {os.path.basename(file_path)}")
                return file_path
            self.logger.error(f"Could not find {description} matching pattern: {pattern}")
            return None
        
        # Helper function to find all matching files (sorted oldest → newest)
        def find_all_files(search_path, pattern, description):
            matches = sorted(glob.glob(os.path.join(search_path, pattern)), key=os.path.getmtime)
            if matches:
                self.logger.info(f"Found {len(matches)} {description} file(s):")
                for m in matches:
                    self.logger.info(f"  {os.path.basename(m)}")
            else:
                self.logger.error(f"Could not find any {description} files matching pattern: {pattern}")
            return matches
        
        # UnaVista: load ALL matching files
        self.unavista_paths = find_all_files(self.data_reference_path, self.unavista_pattern, "UnaVista")
        self.replay_ids_path = find_file(self.replay_input_path, self.replay_ids_pattern, "Replay IDs file")
        self.replay_names_path = find_file(self.replay_input_path, self.replay_names_pattern, "Replay Names file")
        
        # Note: Incident matrix no longer loaded from CSV - now in core library
        
        # Verify all files found
        if not all([self.unavista_paths, self.replay_ids_path, self.replay_names_path]):
            raise FileNotFoundError("Required input files not found. Please check file paths and patterns.")
        
        self.logger.info("All required files discovered successfully")
    
    def load_indexes(self):
        """Load and build all indexes"""
        self.logger.info("Loading indexes...")
        
        # Verify all paths are set (should be guaranteed by find_files)
        if not all([self.replay_ids_path, self.replay_names_path, self.unavista_paths]):
            raise ValueError("File paths not properly initialized. Call find_files() first.")
        
        # Type assertions for type checker (paths verified above)
        assert self.replay_ids_path is not None
        assert self.replay_names_path is not None
        assert self.unavista_paths
        
        # Load replay records (incident matrix loaded from core library)
        incident_columns = self.config.get('incident_columns', {})
        self.replay_index = ReplayRecordIndex(self.logger, incident_columns)
        
        # Load both replay files
        self.replay_index.load_replay_file(self.replay_ids_path, 'IDs')
        self.replay_index.load_replay_file(self.replay_names_path, 'Names')
        
        self.stats.custom_stats['total_replay_records'] = len(self.replay_index.records)
        
        # Load all UnaVista files into a single combined index
        self.unavista_index = UnaVistaIndex(self.unavista_paths, self.logger)

        # Optionally preload incident files for cross-reference
        if self.incident_files_path and self.source_incident_columns:
            self._preload_incident_indexes()
        else:
            self.logger.info(
                "incident_files path or source_incident_columns not configured — "
                "cross-reference will be skipped"
            )

        self.logger.info("All indexes loaded successfully")

    # ------------------------------------------------------------------ #
    # Incident file discovery and cross-reference (v2.1 additions)
    # ------------------------------------------------------------------ #

    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find the incident file for a given code using a four-tier glob strategy.

        Tier 1: Exact match using pattern prefix + space + code.
        Tier 2: Dash-separated variant for backwards compatibility.
        Tier 3: Space-anchored glob with exact code (avoids substring collisions).
        Tier 4: Space-anchored glob with suffix; regex-filtered for collision safety.

        Args:
            incident_code: Incident code string, e.g. ``"7_66"``.

        Returns:
            Absolute path to the incident file, or None if not found.
        """
        pattern_prefix = self.incident_pattern.replace('*.csv', '').strip()

        # Tier 1: "FY25 Q4 7_66.csv"
        path = os.path.join(self.incident_files_path, f"{pattern_prefix} {incident_code}.csv")
        if os.path.exists(path):
            return path

        # Tier 2: "FY25 Q4 - 7_66.csv"
        path_dash = os.path.join(
            self.incident_files_path, f"{pattern_prefix} - {incident_code}.csv"
        )
        if os.path.exists(path_dash):
            return path_dash

        # Tier 3: "* 7_66.csv" (exact, space-anchored)
        matches = glob.glob(os.path.join(self.incident_files_path, f"* {incident_code}.csv"))
        if matches:
            return matches[0]

        # Tier 4: "* 7_66*.csv" with regex collision guard
        code_re = re.compile(rf'\s{re.escape(incident_code)}(?=[\s_.])')
        wider = glob.glob(os.path.join(self.incident_files_path, f"* {incident_code}*.csv"))
        for match in sorted(wider, key=os.path.getmtime):
            if code_re.search(os.path.basename(match)):
                return match

        return None

    def _preload_incident_indexes(self) -> None:
        """Load and index all incident files referenced by the replay records."""
        self.logger.info("Preloading incident files for cross-reference...")

        codes: Set[str] = set()
        for record in self.replay_index.records:
            codes.update(record.incident_codes)

        loaded = 0
        for code in codes:
            path = self.find_incident_file(code)
            if path:
                self.incident_indexes[code] = IncidentIdentityIndex(
                    path, self.source_incident_columns, self.logger
                )
                loaded += 1
            else:
                self.logger.warning(f"Incident file not found for code: {code}")

        self.logger.info(f"Loaded {loaded} incident files for cross-reference")

    def _extract_incident_correction(
        self,
        row: List[str],
        column_mapper: IncidentIdentityColumnMapper,
    ) -> Tuple[str, str]:
        """Extract the effective correction from an incident file row.

        Applies the same decision logic as Phase3Processor._create_lookup_result().

        Args:
            row: Data row from the incident file.
            column_mapper: Column mapper for the incident file.

        Returns:
            Tuple of (correction_value, correction_field). Both are "No Change"
            when no correction applies.
        """
        def _cell(logical: str) -> str:
            col = column_mapper.get(logical)
            return row[col].strip() if col is not None and len(row) > col else ""

        correction_value = _cell('correction')
        correction_field = _cell('correction_field')
        suggested_value = _cell('suggested_correction')
        suggested_field = _cell('suggested_correction_field')
        agree = _cell('agree_with_correction').upper()

        if correction_value:
            if agree in ('N', 'F'):
                if suggested_value:
                    correction_value, correction_field = suggested_value, suggested_field
                else:
                    return "No Change", "No Change"
        else:
            if suggested_value:
                correction_value, correction_field = suggested_value, suggested_field
            else:
                return "No Change", "No Change"

        if re.search(r'\bre\s+accounts?\b', correction_value, re.IGNORECASE):
            return "No Change", "No Change"

        return correction_value, correction_field

    def _parse_correction_to_dict(self, inc_value: str, inc_field: str) -> Dict[str, str]:
        """Parse an incident file correction into a field -> value dict.

        Uses the same delimiter and fan-out logic as ReplayRecordIndex._parse_corrections().

        Args:
            inc_value: Correction value string from the incident file.
            inc_field: Correction field string from the incident file.

        Returns:
            Dict of field_name -> expected_value, or ``{'No Change': 'No Change'}``
            when the correction is No Change.
        """
        if inc_value.strip().lower() == 'no change':
            return {'No Change': 'No Change'}
        if not inc_field:
            return {}

        value_parts = ReplayRecordIndex._split_correction_parts(inc_value)
        field_parts = ReplayRecordIndex._split_correction_parts(inc_field)

        result: Dict[str, str] = {}
        for field_item, val in zip(field_parts, value_parts):
            if ' & ' in field_item:
                for sub_field in field_item.split(' & '):
                    result[sub_field.strip()] = val
            else:
                result[field_item] = val
        return result

    def _cross_reference_records(
        self,
        records: List[ReplayRecord],
        merged_corrections: Dict[str, str],
    ) -> str:
        """Cross-reference Phase 3 output corrections against source incident files.

        Phase 3 output is the source of truth. The incident file value is used
        only to detect discrepancies for annotation.

        Args:
            records: Replay records for the client (from IDs and/or Names files).
            merged_corrections: Merged correction dict (field -> expected_value)
                already resolved from the Phase 3 output.

        Returns:
            Discrepancy annotation string (e.g. ``' [⚠ incident: ...]'``), or
            empty string when there is no discrepancy or no incident indexes are
            loaded.
        """
        if not self.incident_indexes:
            return ''

        all_incident_codes: List[str] = []
        for record in records:
            all_incident_codes.extend(record.incident_codes)

        discrepancy_parts: List[str] = []
        seen_codes: Set[str] = set()

        for code in all_incident_codes:
            if code in seen_codes:
                continue
            seen_codes.add(code)

            index = self.incident_indexes.get(code)
            if index is None:
                continue

            representative = records[0]

            # Try ID lookup first, then name fallback
            lookup_result = None
            if representative.client_id:
                lookup_result = index.lookup_by_id(
                    [representative.client_id],
                    representative.first_name,
                    representative.surname,
                )

            if lookup_result is None and representative.first_name and representative.surname:
                lookup_result = index.lookup_by_name(
                    representative.first_name,
                    representative.surname,
                    representative.date_of_birth,
                )

            if lookup_result is None:
                continue

            row_idx, _ = lookup_result
            row = index.data_rows[row_idx]
            inc_value, inc_field = self._extract_incident_correction(row, index.column_mapper)
            inc_corrections = self._parse_correction_to_dict(inc_value, inc_field)

            # Compare incident corrections with Phase 3 output (source of truth)
            differences: List[str] = []

            for field_name, output_val in merged_corrections.items():
                if field_name == 'No Change':
                    continue
                inc_val = inc_corrections.get(field_name)
                if inc_val is None and inc_corrections != {'No Change': 'No Change'}:
                    differences.append(f"'{field_name}' not in incident")
                elif inc_val is not None and output_val.lower() != inc_val.lower():
                    differences.append(f"'{field_name}': incident='{inc_val}'")

            for field_name in inc_corrections:
                if field_name == 'No Change':
                    continue
                if field_name not in merged_corrections:
                    differences.append(
                        f"incident also has '{field_name}'='{inc_corrections[field_name]}'"
                    )

            if differences:
                discrepancy_parts.append(f"({code}) " + "; ".join(differences))

        if discrepancy_parts:
            self.stats.increment('cross_ref_discrepancies')
            return ' [⚠ incident: ' + ' | '.join(discrepancy_parts) + ']'
        return ''

    def test_field(self, transaction: UnaVistaTransaction, field_name: str, 
                   expected_value: str, client_type: str, source_file: str = "", 
                   client_id: str = "") -> TestResult:
        """
        Test a single field against UnaVista data
        
        Args:
            transaction: UnaVista transaction to test
            field_name: Correction field name
            expected_value: Expected value from correction
            client_type: 'buyer' or 'seller'
            source_file: Source file (IDs or Names) for debugging
            client_id: Client ID for debugging
        
        Returns:
            TestResult object
        """
        # Get column index
        col_idx = FieldMapper.get_unavista_index(field_name, client_type)
        
        if col_idx is None:
            self.logger.warning(
                f"Unknown field mapping: '{field_name}' for {client_type} "
                f"(Source: {source_file}, Client: {client_id}, Transaction: {transaction.transaction_ref})"
            )
            return TestResult(
                field_name=field_name,
                expected=expected_value,
                actual="UNKNOWN_FIELD",
                passed=False,
                source=""
            )
        
        # Get actual value from transaction
        actual_value = transaction.row_data[col_idx].strip() if col_idx < len(transaction.row_data) else ""
        
        # Handle NULL correction expectation - 'NULL' means we expect empty string
        if expected_value.strip().upper() == 'NULL':
            passed = (actual_value == "")
            expected_norm = 'NULL'
            actual_norm = actual_value
        else:
            # Normalize for comparison
            expected_norm = expected_value.strip().lower()
            actual_norm = actual_value.strip().lower()
            
            # Handle date fields specially
            if 'date' in field_name.lower() or 'dob' in field_name.lower():
                expected_norm = DateParser.parse_date(expected_value) or expected_norm
                actual_norm = DateParser.parse_date(actual_value) or actual_norm
            
            passed = (expected_norm == actual_norm)
        
        return TestResult(
            field_name=field_name,
            expected=expected_value,
            actual=actual_value,
            passed=passed,
            source=""
        )
    
    def find_matching_transactions(self, record: ReplayRecord, client_types: Set[str]) -> Dict[str, List[UnaVistaTransaction]]:
        """
        Find all matching UnaVista transactions for a replay record
        
        Args:
            record: ReplayRecord to match
            client_types: Set of 'buyer' and/or 'seller'
        
        Returns:
            Dictionary of client_type -> List[UnaVistaTransaction]
        """
        if not self.unavista_index:
            raise ValueError("UnaVista index not loaded")
        
        matches = {}
        
        for client_type in client_types:
            # Try ID match first
            if record.client_id:
                transactions = self.unavista_index.lookup_by_id(record.client_id, client_type)
                if transactions:
                    matches[client_type] = transactions
                    continue
            
            # Fallback to name match
            if record.first_name and record.surname:
                transactions = self.unavista_index.lookup_by_name(
                    record.first_name, record.surname, record.date_of_birth, client_type
                )
                if transactions:
                    matches[client_type] = transactions
        
        return matches
    
    def merge_duplicate_records(self, records: List[ReplayRecord]) -> Tuple[Dict[str, str], List[str]]:
        """
        Merge corrections from duplicate records (same client in both IDs and Names files)
        
        Args:
            records: List of ReplayRecord objects for the same client
        
        Returns:
            Tuple of (merged_corrections, inconsistencies)
        """
        if len(records) == 1:
            return records[0].corrections, []
        
        merged = {}
        inconsistencies = []
        field_sources = {}  # field -> (value, source)
        
        for record in records:
            for field, value in record.corrections.items():
                if field not in field_sources:
                    field_sources[field] = (value, record.source_file)
                    merged[field] = value
                else:
                    existing_value, existing_source = field_sources[field]
                    if existing_value.lower() != value.lower():
                        inconsistencies.append(
                            f"{field} expected '{existing_value}' ({existing_source}) vs '{value}' ({record.source_file})"
                        )
        
        return merged, inconsistencies
    
    def format_test_results(self, results_by_type: Dict[str, List[TestResult]], 
                           inconsistencies: List[str]) -> str:
        """
        Format test results into output string
        
        Args:
            results_by_type: Dictionary of client_type -> List[TestResult]
            inconsistencies: List of inconsistency messages
        
        Returns:
            Formatted test result string
        """
        if inconsistencies:
            return "Inconsistent corrections: " + " | ".join(inconsistencies)
        
        if not results_by_type:
            return "Client not found"
        
        output_parts = []
        
        for client_type, results in results_by_type.items():
            passed_results = [r for r in results if r.passed]
            failed_results = [r for r in results if not r.passed]
            
            type_parts = []
            
            if passed_results:
                pass_str = ", ".join([f"{r.field_name}={r.expected}" for r in passed_results])
                source = passed_results[0].source if passed_results else ""
                type_parts.append(f"PASS ({source}): {pass_str}")
            
            if failed_results:
                fail_str = " | ".join([f"{r.field_name} expected '{r.expected}' got '{r.actual}'" for r in failed_results])
                type_parts.append(f"FAIL ({failed_results[0].source}): {fail_str}")
            
            output_parts.append(" | ".join(type_parts))
        
        return " || ".join(output_parts)
    
    def process_client(self, client_key: ClientKey, records: List[ReplayRecord]) -> Dict[int, str]:
        """
        Process a client and generate test results for all matching transactions
        
        Args:
            client_key: ClientKey identifying the client
            records: List of ReplayRecord objects for this client
        
        Returns:
            Dictionary of transaction_index -> test_result_string
        """
        if not self.replay_index:
            raise ValueError("Replay index not loaded")
        
        # Merge corrections from multiple sources
        merged_corrections, inconsistencies = self.merge_duplicate_records(records)
        
        if inconsistencies:
            self.stats.increment('inconsistent_corrections')
            # Find transactions to mark with inconsistency message
            all_incident_codes = []
            for record in records:
                all_incident_codes.extend(record.incident_codes)
            client_types = self.replay_index.get_client_types(all_incident_codes)
            
            if client_types:
                matches_by_type = self.find_matching_transactions(records[0], client_types)
                transaction_results = {}
                inconsistency_msg = "Inconsistent corrections: " + " | ".join(inconsistencies)
                
                for client_type, transactions in matches_by_type.items():
                    for transaction in transactions:
                        transaction_results[transaction.row_index] = inconsistency_msg
                
                return transaction_results
            
            return {}
        
        # Determine client types (buyer/seller)
        all_incident_codes = []
        for record in records:
            all_incident_codes.extend(record.incident_codes)
        client_types = self.replay_index.get_client_types(all_incident_codes)
        
        if not client_types:
            self.logger.warning(f"No client type determined for {client_key.id}")
            return {}
        
        # Check if all corrections are "No change"
        all_no_change = all(v.lower() == "no change" for v in merged_corrections.values())
        
        if all_no_change:
            # For "No change" records, we still need to find transactions to mark them
            matches_by_type = self.find_matching_transactions(records[0], client_types)
            transaction_results = {}
            
            if matches_by_type:
                for client_type, transactions in matches_by_type.items():
                    for transaction in transactions:
                        transaction_results[transaction.row_index] = "No change"
            
            return transaction_results
        
        # Find matching transactions
        matches_by_type = self.find_matching_transactions(records[0], client_types)
        
        if not matches_by_type:
            self.stats.increment('not_found')
            # Return "No match" for this client - but we need transaction indices
            # We'll handle this differently - store client info for later
            return {}
        
        # Test all matching transactions
        transaction_results = {}
        
        for client_type, transactions in matches_by_type.items():
            for transaction in transactions:
                self.stats.increment('total_unavista_tested')
                
                # Track buyer/seller stats
                if client_type == 'buyer':
                    self.buyer_stats['tested'] += 1
                else:
                    self.seller_stats['tested'] += 1
                
                # Test each field
                test_results = []
                for field_name, expected_value in merged_corrections.items():
                    # Skip fields marked as "No change"
                    if expected_value.lower() == "no change":
                        continue
                    result = self.test_field(
                        transaction, 
                        field_name, 
                        expected_value, 
                        client_type,
                        source_file=records[0].source_file,
                        client_id=client_key.id
                    )
                    result.source = records[0].source_file  # Tag with source
                    test_results.append(result)
                    
                    # Update field stats
                    if result.passed:
                        self.field_stats[field_name]['pass'] += 1
                    else:
                        self.field_stats[field_name]['fail'] += 1
                
                # Categorize overall result
                passed_count = sum(1 for r in test_results if r.passed)
                total_count = len(test_results)
                
                if passed_count == total_count:
                    self.stats.increment('full_pass')
                    if client_type == 'buyer':
                        self.buyer_stats['pass'] += 1
                    else:
                        self.seller_stats['pass'] += 1
                elif passed_count > 0:
                    self.stats.increment('partial_pass')
                else:
                    self.stats.increment('full_fail')
                    if client_type == 'buyer':
                        self.buyer_stats['fail'] += 1
                    else:
                        self.seller_stats['fail'] += 1
                
                # Format results
                results_by_type = {client_type: test_results}
                result_str = self.format_test_results(results_by_type, inconsistencies)

                # Append cross-reference discrepancy annotation (Phase 3 output is
                # the source of truth; incident file disagreements are flagged but
                # do not affect the PASS/FAIL outcome).
                if not inconsistencies:
                    discrepancy_note = self._cross_reference_records(
                        records, merged_corrections
                    )
                    if discrepancy_note:
                        result_str = f"{result_str}{discrepancy_note}"

                transaction_results[transaction.row_index] = result_str

        return transaction_results
    
    def generate_output(self):
        """Generate output UnaVista file with test results"""
        self.logger.info("Generating output file...")
        
        if not self.unavista_paths:
            raise ValueError("UnaVista paths not set")
        if not self.replay_index:
            raise ValueError("Replay index not loaded")
        
        # Create test results for all transactions
        transaction_test_results = {}  # transaction_index -> test_result_string
        
        processed_clients = set()
        
        for client_key, records in self.replay_index.client_records.items():
            if client_key in processed_clients:
                self.stats.increment('skipped_duplicates')
                continue
            
            processed_clients.add(client_key)
            results = self.process_client(client_key, records)
            if results:
                transaction_test_results.update(results)
        
        # Write output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"output_UnaVista_final_lookup_{timestamp}.csv"
        output_filepath = os.path.join(self.output_path, output_filename)
        
        # Read and concatenate all UnaVista files in the same order they were indexed
        all_data_rows: List[List[str]] = []
        header: List[str] = []
        for path in self.unavista_paths:
            with open(path, 'r', encoding='utf-8', newline='') as f_in:
                file_rows = list(csv.reader(f_in))
            if not header and len(file_rows) >= 1:
                header = file_rows[0]
            all_data_rows.extend(file_rows[1:])
        
        # Insert test_result column after Transaction Reference Number (index 1)
        header.insert(2, 'test_result')
        
        output_rows = [header]
        
        client_not_found_count = 0
        for i, row in enumerate(all_data_rows):
            # UnaVista rows with no matching replay record are annotated as "Client not found"
            test_result = transaction_test_results.get(i, "Client not found")
            if test_result == "Client not found":
                client_not_found_count += 1
            row.insert(2, test_result)
            output_rows.append(row)
        
        if client_not_found_count:
            self.logger.info(
                f"{client_not_found_count} UnaVista transactions had no matching replay record "
                f"and were annotated as 'Client not found'"
            )
        
        # Write output
        with open(output_filepath, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.writer(f_out)
            writer.writerows(output_rows)
        
        self.logger.info(f"Output written to: {output_filename}")
        return output_filename
    
    def generate_summary(self):
        """Generate processing summary"""
        summary_lines = [
            "",
            "=" * 80,
            "PHASE 3 FINAL LOOKUP - SUMMARY",
            "=" * 80,
            f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "PROCESSING STATISTICS:",
            f"  Total replay records processed: {self.stats.custom_stats.get('total_replay_records', 0)}",
            f"  Skipped duplicates: {self.stats.custom_stats.get('skipped_duplicates', 0)}",
            f"  Total UnaVista transactions tested: {self.stats.custom_stats.get('total_unavista_tested', 0)}",
            "",
            "TEST RESULTS:",
            f"  Full pass: {self.stats.custom_stats.get('full_pass', 0)}",
            f"  Partial pass: {self.stats.custom_stats.get('partial_pass', 0)}",
            f"  Full fail: {self.stats.custom_stats.get('full_fail', 0)}",
            f"  Client not found: {self.stats.not_found}",
            f"  Inconsistent corrections: {self.stats.custom_stats.get('inconsistent_corrections', 0)}",
            f"  Cross-reference discrepancies: {self.stats.custom_stats.get('cross_ref_discrepancies', 0)}",
            "",
            "BUYER/SELLER BREAKDOWN:",
            f"  Buyer transactions tested: {self.buyer_stats['tested']}",
            f"    - Pass: {self.buyer_stats['pass']}",
            f"    - Fail: {self.buyer_stats['fail']}",
            f"  Seller transactions tested: {self.seller_stats['tested']}",
            f"    - Pass: {self.seller_stats['pass']}",
            f"    - Fail: {self.seller_stats['fail']}",
            f"  Decision maker fallback matches: {self.unavista_index.dm_match_count if self.unavista_index else 0}",
            "",
            "FIELD-LEVEL STATISTICS:",
        ]
        
        for field, stats in sorted(self.field_stats.items()):
            summary_lines.append(f"  {field}:")
            summary_lines.append(f"    - Pass: {stats['pass']}")
            summary_lines.append(f"    - Fail: {stats['fail']}")
        
        summary_lines.extend([
            "",
            "OPTIMIZATION INFO:",
            f"  Date cache entries: {len(DateParser._date_cache)}",
            "=" * 80
        ])
        
        # Write to log file
        with open(self.log_filepath, 'a', encoding='utf-8') as f:
            f.write('\n'.join(summary_lines) + '\n')
        
        # Print to console
        for line in summary_lines:
            print(line)
    
    def run(self):
        """Main execution"""
        start_time = datetime.now()
        
        try:
            self.logger.log_header("PHASE 3 FINAL LOOKUP v2.0")
            self.logger.info(f"Replay input path: {self.replay_input_path}")
            self.logger.info(f"Reference files path: {self.data_reference_path}")
            self.logger.info(f"Output path: {self.output_path}")
            
            # Discover input files
            self.find_files()
            
            # Load all indexes
            self.load_indexes()
            
            # Generate output
            output_file = self.generate_output()
            
            # Generate summary
            end_time = datetime.now()
            elapsed = end_time - start_time
            self.logger.info(f"Total processing time: {elapsed}")
            
            self.logger.log_header("PROCESSING SUMMARY")
            self.logger.log_stats(self.stats)
            
            # Log additional detailed stats
            self.logger.info(f"Buyer stats: {self.buyer_stats}")
            self.logger.info(f"Seller stats: {self.seller_stats}")
            self.logger.info(f"Date cache entries: {DateParser.cache_size()}")
            
            self.logger.info("Processing completed successfully")
            return 0
            
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

# ============================================================================
# Main Entry Point
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Phase 3 Final Lookup v2.0 - Validate client corrections against UnaVista data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with configuration file
  python phase_3_final_lookup.py --config config/phase3_final.yaml
  
  # Run with environment variables
  export TXR_PATHS_BASE="/path/to/base"
  export TXR_PATHS_DATA_REFERENCE="/path/to/reference"
  python phase_3_final_lookup.py --use-env
  
  # Override log level
  python phase_3_final_lookup.py --config config/phase3_final.yaml --log-level DEBUG
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file (default: config/phase3_final.yaml)'
    )
    
    parser.add_argument(
        '--use-env',
        action='store_true',
        help='Load configuration from environment variables (TXR_* prefix)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Override log level from configuration'
    )

    parser.add_argument(
        '--gui-mode',
        action='store_true',
        help=argparse.SUPPRESS,
    )
    
    return parser.parse_args()


def main():
    """Main entry point with CLI support"""
    args = parse_args()
    
    try:
        # Determine configuration source
        if args.use_env:
            print("Loading configuration from environment variables...")
            config = ConfigManager.load_from_env("TXR_")
        elif args.config:
            print(f"Loading configuration from {args.config}...")
            config = ConfigManager.load_from_yaml(args.config)
        elif not getattr(args, 'gui_mode', False):
            # Default configuration path (use local config)
            default_config = Path(__file__).parent.parent.parent / "config" / "local" / "replay" / "phase3_final.yaml"
            if default_config.exists():
                print(f"Loading default configuration from {default_config}...")
                config = ConfigManager.load_from_yaml(str(default_config))
            else:
                print("Error: No configuration specified and default config not found")
                print("Use --config or --use-env to specify configuration")
                return 1
        
        # Override log level if specified
        if args.log_level:
            if 'processor' not in config:
                config['processor'] = {}
            config['processor']['log_level'] = args.log_level
        
        # Create and run processor
        processor = Phase3FinalLookup(config_dict=config)
        return processor.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
