#!/usr/bin/env python3
"""
Phase 3 Processor v5.2
Refactored version using shared txr_replay_core library.
Leverages ConfigManager, StructuredLogger, DateParser, and shared data structures.

Author: GitHub Copilot
Date: March 13, 2026
Version: 5.2 - Prefer correction-bearing rows when multiple transactions share same ID/name

CHANGES IN v5.2:
- **BUG FIX**: Lookup methods previously returned the *first* matching transaction row.
  In high-volume incident files (e.g. 7_66: 2,780 rows / 635 unique IDs ≈ 4.4 tx/person;
  7_68: 6,818 rows / 638 unique IDs ≈ 10.7 tx/person), corrections are only present on a
  subset of rows.  Taking the first row caused ~95% of records to return "No Change" even
  when a correction existed in a later row for the same person.
- Added _find_best_row_idx() helper that scans all candidate rows and returns the first one
  with a non-empty Correction or Suggested Correction; falls back to the first row if none
  have corrections (no behaviour change for files that are uniformly uncorrected).
- Updated lookup_by_id(): name-disambiguation loop now *collects* all name-matching rows
  and then calls _find_best_row_idx() on them, rather than early-returning on the first hit.
  Fall-through (no name match) also uses _find_best_row_idx() instead of row_indices[0].
- Updated lookup_by_name(): all eight index lookups now use _find_best_row_idx() instead
  of taking index [0] directly.
- All four index types (buyer, seller, buyer DM, seller DM) are covered in both methods.

CHANGES IN v5.1:
- **BUG FIX**: Fixed ID lookup to disambiguate when multiple records share the same ID
- When multiple incident file rows have the same ID, now checks name to find correct match
- Previously took first match blindly, causing wrong corrections to be applied
- Example: GB20140522ALEXASTEID matched to both STEID and STEIDL records - now correctly selects STEIDL
- Updated lookup_by_id() to accept client_first and client_surname parameters for disambiguation
- Applies to both buyer and seller ID indexes

CHANGES IN v5.0:
- Migrated to txr_replay_core library (ConfigManager, StructuredLogger, DateParser)
- Replaced hardcoded paths with configuration file
- Added CLI interface with argparse
- Using shared ReplayRecord, LookupResult, ProcessingStats
- Eliminated duplicate DateParser class
- Improved logging with structured logger
- Implemented new correction decision logic (February 2026)
- Removed Error Flag dependency from decision flow
- Correction column existence checked first (not last)
- Agree With Correction now supports Y/P (apply) and N/F (don't apply) values
- Suggested Correction is fallback when Correction is empty or analyst disagrees
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
            # Joint account rows in incident files store pipe-delimited IDs (e.g.
            # "GB001|GB002"). Each individual ID is indexed so that replay records
            # carrying a single member ID are still matched.
            buyer_id_col = col.get('buyer_id')
            if buyer_id_col is not None and len(row) > buyer_id_col:
                for buyer_id in row[buyer_id_col].split('|'):
                    buyer_id = buyer_id.strip().lower()
                    if buyer_id:
                        if buyer_id not in self.buyer_id_index:
                            self.buyer_id_index[buyer_id] = []
                        self.buyer_id_index[buyer_id].append(i)
            
            # Index seller data
            seller_id_col = col.get('seller_id')
            if seller_id_col is not None and len(row) > seller_id_col:
                for seller_id in row[seller_id_col].split('|'):
                    seller_id = seller_id.strip().lower()
                    if seller_id:
                        if seller_id not in self.seller_id_index:
                            self.seller_id_index[seller_id] = []
                        self.seller_id_index[seller_id].append(i)
            
            # Index buyer names
            # Joint account rows also pipe-delimit name/DOB fields, so zip the
            # split parts and index each member individually.
            buyer_first_col = col.get('buyer_first_name')
            buyer_last_col = col.get('buyer_last_name')
            buyer_dob_col = col.get('buyer_dob')
            
            if (buyer_first_col is not None and buyer_last_col is not None and 
                len(row) > max(buyer_first_col, buyer_last_col)):
                buyer_first_parts = [p.strip().lower() for p in row[buyer_first_col].split('|')]
                buyer_last_parts = [p.strip().lower() for p in row[buyer_last_col].split('|')]
                buyer_dob_raw = row[buyer_dob_col] if buyer_dob_col is not None and len(row) > buyer_dob_col else ""
                buyer_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in buyer_dob_raw.split('|')] if buyer_dob_raw else [""]
                
                for buyer_first, buyer_last, buyer_dob in zip(buyer_first_parts, buyer_last_parts, buyer_dob_parts):
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
                seller_first_parts = [p.strip().lower() for p in row[seller_first_col].split('|')]
                seller_last_parts = [p.strip().lower() for p in row[seller_last_col].split('|')]
                seller_dob_raw = row[seller_dob_col] if seller_dob_col is not None and len(row) > seller_dob_col else ""
                seller_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in seller_dob_raw.split('|')] if seller_dob_raw else [""]
                
                for seller_first, seller_last, seller_dob in zip(seller_first_parts, seller_last_parts, seller_dob_parts):
                    if seller_first and seller_last:
                        name_key = (seller_first, seller_last, seller_dob)
                        if name_key not in self.seller_name_index:
                            self.seller_name_index[name_key] = []
                        self.seller_name_index[name_key].append(i)
            
            # Index buyer decision maker data
            buyer_dm_id_col = col.get('buyer_dm_id')
            if buyer_dm_id_col is not None and len(row) > buyer_dm_id_col:
                for buyer_dm_id in row[buyer_dm_id_col].split('|'):
                    buyer_dm_id = buyer_dm_id.strip().lower()
                    if buyer_dm_id:
                        if buyer_dm_id not in self.buyer_dm_id_index:
                            self.buyer_dm_id_index[buyer_dm_id] = []
                        self.buyer_dm_id_index[buyer_dm_id].append(i)
            
            buyer_dm_first_col = col.get('buyer_dm_first_name')
            buyer_dm_last_col = col.get('buyer_dm_last_name')
            buyer_dm_dob_col = col.get('buyer_dm_dob')
            
            if (buyer_dm_first_col is not None and buyer_dm_last_col is not None and
                len(row) > max(buyer_dm_first_col, buyer_dm_last_col)):
                buyer_dm_first_parts = [p.strip().lower() for p in row[buyer_dm_first_col].split('|')]
                buyer_dm_last_parts = [p.strip().lower() for p in row[buyer_dm_last_col].split('|')]
                buyer_dm_dob_raw = row[buyer_dm_dob_col] if buyer_dm_dob_col is not None and len(row) > buyer_dm_dob_col else ""
                buyer_dm_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in buyer_dm_dob_raw.split('|')] if buyer_dm_dob_raw else [""]
                
                for buyer_dm_first, buyer_dm_last, buyer_dm_dob in zip(buyer_dm_first_parts, buyer_dm_last_parts, buyer_dm_dob_parts):
                    if buyer_dm_first and buyer_dm_last:
                        name_key = (buyer_dm_first, buyer_dm_last, buyer_dm_dob)
                        if name_key not in self.buyer_dm_name_index:
                            self.buyer_dm_name_index[name_key] = []
                        self.buyer_dm_name_index[name_key].append(i)
            
            # Index seller decision maker data
            seller_dm_id_col = col.get('seller_dm_id')
            if seller_dm_id_col is not None and len(row) > seller_dm_id_col:
                for seller_dm_id in row[seller_dm_id_col].split('|'):
                    seller_dm_id = seller_dm_id.strip().lower()
                    if seller_dm_id:
                        if seller_dm_id not in self.seller_dm_id_index:
                            self.seller_dm_id_index[seller_dm_id] = []
                        self.seller_dm_id_index[seller_dm_id].append(i)
            
            seller_dm_first_col = col.get('seller_dm_first_name')
            seller_dm_last_col = col.get('seller_dm_last_name')
            seller_dm_dob_col = col.get('seller_dm_dob')
            
            if (seller_dm_first_col is not None and seller_dm_last_col is not None and
                len(row) > max(seller_dm_first_col, seller_dm_last_col)):
                seller_dm_first_parts = [p.strip().lower() for p in row[seller_dm_first_col].split('|')]
                seller_dm_last_parts = [p.strip().lower() for p in row[seller_dm_last_col].split('|')]
                seller_dm_dob_raw = row[seller_dm_dob_col] if seller_dm_dob_col is not None and len(row) > seller_dm_dob_col else ""
                seller_dm_dob_parts = [DateParser.parse_date(p.strip()) or "" for p in seller_dm_dob_raw.split('|')] if seller_dm_dob_raw else [""]
                
                for seller_dm_first, seller_dm_last, seller_dm_dob in zip(seller_dm_first_parts, seller_dm_last_parts, seller_dm_dob_parts):
                    if seller_dm_first and seller_dm_last:
                        name_key = (seller_dm_first, seller_dm_last, seller_dm_dob)
                        if name_key not in self.seller_dm_name_index:
                            self.seller_dm_name_index[name_key] = []
                        self.seller_dm_name_index[name_key].append(i)
    
    def _find_best_row_idx(self, row_indices: List[int]) -> int:
        """Return the row index with the most useful correction data.

        Scans all candidates and returns the first one that has a non-empty
        Correction or Suggested Correction value.  Falls back to the first
        candidate if none have corrections, preserving the previous behaviour.

        Args:
            row_indices: Non-empty list of candidate row indices.

        Returns:
            The index of the best candidate row.
        """
        correction_col = self.column_mapper.get('correction') if self.column_mapper else None
        suggested_col = self.column_mapper.get('suggested_correction') if self.column_mapper else None

        if correction_col is None and suggested_col is None:
            return row_indices[0]

        for row_idx in row_indices:
            row = self.data_rows[row_idx]
            has_correction = (
                correction_col is not None
                and len(row) > correction_col
                and row[correction_col].strip()
            )
            has_suggested = (
                suggested_col is not None
                and len(row) > suggested_col
                and row[suggested_col].strip()
            )
            if has_correction or has_suggested:
                return row_idx

        return row_indices[0]

    def lookup_by_id(self, client_ids: List[str], client_first: str = "", client_surname: str = "") -> Optional[Tuple[int, str]]:
        """Fast O(1) ID lookup using indexes
        
        When multiple records share the same ID, prefers the row that already
        has a correction (Correction or Suggested Correction) and uses the
        client name to disambiguate when rows are tied on that criterion.
        
        Args:
            client_ids: List of client IDs to search for
            client_first: Client first name for disambiguation (optional)
            client_surname: Client surname for disambiguation (optional)
        """
        if self.logger:
            self.logger.debug(f"Looking up IDs: {client_ids}")
        
        for client_id in client_ids:
            if not client_id:
                continue
            client_id_lower = client_id.lower()
            
            # Check buyer index
            if client_id_lower in self.buyer_id_index:
                row_indices = self.buyer_id_index[client_id_lower]
                
                # If multiple matches and we have name info, try to disambiguate
                if len(row_indices) > 1 and client_first and client_surname:
                    col = self.column_mapper
                    buyer_first_col = col.get('buyer_first_name')
                    buyer_last_col = col.get('buyer_last_name')
                    
                    if buyer_first_col is not None and buyer_last_col is not None:
                        # Collect ALL rows that match by name, then pick the one
                        # with the best correction data among them.
                        name_matched = []
                        for row_idx in row_indices:
                            row = self.data_rows[row_idx]
                            if len(row) > max(buyer_first_col, buyer_last_col):
                                first = row[buyer_first_col].strip().lower()
                                last = row[buyer_last_col].strip().lower()
                                if first == client_first.lower() and last == client_surname.lower():
                                    name_matched.append(row_idx)
                        if name_matched:
                            row_idx = self._find_best_row_idx(name_matched)
                            if self.logger:
                                self.logger.debug(f"Found ID '{client_id}' with name match in buyer_id_index (row {row_idx})")
                            return (row_idx, "id_buyer")
                
                # No name match or no disambiguation needed - prefer row with corrections
                row_idx = self._find_best_row_idx(row_indices)
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in buyer_id_index (row {row_idx}, {len(row_indices)} total matches)")
                return (row_idx, "id_buyer")
            
            # Check seller index
            if client_id_lower in self.seller_id_index:
                row_indices = self.seller_id_index[client_id_lower]
                
                # If multiple matches and we have name info, try to disambiguate
                if len(row_indices) > 1 and client_first and client_surname:
                    col = self.column_mapper
                    seller_first_col = col.get('seller_first_name')
                    seller_last_col = col.get('seller_last_name')
                    
                    if seller_first_col is not None and seller_last_col is not None:
                        name_matched = []
                        for row_idx in row_indices:
                            row = self.data_rows[row_idx]
                            if len(row) > max(seller_first_col, seller_last_col):
                                first = row[seller_first_col].strip().lower()
                                last = row[seller_last_col].strip().lower()
                                if first == client_first.lower() and last == client_surname.lower():
                                    name_matched.append(row_idx)
                        if name_matched:
                            row_idx = self._find_best_row_idx(name_matched)
                            if self.logger:
                                self.logger.debug(f"Found ID '{client_id}' with name match in seller_id_index (row {row_idx})")
                            return (row_idx, "id_seller")
                
                row_idx = self._find_best_row_idx(row_indices)
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in seller_id_index (row {row_idx}, {len(row_indices)} total matches)")
                return (row_idx, "id_seller")
            
            # Check buyer decision maker index (fallback)
            if client_id_lower in self.buyer_dm_id_index:
                row_indices = self.buyer_dm_id_index[client_id_lower]

                if len(row_indices) > 1 and client_first and client_surname:
                    col = self.column_mapper
                    buyer_dm_first_col = col.get('buyer_dm_first_name')
                    buyer_dm_last_col = col.get('buyer_dm_last_name')

                    if buyer_dm_first_col is not None and buyer_dm_last_col is not None:
                        name_matched = []
                        for row_idx in row_indices:
                            row = self.data_rows[row_idx]
                            if len(row) > max(buyer_dm_first_col, buyer_dm_last_col):
                                first = row[buyer_dm_first_col].strip().lower()
                                last = row[buyer_dm_last_col].strip().lower()
                                if first == client_first.lower() and last == client_surname.lower():
                                    name_matched.append(row_idx)
                        if name_matched:
                            row_idx = self._find_best_row_idx(name_matched)
                            if self.logger:
                                self.logger.debug(f"Found ID '{client_id}' with name match in buyer_dm_id_index (row {row_idx})")
                            return (row_idx, "id_buyer_dm")

                row_idx = self._find_best_row_idx(row_indices)
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in buyer_dm_id_index (row {row_idx}, {len(row_indices)} total matches)")
                return (row_idx, "id_buyer_dm")

            # Check seller decision maker index (fallback)
            if client_id_lower in self.seller_dm_id_index:
                row_indices = self.seller_dm_id_index[client_id_lower]

                if len(row_indices) > 1 and client_first and client_surname:
                    col = self.column_mapper
                    seller_dm_first_col = col.get('seller_dm_first_name')
                    seller_dm_last_col = col.get('seller_dm_last_name')

                    if seller_dm_first_col is not None and seller_dm_last_col is not None:
                        name_matched = []
                        for row_idx in row_indices:
                            row = self.data_rows[row_idx]
                            if len(row) > max(seller_dm_first_col, seller_dm_last_col):
                                first = row[seller_dm_first_col].strip().lower()
                                last = row[seller_dm_last_col].strip().lower()
                                if first == client_first.lower() and last == client_surname.lower():
                                    name_matched.append(row_idx)
                        if name_matched:
                            row_idx = self._find_best_row_idx(name_matched)
                            if self.logger:
                                self.logger.debug(f"Found ID '{client_id}' with name match in seller_dm_id_index (row {row_idx})")
                            return (row_idx, "id_seller_dm")

                row_idx = self._find_best_row_idx(row_indices)
                if self.logger:
                    self.logger.debug(f"Found ID '{client_id}' in seller_dm_id_index (row {row_idx}, {len(row_indices)} total matches)")
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
            row_idx = self._find_best_row_idx(self.buyer_name_index[name_key])
            if self.logger:
                self.logger.debug(f"Found name in buyer_name_index")
            return (row_idx, "name_buyer")
        
        # Check seller index  
        if name_key in self.seller_name_index:
            row_idx = self._find_best_row_idx(self.seller_name_index[name_key])
            if self.logger:
                self.logger.debug(f"Found name in seller_name_index")
            return (row_idx, "name_seller")
        
        # Try without DOB if no exact match
        if dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            
            if name_key_no_dob in self.buyer_name_index:
                row_idx = self._find_best_row_idx(self.buyer_name_index[name_key_no_dob])
                return (row_idx, "name_buyer")
            
            if name_key_no_dob in self.seller_name_index:
                row_idx = self._find_best_row_idx(self.seller_name_index[name_key_no_dob])
                return (row_idx, "name_seller")
        
        # Check buyer decision maker index (fallback)
        if name_key in self.buyer_dm_name_index:
            row_idx = self._find_best_row_idx(self.buyer_dm_name_index[name_key])
            return (row_idx, "name_buyer_dm")
        
        # Check seller decision maker index (fallback)
        if name_key in self.seller_dm_name_index:
            row_idx = self._find_best_row_idx(self.seller_dm_name_index[name_key])
            return (row_idx, "name_seller_dm")
        
        # Try decision makers without DOB
        if dob_parsed:
            name_key_no_dob = (first_lower, surname_lower, "")
            
            if name_key_no_dob in self.buyer_dm_name_index:
                row_idx = self._find_best_row_idx(self.buyer_dm_name_index[name_key_no_dob])
                return (row_idx, "name_buyer_dm")
            
            if name_key_no_dob in self.seller_dm_name_index:
                row_idx = self._find_best_row_idx(self.seller_dm_name_index[name_key_no_dob])
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
            id_result = index.lookup_by_id(client.all_ids, client.first_name, client.surname)
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
        """Create lookup result from row data with new correction decision logic.
        
        Decision Flow:
        1. Check if Correction column has value:
           - If YES: Check Agree With Correction
             - If Y/P/empty: Apply Correction
             - If N/F: Check Suggested Correction -> Apply if exists, else No Change
           - If NO: Check Suggested Correction -> Apply if exists, else No Change
        """
        try:
            # Get column indices
            txn_ref_col = column_mapper.get('transaction_ref')
            correction_col = column_mapper.get('correction')
            correction_field_col = column_mapper.get('correction_field')
            agree_col = column_mapper.get('agree_with_correction')
            suggested_correction_col = column_mapper.get('suggested_correction')
            suggested_correction_field_col = column_mapper.get('suggested_correction_field')
            
            # Extract transaction reference
            transaction_ref = row[txn_ref_col].strip() if txn_ref_col is not None and len(row) > txn_ref_col else ""
            
            # Extract correction values
            correction_value = row[correction_col].strip() if correction_col is not None and len(row) > correction_col else ""
            correction_field_value = row[correction_field_col].strip() if correction_field_col is not None and len(row) > correction_field_col else ""
            
            # Extract suggested correction values
            suggested_correction_value = row[suggested_correction_col].strip() if suggested_correction_col is not None and len(row) > suggested_correction_col else ""
            suggested_correction_field_value = row[suggested_correction_field_col].strip() if suggested_correction_field_col is not None and len(row) > suggested_correction_field_col else ""
            
            # NEW DECISION LOGIC
            correction = "No Change"
            correction_field = ""
            
            # Check if Correction column has a value
            if correction_value:
                # Extract Agree With Correction value
                agree_value = row[agree_col].strip().upper() if agree_col is not None and len(row) > agree_col else ""
                
                # If agree is Y, P, or empty -> apply Correction
                if agree_value in ('Y', 'P', ''):
                    correction = correction_value
                    correction_field = correction_field_value
                    if self.logger:
                        self.logger.debug(f"Applying Correction (Agree={agree_value or 'empty'}, match={match_type})")
                # If agree is N or F -> check Suggested Correction
                elif agree_value in ('N', 'F'):
                    if suggested_correction_value:
                        correction = suggested_correction_value
                        correction_field = suggested_correction_field_value
                        if self.logger:
                            self.logger.debug(f"Applying Suggested Correction (analyst disagreed, match={match_type})")
                    else:
                        if self.logger:
                            self.logger.debug(f"No correction (analyst disagreed, no suggestion, match={match_type})")
                else:
                    # Unknown agree value - default to applying Correction
                    correction = correction_value
                    correction_field = correction_field_value
                    if self.logger:
                        self.logger.warning(f"Unknown Agree value '{agree_value}', defaulting to Correction")
            else:
                # No Correction value -> check Suggested Correction as fallback
                if suggested_correction_value:
                    correction = suggested_correction_value
                    correction_field = suggested_correction_field_value
                    if self.logger:
                        self.logger.debug(f"Applying Suggested Correction (no automated correction, match={match_type})")
                else:
                    if self.logger:
                        self.logger.debug(f"No correction to apply (match={match_type})")
            
            # Corrections referring to RE Account(s) are not client data changes.
            if re.search(r'\bre\s+accounts?\b', correction, re.IGNORECASE):
                if self.logger:
                    self.logger.debug(f"RE Account correction detected, treating as No Change (match={match_type})")
                correction = "No Change"
                correction_field = ""

            return LookupResult(
                found=True,
                correction=correction,
                correction_field=correction_field,
                error_flag="",  # Deprecated - no longer used
                transaction_ref=transaction_ref,
                match_type=match_type
            )
        except Exception as e:
            self.logger.error(f"Error creating lookup result: {e}")
            return LookupResult(found=False)
    
    def process_client_record(self, client: ClientRecord) -> Tuple[str, str]:
        """Process client record with ultra-fast lookups
        
        Returns:
            Tuple of (correction_value, correction_field) for Phase 3 output columns 6 and 7
        """
        if not client.incident_codes:
            self.logger.debug(f"No incident codes for client: {client.id_value} {client.first_name} {client.surname}")
            return "Client not found", ""
        
        all_correction_values = []
        all_correction_fields = []
        
        for incident_code in client.incident_codes:
            result = self.lookup_client(client, incident_code)
            
            if result.found:
                all_correction_values.append(result.correction)
                all_correction_fields.append(result.correction_field)
                if '_dm' in result.match_type:
                    self.stats.increment('dm_matches')
        
        if not all_correction_values:
            self.stats.increment('not_found')
            return "Client not found", ""
        
        # Normalise RE Account corrections to No Change (catches any that slipped
        # past _create_lookup_result due to encoding or whitespace variations).
        _re_account_pat = re.compile(r'\bre\s+accounts?\b', re.IGNORECASE)
        normalised = [
            ("No Change", "") if _re_account_pat.search(v.strip()) else (v, f)
            for v, f in zip(all_correction_values, all_correction_fields)
        ]
        all_correction_values, all_correction_fields = zip(*normalised)

        # Handle multiple corrections from different incident codes
        unique_corrections = list(set(zip(all_correction_values, all_correction_fields)))
        
        if len(unique_corrections) > 1:
            # Multiple different corrections - concatenate with pipe separator
            self.stats.increment('inconsistent_corrections')
            correction_values = "|".join([c[0] for c in unique_corrections])
            correction_fields = "|".join([c[1] for c in unique_corrections])
            return correction_values, correction_fields
        else:
            # Single correction - return as separate values
            return unique_corrections[0][0], unique_corrections[0][1]
    
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
            f"  Decision maker fallback matches: {self.stats.custom_stats.get('dm_matches', 0)}",
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
        
        self.logger.log_header("PHASE 3 PROCESSOR v5.1 (NAME DISAMBIGUATION FIX)")
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
        
        self.logger.info("Phase 3 Processor v5.1 completed successfully")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Phase 3 Processor v5.1 - Inconsistent IDs/Names Processor",
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