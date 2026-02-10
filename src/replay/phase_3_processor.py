#!/usr/bin/env python3
"""
Phase 3 Processor v5.0
Refactored version using shared txr_replay_core library.
Leverages ConfigManager, StructuredLogger, DateParser, and shared data structures.

Author: GitHub Copilot
Date: December 23, 2025
Version: 5.0 - Refactored to use txr_replay_core library

CHANGES IN v5.0:
- Migrated to txr_replay_core library (ConfigManager, StructuredLogger, DateParser)
- Replaced hardcoded paths with configuration file
- Added CLI interface with argparse
- Using shared ReplayRecord, LookupResult, ProcessingStats
- Eliminated duplicate DateParser class
- Improved logging with structured logger
"""

import csv
import os
import glob
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
import re
from difflib import SequenceMatcher
from collections import defaultdict
from pathlib import Path

# Import from core library
from core import (
    ReplayRecord,
    LookupResult,
    ProcessingStats,
    ConfigManager,
    create_logger,
    DateParser,
    CharacterReplacement,
    safe_open_csv,
)
from core.data import ClientErrorColumns


class IncidentColumnMapper:
    """Maps column names to indices in incident template files."""
    
    def __init__(self, header: List[str], column_config: Dict[str, str], logger=None):
        """
        Initialize column mapper.
        
        Args:
            header: List of column names from CSV header
            column_config: Dict mapping logical names to column names from config
            logger: Logger instance
        """
        self.header = header
        self.column_config = column_config
        self.logger = logger
        self.indices = {}
        
        self._map_columns()
    
    def _map_columns(self):
        """Map column names to their indices."""
        for logical_name, column_name in self.column_config.items():
            try:
                index = self.header.index(column_name)
                self.indices[logical_name] = index
            except ValueError:
                if self.logger:
                    self.logger.warning(f"Column '{column_name}' not found in incident file")
                self.indices[logical_name] = None
    
    def get(self, logical_name: str, default=None) -> Optional[int]:
        """Get column index by logical name."""
        return self.indices.get(logical_name, default)
    
    def has_column(self, logical_name: str) -> bool:
        """Check if column exists."""
        return self.indices.get(logical_name) is not None


# Local dataclass for Phase 3 specific client records
@dataclass
class ClientRecord:
    """Represents a client record with parsed details for Phase 3"""
    first_name: str
    surname: str
    date_of_birth: str
    id_value: str
    id_type: str
    incident_codes: List[str]
    original_row: List[str]
    row_index: int
    file_type: str
    all_ids: Optional[List[str]] = None

class IncidentFileIndex:
    """Optimized incident file with pre-built indexes for fast lookups"""
    
    def __init__(self, file_path: str, column_config: Dict[str, str], logger=None):
        self.file_path = file_path
        self.data_rows = []
        self.header = []
        self.column_mapper = None
        self.logger = logger
        self.column_config = column_config
        
        # Pre-built indexes for O(1) lookups
        self.buyer_id_index = {}      # id -> row_indices
        self.seller_id_index = {}     # id -> row_indices  
        self.buyer_name_index = {}    # (first, last, dob) -> row_indices
        self.seller_name_index = {}   # (first, last, dob) -> row_indices
        
        # Decision maker indexes (fallback)
        self.buyer_dm_id_index = {}      # id -> row_indices
        self.seller_dm_id_index = {}     # id -> row_indices
        self.buyer_dm_name_index = {}    # (first, last, dob) -> row_indices
        self.seller_dm_name_index = {}   # (first, last, dob) -> row_indices
        
        self.load_and_index()
    
    def load_and_index(self):
        """Load file and build all indexes"""
        try:
            f, encoding = safe_open_csv(self.file_path, 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                return
            
            self.header = rows[0]
            self.data_rows = rows[1:]  # Skip header
            
            # Initialize column mapper for correction data
            self.column_mapper = IncidentColumnMapper(self.header, self.column_config, self.logger)
            
            self._build_indexes()
            
            # Log index sizes for diagnostics
            if self.logger:
                self.logger.info(f"Loaded {os.path.basename(self.file_path)}: {len(self.data_rows)} rows")
                self.logger.info(f"  - Buyer IDs: {len(self.buyer_id_index)}, Seller IDs: {len(self.seller_id_index)}")
                self.logger.info(f"  - Buyer DM IDs: {len(self.buyer_dm_id_index)}, Seller DM IDs: {len(self.seller_dm_id_index)}")
                self.logger.info(f"  - Buyer Names: {len(self.buyer_name_index)}, Seller Names: {len(self.seller_name_index)}")
                self.logger.info(f"  - Buyer DM Names: {len(self.buyer_dm_name_index)}, Seller DM Names: {len(self.seller_dm_name_index)}")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error loading {self.file_path}: {e}")
    
    def _build_indexes(self):
        """Build all lookup indexes using column mapper from config"""
        # Get column mapper for data columns
        col = self.column_mapper
        
        for i, row in enumerate(self.data_rows):
            if not row:
                continue
                
            # Index buyer data
            buyer_id_col = col.get('buyer_id')
            if buyer_id_col is not None and len(row) > buyer_id_col:
                buyer_id = row[buyer_id_col].strip().lower()
                if buyer_id:
                    if buyer_id not in self.buyer_id_index:
                        self.buyer_id_index[buyer_id] = []
                    self.buyer_id_index[buyer_id].append(i)
            
            # Index seller data
            seller_id_col = col.get('seller_id')
            if seller_id_col is not None and len(row) > seller_id_col:
                seller_id = row[seller_id_col].strip().lower()
                if seller_id:
                    if seller_id not in self.seller_id_index:
                        self.seller_id_index[seller_id] = []
                    self.seller_id_index[seller_id].append(i)
            
            # Index buyer names
            buyer_first_col = col.get('buyer_first_name')
            buyer_last_col = col.get('buyer_last_name')
            buyer_dob_col = col.get('buyer_dob')
            
            if (buyer_first_col is not None and buyer_last_col is not None and 
                len(row) > max(buyer_first_col, buyer_last_col)):
                buyer_first = row[buyer_first_col].strip().lower()
                buyer_last = row[buyer_last_col].strip().lower()
                buyer_dob = ""
                if buyer_dob_col is not None and len(row) > buyer_dob_col:
                    buyer_dob = DateParser.parse_date(row[buyer_dob_col]) or ""
                
                if buyer_first and buyer_last:
                    name_key = (buyer_first, buyer_last, buyer_dob)
                    if name_key not in self.buyer_name_index:
                        self.buyer_name_index[name_key] = []
                    self.buyer_name_index[name_key].append(i)
            
            # Index seller names
            seller_first_col = col.get('seller_first_name')
            seller_last_col = col.get('seller_last_name')
            seller_dob_col = col.get('seller_dob')
            
            if (seller_first_col is not None and seller_last_col is not None and
                len(row) > max(seller_first_col, seller_last_col)):
                seller_first = row[seller_first_col].strip().lower()
                seller_last = row[seller_last_col].strip().lower()
                seller_dob = ""
                if seller_dob_col is not None and len(row) > seller_dob_col:
                    seller_dob = DateParser.parse_date(row[seller_dob_col]) or ""
                
                if seller_first and seller_last:
                    name_key = (seller_first, seller_last, seller_dob)
                    if name_key not in self.seller_name_index:
                        self.seller_name_index[name_key] = []
                    self.seller_name_index[name_key].append(i)
            
            # Index buyer decision maker data
            buyer_dm_id_col = col.get('buyer_dm_id')
            if buyer_dm_id_col is not None and len(row) > buyer_dm_id_col:
                buyer_dm_id = row[buyer_dm_id_col].strip().lower()
                if buyer_dm_id:
                    if buyer_dm_id not in self.buyer_dm_id_index:
                        self.buyer_dm_id_index[buyer_dm_id] = []
                    self.buyer_dm_id_index[buyer_dm_id].append(i)
            
            buyer_dm_first_col = col.get('buyer_dm_first_name')
            buyer_dm_last_col = col.get('buyer_dm_last_name')
            buyer_dm_dob_col = col.get('buyer_dm_dob')
            
            if (buyer_dm_first_col is not None and buyer_dm_last_col is not None and
                len(row) > max(buyer_dm_first_col, buyer_dm_last_col)):
                buyer_dm_first = row[buyer_dm_first_col].strip().lower()
                buyer_dm_last = row[buyer_dm_last_col].strip().lower()
                buyer_dm_dob = ""
                if buyer_dm_dob_col is not None and len(row) > buyer_dm_dob_col:
                    buyer_dm_dob = DateParser.parse_date(row[buyer_dm_dob_col]) or ""
                
                if buyer_dm_first and buyer_dm_last:
                    name_key = (buyer_dm_first, buyer_dm_last, buyer_dm_dob)
                    if name_key not in self.buyer_dm_name_index:
                        self.buyer_dm_name_index[name_key] = []
                    self.buyer_dm_name_index[name_key].append(i)
            
            # Index seller decision maker data
            seller_dm_id_col = col.get('seller_dm_id')
            if seller_dm_id_col is not None and len(row) > seller_dm_id_col:
                seller_dm_id = row[seller_dm_id_col].strip().lower()
                if seller_dm_id:
                    if seller_dm_id not in self.seller_dm_id_index:
                        self.seller_dm_id_index[seller_dm_id] = []
                    self.seller_dm_id_index[seller_dm_id].append(i)
            
            seller_dm_first_col = col.get('seller_dm_first_name')
            seller_dm_last_col = col.get('seller_dm_last_name')
            seller_dm_dob_col = col.get('seller_dm_dob')
            
            if (seller_dm_first_col is not None and seller_dm_last_col is not None and
                len(row) > max(seller_dm_first_col, seller_dm_last_col)):
                seller_dm_first = row[seller_dm_first_col].strip().lower()
                seller_dm_last = row[seller_dm_last_col].strip().lower()
                seller_dm_dob = ""
                if seller_dm_dob_col is not None and len(row) > seller_dm_dob_col:
                    seller_dm_dob = DateParser.parse_date(row[seller_dm_dob_col]) or ""
                
                if seller_dm_first and seller_dm_last:
                    name_key = (seller_dm_first, seller_dm_last, seller_dm_dob)
                    if name_key not in self.seller_dm_name_index:
                        self.seller_dm_name_index[name_key] = []
                    self.seller_dm_name_index[name_key].append(i)
    
    def lookup_by_id(self, client_ids: List[str]) -> Optional[Tuple[int, str]]:
        """Fast O(1) ID lookup using indexes"""
        if self.logger:
            self.logger.debug(f"Looking up IDs: {client_ids}")
        
        for client_id in client_ids:
            if not client_id:
                continue
            client_id_lower = client_id.lower()
            
            # Check buyer index
            if client_id_lower in self.buyer_id_index:
                row_idx = self.buyer_id_index[client_id_lower][0]  # Take first match
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in buyer_id_index")
                return (row_idx, "id_buyer")
            
            # Check seller index
            if client_id_lower in self.seller_id_index:
                row_idx = self.seller_id_index[client_id_lower][0]  # Take first match
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in seller_id_index")
                return (row_idx, "id_seller")
            
            # Check buyer decision maker index (fallback)
            if client_id_lower in self.buyer_dm_id_index:
                row_idx = self.buyer_dm_id_index[client_id_lower][0]
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in buyer_dm_id_index")
                return (row_idx, "id_buyer_dm")
            
            # Check seller decision maker index (fallback)
            if client_id_lower in self.seller_dm_id_index:
                row_idx = self.seller_dm_id_index[client_id_lower][0]
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in seller_dm_id_index")
                return (row_idx, "id_seller_dm")
        
        if self.logger:
            self.logger.debug(f"ID lookup failed for: {client_ids}")
        return None
    
    def lookup_by_name(self, first_name: str, surname: str, dob: str) -> Optional[Tuple[int, str]]:
        """Fast O(1) name lookup using indexes"""
        first_lower = first_name.lower().strip()
        surname_lower = surname.lower().strip()
        dob_parsed = DateParser.parse_date(dob) if dob else ""
        
        name_key = (first_lower, surname_lower, dob_parsed or "")
        if self.logger:
            self.logger.debug(f"Looking up name: {name_key}")
        
        # Check buyer index
        if name_key in self.buyer_name_index:
            row_idx = self.buyer_name_index[name_key][0]  # Take first match
            if self.logger:
                self.logger.debug(f"Found name in buyer_name_index")
            return (row_idx, "name_buyer")
        
        # Check seller index  
        if name_key in self.seller_name_index:
            row_idx = self.seller_name_index[name_key][0]  # Take first match
            if self.logger:
                self.logger.debug(f"Found name in seller_name_index")
            return (row_idx, "name_seller")
        
        # Try without DOB if no exact match
        if dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            
            if name_key_no_dob in self.buyer_name_index:
                row_idx = self.buyer_name_index[name_key_no_dob][0]
                return (row_idx, "name_buyer")
            
            if name_key_no_dob in self.seller_name_index:
                row_idx = self.seller_name_index[name_key_no_dob][0]
                return (row_idx, "name_seller")
        
        # Check buyer decision maker index (fallback)
        if name_key in self.buyer_dm_name_index:
            row_idx = self.buyer_dm_name_index[name_key][0]
            return (row_idx, "name_buyer_dm")
        
        # Check seller decision maker index (fallback)
        if name_key in self.seller_dm_name_index:
            row_idx = self.seller_dm_name_index[name_key][0]
            return (row_idx, "name_seller_dm")
        
        # Try decision makers without DOB
        if dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            
            if name_key_no_dob in self.buyer_dm_name_index:
                row_idx = self.buyer_dm_name_index[name_key_no_dob][0]
                return (row_idx, "name_buyer_dm")
            
            if name_key_no_dob in self.seller_dm_name_index:
                row_idx = self.seller_dm_name_index[name_key_no_dob][0]
                return (row_idx, "name_seller_dm")
        
        if self.logger:
            self.logger.debug(f"Name lookup failed for: {name_key}")
        return None

class Phase3Processor:
    """Phase 3 processor with configuration management and core library integration"""
    
    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize Phase 3 Processor
        
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
        
        # Get typed configuration objects
        self.path_config = ConfigManager.get_path_config(self.config)
        self.proc_config = ConfigManager.get_processor_config(self.config)
        
        # Setup logging
        self.logger = create_logger(
            name="phase3_processor",
            log_dir=self.path_config.log_output,
            log_level=self.proc_config.log_level
        )
        
        # Get replay file patterns from config and discover files
        replay_patterns = self.config.get('files', {}).get('replay_patterns')
        if not replay_patterns:
            raise ValueError("Configuration error: 'files.replay_patterns' is required in config file")
        
        self.replay_files = []
        for pattern in replay_patterns:
            pattern_path = os.path.join(self.path_config.replay_input, pattern)
            matches = glob.glob(pattern_path)
            self.replay_files.extend([os.path.basename(f) for f in matches])
        
        if not self.replay_files:
            raise ValueError(f"No replay files found matching patterns: {replay_patterns}")
        
        # Statistics using ProcessingStats from core library
        self.stats = ProcessingStats()
        
        # Character replacement utility
        self.char_replacer = CharacterReplacement()
        
        # Ultra-optimized: Pre-indexed incident files
        self.incident_indexes = {}  # incident_code -> IncidentFileIndex
        
        # Output filename replacement pattern (from config)
        replace_config = self.config.get('processor', {}).get('replace_pattern', {})
        self.replace_from = replace_config.get('from', '')
        self.replace_to = replace_config.get('to', '')
        
        if self.replace_from and not self.replace_to:
            raise ValueError("Configuration error: 'replace_pattern.to' is required when 'replace_pattern.from' is specified")
        if self.replace_to and not self.replace_from:
            raise ValueError("Configuration error: 'replace_pattern.from' is required when 'replace_pattern.to' is specified")
        
        # Similarity threshold for fuzzy matching (reasonable technical default)
        self.similarity_threshold = self.config.get('processor', {}).get('similarity_threshold', 0.85)
        
        # Incident file pattern from config (NO default - user must specify)
        incident_pattern = self.config.get('files', {}).get('incident_pattern')
        if not incident_pattern:
            raise ValueError("Configuration error: 'files.incident_pattern' is required in config file")
        self.incident_pattern = incident_pattern
        
        # Incident template column configuration (NO defaults - user must specify)
        self.incident_columns = self.config.get('incident_columns')
        if not self.incident_columns:
            raise ValueError("Configuration error: 'incident_columns' section is required in config file")
    
    def preload_and_index_incident_files(self):
        """Preload and index all required incident files"""
        self.logger.info("Analyzing replay files for incident codes...")
        
        # Collect all incident codes from replay files
        incident_codes = set()
        
        for replay_filename in self.replay_files:
            replay_filepath = os.path.join(self.path_config.replay_input, replay_filename)
            if os.path.exists(replay_filepath):
                try:
                    f, encoding = safe_open_csv(Path(replay_filepath), 'r', newline='')
                    with f:
                        reader = csv.reader(f)
                        rows = list(reader)
                    
                    for row in rows[1:]:  # Skip header
                        if len(row) > 4 and row[4].strip():
                            codes = [code.strip() for code in row[4].split('|') if code.strip()]
                            incident_codes.update(codes)
                            
                except Exception as e:
                    self.logger.warning(f"Error analyzing {replay_filename}: {e}")
        
        # Load and index incident files
        self.logger.info(f"Loading and indexing {len(incident_codes)} incident files...")
        
        loaded_count = 0
        for incident_code in incident_codes:
            incident_file = self.find_incident_file(incident_code)
            if incident_file:
                self.logger.debug(f"Indexing {incident_code}...")
                self.incident_indexes[incident_code] = IncidentFileIndex(
                    incident_file, 
                    self.incident_columns, 
                    self.logger
                )
                loaded_count += 1
        
        self.logger.info(f"Successfully indexed {loaded_count} incident files")
    
    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find incident file for given code using configurable pattern"""
        # Extract prefix from pattern (e.g., "FY25 Q4 " from "FY25 Q4 *.csv")
        pattern_prefix = self.incident_pattern.replace('*.csv', '').strip()
        
        # Try primary pattern (space, no dash)
        pattern = f"{pattern_prefix} {incident_code}.csv"
        filepath = os.path.join(self.path_config.incident_files, pattern)
        
        if os.path.exists(filepath):
            return filepath
        
        # Try backwards compatible pattern (with dash)
        pattern_with_dash = f"{pattern_prefix} - {incident_code}.csv"
        filepath_with_dash = os.path.join(self.path_config.incident_files, pattern_with_dash)
        
        if os.path.exists(filepath_with_dash):
            return filepath_with_dash
        
        # Fallback glob search
        glob_pattern = os.path.join(self.path_config.incident_files, f"*{incident_code}*.csv")
        matches = glob.glob(glob_pattern)
        return matches[0] if matches else None
    
    def parse_client_record_ids(self, row: List[str], row_index: int) -> ClientRecord:
        """Parse IDs format record"""
        try:
            # Parse name/DOB
            name_dob_parts = row[0].split('~')
            if len(name_dob_parts) >= 3:
                first_name = name_dob_parts[0].strip()
                surname = name_dob_parts[1].strip() 
                raw_dob = name_dob_parts[2].strip()
                parsed_dob = DateParser.parse_date(raw_dob) or raw_dob
            else:
                first_name = surname = parsed_dob = ""
            
            # Parse IDs
            id_data = row[1].strip()
            ids = id_data.split('\n') if '\n' in id_data else [id_data]
            
            parsed_ids = []
            for id_entry in ids:
                if ':' in id_entry:
                    id_parts = id_entry.split(':', 1)
                    parsed_ids.append(id_parts[1].strip())  # Just the ID value
            
            primary_id = parsed_ids[0] if parsed_ids else ""
            
            # Parse incident codes
            incident_codes_str = row[4].strip() if len(row) > 4 else ""
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            return ClientRecord(
                first_name=first_name,
                surname=surname,
                date_of_birth=parsed_dob,
                id_value=primary_id,
                id_type="",
                incident_codes=incident_codes,
                original_row=row.copy(),
                row_index=row_index,
                file_type='IDs',
                all_ids=parsed_ids
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing IDs record at row {row_index + 1}: {e}")
            return ClientRecord("", "", "", "", "", [], row.copy(), row_index, 'IDs', [])
    
    def parse_client_record_names(self, row: List[str], row_index: int) -> ClientRecord:
        """Parse Names format record"""
        try:
            # Parse ID
            id_data = row[0].strip()
            if '~' in id_data:
                id_value = id_data.split('~', 1)[0].strip()
            else:
                id_value = id_data
            
            # Parse name/DOB
            name_dob_data = row[1].strip()
            name_dob_parts = name_dob_data.split(':')
            if len(name_dob_parts) >= 3:
                first_name = name_dob_parts[0].strip()
                surname = name_dob_parts[1].strip()
                raw_dob = name_dob_parts[2].strip()
                parsed_dob = DateParser.parse_date(raw_dob) or raw_dob
            else:
                first_name = surname = parsed_dob = ""
            
            # Parse incident codes
            incident_codes_str = row[4].strip() if len(row) > 4 else ""
            incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
            
            return ClientRecord(
                first_name=first_name,
                surname=surname,
                date_of_birth=parsed_dob,
                id_value=id_value,
                id_type="",
                incident_codes=incident_codes,
                original_row=row.copy(),
                row_index=row_index,
                file_type='Names',
                all_ids=[id_value] if id_value else []
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Names record at row {row_index + 1}: {e}")
            return ClientRecord("", "", "", "", "", [], row.copy(), row_index, 'Names', [])
    
    def lookup_client(self, client: ClientRecord, incident_code: str) -> LookupResult:
        """Ultra-fast client lookup using pre-built indexes"""
        if incident_code not in self.incident_indexes:
            return LookupResult(found=False)
        
        index = self.incident_indexes[incident_code]
        
        # Try ID lookup first (O(1) with index)
        if client.all_ids and any(client.all_ids):
            id_result = index.lookup_by_id(client.all_ids)
            if id_result:
                row_idx, match_type = id_result
                return self._create_lookup_result(index.data_rows[row_idx], index.column_mapper, match_type)
        
        # Try name lookup (O(1) with index)
        if client.first_name and client.surname:
            name_result = index.lookup_by_name(client.first_name, client.surname, client.date_of_birth)
            if name_result:
                row_idx, match_type = name_result
                return self._create_lookup_result(index.data_rows[row_idx], index.column_mapper, match_type)
        
        return LookupResult(found=False)
    
    def _create_lookup_result(self, row: List[str], column_mapper: IncidentColumnMapper, match_type: str) -> LookupResult:
        """Create lookup result from row data, checking for analyst corrections"""
        try:
            # Get column indices
            error_flag_col = column_mapper.get('error_flag')
            txn_ref_col = column_mapper.get('transaction_ref')
            correction_col = column_mapper.get('correction')
            correction_field_col = column_mapper.get('correction_field')
            agree_col = column_mapper.get('agree_with_correction')
            suggested_correction_col = column_mapper.get('suggested_correction')
            suggested_correction_field_col = column_mapper.get('suggested_correction_field')
            
            # Extract basic fields
            error_flag = row[error_flag_col].strip() if error_flag_col is not None and len(row) > error_flag_col else ""
            transaction_ref = row[txn_ref_col].strip() if txn_ref_col is not None and len(row) > txn_ref_col else ""
            
            # Check if analyst disagrees with correction
            use_suggested = False
            if agree_col is not None and len(row) > agree_col:
                agree_value = row[agree_col].strip().upper()
                if agree_value == 'N':
                    use_suggested = True
            
            # Route to appropriate correction source
            if use_suggested and suggested_correction_col is not None and suggested_correction_field_col is not None:
                # Use analyst's suggested correction
                correction = row[suggested_correction_col].strip() if len(row) > suggested_correction_col else ""
                correction_field = row[suggested_correction_field_col].strip() if len(row) > suggested_correction_field_col else ""
            elif error_flag.upper() == 'Y' and correction_col is not None and correction_field_col is not None:
                # Use standard correction
                correction = row[correction_col].strip() if len(row) > correction_col else ""
                correction_field = row[correction_field_col].strip() if len(row) > correction_field_col else ""
            else:
                correction = "No Change"
                correction_field = ""
            
            return LookupResult(
                found=True,
                correction=correction,
                correction_field=correction_field,
                error_flag=error_flag,
                transaction_ref=transaction_ref,
                match_type=match_type
            )
        except Exception as e:
            self.logger.error(f"Error creating lookup result: {e}")
            return LookupResult(found=False)
    
    def process_client_record(self, client: ClientRecord) -> Tuple[str, str]:
        """Process client record with ultra-fast lookups"""
        if not client.incident_codes:
            self.logger.debug(f"No incident codes for client: {client.id_value} {client.first_name} {client.surname}")
            return "Client not found", ""
        
        all_corrections = []
        
        for incident_code in client.incident_codes:
            result = self.lookup_client(client, incident_code)
            
            if result.found:
                correction_pair = f"{result.correction}~{result.correction_field}" if result.correction_field else result.correction
                all_corrections.append(correction_pair)
        
        if not all_corrections:
            self.stats.increment('not_found')
            return "Client not found", ""
        
        # Handle multiple corrections
        unique_corrections = list(set(all_corrections))
        if len(unique_corrections) > 1:
            self.stats.increment('inconsistent_corrections')
            return "|".join(unique_corrections), ""
        else:
            correction_data = unique_corrections[0]
            if '~' in correction_data and correction_data != "No Change":
                parts = correction_data.split('~', 1)
                return parts[0], parts[1]
            else:
                return correction_data, ""
    
    def process_replay_file(self, filename: str):
        """Process replay file with batch optimizations"""
        input_filepath = os.path.join(self.path_config.replay_input, filename)
        
        # Apply filename replacements from config if specified
        output_filename = filename
        if self.replace_from and self.replace_to:
            output_filename = filename.replace(self.replace_from, self.replace_to)
        
        output_filepath = os.path.join(self.path_config.replay_output, output_filename)
        
        self.logger.info(f"Processing replay file: {filename}")
        
        try:
            # Read file
            f, encoding = safe_open_csv(Path(input_filepath), 'r', newline='')
            with f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                self.logger.warning(f"No data rows in {filename}")
                return
            
            header = rows[0]
            data_rows = rows[1:]
            processed_rows = [header]
            
            # Batch process with progress reporting
            batch_size = self.proc_config.batch_size
            total_rows = len(data_rows)
            
            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                
                # Process batch
                for i in range(batch_start, batch_end):
                    row = data_rows[i]
                    
                    try:
                        # Ensure row has enough columns
                        while len(row) < 9:
                            row.append("")
                        
                        # Parse client record
                        if 'IDs' in filename:
                            client = self.parse_client_record_ids(row, i + 1)
                        else:
                            client = self.parse_client_record_names(row, i + 1)
                        
                        # Process record
                        correction, correction_field = self.process_client_record(client)
                        
                        # Update row
                        row[6] = correction
                        row[7] = correction_field
                        
                        processed_rows.append(row)
                        self.stats.increment('processed_records')
                        
                        if correction != "Client not found":
                            self.stats.increment('successful_matches')
                            if correction == "No Change":
                                self.stats.increment('no_corrections')
                    
                    except Exception as e:
                        self.logger.error(f"Error processing row {i + 1}: {e}")
                        row[6] = "Processing Error"
                        row[7] = ""
                        processed_rows.append(row)
                        self.stats.increment('errors')
                
                # Progress report
                progress = ((batch_end / total_rows) * 100)
                self.logger.info(f"Progress: {batch_end}/{total_rows} ({progress:.1f}%)")
            
            # Write output
            os.makedirs(self.path_config.replay_output, exist_ok=True)
            with open(output_filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(processed_rows)
            
            self.logger.info(f"Completed {filename} -> {output_filename}")
            
        except Exception as e:
            self.logger.error(f"Error processing {filename}: {e}")
            self.stats.increment('errors')
    
    def generate_summary_log(self):
        """Generate processing summary"""
        summary_lines = [
            "=" * 80,
            "PHASE 3 PROCESSOR v4.2 (ULTRA-OPTIMIZED) - SUMMARY",
            "=" * 80,
            f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "STATISTICS:",
            f"  Processed records: {self.stats['processed_records']}",
            f"  Successful matches: {self.stats['successful_matches']}",
            f"  Not found: {self.stats['not_found']}",
            f"  No corrections needed: {self.stats['no_corrections']}",
            f"  Inconsistent corrections: {self.stats['inconsistent_corrections']}",
            f"  Processing errors: {self.stats['errors']}",
            "",
            "OPTIMIZATION INFO:",
            f"  Incident files indexed: {len(self.incident_indexes)}",
            f"  Date cache entries: {len(DateParser._date_cache)}",
            "=" * 80
        ]
        
        with open(self.log_filepath, 'a', encoding='utf-8') as f:
            f.write('\n' + '\n'.join(summary_lines) + '\n')
        
        for line in summary_lines:
            print(line)
    
    def run(self):
        """Main execution with ultra optimizations"""
        start_time = datetime.now()
        
        self.logger.log_header("PHASE 3 PROCESSOR v5.0")
        self.logger.info(f"Replay input path: {self.path_config.replay_input}")
        self.logger.info(f"Incident files path: {self.path_config.incident_files}")
        self.logger.info(f"Output path: {self.path_config.replay_output}")
        
        # Ensure directories exist
        os.makedirs(self.path_config.replay_output, exist_ok=True)
        os.makedirs(self.path_config.log_output, exist_ok=True)
        
        # Preload and index everything upfront
        self.preload_and_index_incident_files()
        
        # Process files
        for filename in self.replay_files:
            input_path = os.path.join(self.path_config.replay_input, filename)
            if os.path.exists(input_path):
                self.process_replay_file(filename)
            else:
                self.logger.error(f"File not found: {input_path}")
        
        # Summary
        end_time = datetime.now()
        duration = end_time - start_time
        self.logger.info(f"Total processing time: {duration}")
        
        self.logger.log_header("PROCESSING SUMMARY")
        self.logger.log_stats(self.stats)
        
        # Additional metrics
        total_indexed = sum(len(idx.buyer_id_index) + len(idx.seller_id_index) for idx in self.incident_indexes.values())
        self.logger.info(f"Incident files indexed: {len(self.incident_indexes)}")
        self.logger.info(f"Total IDs indexed: {total_indexed}")
        
        self.logger.info("Phase 3 Processor v5.0 completed successfully")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Phase 3 Processor v5.0 - Inconsistent IDs/Names Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with configuration file
  python phase_3_processor.py --config config/phase3.yaml
  
  # Run with environment variables
  export TXR_PATHS_REPLAY_INPUT="/path/to/replay"
  export TXR_PATHS_INCIDENT_FILES="/path/to/incidents"
  python phase_3_processor.py --use-env
  
  # Override log level
  python phase_3_processor.py --config config/phase3.yaml --log-level DEBUG
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file (default: config/phase3.yaml)'
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
            # Default configuration path (use local config)
            default_config = Path(__file__).parent.parent.parent / "config" / "local" / "replay" / "phase3.yaml"
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
        processor = Phase3Processor(config_dict=config)
        processor.run()
        
        return 0
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())