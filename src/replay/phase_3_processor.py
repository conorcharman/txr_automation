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

# Import from txr_replay_core library
from txr_replay_core.data_structures import ReplayRecord, LookupResult, ProcessingStats
from txr_replay_core.config import ConfigManager
from txr_replay_core.logger import create_logger
from txr_replay_core.utils import DateParser, CharacterReplacement, safe_open_csv

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
    
    def __init__(self, file_path: str, logger=None):
        self.file_path = file_path
        self.data_rows = []
        self.logger = logger
        
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
                
            self.data_rows = rows[1:]  # Skip header
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
        """Build all lookup indexes"""
        for i, row in enumerate(self.data_rows):
            if len(row) < 22:  # Minimum for buyer ID at index 21
                continue
                
            # Index buyer data
            buyer_id = row[21].strip().lower() if len(row) > 21 else ""
            if buyer_id:
                if buyer_id not in self.buyer_id_index:
                    self.buyer_id_index[buyer_id] = []
                self.buyer_id_index[buyer_id].append(i)
            
            # Index seller data
            seller_id = row[32].strip().lower() if len(row) > 32 else ""
            if seller_id:
                if seller_id not in self.seller_id_index:
                    self.seller_id_index[seller_id] = []
                self.seller_id_index[seller_id].append(i)
            
            # Index buyer names
            buyer_first = row[24].strip().lower() if len(row) > 24 else ""
            buyer_last = row[25].strip().lower() if len(row) > 25 else ""
            buyer_dob = DateParser.parse_date(row[26]) if len(row) > 26 else ""
            
            if buyer_first and buyer_last:
                name_key = (buyer_first, buyer_last, buyer_dob or "")
                if name_key not in self.buyer_name_index:
                    self.buyer_name_index[name_key] = []
                self.buyer_name_index[name_key].append(i)
            
            # Index seller names
            seller_first = row[35].strip().lower() if len(row) > 35 else ""
            seller_last = row[36].strip().lower() if len(row) > 36 else ""
            seller_dob = DateParser.parse_date(row[37]) if len(row) > 37 else ""
            
            if seller_first and seller_last:
                name_key = (seller_first, seller_last, seller_dob or "")
                if name_key not in self.seller_name_index:
                    self.seller_name_index[name_key] = []
                self.seller_name_index[name_key].append(i)
            
            # Index buyer decision maker data
            buyer_dm_id = row[27].strip().lower() if len(row) > 27 else ""
            if buyer_dm_id:
                if buyer_dm_id not in self.buyer_dm_id_index:
                    self.buyer_dm_id_index[buyer_dm_id] = []
                self.buyer_dm_id_index[buyer_dm_id].append(i)
            
            buyer_dm_first = row[29].strip().lower() if len(row) > 29 else ""
            buyer_dm_last = row[30].strip().lower() if len(row) > 30 else ""
            buyer_dm_dob = DateParser.parse_date(row[31]) if len(row) > 31 else ""
            
            if buyer_dm_first and buyer_dm_last:
                name_key = (buyer_dm_first, buyer_dm_last, buyer_dm_dob or "")
                if name_key not in self.buyer_dm_name_index:
                    self.buyer_dm_name_index[name_key] = []
                self.buyer_dm_name_index[name_key].append(i)
            
            # Index seller decision maker data
            seller_dm_id = row[38].strip().lower() if len(row) > 38 else ""
            if seller_dm_id:
                if seller_dm_id not in self.seller_dm_id_index:
                    self.seller_dm_id_index[seller_dm_id] = []
                self.seller_dm_id_index[seller_dm_id].append(i)
            
            seller_dm_first = row[40].strip().lower() if len(row) > 40 else ""
            seller_dm_last = row[41].strip().lower() if len(row) > 41 else ""
            seller_dm_dob = DateParser.parse_date(row[42]) if len(row) > 42 else ""
            
            if seller_dm_first and seller_dm_last:
                name_key = (seller_dm_first, seller_dm_last, seller_dm_dob or "")
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
        replay_patterns = self.config.get('files', {}).get('replay_patterns', ['*.csv'])
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
        
        # Output filename replacement pattern
        self.replace_from = self.config.get('processor', {}).get('replace_pattern', {}).get('from', 'KR')
        self.replace_to = self.config.get('processor', {}).get('replace_pattern', {}).get('to', 'AJB')
        
        # Similarity threshold for fuzzy matching
        self.similarity_threshold = self.config.get('processor', {}).get('similarity_threshold', 0.85)
    
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
                self.incident_indexes[incident_code] = IncidentFileIndex(incident_file, self.logger)
                loaded_count += 1
        
        self.logger.info(f"Successfully indexed {loaded_count} incident files")
    
    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find incident file for given code"""
        pattern = f"FY25 Q3 - {incident_code}.csv"
        filepath = os.path.join(self.path_config.incident_files, pattern)
        
        if os.path.exists(filepath):
            return filepath
        
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
                return self._create_lookup_result(index.data_rows[row_idx], match_type)
        
        # Try name lookup (O(1) with index)
        if client.first_name and client.surname:
            name_result = index.lookup_by_name(client.first_name, client.surname, client.date_of_birth)
            if name_result:
                row_idx, match_type = name_result
                return self._create_lookup_result(index.data_rows[row_idx], match_type)
        
        return LookupResult(found=False)
    
    def _create_lookup_result(self, row: List[str], match_type: str) -> LookupResult:
        """Create lookup result from row data"""
        try:
            error_flag = row[4].strip() if len(row) > 4 else ""
            transaction_ref = row[0].strip() if len(row) > 0 else ""
            
            if error_flag.upper() == 'Y':
                correction = row[5].strip() if len(row) > 5 else ""
                correction_field = row[6].strip() if len(row) > 6 else ""
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
        output_filename = filename.replace('_FINAL.csv', '_AJB.csv')
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
            batch_size = 50  # Process in smaller batches
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
            # Default configuration path
            default_config = Path(__file__).parent.parent.parent / "config" / "phase3.yaml"
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