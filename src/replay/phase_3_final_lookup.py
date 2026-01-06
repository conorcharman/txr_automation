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
from pathlib import Path

# Import from txr_replay_core library
from txr_replay_core.data_structures import ProcessingStats, UnaVistaTransaction
from txr_replay_core.config import ConfigManager
from txr_replay_core.logger import create_logger
from txr_replay_core.utils import DateParser, safe_open_csv

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
    """Optimized UnaVista file with pre-built indexes for fast lookups"""
    
    def __init__(self, file_path: str, logger: logging.Logger):
        self.file_path = file_path
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
        
        self.load_and_index()
    
    def load_and_index(self):
        """Load UnaVista file and build all indexes"""
        try:
            f, encoding = safe_open_csv(self.file_path, 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                self.logger.warning(f"UnaVista file is empty or has no data rows")
                return
            
            self.header = rows[0]
            data_rows = rows[1:]
            
            self.logger.info(f"Loading {len(data_rows)} UnaVista transactions...")
            
            for i, row in enumerate(data_rows):
                if len(row) < 32:
                    continue
                
                transaction_ref = row[1].strip() if len(row) > 1 else ""
                transaction = UnaVistaTransaction(
                    transaction_ref=transaction_ref,
                    row_data=row,
                    row_index=i
                )
                self.transactions.append(transaction)
                
                # Index buyer data
                self._index_buyer(row, i)
                # Index seller data
                self._index_seller(row, i)
                # Index decision makers
                self._index_decision_makers(row, i)
            
            self.logger.info(f"Indexed {len(self.transactions)} UnaVista transactions")
            
        except Exception as e:
            self.logger.error(f"Error loading UnaVista file: {e}")
    
    def _index_buyer(self, row: List[str], idx: int):
        """Index buyer fields"""
        buyer_id = row[8].strip().lower() if len(row) > 8 else ""
        if buyer_id:
            self.buyer_id_index[buyer_id].append(idx)
        
        buyer_first = row[10].strip().lower() if len(row) > 10 else ""
        buyer_last = row[11].strip().lower() if len(row) > 11 else ""
        buyer_dob = DateParser.parse_date(row[12]) if len(row) > 12 else ""
        
        if buyer_first and buyer_last:
            name_key = (buyer_first, buyer_last, buyer_dob or "")
            self.buyer_name_index[name_key].append(idx)
    
    def _index_seller(self, row: List[str], idx: int):
        """Index seller fields"""
        seller_id = row[21].strip().lower() if len(row) > 21 else ""
        if seller_id:
            self.seller_id_index[seller_id].append(idx)
        
        seller_first = row[23].strip().lower() if len(row) > 23 else ""
        seller_last = row[24].strip().lower() if len(row) > 24 else ""
        seller_dob = DateParser.parse_date(row[25]) if len(row) > 25 else ""
        
        if seller_first and seller_last:
            name_key = (seller_first, seller_last, seller_dob or "")
            self.seller_name_index[name_key].append(idx)
    
    def _index_decision_makers(self, row: List[str], idx: int):
        """Index decision maker fields"""
        # Buyer decision maker
        buyer_dm_id = row[15].strip().lower() if len(row) > 15 else ""
        if buyer_dm_id:
            self.buyer_dm_id_index[buyer_dm_id].append(idx)
        
        buyer_dm_first = row[16].strip().lower() if len(row) > 16 else ""
        buyer_dm_last = row[17].strip().lower() if len(row) > 17 else ""
        buyer_dm_dob = DateParser.parse_date(row[18]) if len(row) > 18 else ""
        
        if buyer_dm_first and buyer_dm_last:
            name_key = (buyer_dm_first, buyer_dm_last, buyer_dm_dob or "")
            self.buyer_dm_name_index[name_key].append(idx)
        
        # Seller decision maker
        seller_dm_id = row[28].strip().lower() if len(row) > 28 else ""
        if seller_dm_id:
            self.seller_dm_id_index[seller_dm_id].append(idx)
        
        seller_dm_first = row[29].strip().lower() if len(row) > 29 else ""
        seller_dm_last = row[30].strip().lower() if len(row) > 30 else ""
        seller_dm_dob = DateParser.parse_date(row[31]) if len(row) > 31 else ""
        
        if seller_dm_first and seller_dm_last:
            name_key = (seller_dm_first, seller_dm_last, seller_dm_dob or "")
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
        
        return [self.transactions[i] for i in indices]
    
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
        
        return [self.transactions[i] for i in indices]

# ============================================================================
# Replay Record Index
# ============================================================================

class ReplayRecordIndex:
    """Index of client correction records from Replay files"""
    
    def __init__(self, incident_matrix_path: str, logger: logging.Logger):
        self.logger = logger
        self.records = []  # List of ReplayRecord objects
        self.client_records = defaultdict(list)  # ClientKey -> List[ReplayRecord]
        self.incident_matrix = {}  # incident_code -> set of 'buyer' and/or 'seller'
        
        self.load_incident_matrix(incident_matrix_path)
    
    def load_incident_matrix(self, file_path: str):
        """Load incident code matrix"""
        try:
            f, encoding = safe_open_csv(Path(file_path), 'r', newline='')
            with f:
                reader = csv.DictReader(f)
                row_count = 0
                for row in reader:
                    # Read buyer incidents
                    buyer_incident = row.get('buyer_incidents', '').strip()
                    if buyer_incident:
                        if buyer_incident not in self.incident_matrix:
                            self.incident_matrix[buyer_incident] = set()
                        self.incident_matrix[buyer_incident].add('buyer')
                    
                    # Read seller incidents
                    seller_incident = row.get('seller_incidents', '').strip()
                    if seller_incident:
                        if seller_incident not in self.incident_matrix:
                            self.incident_matrix[seller_incident] = set()
                        self.incident_matrix[seller_incident].add('seller')
                    
                    row_count += 1
            
            self.logger.info(f"Loaded {len(self.incident_matrix)} incident code mappings from {row_count} rows")
            if len(self.incident_matrix) == 0:
                self.logger.warning("Incident matrix is empty - no client types will be determined")
        except KeyError as e:
            self.logger.error(f"Error loading incident matrix - missing column: {e}")
            # Try to show available columns from first row
            try:
                f, encoding = safe_open_csv(Path(file_path), 'r', newline='')
                with f:
                    reader = csv.DictReader(f)
                    first_row = next(reader, None)
                    if first_row:
                        self.logger.error(f"Available columns: {list(first_row.keys())}")
            except:
                pass
        except Exception as e:
            self.logger.error(f"Error loading incident matrix: {e}")
    
    def load_replay_file(self, file_path: str, file_type: str):
        """
        Load and index a Replay file
        
        Args:
            file_path: Path to replay file
            file_type: 'IDs' or 'Names'
        """
        try:
            f, encoding = safe_open_csv(Path(file_path), 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                self.logger.warning(f"Replay file {file_type} is empty")
                return
            
            data_rows = rows[1:]
            self.logger.info(f"Processing {len(data_rows)} records from {file_type} file...")
            
            for i, row in enumerate(data_rows):
                # Ensure row has enough columns
                while len(row) < 9:
                    row.append("")
                
                # Parse record based on file type
                if file_type == 'IDs':
                    record = self._parse_ids_record(row, i, file_type)
                else:
                    record = self._parse_names_record(row, i, file_type)
                
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
    
    def _parse_ids_record(self, row: List[str], row_index: int, file_type: str) -> Optional[ReplayRecord]:
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
            
            # Index 4: Incident Codes
            incident_codes_str = row[4].strip()
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            # Index 6: Client Confirmed Correction
            # Index 7: Client Confirmed Correction Fields
            corrections = self._parse_corrections(row[6], row[7])
            
            # Skip if all corrections are "No change"
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
    
    def _parse_names_record(self, row: List[str], row_index: int, file_type: str) -> Optional[ReplayRecord]:
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
            
            # Index 4: Incident Codes
            incident_codes_str = row[4].strip()
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            # Index 6: Client Confirmed Correction
            # Index 7: Client Confirmed Correction Fields
            corrections = self._parse_corrections(row[6], row[7])
            
            # Skip if all corrections are "No change"
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
    
    def _parse_corrections(self, correction_str: str, field_str: str) -> Dict[str, str]:
        """
        Parse corrections and fields with support for ampersand-combined fields
        
        Args:
            correction_str: e.g., "Val1:Val2:Val3:Val4" 
            field_str: e.g., "Field1:Field2:Field3 & Field4:Field5"
                       Note: Field3 & Field4 share the same value (Val3)
        
        Returns:
            Dictionary of field -> expected_value
        
        Note: When a colon-separated field item contains ' & ', it means that item
              represents multiple fields that all receive the same correction value.
        """
        corrections = {}
        
        if not correction_str or not field_str:
            return corrections
        
        # First split on colons
        correction_parts = [p.strip() for p in correction_str.split(':')]
        field_parts = [p.strip() for p in field_str.split(':')]
        
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
                # incident_matrix[code] is now a set of client types
                types.update(self.incident_matrix[code])
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
        self.data_reference_path = self.config.get('paths', {}).get('unavista_files', 
                                   self.config.get('paths', {}).get('incident_files', ''))
        self.output_path = self.config.get('paths', {}).get('replay_output', '')
        self.log_output_path = self.config.get('paths', {}).get('log_output', self.output_path)
        
        # File patterns from config
        files_config = self.config.get('files', {})
        self.unavista_pattern = files_config.get('unavista_pattern', 'UnaVista_MiFIR_Manual_Corrections_*.csv')
        self.replay_ids_pattern = files_config.get('replay_ids_pattern', 'Replay_*_Inconsistent_IDs_Summary_FINAL*.csv')
        self.replay_names_pattern = files_config.get('replay_names_pattern', 'Replay_*_Inconsistent_Names_Summary_FINAL*.csv')
        self.incident_matrix_filename = files_config.get('incident_matrix', 'incident_code_matrix.csv')
        
        # Actual file paths (will be set by find_files)
        self.unavista_path = None
        self.replay_ids_path = None
        self.replay_names_path = None
        self.incident_matrix_path = None
        
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
        
        # Helper function to find file with custom search path
        def find_file(search_path, pattern, description):
            matches = glob.glob(os.path.join(search_path, pattern))
            if matches:
                # Use the most recent file if multiple matches
                file_path = max(matches, key=os.path.getmtime)
                self.logger.info(f"Found {description}: {os.path.basename(file_path)}")
                return file_path
            
            self.logger.error(f"Could not find {description} matching pattern: {pattern}")
            return None
        
        # Find files in their respective directories
        self.unavista_path = find_file(self.data_reference_path, self.unavista_pattern, "UnaVista file")
        self.replay_ids_path = find_file(self.replay_input_path, self.replay_ids_pattern, "Replay IDs file")
        self.replay_names_path = find_file(self.replay_input_path, self.replay_names_pattern, "Replay Names file")
        
        # Incident matrix (in reference data)
        self.incident_matrix_path = os.path.join(self.data_reference_path, self.incident_matrix_filename)
        if os.path.exists(self.incident_matrix_path):
            self.logger.info(f"Found incident matrix: {os.path.basename(self.incident_matrix_path)}")
        else:
            self.logger.error(f"Could not find incident matrix: {self.incident_matrix_filename}")
            self.incident_matrix_path = None
        
        # Verify all files found
        if not all([self.unavista_path, self.replay_ids_path, self.replay_names_path, self.incident_matrix_path]):
            raise FileNotFoundError("Required input files not found. Please check file paths and patterns.")
        
        self.logger.info("All required files discovered successfully")
    
    def load_indexes(self):
        """Load and build all indexes"""
        self.logger.info("Loading indexes...")
        
        # Verify all paths are set (should be guaranteed by find_files)
        if not all([self.incident_matrix_path, self.replay_ids_path, 
                   self.replay_names_path, self.unavista_path]):
            raise ValueError("File paths not properly initialized. Call find_files() first.")
        
        # Type assertions for type checker (paths verified above)
        assert self.incident_matrix_path is not None
        assert self.replay_ids_path is not None
        assert self.replay_names_path is not None
        assert self.unavista_path is not None
        
        # Load incident matrix and replay records
        self.replay_index = ReplayRecordIndex(self.incident_matrix_path, self.logger)
        
        # Load both replay files
        self.replay_index.load_replay_file(self.replay_ids_path, 'IDs')
        self.replay_index.load_replay_file(self.replay_names_path, 'Names')
        
        self.stats['total_replay_records'] = len(self.replay_index.records)
        
        # Load UnaVista file
        self.unavista_index = UnaVistaIndex(self.unavista_path, self.logger)
        
        self.logger.info("All indexes loaded successfully")
    
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
                    self.stats['buyer_stats']['tested'] += 1
                else:
                    self.stats['seller_stats']['tested'] += 1
                
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
                        self.stats['field_stats'][field_name]['pass'] += 1
                    else:
                        self.stats['field_stats'][field_name]['fail'] += 1
                
                # Categorize overall result
                passed_count = sum(1 for r in test_results if r.passed)
                total_count = len(test_results)
                
                if passed_count == total_count:
                    self.stats.increment('full_pass')
                    if client_type == 'buyer':
                        self.stats['buyer_stats']['pass'] += 1
                    else:
                        self.stats['seller_stats']['pass'] += 1
                elif passed_count > 0:
                    self.stats.increment('partial_pass')
                else:
                    self.stats.increment('full_fail')
                    if client_type == 'buyer':
                        self.stats['buyer_stats']['fail'] += 1
                    else:
                        self.stats['seller_stats']['fail'] += 1
                
                # Format results
                results_by_type = {client_type: test_results}
                result_str = self.format_test_results(results_by_type, inconsistencies)
                
                transaction_results[transaction.row_index] = result_str
        
        return transaction_results
    
    def generate_output(self):
        """Generate output UnaVista file with test results"""
        self.logger.info("Generating output file...")
        
        if not self.unavista_path:
            raise ValueError("UnaVista path not set")
        if not self.replay_index:
            raise ValueError("Replay index not loaded")
        
        # Create test results for all transactions
        transaction_test_results = {}  # transaction_index -> test_result_string
        
        processed_clients = set()
        clients_not_found = []  # Track clients with no matches
        
        for client_key, records in self.replay_index.client_records.items():
            if client_key in processed_clients:
                self.stats.increment('skipped_duplicates')
                continue
            
            processed_clients.add(client_key)
            results = self.process_client(client_key, records)
            if results:
                transaction_test_results.update(results)
            else:
                # Check if this was a "not found" case
                merged_corrections, _ = self.merge_duplicate_records(records)
                all_no_change = all(v.lower() == "no change" for v in merged_corrections.values())
                if not all_no_change:
                    clients_not_found.append((client_key, records))
        
        # Log clients with no matches
        if clients_not_found:
            self.logger.info(f"{len(clients_not_found)} clients could not be matched to UnaVista transactions")
            for client_key, records in clients_not_found[:10]:  # Log first 10
                self.logger.debug(f"No match: ID={client_key.id}, Name={client_key.first_name} {client_key.surname}")
        
        # Write output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"output_UnaVista_final_lookup_{timestamp}.csv"
        output_filepath = os.path.join(self.output_path, output_filename)
        
        with open(self.unavista_path, 'r', encoding='utf-8', newline='') as f_in:
            reader = csv.reader(f_in)
            rows = list(reader)
        
        # Insert test_result column after Transaction Reference Number (index 1)
        header = rows[0]
        header.insert(2, 'test_result')
        
        output_rows = [header]
        
        for i, row in enumerate(rows[1:]):
            # Get test result for this transaction
            test_result = transaction_test_results.get(i, "")
            row.insert(2, test_result)
            output_rows.append(row)
        
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
            f"  Total replay records processed: {self.stats['total_replay_records']}",
            f"  Skipped duplicates: {self.stats['skipped_duplicates']}",
            f"  Total UnaVista transactions tested: {self.stats['total_unavista_tested']}",
            "",
            "TEST RESULTS:",
            f"  Full pass: {self.stats['full_pass']}",
            f"  Partial pass: {self.stats['partial_pass']}",
            f"  Full fail: {self.stats['full_fail']}",
            f"  Client not found: {self.stats['not_found']}",
            f"  Inconsistent corrections: {self.stats['inconsistent_corrections']}",
            "",
            "BUYER/SELLER BREAKDOWN:",
            f"  Buyer transactions tested: {self.stats['buyer_stats']['tested']}",
            f"    - Pass: {self.stats['buyer_stats']['pass']}",
            f"    - Fail: {self.stats['buyer_stats']['fail']}",
            f"  Seller transactions tested: {self.stats['seller_stats']['tested']}",
            f"    - Pass: {self.stats['seller_stats']['pass']}",
            f"    - Fail: {self.stats['seller_stats']['fail']}",
            "",
            "FIELD-LEVEL STATISTICS:",
        ]
        
        for field, stats in sorted(self.stats['field_stats'].items()):
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
            self.logger.info(f"Date cache entries: {len(DateParser.cache_size())}")
            
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
        else:
            # Default configuration path
            default_config = Path(__file__).parent.parent.parent / "config" / "phase3_final.yaml"
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
