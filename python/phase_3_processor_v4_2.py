#!/usr/bin/env python3
"""
Phase 3 Processor v4.2
ULTRA-OPTIMIZED VERSION with indexing, batch processing, and algorithmic improvements.

Author: GitHub Copilot
Date: October 8, 2025
Version: 4.2 - Ultra Performance Optimized
"""

import csv
import os
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
import logging
from dataclasses import dataclass
import re
from difflib import SequenceMatcher
from collections import defaultdict

@dataclass
class ClientRecord:
    """Represents a client record with parsed details"""
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

@dataclass
class LookupResult:
    """Represents the result of a client lookup"""
    found: bool
    correction: str = ""
    correction_field: str = ""
    error_flag: str = ""
    transaction_ref: str = ""
    match_type: str = ""

class DateParser:
    """Handles various date format parsing with caching"""
    
    _date_cache = {}  # Cache parsed dates
    
    @classmethod
    def parse_date(cls, date_str: str) -> Optional[str]:
        """Parse date with caching for performance"""
        if not date_str or date_str.strip() == "":
            return None
            
        date_str = date_str.strip()
        
        # Check cache first
        if date_str in cls._date_cache:
            return cls._date_cache[date_str]
        
        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',  # YYYY-MM-DD
            '%d/%m/%Y',  # DD/MM/YYYY
            '%m/%d/%Y',  # MM/DD/YYYY
            '%d-%m-%Y',  # DD-MM-YYYY
            '%m-%d-%Y',  # MM-DD-YYYY
            '%Y/%m/%d',  # YYYY/MM/DD
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                result = parsed_date.strftime('%Y-%m-%d')
                cls._date_cache[date_str] = result
                return result
            except ValueError:
                continue
        
        # Cache miss result too
        cls._date_cache[date_str] = None
        return None

class IncidentFileIndex:
    """Optimized incident file with pre-built indexes for fast lookups"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data_rows = []
        
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
            with open(self.file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if len(rows) < 2:
                return
                
            self.data_rows = rows[1:]  # Skip header
            self._build_indexes()
            
            # Log index sizes for diagnostics
            logging.info(f"Loaded {os.path.basename(self.file_path)}: {len(self.data_rows)} rows")
            logging.info(f"  - Buyer IDs: {len(self.buyer_id_index)}, Seller IDs: {len(self.seller_id_index)}")
            logging.info(f"  - Buyer DM IDs: {len(self.buyer_dm_id_index)}, Seller DM IDs: {len(self.seller_dm_id_index)}")
            logging.info(f"  - Buyer Names: {len(self.buyer_name_index)}, Seller Names: {len(self.seller_name_index)}")
            logging.info(f"  - Buyer DM Names: {len(self.buyer_dm_name_index)}, Seller DM Names: {len(self.seller_dm_name_index)}")
            
        except Exception as e:
            logging.error(f"Error loading {self.file_path}: {e}")
    
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
        logging.debug(f"Looking up IDs: {client_ids}")
        
        for client_id in client_ids:
            if not client_id:
                continue
            client_id_lower = client_id.lower()
            
            # Check buyer index
            if client_id_lower in self.buyer_id_index:
                row_idx = self.buyer_id_index[client_id_lower][0]  # Take first match
                logging.debug(f"Found ID '{client_id}' in buyer_id_index")
                return (row_idx, "id_buyer")
            
            # Check seller index
            if client_id_lower in self.seller_id_index:
                row_idx = self.seller_id_index[client_id_lower][0]  # Take first match
                logging.debug(f"Found ID '{client_id}' in seller_id_index")
                return (row_idx, "id_seller")
            
            # Check buyer decision maker index (fallback)
            if client_id_lower in self.buyer_dm_id_index:
                row_idx = self.buyer_dm_id_index[client_id_lower][0]
                logging.debug(f"Found ID '{client_id}' in buyer_dm_id_index")
                return (row_idx, "id_buyer_dm")
            
            # Check seller decision maker index (fallback)
            if client_id_lower in self.seller_dm_id_index:
                row_idx = self.seller_dm_id_index[client_id_lower][0]
                logging.debug(f"Found ID '{client_id}' in seller_dm_id_index")
                return (row_idx, "id_seller_dm")
        
        logging.debug(f"ID lookup failed for: {client_ids}")
        return None
    
    def lookup_by_name(self, first_name: str, surname: str, dob: str) -> Optional[Tuple[int, str]]:
        """Fast O(1) name lookup using indexes"""
        first_lower = first_name.lower().strip()
        surname_lower = surname.lower().strip()
        dob_parsed = DateParser.parse_date(dob) if dob else ""
        
        name_key = (first_lower, surname_lower, dob_parsed or "")
        logging.debug(f"Looking up name: {name_key}")
        
        # Check buyer index
        if name_key in self.buyer_name_index:
            row_idx = self.buyer_name_index[name_key][0]  # Take first match
            logging.debug(f"Found name in buyer_name_index")
            return (row_idx, "name_buyer")
        
        # Check seller index  
        if name_key in self.seller_name_index:
            row_idx = self.seller_name_index[name_key][0]  # Take first match
            logging.debug(f"Found name in seller_name_index")
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
        
        logging.debug(f"Name lookup failed for: {name_key}")
        return None

class Phase3ProcessorUltraOptimized:
    """Ultra-optimized Phase 3 processor with indexing and batch processing"""
    
    def __init__(self):
        # File paths
        self.replay_input_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\reference\csv"
        self.incident_files_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\reference\FY25\Q3\incident_code_files\csv"
        self.replay_output_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\output"
        self.log_output_path = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\phase_iii\FY25\Q3\output\logs"
        
        self.replay_files = [
            "Replay_2025Q2_PHASE 3_Inconsistent_IDs_Summary_FINAL.csv",
            "Replay_2025Q2_PHASE 3_Inconsistent_Names_Summary_FINAL.csv"
        ]
        
        self.setup_logging()
        
        # Statistics
        self.stats = {
            'processed_records': 0,
            'successful_matches': 0,
            'not_found': 0,
            'no_corrections': 0,
            'inconsistent_corrections': 0,
            'errors': 0,
            'partial_matches': []
        }
        
        # Ultra-optimized: Pre-indexed incident files
        self.incident_indexes = {}  # incident_code -> IncidentFileIndex
        
    def setup_logging(self):
        """Setup logging configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"phase_3_processor_v42_log_{timestamp}.txt"
        log_filepath = os.path.join(self.log_output_path, log_filename)
        
        os.makedirs(self.log_output_path, exist_ok=True)
        
        logging.basicConfig(
            level=logging.DEBUG,  # Changed to DEBUG for detailed diagnostics
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.log_filepath = log_filepath
    
    def preload_and_index_incident_files(self):
        """Preload and index all required incident files"""
        self.logger.info("Analyzing replay files for incident codes...")
        
        # Collect all incident codes from replay files
        incident_codes = set()
        
        for replay_filename in self.replay_files:
            replay_filepath = os.path.join(self.replay_input_path, replay_filename)
            if os.path.exists(replay_filepath):
                try:
                    with open(replay_filepath, 'r', encoding='utf-8', newline='') as f:
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
                self.incident_indexes[incident_code] = IncidentFileIndex(incident_file)
                loaded_count += 1
        
        self.logger.info(f"Successfully indexed {loaded_count} incident files")
    
    def find_incident_file(self, incident_code: str) -> Optional[str]:
        """Find incident file for given code"""
        pattern = f"FY25 Q3 - {incident_code}.csv"
        filepath = os.path.join(self.incident_files_path, pattern)
        
        if os.path.exists(filepath):
            return filepath
        
        # Fallback glob search
        glob_pattern = os.path.join(self.incident_files_path, f"*{incident_code}*.csv")
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
                correction_pair = f"{result.correction}:{result.correction_field}" if result.correction_field else result.correction
                all_corrections.append(correction_pair)
        
        if not all_corrections:
            self.stats['not_found'] += 1
            return "Client not found", ""
        
        # Handle multiple corrections
        unique_corrections = list(set(all_corrections))
        if len(unique_corrections) > 1:
            self.stats['inconsistent_corrections'] += 1
            return "|".join(unique_corrections), ""
        else:
            correction_data = unique_corrections[0]
            if ':' in correction_data and correction_data != "No Change":
                parts = correction_data.split(':', 1)
                return parts[0], parts[1]
            else:
                return correction_data, ""
    
    def process_replay_file(self, filename: str):
        """Process replay file with batch optimizations"""
        input_filepath = os.path.join(self.replay_input_path, filename)
        output_filename = filename.replace('_FINAL.csv', '_AJB.csv')
        output_filepath = os.path.join(self.replay_output_path, output_filename)
        
        self.logger.info(f"Processing replay file: {filename}")
        
        try:
            # Read file
            with open(input_filepath, 'r', encoding='utf-8', newline='') as f:
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
                        self.stats['processed_records'] += 1
                        
                        if correction != "Client not found":
                            self.stats['successful_matches'] += 1
                            if correction == "No Change":
                                self.stats['no_corrections'] += 1
                    
                    except Exception as e:
                        self.logger.error(f"Error processing row {i + 1}: {e}")
                        row[6] = "Processing Error"
                        row[7] = ""
                        processed_rows.append(row)
                        self.stats['errors'] += 1
                
                # Progress report
                progress = ((batch_end / total_rows) * 100)
                self.logger.info(f"Progress: {batch_end}/{total_rows} ({progress:.1f}%)")
            
            # Write output
            os.makedirs(self.replay_output_path, exist_ok=True)
            with open(output_filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(processed_rows)
            
            self.logger.info(f"Completed {filename} -> {output_filename}")
            
        except Exception as e:
            self.logger.error(f"Error processing {filename}: {e}")
            self.stats['errors'] += 1
    
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
        
        self.logger.info("Starting Phase 3 Processor v4.2 (Ultra-Optimized)")
        
        # Ensure directories exist
        os.makedirs(self.replay_output_path, exist_ok=True)
        os.makedirs(self.log_output_path, exist_ok=True)
        
        # Preload and index everything upfront
        self.preload_and_index_incident_files()
        
        # Process files
        for filename in self.replay_files:
            input_path = os.path.join(self.replay_input_path, filename)
            if os.path.exists(input_path):
                self.process_replay_file(filename)
            else:
                self.logger.error(f"File not found: {input_path}")
        
        # Summary
        end_time = datetime.now()
        self.logger.info(f"Total time: {end_time - start_time}")
        self.generate_summary_log()

def main():
    """Main entry point"""
    try:
        processor = Phase3ProcessorUltraOptimized()
        processor.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())