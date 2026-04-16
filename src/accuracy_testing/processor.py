"""
ID Validation Processor
=======================

Core processing logic for buyer and seller ID validation workflows.
Implements the validation pipeline using Phase 1 core library.

This module provides:
- Record validation using country codes and ID formats
- Correction generation for invalid IDs
- CONCAT generation from client data
- Processing statistics and reporting
- Configuration management for accuracy testing
- Italian tracker logic for fiscal code validation
- Joint account aggregation for JNT accounts
- Kaizen error lookup validation

Version: 3.0 - Independent configuration management
"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from datetime import date, datetime
from pathlib import Path
import csv
from collections import defaultdict
from copy import deepcopy

from .core import (
    country_manager,
    id_format_manager,
    validate_id,
    validate_id_auto,
    validate_date_format,
    validate_not_empty,
    IDType,
)

# Import structured logger from core
try:
    from core import StructuredLogger
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    StructuredLogger = None

# Import ID logic validator
from .id_logic_validator import IDLogicValidator


# ============================================================================
# Configuration Classes (Independent from Replay)
# ============================================================================

@dataclass
class AccuracyPathConfig:
    """
    Path configuration for accuracy testing scripts.
    
    Attributes:
        input_file: Path to input CSV file
        output_file: Path to output CSV file
        log_output: Directory for log files
        italian_tracker: Path to Italian tracker Excel file (optional)
        main_tracker: Path to main tracker Excel file (optional)
        template_file: Path to template Excel file for Kaizen lookup (optional)
        template_id_column: Column name for expected ID in template (default: auto-detect based on client_type)
        template_type_column: Column name for expected type in template (default: auto-detect based on client_type)
    """
    input_file: str
    output_file: str
    log_output: str = "logs"
    italian_tracker: str = ""
    main_tracker: str = ""
    template_file: str = ""
    template_id_column: str = ""
    template_type_column: str = ""


@dataclass
class AccuracyProcessorConfig:
    """
    Processor configuration for accuracy testing scripts.
    
    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        verbose: Enable verbose console output
        batch_size: Batch size for processing (future use)
    """
    log_level: str = "INFO"
    verbose: bool = False
    batch_size: int = 1000


class AccuracyConfigManager:
    """Configuration manager for accuracy testing scripts."""
    
    @staticmethod
    def load_from_yaml(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
        """
        config_path_obj = Path(config_path)
        
        if not config_path_obj.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path_obj, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            raise ValueError(f"Empty or invalid configuration file: {config_path}")
        
        return config
    
    @staticmethod
    def load_from_env(prefix: str = "TXR_ACCURACY_") -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Environment variables:
            TXR_ACCURACY_PATHS_INPUT_FILE: Input CSV file path
            TXR_ACCURACY_PATHS_OUTPUT_FILE: Output CSV file path
            TXR_ACCURACY_PATHS_LOG_OUTPUT: Log directory
            TXR_ACCURACY_PROCESSOR_LOG_LEVEL: Logging level
            TXR_ACCURACY_PROCESSOR_VERBOSE: Verbose output (true/false)
            TXR_ACCURACY_PROCESSOR_BATCH_SIZE: Batch size
        
        Args:
            prefix: Environment variable prefix (default: TXR_ACCURACY_)
            
        Returns:
            Configuration dictionary
            
        Raises:
            ValueError: If required environment variables are missing
        """
        config = {
            'paths': {},
            'processor': {}
        }
        
        # Required paths
        input_file = os.getenv(f"{prefix}PATHS_INPUT_FILE")
        output_file = os.getenv(f"{prefix}PATHS_OUTPUT_FILE")
        
        if not input_file or not output_file:
            raise ValueError(
                f"Required environment variables not set: "
                f"{prefix}PATHS_INPUT_FILE, {prefix}PATHS_OUTPUT_FILE"
            )
        
        config['paths']['input_file'] = input_file
        config['paths']['output_file'] = output_file
        config['paths']['log_output'] = os.getenv(f"{prefix}PATHS_LOG_OUTPUT", "logs")
        
        # Optional processor settings
        config['processor']['log_level'] = os.getenv(f"{prefix}PROCESSOR_LOG_LEVEL", "INFO")
        config['processor']['verbose'] = os.getenv(f"{prefix}PROCESSOR_VERBOSE", "false").lower() == "true"
        config['processor']['batch_size'] = int(os.getenv(f"{prefix}PROCESSOR_BATCH_SIZE", "1000"))
        
        return config
    
    @staticmethod
    def get_path_config(config: Dict[str, Any]) -> AccuracyPathConfig:
        """
        Extract and validate path configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            AccuracyPathConfig object
            
        Raises:
            ValueError: If required paths are missing
        """
        # Support both 'paths' (direct) and 'single.paths' (structured) formats
        # This allows backward compatibility and consistency with YAML config files
        if 'single' in config and 'paths' in config['single']:
            paths = config['single']['paths']
        else:
            paths = config.get('paths', {})
        
        required_keys = ['input_file', 'output_file']
        missing_keys = [key for key in required_keys if key not in paths]
        
        if missing_keys:
            raise ValueError(f"Missing required path configuration: {', '.join(missing_keys)}")
        
        return AccuracyPathConfig(
            input_file=paths['input_file'],
            output_file=paths['output_file'],
            log_output=paths.get('log_output', 'logs'),
            italian_tracker=paths.get('italian_tracker', ''),
            main_tracker=paths.get('main_tracker', ''),
            template_file=paths.get('template_file', ''),
            template_id_column=paths.get('template_id_column', ''),
            template_type_column=paths.get('template_type_column', '')
        )
    
    @staticmethod
    def get_processor_config(config: Dict[str, Any]) -> AccuracyProcessorConfig:
        """
        Extract processor configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            AccuracyProcessorConfig object
        """
        processor = config.get('processor', {})
        
        return AccuracyProcessorConfig(
            log_level=processor.get('log_level', 'INFO'),
            verbose=processor.get('verbose', False),
            batch_size=processor.get('batch_size', 1000)
        )


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class ClientRecord:
    """
    Client identification record from input CSV.
    Represents a single transaction's buyer or seller information.
    """
    row_index: int
    transaction_ref: str
    account_id: str
    person_code: str
    account_type: str
    id_value: str
    id_type: str
    first_name: str
    surname: str
    date_of_birth: str
    gender: str
    primary_nationality: str
    secondary_nationality: str = ""
    prefixed_nationality: str = ""  # Extracted from ID prefix (first 2 chars)
    
    # Processing results
    is_valid: bool = False
    validation_error: str = ""
    format_status: str = ""  # Format validation: Pass/Fail
    logic_status: str = ""  # Logic validation: Pass/Fail/N/A
    failure_reason: str = ""  # Specific reason for format or logic validation failure
    correction: str = ""
    correction_type: str = ""
    correction_output: str = ""  # Formatted as "ID:TYPE"
    correction_fields: str = ""  # Fields that were corrected (e.g., "ID:IDT")
    tracker_status: str = ""  # Tracker system status
    actions_taken: List[str] = field(default_factory=list)
    
    # Kaizen template validation fields
    error: str = ""  # "Y" if mismatch, "N" if match
    kaizen_error: str = ""  # Template lookup result (ID:TYPE)
    match: str = ""  # "TRUE" if correction matches template, "FALSE" if not
    
    # Inconsistent ID validation fields (Phase 4)
    trade_date_time_raw: str = ""  # Raw Trade_Date_Time string from CSV
    trade_date_time_parsed: Optional[datetime] = None  # Parsed datetime for sorting
    is_fallback_id: bool = False  # True if ID matches CountryCode_PersonCode pattern
    is_valid_id: bool = False  # True if ID passes format + logic validation
    requires_standard_validation: bool = True  # False if corrected by inconsistent ID logic
    correction_source: str = ""  # Description of where correction came from
    priority_country_code: str = ""  # Computed ISO-2 country code for validation
    
    # Original row data for output
    original_row: List[str] = field(default_factory=list)


@dataclass
class ProcessingStats:
    """Statistics for a validation run with detailed error tracking."""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    invalid_format: int = 0
    invalid_logic: int = 0
    corrected_records: int = 0
    concat_generated: int = 0
    no_correction_possible: int = 0
    errors: int = 0
    jnt_aggregated: int = 0
    
    def __init__(self):
        """Initialize stats with error tracking dictionaries."""
        self.total_records = 0
        self.valid_records = 0
        self.invalid_records = 0
        self.invalid_format = 0
        self.invalid_logic = 0
        self.corrected_records = 0
        self.concat_generated = 0
        self.no_correction_possible = 0
        self.errors = 0
        self.jnt_aggregated = 0
        
        # Detailed error tracking
        self.errors_by_country = defaultdict(int)  # Country code -> count
        self.errors_by_type = defaultdict(int)  # ID type -> count
        self.errors_by_reason = defaultdict(int)  # Failure reason -> count
        self.italian_tracker_actions = defaultdict(int)  # Tracker action -> count
    
    def track_error(self, country_code: str, id_type: str, reason: str):
        """Track detailed error information."""
        if country_code:
            self.errors_by_country[country_code] += 1
        if id_type:
            self.errors_by_type[id_type] += 1
        if reason:
            self.errors_by_reason[reason] += 1
    
    def track_italian_action(self, action: str):
        """Track Italian tracker actions."""
        if action and "Checked Tracker" in action:
            self.italian_tracker_actions[action] += 1
    
    def print_summary(self, logger=None):
        """
        Print processing summary to logger or console.
        
        Args:
            logger: Optional StructuredLogger instance
        """
        if logger and LOGGER_AVAILABLE:
            logger.info("=" * 70)
            logger.info("PROCESSING SUMMARY")
            logger.info("=" * 70)
            logger.info(f"Total records processed:     {self.total_records:>6}")
            logger.info(f"Valid records (no changes):  {self.valid_records:>6}")
            logger.info(f"Invalid records found:       {self.invalid_records:>6}")
            logger.info(f"  - Invalid format:          {self.invalid_format:>6}")
            logger.info(f"  - Invalid logic:           {self.invalid_logic:>6}")
            logger.info(f"Records corrected:           {self.corrected_records:>6}")
            logger.info(f"CONCAT IDs generated:        {self.concat_generated:>6}")
            logger.info(f"No correction possible:      {self.no_correction_possible:>6}")
            logger.info(f"JNT accounts aggregated:     {self.jnt_aggregated:>6}")
            logger.info(f"Processing errors:           {self.errors:>6}")
            logger.info("=" * 70)
            
            # Print detailed error breakdown
            if self.errors_by_country:
                logger.info("\nERRORS BY COUNTRY:")
                for country, count in sorted(self.errors_by_country.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"  {country}: {count}")
            
            if self.errors_by_type:
                logger.info("\nERRORS BY ID TYPE:")
                for id_type, count in sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"  {id_type}: {count}")
            
            if self.italian_tracker_actions:
                logger.info("\nITALIAN TRACKER ACTIONS:")
                for action, count in sorted(self.italian_tracker_actions.items()):
                    logger.info(f"  {action}: {count}")
        else:
            # Fallback to print
            print(f"\n{'='*70}")
            print(f"PROCESSING SUMMARY")
            print(f"{'='*70}")
            print(f"Total records processed:     {self.total_records:>6}")
            print(f"Valid records (no changes):  {self.valid_records:>6}")
            print(f"Invalid records found:       {self.invalid_records:>6}")
            print(f"  - Invalid format:          {self.invalid_format:>6}")
            print(f"  - Invalid logic:           {self.invalid_logic:>6}")
            print(f"Records corrected:           {self.corrected_records:>6}")
            print(f"CONCAT IDs generated:        {self.concat_generated:>6}")
            print(f"No correction possible:      {self.no_correction_possible:>6}")
            print(f"Processing errors:           {self.errors:>6}")
            print(f"{'='*70}\n")
            
            # Print detailed error breakdown
            if self.errors_by_country:
                print("\nERRORS BY COUNTRY:")
                for country, count in sorted(self.errors_by_country.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {country}: {count}")
            
            if self.errors_by_type:
                print("\nERRORS BY ID TYPE:")
                for id_type, count in sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True):
                    print(f"  {id_type}: {count}")
            
            if self.italian_tracker_actions:
                print("\nITALIAN TRACKER ACTIONS:")
                for action, count in sorted(self.italian_tracker_actions.items()):
                    print(f"  {action}: {count}")


# ============================================================================
# Inconsistent ID Processor (Phase 4)
# ============================================================================


@dataclass
class InconsistentIDStats:
    """Statistics for inconsistent ID validation run."""
    total_records: int = 0
    person_groups: int = 0
    inconsistent_groups: int = 0
    fallback_ids_found: int = 0
    invalid_ids_found: int = 0
    corrected_to_most_recent: int = 0  # Invalid/fallback IDs corrected to most recent valid
    valid_standardized: int = 0  # Valid but different IDs corrected to most recent valid
    no_valid_in_group: int = 0  # No valid ID found, needs standard correction
    already_most_recent: int = 0  # Already matches most recent valid, no change


class InconsistentIDProcessor:
    """
    Pre-processor for inconsistent ID validation (incident codes 7_66, 16_20).
    
    Handles:
    - Grouping records by Person Code
    - Chronological sorting by Trade_Date_Time
    - Detection of fallback ID patterns
    - Standardization of IDs within (ID Type, Nationality Prefix) groups
    - Application of corrections from most recent valid ID
    
    New behavior (v1.4, 2026-02-11):
    - Corrects ALL IDs (including valid ones) to most recent valid within each group
    - Only IDs matching the most recent valid ID value are left unchanged
    - Previous versions only corrected invalid IDs to closest valid
    
    Algorithm:
    1. Parse Trade_Date_Time and compute priority country codes
    2. Group records by Person Code
    3. Sort each group chronologically
    4. Validate each ID (format + logic validation)
    5. Detect fallback ID patterns
    6. Within each (ID Type, Nationality Prefix) group:
       - Find the MOST RECENT (latest datetime) VALID ID
       - Correct ALL records with different ID values to most recent valid
       - This includes both INVALID and VALID-but-different IDs
    7. If no valid ID in group, mark all for standard correction pipeline
    
    IMPORTANT: This is a PRE-PROCESSOR, not a replacement for IDValidationProcessor.
    After preprocessing, records that still need correction go through standard validation.
    
    Usage:
        inconsistent = InconsistentIDProcessor(logger=logger)
        records = inconsistent.preprocess_for_inconsistent_validation(
            records, 
            id_processor  # For format/logic validation
        )
        
        # Then standard validation for remaining
        for record in records:
            if record.requires_standard_validation:
                processor.validate_record(record)
    """
    
    def __init__(self, client_type: str = "buyer", logger=None, verbose: bool = False):
        """
        Initialize inconsistent ID processor.
        
        Args:
            client_type: Either "buyer" or "seller"
            logger: Optional StructuredLogger instance
            verbose: Enable verbose output
        """
        self.client_type = client_type.lower()
        self.logger = logger
        self.verbose = verbose
        self.stats = InconsistentIDStats()
    
    def _log(self, message: str, level: str = "info"):
        """Log message using logger or print if verbose."""
        if self.logger and LOGGER_AVAILABLE:
            getattr(self.logger, level)(message)
        elif self.verbose:
            print(f"[{level.upper()}] {message}")
    
    @staticmethod
    def parse_trade_date_time(raw_string: str) -> Optional[datetime]:
        """
        Parse Trade_Date_Time format: YYYY-MM-DD-HH-MM-SS-MSMS
        
        Args:
            raw_string: String like "2024-03-15-14-30-45-123456"
        
        Returns:
            datetime object or None if parsing fails
        
        Examples:
            >>> InconsistentIDProcessor.parse_trade_date_time("2024-03-15-14-30-45-123456")
            datetime(2024, 3, 15, 14, 30, 45)
        """
        if not raw_string:
            return None
        
        clean = str(raw_string).strip()
        
        # Minimum length check (YYYY-MM-DD-HH-MM-SS = 19 chars)
        if len(clean) < 19:
            return None
        
        try:
            # Extract components by position
            year = int(clean[0:4])
            month = int(clean[5:7])
            day = int(clean[8:10])
            hour = int(clean[11:13])
            minute = int(clean[14:16])
            second = int(clean[17:19])
            
            return datetime(year, month, day, hour, minute, second)
        except (ValueError, IndexError):
            return None
    
    @staticmethod
    def is_fallback_id_pattern(id_value: str, person_code: str, country_code: str) -> bool:
        """
        Check if ID matches the fallback pattern: CountryCode_PersonCode
        
        This method validates that:
        1. The ID has the pattern CC_PersonCode where CC is a 2-letter country code
        2. The country code matches the expected country_code argument
        3. The PersonCode matches the expected person_code argument
        
        Args:
            id_value: The ID to check
            person_code: The person code for this record
            country_code: ISO-2 country code (expected nationality)
        
        Returns:
            True if ID matches fallback pattern AND is correct for this client
            
        Examples:
            >>> InconsistentIDProcessor.is_fallback_id_pattern("GB_12345", "12345", "GB")
            True
            >>> InconsistentIDProcessor.is_fallback_id_pattern("FR_12345", "12345", "GB")
            False  # Country code mismatch
            >>> InconsistentIDProcessor.is_fallback_id_pattern("AB123456C", "12345", "GB")
            False  # Not fallback pattern
        """
        if not id_value or not person_code or not country_code:
            return False
        
        clean_id = str(id_value).strip().upper()
        clean_pc = str(person_code).strip()
        clean_cc = str(country_code).strip().upper()
        
        if len(clean_cc) == 2 and clean_pc:
            expected = f"{clean_cc}_{clean_pc}"
            return clean_id == expected
        
        return False
    
    @staticmethod
    def supports_concat(country_code: str) -> bool:
        """
        Check if a country supports CONCAT as an ID type.
        
        Args:
            country_code: ISO-2 country code
        
        Returns:
            True if country has CONCAT patterns defined, False otherwise
            
        Examples:
            >>> InconsistentIDProcessor.supports_concat("GB")
            True
            >>> InconsistentIDProcessor.supports_concat("ES")
            False
        """
        if not country_code:
            return False
        
        patterns = id_format_manager.get_patterns(country_code.upper(), "CONCAT")
        return len(patterns) > 0
    
    def group_by_person_code(self, records: List[ClientRecord]) -> Dict[str, List[int]]:
        """
        Group record indices by Person Code.
        
        Args:
            records: List of ClientRecord objects
        
        Returns:
            Dictionary mapping person_code -> list of record indices
        """
        groups = defaultdict(list)
        
        for idx, record in enumerate(records):
            if record.person_code and record.person_code.strip():
                groups[record.person_code.strip()].append(idx)
        
        return dict(groups)
    
    def has_inconsistent_ids(self, records: List[ClientRecord], indices: List[int]) -> bool:
        """
        Check if a group has different IDs or ID types (accounting for prefixed nationality).
        
        Different IDs with different nationality prefixes are NOT considered inconsistent
        (person may have changed nationality). Only flag as inconsistent if IDs differ
        within the same nationality prefix.
        
        Args:
            records: Full list of records
            indices: Indices of records in this person group
        
        Returns:
            True if IDs or types differ within the group for the same nationality
        """
        if len(indices) <= 1:
            return False
        
        # Extract prefixes and group records by prefix
        prefix_groups = defaultdict(list)
        
        for idx in indices:
            record = records[idx]
            id_value = str(record.id_value).strip()
            id_type = str(record.id_type).strip()
            
            # Extract prefix (inline, before it's officially set)
            prefix = self._extract_nationality_prefix(record)
            
            # Group by prefix
            key = prefix if prefix else "NO_PREFIX"
            prefix_groups[key].append((idx, id_value, id_type, prefix))
        
        # Check for inconsistencies WITHIN each prefix group
        for prefix, group in prefix_groups.items():
            if len(group) <= 1:
                continue
            
            # Get first ID in this prefix group
            first_idx, first_id, first_type, first_prefix = group[0]
            
            # Strip prefix for comparison if present
            if first_prefix:
                first_id_stripped = first_id[len(first_prefix):] if first_id.startswith(first_prefix) else first_id
            else:
                first_id_stripped = first_id
            
            # Compare with other IDs in same prefix group
            for idx, id_value, id_type, prefix in group[1:]:
                # Strip prefix for comparison
                if prefix:
                    id_stripped = id_value[len(prefix):] if id_value.startswith(prefix) else id_value
                else:
                    id_stripped = id_value
                
                # If IDs or types differ within same prefix group, it's inconsistent
                if id_stripped != first_id_stripped or id_type != first_type:
                    return True
        
        # No inconsistencies found within any prefix group
        return False
    
    def _extract_nationality_prefix(self, record: ClientRecord) -> Optional[str]:
        """
        Extract nationality prefix from ID if present.
        
        Helper method to detect prefixes inline before prefixed_nationality is set.
        
        Args:
            record: Client record
        
        Returns:
            Two-letter country code prefix if detected, None otherwise
        """
        id_value = str(record.id_value).strip().upper()
        
        # Check if ID starts with a 2-letter country code
        if len(id_value) >= 2:
            potential_prefix = id_value[:2]
            
            # Check if prefix is a valid country code
            if potential_prefix.isalpha() and country_manager.validate_code(potential_prefix):
                # Verify it matches one of the nationalities
                nat1 = str(record.primary_nationality).strip().upper()
                nat2 = str(record.secondary_nationality).strip().upper()
                
                if potential_prefix in [nat1, nat2]:
                    return potential_prefix
        
        return None
    
    def validate_id_complete(
        self, 
        record: ClientRecord, 
        id_processor: 'IDValidationProcessor'
    ) -> Tuple[bool, bool, Optional[str]]:
        """
        Validate ID completely (format + logic) using the processor's methods.
        
        This method performs BOTH format and logic validation separately,
        matching the behavior of process_record().
        
        Args:
            record: ClientRecord to validate
            id_processor: IDValidationProcessor for validation logic
        
        Returns:
            Tuple of (format_valid, logic_valid, error_message)
        """
        # Use the processor's validation method
        # This reuses the existing v5.6 validation logic
        
        # Get priority country code
        country_code = record.priority_country_code
        if not country_code:
            country_code = id_processor._get_priority_country(record)
            record.priority_country_code = country_code
        
        if not country_code:
            return (False, False, "No valid country code found")
        
        # Step 1: Validate format
        format_valid, format_error = id_processor._validate_existing_id(
            record.id_value,
            record.id_type,
            country_code,
            first_name=record.first_name,
            surname=record.surname,
        )
        
        # Step 2: If format is valid, validate logic (DOB/gender/checksum)
        logic_valid = True
        logic_error = ""
        
        if format_valid:
            logic_valid = id_processor.id_logic_validator.validate_id_logic(
                record.id_value,
                record.id_type,
                country_code,
                record.date_of_birth,
                record.gender
            )
            if not logic_valid:
                logic_error = id_processor.id_logic_validator.last_failure_reason or "Logic validation failed"
        
        # Combine error messages
        if not format_valid:
            error_message = format_error
        elif not logic_valid:
            error_message = logic_error
        else:
            error_message = ""
        
        return (format_valid, logic_valid, error_message)
    
    def _find_most_recent_valid_id(
        self,
        records: List[ClientRecord],
        indices: List[int],
        id_type: str,
        prefix: str
    ) -> Optional[Tuple[str, str, datetime]]:
        """
        Find the most recent (latest trade_date_time) valid ID for a given ID type and prefix.
        
        Args:
            records: Full list of records
            indices: Indices of records in this person group (already sorted chronologically)
            id_type: The ID type to search for (e.g., "NIDN", "CCPT")
            prefix: The nationality prefix to match (e.g., "GB", "NL")
        
        Returns:
            Tuple of (id_value, id_type, trade_date_time) if found, None otherwise
        """
        most_recent_valid = None
        most_recent_datetime = None
        most_recent_type = None
        
        for idx in indices:
            record = records[idx]
            
            # Must match ID type, prefix, and be valid (not fallback)
            if (record.id_type == id_type and
                record.prefixed_nationality == prefix and
                record.is_valid_id and
                not record.is_fallback_id):
                
                # Compare datetimes to find most recent
                if most_recent_datetime is None or (
                    record.trade_date_time_parsed and 
                    record.trade_date_time_parsed > most_recent_datetime
                ):
                    most_recent_valid = record.id_value
                    most_recent_type = record.id_type
                    most_recent_datetime = record.trade_date_time_parsed
        
        if most_recent_valid:
            return (most_recent_valid, most_recent_type, most_recent_datetime)
        return None
    
    def apply_prior_valid_corrections(
        self, 
        records: List[ClientRecord], 
        indices: List[int]
    ) -> None:
        """
        Apply correction logic to standardize IDs within groups:
        - Group records by (ID Type, Nationality Prefix)
        - Find the MOST RECENT (latest datetime) VALID ID for each group
        - Correct ALL records with DIFFERENT ID values to the most recent valid one
        - This includes both INVALID and VALID IDs with different values
        - If no valid ID exists in group, mark all for standard correction
        
        New behavior (2026-02-11):
        - Valid IDs that differ from most recent valid are now corrected
        - Only IDs matching the most recent valid ID value are left unchanged
        
        Args:
            records: Full list of records
            indices: Indices of records in this person group (already sorted chronologically)
        """
        # Group records by (ID Type, Nationality Prefix)
        id_type_groups = defaultdict(list)
        
        for idx in indices:
            record = records[idx]
            
            # Skip records without ID type
            if not record.id_type:
                record.requires_standard_validation = True
                continue
            
            # Group by ID type and prefix nationality
            prefix = record.prefixed_nationality or ""
            group_key = (record.id_type, prefix)
            id_type_groups[group_key].append(idx)
        
        # Process each ID type + prefix group
        for (id_type, prefix), group_indices in id_type_groups.items():
            # Find the most recent valid ID for this group
            most_recent_valid = self._find_most_recent_valid_id(
                records, group_indices, id_type, prefix
            )
            
            if not most_recent_valid:
                # No valid ID found in this group - mark all for standard correction
                # BUT preserve failure_reason from validation so it appears in output
                for idx in group_indices:
                    record = records[idx]
                    record.requires_standard_validation = True
                    if prefix:
                        record.correction_source = f"No valid {id_type} with prefix {prefix} - will use CONCAT"
                        record.actions_taken.append(f"Inconsistent ID - No valid {id_type} with prefix {prefix}, using CONCAT")
                    else:
                        record.correction_source = f"No valid {id_type} found - requires standard correction"
                        record.actions_taken.append(f"Inconsistent ID - No valid {id_type}, using standard correction")
                    self.stats.no_valid_in_group += 1
                    # Note: failure_reason is preserved from validation phase above
                    
                self._log(f"ID Type {id_type} (prefix: {prefix}): No valid ID found, marking {len(group_indices)} records for standard correction")
                continue
            
            # Unpack most recent valid ID details
            most_recent_id, most_recent_type, most_recent_datetime = most_recent_valid
            
            # Apply corrections to ALL records where ID differs from most recent valid
            for idx in group_indices:
                record = records[idx]
                
                # Check if this record's ID matches the most recent valid
                if record.id_value == most_recent_id:
                    # Already matches most recent valid - no correction needed
                    record.requires_standard_validation = False
                    record.correction_source = f"Already matches most recent valid {id_type} (prefix: {prefix})"
                    if record.is_valid_id and not record.is_fallback_id:
                        record.actions_taken.append(f"Pass - Most recent valid {id_type}")
                    # If this record is invalid, preserve its failure_reason for output
                    # (failure_reason was already set during validation phase)
                    self.stats.already_most_recent += 1
                    
                    self._log(f"Record {record.row_index}: Already matches most recent valid {id_type}: {most_recent_id}")
                else:
                    # ID differs from most recent valid - apply correction
                    was_valid = record.is_valid_id and not record.is_fallback_id
                    
                    record.correction = most_recent_id
                    record.correction_type = most_recent_type
                    record.correction_output = f"{most_recent_id}:{most_recent_type}"
                    record.correction_fields = "ID:IDT"
                    record.requires_standard_validation = False
                    record.correction_source = f"Most recent valid {id_type} (prefix: {prefix}) from {most_recent_datetime}"
                    record.is_valid = False  # Mark as corrected
                    # Preserve failure_reason from validation phase (already set above)
                    
                    if was_valid:
                        # Valid but different ID - standardizing to most recent
                        record.actions_taken.append(f"Inconsistent ID - Valid {id_type} standardized to most recent: {most_recent_id}")
                        self.stats.valid_standardized += 1
                        self._log(f"Record {record.row_index}: Standardized valid {id_type} '{record.id_value}' to most recent: {most_recent_id}")
                    else:
                        # Invalid or fallback ID - correcting to most recent
                        record.actions_taken.append(f"Inconsistent ID - Corrected to most recent valid {id_type} (prefix: {prefix})")
                        self.stats.corrected_to_most_recent += 1
                        self._log(f"Record {record.row_index}: Corrected invalid {id_type} to most recent: {most_recent_id}")
    
    def preprocess_for_inconsistent_validation(
        self,
        records: List[ClientRecord],
        id_processor: 'IDValidationProcessor'
    ) -> List[ClientRecord]:
        """
        Apply inconsistent ID preprocessing to records.
        
        This method:
        1. Parses Trade_Date_Time fields
        2. Computes priority country codes
        3. Groups records by Person Code
        4. Sorts each group chronologically
        5. Validates each ID (format + logic)
        6. Detects fallback ID patterns
        7. Applies corrections from most recent valid ID
        
        Records that receive corrections will have:
        - requires_standard_validation = False
        - correction, correction_type, correction_output set
        
        Records without prior valid ID will have:
        - requires_standard_validation = True
        
        Args:
            records: List of ClientRecord objects to preprocess
            id_processor: IDValidationProcessor instance for format/logic validation
        
        Returns:
            Same list of records, modified in place
        """
        self._log(f"Starting inconsistent ID preprocessing for {len(records)} records")
        self.stats.total_records = len(records)
        
        # Phase 1: Parse Trade_Date_Time and compute priority country
        self._log("Phase 1: Parsing Trade_Date_Time fields...")
        for record in records:
            if record.trade_date_time_raw:
                record.trade_date_time_parsed = self.parse_trade_date_time(
                    record.trade_date_time_raw
                )
            
            # Compute priority country code
            if not record.priority_country_code:
                record.priority_country_code = id_processor._get_priority_country(record)
        
        # Phase 2: Group by Person Code
        self._log("Phase 2: Grouping records by Person Code...")
        person_groups = self.group_by_person_code(records)
        self.stats.person_groups = len(person_groups)
        self._log(f"Found {len(person_groups)} unique Person Codes")
        
        # Phase 3: Process each person group
        self._log("Phase 3: Processing person groups for inconsistencies...")
        for person_code, record_indices in person_groups.items():
            # Skip single-record groups
            if len(record_indices) <= 1:
                # Single record - mark for standard validation
                records[record_indices[0]].requires_standard_validation = True
                continue
            
            # Sort indices by trade_date_time (chronological order)
            record_indices.sort(
                key=lambda idx: records[idx].trade_date_time_parsed or datetime.min
            )
            
            # Check if IDs differ within this group
            if not self.has_inconsistent_ids(records, record_indices):
                # All IDs identical - mark for standard validation (no inconsistency)
                for idx in record_indices:
                    records[idx].requires_standard_validation = True
                continue
            
            self.stats.inconsistent_groups += 1
            self._log(f"Person {person_code}: Found {len(record_indices)} records with inconsistent IDs")
            
            # Phase 4: Validate each ID in the group
            for idx in record_indices:
                record = records[idx]
                
                # Auto-detect CONCAT when ID type is missing
                # CONCATs are not stored in database but generated alongside transaction records
                # Check ID prefix first to determine country for CONCAT validation
                if record.id_value and not record.id_type:
                    # Try to extract prefix from ID value
                    id_prefix = extract_id_prefix(record.id_value, "CONCAT")
                    if id_prefix:
                        # First try specific pattern validation for EEA countries
                        is_concat = id_format_manager.validate(id_prefix, "CONCAT", record.id_value)
                        
                        # If no specific pattern exists, use generic CONCAT validation
                        # This allows detection of rest-of-world CONCATs
                        if not is_concat:
                            is_concat = is_valid_concat_format(record.id_value)
                        
                        if is_concat:
                            record.id_type = "CONCAT"
                            record.prefixed_nationality = id_prefix
                            record.actions_taken.append(f"Auto-detected ID type as CONCAT (prefix: {id_prefix})")
                            self._log(
                                f"[AUTO-DETECT] Row {record.row_index}: Detected CONCAT format "
                                f"for ID '{record.id_value}' with prefix '{id_prefix}' (type was empty)"
                            )
                
                # Check if fallback ID pattern
                record.is_fallback_id = self.is_fallback_id_pattern(
                    record.id_value,
                    record.person_code,
                    record.priority_country_code
                )
                
                if record.is_fallback_id:
                    # Fallback ID detected - verify it's correct
                    self.stats.fallback_ids_found += 1
                    # The is_fallback_id_pattern method already validates that:
                    # 1. ID matches CountryCode_PersonCode pattern
                    # 2. CountryCode matches priority_country_code
                    # 3. PersonCode matches person_code
                    # Therefore, if we reach here, the fallback ID is VALID
                    record.is_valid_id = True
                    record.format_status = "Pass"
                    record.logic_status = "N/A"
                    record.is_valid = True
                    record.actions_taken.append("Valid fallback ID")
                    self._log(
                        f"[FALLBACK] Row {record.row_index}: Valid fallback ID detected: {record.id_value}"
                    )
                else:
                    # Validate format + logic
                    format_valid, logic_valid, error_message = self.validate_id_complete(record, id_processor)
                    record.is_valid_id = format_valid and logic_valid
                    
                    # Populate Pass/Fail fields based on separate format and logic validations
                    if format_valid and logic_valid:
                        # Both pass
                        record.format_status = "Pass"
                        record.logic_status = "Pass"
                        record.is_valid = True
                        if "Pass" not in record.actions_taken:
                            record.actions_taken.append("Pass")
                        
                        # NORMALIZATION: Add century prefix to 10-digit Swedish NIDNs
                        if (record.priority_country_code == "SE" and 
                            record.id_type == "NIDN" and 
                            record.id_value):
                            # Check if ID is 10 digits (after stripping country prefix)
                            id_without_prefix = record.id_value[2:] if len(record.id_value) > 2 and record.id_value[:2].upper() == "SE" else record.id_value
                            if len(id_without_prefix) == 10 and id_without_prefix.isdigit():
                                # Extract century from DOB
                                if record.date_of_birth:
                                    try:
                                        # Parse DOB to get century
                                        from src.accuracy_testing.core.validators import validate_date_format
                                        dob_result = validate_date_format(record.date_of_birth, "%Y-%m-%d")
                                        if not dob_result.is_valid:
                                            dob_result = validate_date_format(record.date_of_birth, "%d/%m/%Y")
                                        if not dob_result.is_valid:
                                            dob_result = validate_date_format(record.date_of_birth, "%d-%m-%Y")
                                        
                                        if dob_result.is_valid and dob_result.corrected_value:
                                            century = str(dob_result.corrected_value.year)[:2]  # "19" or "20"
                                            # Reconstruct with century: SE + CC + YYMMDDBBBC
                                            normalized_id = record.id_value[:2] + century + id_without_prefix
                                            
                                            if normalized_id != record.id_value:
                                                record.id_value = normalized_id
                                                self._log(f"Normalized SE NIDN from 10 to 12 digits: {id_without_prefix} -> {normalized_id}")
                                    except Exception as e:
                                        self._log(f"Warning: Could not normalize SE NIDN: {e}")
                    elif format_valid and not logic_valid:
                        # Format passes but logic fails
                        record.format_status = "Pass"
                        record.logic_status = "Fail"
                        record.failure_reason = error_message or f"{record.id_type} logic validation failed"
                        self.stats.invalid_ids_found += 1
                    elif not format_valid:
                        # Format fails (logic not tested)
                        record.format_status = "Fail"
                        record.logic_status = "N/A"
                        record.failure_reason = error_message or f"Invalid {record.id_type} format"
                        self.stats.invalid_ids_found += 1
                    else:
                        # Both fail (shouldn't reach here, but handle it)
                        self.stats.invalid_ids_found += 1
                        record.format_status = "Fail"
                        record.logic_status = "Fail"
                        record.failure_reason = error_message or "Validation failed"
            
            # Phase 5: Apply correction logic
            self.apply_prior_valid_corrections(records, record_indices)
        
        self._log(f"Preprocessing complete:")
        self._log(f"  - Person groups processed: {self.stats.person_groups}")
        self._log(f"  - Inconsistent groups: {self.stats.inconsistent_groups}")
        self._log(f"  - Fallback IDs found: {self.stats.fallback_ids_found}")
        self._log(f"  - Invalid IDs found: {self.stats.invalid_ids_found}")
        self._log(f"  - Invalid corrected to most recent: {self.stats.corrected_to_most_recent}")
        self._log(f"  - Valid standardized to most recent: {self.stats.valid_standardized}")
        self._log(f"  - No valid in group (need standard): {self.stats.no_valid_in_group}")
        self._log(f"  - Already most recent (no change): {self.stats.already_most_recent}")
        
        return records
    
    def print_stats(self, logger=None):
        """Print preprocessing statistics."""
        log = logger or self.logger
        
        lines = [
            "=" * 70,
            "INCONSISTENT ID PREPROCESSING SUMMARY",
            "=" * 70,
            f"Total records:                      {self.stats.total_records:>6}",
            f"Person groups:                      {self.stats.person_groups:>6}",
            f"Inconsistent groups:                {self.stats.inconsistent_groups:>6}",
            f"Fallback IDs found:                 {self.stats.fallback_ids_found:>6}",
            f"Invalid IDs found:                  {self.stats.invalid_ids_found:>6}",
            f"Invalid corrected to most recent:   {self.stats.corrected_to_most_recent:>6}",
            f"Valid standardized to most recent:  {self.stats.valid_standardized:>6}",
            f"No valid ID in group:               {self.stats.no_valid_in_group:>6}",
            f"Already most recent (no change):    {self.stats.already_most_recent:>6}",
            "=" * 70,
        ]
        
        if log and LOGGER_AVAILABLE:
            for line in lines:
                log.info(line)
        else:
            for line in lines:
                print(line)


def extract_id_prefix(id_value: str, id_type: str) -> Optional[str]:
    """
    Extract and validate the country code prefix from an ID.
    
    IDs with country prefixes: NIDN, CCPT, CONCAT
    IDs without prefixes: LEI
    
    Args:
        id_value: The identification code
        id_type: The type of ID
    
    Returns:
        ISO-2 country code if valid prefix exists, None otherwise
    
    Examples:
        >>> extract_id_prefix("NLNPPD7P215", "CCPT")
        "NL"
        >>> extract_id_prefix("GBSG500496A", "NIDN")
        "GB"
        >>> extract_id_prefix("123456789012345678", "LEI")
        None
    """
    if not id_value or id_type == 'LEI':
        return None
    
    if len(id_value) < 2:
        return None
    
    # Extract first 2 characters as potential country code
    prefix = id_value[:2].upper()
    
    # Validate it's a real country code
    country = country_manager.get_by_alpha2(prefix)
    if country:
        return prefix
    
    return None


# Generic CONCAT pattern for universal validation
# Format: 2-letter country code + 8 digits (YYYYMMDD) + 5 chars (first name) + 5 chars (last name)
GENERIC_CONCAT_PATTERN = re.compile(r'^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$')


def is_valid_concat_format(id_value: str) -> bool:
    """
    Check if an ID matches the universal CONCAT format with a valid country prefix.
    
    Uses generic CONCAT pattern validation combined with country code verification.
    This allows detection of CONCATs for countries without specific patterns in id_formats.py.
    
    Args:
        id_value: The identification code to check
    
    Returns:
        True if ID matches CONCAT format and has a valid country prefix, False otherwise
    
    Examples:
        >>> is_valid_concat_format("MU19900720SHABNIBRAH")
        True
        >>> is_valid_concat_format("BD19970130SHABIHOSSA")
        True
        >>> is_valid_concat_format("XX19900720SHABNIBRAH")  # Invalid country code
        False
        >>> is_valid_concat_format("MU1990072")
        False
    """
    if not id_value or len(id_value) != 20:
        return False
    
    # Check if matches generic CONCAT pattern
    if not GENERIC_CONCAT_PATTERN.match(id_value.upper()):
        return False
    
    # Extract and validate country code prefix
    prefix = id_value[:2].upper()
    return country_manager.validate_code(prefix)


class IDValidationProcessor:
    """
    Processes ID validation for buyer/seller identification codes.
    Uses Phase 1 core library for validation logic.
    """
    
    def __init__(self, client_type: str = "buyer", logger=None, verbose: bool = False, 
                 italian_tracker_path: str = "", main_tracker_path: str = "", template_path: str = "",
                 template_id_column: str = "", template_type_column: str = ""):
        """
        Initialize processor.
        
        Args:
            client_type: Either "buyer" or "seller"
            logger: Optional StructuredLogger instance
            verbose: Enable verbose output (fallback if no logger)
            italian_tracker_path: Path to Italian tracker Excel file (optional)
            main_tracker_path: Path to main tracker Excel file (optional)
            template_path: Path to template Excel file for Kaizen lookup (optional)
        """
        self.client_type = client_type.lower()
        self.logger = logger
        self.verbose = verbose
        self.stats = ProcessingStats()
        self.italian_tracker_path = italian_tracker_path
        self.main_tracker_path = main_tracker_path
        self.template_path = template_path
        
        # Auto-detect column names based on client type if not provided
        if not template_id_column:
            template_id_column = "Buyer identification code" if client_type == "buyer" else "Seller identification code"
        if not template_type_column:
            template_type_column = "Type of buyer identification code" if client_type == "buyer" else "Type of seller identification code"
        
        self.template_id_column = template_id_column
        self.template_type_column = template_type_column
        
        # Initialize ID logic validator
        self.id_logic_validator = IDLogicValidator(verbose=verbose)
        
        # Load tracker data if paths provided and Excel support available
        self.italian_tracker_data = {}
        self.main_tracker_data = {}
        self.template_data = {}
        
        if italian_tracker_path and Path(italian_tracker_path).exists():
            self._load_italian_tracker(italian_tracker_path)
        if main_tracker_path and Path(main_tracker_path).exists():
            self._load_main_tracker(main_tracker_path)
        if template_path and Path(template_path).exists():
            self._load_template(template_path)
    
    def process_record(self, record: ClientRecord) -> ClientRecord:
        """
        Process a single client record through validation pipeline.
        
        Pipeline:
        1. Validate existing ID against type and country
        2. If invalid, attempt correction
        3. If no valid ID, generate CONCAT
        4. Record actions and statistics
        
        Args:
            record: ClientRecord to process
            
        Returns:
            Processed ClientRecord with validation results
        """
        self.stats.total_records += 1
        
        # Auto-detect CONCAT when ID type is missing
        # CONCATs are not stored in database but generated alongside transaction records
        # Check ID prefix first to determine country for CONCAT validation
        if record.id_value and not record.id_type:
            # Try to extract prefix from ID value
            id_prefix = extract_id_prefix(record.id_value, "CONCAT")
            if id_prefix:
                # First try specific pattern validation for EEA countries
                is_concat = id_format_manager.validate(id_prefix, "CONCAT", record.id_value)
                
                # If no specific pattern exists, use generic CONCAT validation
                # This allows detection of rest-of-world CONCATs
                if not is_concat:
                    is_concat = is_valid_concat_format(record.id_value)
                
                if is_concat:
                    record.id_type = "CONCAT"
                    record.prefixed_nationality = id_prefix
                    record.actions_taken.append(f"Auto-detected ID type as CONCAT (prefix: {id_prefix})")
                    if self.verbose and self.logger:
                        self.logger.debug(
                            f"[AUTO-DETECT] Row {record.row_index}: Detected CONCAT format "
                            f"for ID '{record.id_value}' with prefix '{id_prefix}' (type was empty)"
                        )
        
        # Determine priority country for validation
        country_code = self._get_priority_country(record)
        
        if not country_code:
            record.validation_error = "No valid country code found"
            record.actions_taken.append("ERROR: Invalid nationality codes")
            self.stats.errors += 1
            # Perform template validation before early exit to ensure Error field is populated
            self._perform_template_validation(record)
            return record
        
        # Step 1: Validate existing ID
        if record.id_value and record.id_type:
            is_valid, format_error = self._validate_existing_id(
                record.id_value,
                record.id_type,
                country_code,
                first_name=record.first_name,
                surname=record.surname,
            )
            
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[VALIDATION] Row {record.row_index}: id_value='{record.id_value}', id_type='{record.id_type}', country='{country_code}', valid={is_valid}")
            
            if is_valid:
                # Additional validation: Check ID logic (DOB/gender embedded in ID)
                if self.verbose:
                    if self.logger:
                        self.logger.debug(f"[LOGIC CHECK] Row {record.row_index}: Calling logic validator with id='{record.id_value}', type='{record.id_type}', country='{country_code}', dob='{record.date_of_birth}', gender='{record.gender}'")
                
                logic_valid = self.id_logic_validator.validate_id_logic(
                    record.id_value,
                    record.id_type,
                    country_code,
                    record.date_of_birth,
                    record.gender
                )
                
                if self.verbose:
                    if self.logger:
                        self.logger.debug(f"[LOGIC CHECK] Row {record.row_index}: Logic validation result = {logic_valid}")
                
                if not logic_valid:
                    # ID format is valid but logic check failed - treat as invalid
                    record.is_valid = False
                    record.validation_error = f"{record.id_type} failed logic validation (DOB/gender mismatch)"
                    record.format_status = "Pass"
                    record.logic_status = "Fail"
                    record.failure_reason = self.id_logic_validator.last_failure_reason
                    # Don't set actions_taken yet - will be set during correction generation
                    self.stats.invalid_records += 1
                    self.stats.invalid_logic += 1
                    self.stats.track_error(country_code, record.id_type, record.failure_reason)
                else:
                    record.is_valid = True
                    record.format_status = "Pass"
                    record.logic_status = "Pass"
                    record.actions_taken.append("Pass")
                    self.stats.valid_records += 1
                    
                    # NORMALIZATION: Add century prefix to 10-digit Swedish NIDNs
                    if country_code == "SE" and record.id_type == "NIDN" and record.id_value:
                        # Check if ID is 10 digits (after stripping country prefix)
                        id_without_prefix = record.id_value[2:] if len(record.id_value) > 2 and record.id_value[:2].upper() == "SE" else record.id_value
                        if len(id_without_prefix) == 10 and id_without_prefix.isdigit():
                            # Extract century from DOB
                            if record.date_of_birth:
                                try:
                                    # Parse DOB to get century
                                    from src.accuracy_testing.core.validators import validate_date_format
                                    dob_result = validate_date_format(record.date_of_birth, "%Y-%m-%d")
                                    if not dob_result.is_valid:
                                        dob_result = validate_date_format(record.date_of_birth, "%d/%m/%Y")
                                    if not dob_result.is_valid:
                                        dob_result = validate_date_format(record.date_of_birth, "%d-%m-%Y")
                                    
                                    if dob_result.is_valid and dob_result.corrected_value:
                                        century = str(dob_result.corrected_value.year)[:2]  # "19" or "20"
                                        # Reconstruct with century: SE + CC + YYMMDDBBBC
                                        has_prefix = record.id_value[:2].upper() == "SE"
                                        if has_prefix:
                                            normalized_id = "SE" + century + id_without_prefix
                                        else:
                                            normalized_id = century + id_without_prefix
                                        
                                        if normalized_id != record.id_value:
                                            if self.verbose and self.logger:
                                                self.logger.debug(f"Normalized SE NIDN from 10 to 12 digits: {record.id_value} -> {normalized_id}")
                                            record.id_value = normalized_id
                                except Exception as e:
                                    if self.verbose and self.logger:
                                        self.logger.warning(f"Could not normalize SE NIDN: {e}")
                    
                    # Apply Italian tracker logic for valid IT records
                    self._apply_italian_tracker_logic(record, country_code)
                    
                    # Track Italian tracker actions
                    if record.actions_taken:
                        for action in record.actions_taken:
                            self.stats.track_italian_action(action)
                    
                    # Perform template validation for valid records
                    self._perform_template_validation(record)
                    
                    return record
            else:
                record.is_valid = False
                record.validation_error = f"Invalid {record.id_type} format for {country_code}"
                record.format_status = "Fail"
                record.logic_status = "N/A"
                # Use detailed error message if available, otherwise use generic message
                if format_error:
                    record.failure_reason = format_error
                else:
                    record.failure_reason = f"Invalid {record.id_type} format for {country_code}"
                record.actions_taken.append(f"INVALID: {record.id_type}")
                self.stats.invalid_records += 1
                self.stats.invalid_format += 1
                self.stats.track_error(country_code, record.id_type, record.failure_reason)
        else:
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[VALIDATION] Row {record.row_index}: Missing ID or type - id_value='{record.id_value}', id_type='{record.id_type}'")
            record.is_valid = False
            record.validation_error = "No ID provided"
            record.format_status = "Fail"
            record.logic_status = "N/A"
            record.failure_reason = "No ID provided"
            record.actions_taken.append("NO ID: Missing identification")
            self.stats.invalid_records += 1
            self.stats.invalid_format += 1
            self.stats.track_error(country_code, record.id_type or "Unknown", record.failure_reason)
        
        # Step 2: Attempt to generate correction
        correction = self._generate_correction(record, country_code)
        
        if correction:
            record.correction, record.correction_type = correction
            # Format correction output as "ID:TYPE" (matching VBA)
            record.correction_output = f"{record.correction}:{record.correction_type}"
            record.correction_fields = "ID:IDT"  # Both ID and Type corrected
            
            # Clear previous "INVALID" action since we found a correction
            record.actions_taken = [action for action in record.actions_taken if not action.startswith("INVALID:")]
            
            # Set action message based on correction type (matching VBA)
            if record.correction_type == "CONCAT":
                record.actions_taken.append("Replaced With CONCAT")
                self.stats.concat_generated += 1
            elif record.correction_type == "NIDN" and correction[0].startswith(country_code):
                # Fallback ID (CountryCode + PersonCode)
                record.actions_taken.append("Replaced With fallback")
            elif record.correction_type == record.id_type:
                # Swedish century fix or alternative type
                if country_code == "SE" and len(correction[0]) == 12:
                    record.actions_taken.append("Review - Century Added")
                else:
                    record.actions_taken.append("Valid format - ID Type updated")
            else:
                # Alternative type found
                record.actions_taken.append("Valid format - ID Type updated")
            
            self.stats.corrected_records += 1
        else:
            # Debug: Log why no correction was possible
            debug_msg = "NO CORRECTION:"
            if not record.person_code:
                debug_msg += " Missing person_code"
            else:
                debug_msg += f" All generation methods failed (person_code={record.person_code})"
            record.actions_taken.append(debug_msg)
            self.stats.no_correction_possible += 1
        
        # Step 3: Apply Italian tracker logic (if applicable)
        self._apply_italian_tracker_logic(record, country_code)
        
        # Step 4: Perform Kaizen template validation (if template loaded)
        self._perform_template_validation(record)
        
        return record
    
    def _get_priority_country(self, record: ClientRecord) -> Optional[str]:
        """
        Determine priority country code for validation.
        
        Priority rules (NEW with prefixed nationality):
        1. ID prefix (first 2 chars) if valid ISO-2 country code - HIGHEST PRIORITY
        2. If no valid prefix, fall back to Primary/Secondary nationality:
           a. EEA countries take precedence over Rest of World countries
           b. Within EEA countries, prioritize alphabetically by country code
           c. Nationality field order (primary vs secondary) is irrelevant
        """
        # PRIORITY 1: Check ID prefix first
        if record.id_value and record.id_type:
            prefix = extract_id_prefix(record.id_value, record.id_type)
            if prefix:
                # Valid prefix found - store it and use it
                record.prefixed_nationality = prefix
                return prefix
        
        # PRIORITY 2: Fall back to nationality fields
        countries = []
        
        # Collect both nationalities
        if record.primary_nationality:
            country = country_manager.get_by_alpha2(record.primary_nationality)
            if not country:
                country = country_manager.get_by_alpha3(record.primary_nationality)
            if country:
                countries.append(country)
        
        if record.secondary_nationality:
            country = country_manager.get_by_alpha2(record.secondary_nationality)
            if not country:
                country = country_manager.get_by_alpha3(record.secondary_nationality)
            if country:
                countries.append(country)
        
        if not countries:
            return None
        
        # Separate EEA and non-EEA countries
        eea_countries = [c for c in countries if c.is_eea]
        non_eea_countries = [c for c in countries if not c.is_eea]
        
        # Prioritize EEA countries, then alphabetically
        if eea_countries:
            # Sort EEA countries alphabetically by alpha2 code
            eea_countries.sort(key=lambda c: c.alpha2)
            return eea_countries[0].alpha2
        elif non_eea_countries:
            # If only non-EEA countries, sort alphabetically
            non_eea_countries.sort(key=lambda c: c.alpha2)
            return non_eea_countries[0].alpha2
        
        return None
    
    def _validate_existing_id(
        self,
        id_value: str,
        id_type: str,
        country_code: str,
        first_name: str = "",
        surname: str = "",
    ) -> Tuple[bool, str]:
        """
        Validate an ID against its declared type and country-specific patterns.
        Strips country code prefix from NIDN/CCPT codes (stored in DB)
        before validation against patterns.
        CONCAT IDs keep their prefix as it's part of the format.

        For CONCAT IDs: after the structural regex passes, an additional semantic
        cross-check compares the embedded first-name and surname segments against
        the supplied ``first_name`` / ``surname`` values (using the same
        ``_clean_name_for_concat()`` logic as ``_generate_concat()``).
        The check is skipped (and the structural result accepted) when either name
        field is absent, preserving backward-compatibility for callers that do not
        supply name arguments.

        Args:
            id_value: The ID string to validate.
            id_type: The declared ID type (e.g. "CONCAT", "NIDN").
            country_code: ISO-2 country code.
            first_name: Optional first name from the client record.
            surname: Optional surname from the client record.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not id_value or not id_type:
            return (False, "Missing ID value or type")

        # Normalize ID type
        id_type_upper = id_type.upper().strip()

        # Rest of World passports: no format patterns are defined for non-EEA countries,
        # but a declared CCPT from a ROW client is assumed to be correct as-is.
        if id_type_upper == "CCPT" and not country_manager.is_eea(country_code):
            return (True, "")

        # Strip country code prefix if applicable
        # Only NIDN and CCPT have prefixes that need stripping (not CONCAT or LEI)
        # CONCAT format INCLUDES the prefix: ^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$
        id_to_validate = id_value

        if id_type_upper in ['NIDN', 'CCPT']:
            # Check if first 2 chars are a valid country code
            prefix = extract_id_prefix(id_value, id_type_upper)
            if prefix:
                # Valid prefix found - strip it for validation
                id_to_validate = id_value[2:] if len(id_value) > 2 else id_value
            # else: No valid prefix or too short - validate full ID
        # else: CONCAT, LEI or other type - validate full ID including prefix

        # Validate using Phase 1 library
        result = validate_id(country_code, id_type_upper, id_to_validate)

        # Extract detailed error message if validation failed
        error_message = ""
        if not result.is_valid and result.errors:
            error_message = result.errors[0]  # Use first error message

        if not result.is_valid:
            return (False, error_message)

        # For CONCAT IDs: perform a semantic cross-check of the embedded name segments
        # against the record's first_name / surname to catch prefix-in-segment errors
        # (e.g. surname "VAN SMITH" generating segment "VANSM" instead of "SMITH").
        if id_type_upper == "CONCAT":
            seg_valid, seg_error = self._validate_concat_name_segments(
                id_value, first_name, surname
            )
            if not seg_valid:
                return (False, seg_error)

        return (True, "")

    def _validate_concat_name_segments(
        self,
        id_value: str,
        first_name: str,
        surname: str,
    ) -> Tuple[bool, str]:
        """
        Cross-check the first-name and surname segments embedded in a CONCAT ID
        against the cleaned forms derived from the supplied name fields.

        The CONCAT format is: CC(2) + YYYYMMDD(8) + FirstName(5) + Surname(5)
        So positions [10:15] hold the first-name segment and [15:20] the surname.

        The expected segments are computed via ``_clean_name_for_concat()``, which
        strips name prefixes (VON, VAN, DE, …) and pads/truncates to 5 characters —
        the same logic used when generating a CONCAT.

        If either ``first_name`` or ``surname`` is empty the check is skipped and
        ``(True, "")`` is returned, as there is nothing to compare against.

        Args:
            id_value: The 20-character CONCAT ID string (already regex-validated).
            first_name: First name from the client record.
            surname: Surname from the client record.

        Returns:
            Tuple of (is_valid, error_message).  ``is_valid`` is False when a
            mismatch is detected; the error message describes which segment differs.
        """
        # Skip check if name data is unavailable
        if not first_name or not surname:
            return (True, "")

        actual_firstname_seg = id_value[10:15]
        actual_surname_seg = id_value[15:20]

        expected_firstname = self._clean_name_for_concat(first_name, is_surname=False)
        expected_surname = self._clean_name_for_concat(surname, is_surname=True)

        if actual_firstname_seg != expected_firstname:
            return (
                False,
                f"CONCAT first-name segment '{actual_firstname_seg}' does not match "
                f"expected '{expected_firstname}' (first_name='{first_name}')",
            )

        if actual_surname_seg != expected_surname:
            return (
                False,
                f"CONCAT surname segment '{actual_surname_seg}' does not match "
                f"expected '{expected_surname}' (surname='{surname}')",
            )

        return (True, "")

    @staticmethod
    def supports_concat(country_code: str) -> bool:
        """
        Check if a country supports CONCAT as an ID type.
        
        Args:
            country_code: ISO-2 country code
        
        Returns:
            True if country has CONCAT patterns defined, False otherwise
            
        Examples:
            >>> IDValidationProcessor.supports_concat("GB")
            True
            >>> IDValidationProcessor.supports_concat("ES")
            False
        """
        if not country_code:
            return False
        
        patterns = id_format_manager.get_patterns(country_code.upper(), "CONCAT")
        return len(patterns) > 0
    
    def _generate_correction(
        self, 
        record: ClientRecord, 
        country_code: str
    ) -> Optional[Tuple[str, str]]:
        """
        Generate a correction for invalid or missing ID.
        
        Following VBA logic with EEA/Rest of World distinction:
        1. Test alternative ID types in priority order (NIDN, PASSPORT, CONCAT, CCPT, PASS, DLIC)
        2. Try Swedish century fix (if SE + NIDN + 10 digits)
        3. Generate CONCAT from client data (ONLY if country supports CONCAT)
           - Skip this step if country does not have CONCAT patterns defined
           - EEA countries: CONCAT must pass format validation
           - Rest of World: CONCAT is default correction (no validation required)
        4. Generate fallback ID (CountryCode_PersonCode as NIDN)
           - Used when CONCAT is not supported or generation fails
           - Used for EEA countries if CONCAT validation fails
        
        Returns:
            Tuple of (correction_value, correction_type) or None
        """
        if self.verbose:  # DEBUG level
            if self.logger:
                self.logger.debug(f"[CORRECTION] Attempting correction for row {record.row_index}")
        
        # Step 1: Try alternative ID types if ID exists but is wrong type
        if record.id_value:
            detected_type = self._test_alternative_types(record.id_value, country_code)
            if detected_type:
                if self.verbose:
                    if self.logger:
                        self.logger.debug(f"[CORRECTION] Alternative type found: {detected_type}")
                return (record.id_value, detected_type)
        
        # Step 2: Try Swedish century fix (special case for SE + NIDN + 10 digits)
        if country_code == "SE" and record.id_value and record.id_type == "NIDN":
            if len(record.id_value) == 10 and record.date_of_birth:
                swedish_fix = self._try_swedish_century_fix(record, country_code)
                if swedish_fix:
                    return swedish_fix
        
        # Check if country is EEA/ESMA
        is_eea = country_manager.is_eea(country_code)
        
        # Check if country supports CONCAT ID type
        concat_supported = self.supports_concat(country_code)
        
        # Step 3: Try to generate CONCAT (only if supported by country)
        if concat_supported:
            concat_id = self._generate_concat(record, country_code)
            if concat_id:
                if self.verbose:
                    if self.logger:
                        self.logger.debug(f"[CORRECTION] Generated CONCAT: {concat_id}")
                
                # For EEA countries: Validate the generated CONCAT against format patterns
                # VBA: "tested against format patterns and logic validation. If both pass"
                if is_eea:
                    is_valid = id_format_manager.validate(country_code, "CONCAT", concat_id)
                    if self.verbose:
                        if self.logger:
                            self.logger.debug(f"[CORRECTION] CONCAT validation result (EEA): {is_valid}")
                    if is_valid:
                        return (concat_id, "CONCAT")
                    # If CONCAT validation fails for EEA, continue to fallback
                else:
                    # For Rest of World countries: Use CONCAT as default correction without validation
                    if self.verbose:
                        if self.logger:
                            self.logger.debug(f"[CORRECTION] Using CONCAT for Rest of World country (no validation)")
                    return (concat_id, "CONCAT")
            else:
                if self.verbose:
                    if self.logger:
                        self.logger.debug(f"[CORRECTION] CONCAT generation failed - missing data (fname={bool(record.first_name)}, sname={bool(record.surname)}, dob={bool(record.date_of_birth)})")
        else:
            # Country does not support CONCAT - skip to fallback ID
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[CORRECTION] Country {country_code} does not support CONCAT - skipping to fallback ID")
        
        # Step 4: Generate fallback ID (CountryCode + PersonCode as NIDN)
        # Used when:
        # - CONCAT generation failed (missing data)
        # - Country does not support CONCAT
        # - CONCAT validation failed (for EEA countries)
        # VBA: "No format or logic validation performed" - always return if person_code exists
        if record.person_code:
            fallback_id = country_code.upper() + record.person_code.strip()
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[CORRECTION] Generated fallback ID: {fallback_id}")
            return (fallback_id, "NIDN")
        
        if self.verbose:
            if self.logger:
                self.logger.debug(f"[CORRECTION] No correction possible - missing person_code")
        return None
    
    def _test_alternative_types(self, id_value: str, country_code: str) -> Optional[str]:
        """
        Test ID against alternative types in priority order.
        Following VBA TestAlternativeTypes logic.
        
        NOTE: CONCAT is excluded - it's a generated format (Step 3), not an
        alternative interpretation of existing data (Step 2).
        
        Priority: NIDN > PASSPORT > CCPT > PASS > DLIC
        
        Args:
            id_value: ID value to test (with country code prefix)
            country_code: Country code
            
        Returns:
            Detected ID type or None
        """
        # Strip country code prefix (first 2 characters)
        id_without_prefix = id_value[2:] if len(id_value) > 2 else id_value
        
        # Priority order from VBA documentation (CONCAT excluded per Step 2 rules)
        id_types = ["NIDN", "PASSPORT", "CCPT", "PASS", "DLIC"]
        
        for id_type in id_types:
            if id_format_manager.validate(country_code, id_type, id_without_prefix):
                return id_type
        
        return None
    
    def _try_swedish_century_fix(
        self, 
        record: ClientRecord, 
        country_code: str
    ) -> Optional[Tuple[str, str]]:
        """
        Try Swedish century fix for 10-digit NIDNs.
        Adds century prefix from date of birth.
        
        Following VBA: Extract century from DOB, prepend to original ID,
        test format AND logic validation.
        
        Args:
            record: Client record
            country_code: Country code (should be SE)
            
        Returns:
            Tuple of (corrected_id, "NIDN") or None
        """
        # Strip country code prefix from ID value
        id_without_prefix = record.id_value[2:] if len(record.id_value) > 2 else record.id_value
        
        # Parse date of birth
        dob_result = validate_date_format(record.date_of_birth, "%Y-%m-%d")
        if not dob_result.is_valid:
            dob_result = validate_date_format(record.date_of_birth, "%d/%m/%Y")
        if not dob_result.is_valid:
            return None
        
        dob = dob_result.corrected_value
        if not dob:
            return None
        
        # Extract century from DOB (e.g., 1985 -> "19")
        century = str(dob.year)[:2]
        
        # Create corrected ID by prepending century (without country code)
        corrected_id = century + id_without_prefix
        
        # Test corrected ID against format patterns AND logic validation
        # VBA: TestIDAgainstAllPatterns + ValidateIDLogic
        if id_format_manager.validate(country_code, "NIDN", corrected_id):
            # Additional logic validation would go here (DOB match, gender, check digit)
            # For now, format validation is sufficient
            # Return WITH country code prefix for output
            return (country_code.upper() + corrected_id, "NIDN")
        
        return None
    
    def _generate_concat(
        self, 
        record: ClientRecord, 
        country_code: str
    ) -> Optional[str]:
        """
        Generate CONCAT ID from client data.
        Format: CC + YYYYMMDD + FIRST5(FirstName) + FIRST5(Surname)
        
        Matches VBA BuildCONCATID logic with proper name cleaning.
        """
        # Validate required fields
        if not all([record.first_name, record.surname, record.date_of_birth]):
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[CONCAT] Missing required fields - fname={bool(record.first_name)}, sname={bool(record.surname)}, dob={bool(record.date_of_birth)}")
            return None
        
        # Parse date of birth - try multiple formats
        dob_result = validate_date_format(record.date_of_birth, "%Y-%m-%d")
        if not dob_result.is_valid:
            # Try DD/MM/YYYY format
            dob_result = validate_date_format(record.date_of_birth, "%d/%m/%Y")
        if not dob_result.is_valid:
            # Try DD-MM-YYYY format
            dob_result = validate_date_format(record.date_of_birth, "%d-%m-%Y")
        if not dob_result.is_valid:
            # Try DD/MM/YY format (2-digit year)
            dob_result = validate_date_format(record.date_of_birth, "%d/%m/%y")
        if not dob_result.is_valid:
            # Try DD-MM-YY format (2-digit year)
            dob_result = validate_date_format(record.date_of_birth, "%d-%m-%y")
        if not dob_result.is_valid:
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[CONCAT] Date parsing failed for: '{record.date_of_birth}'")
            return None
        
        dob = dob_result.corrected_value
        if not dob:
            if self.verbose:
                if self.logger:
                    self.logger.debug(f"[CONCAT] Date conversion returned None")
            return None
        
        # Clean names using VBA logic
        clean_first_name = self._clean_name_for_concat(record.first_name, is_surname=False)
        clean_surname = self._clean_name_for_concat(record.surname, is_surname=True)
        
        # Build CONCAT: CC + YYYYMMDD + FIRST5FNAME + FIRST5SNAME
        # Following VBA: FORMAT(client.DateOfBirth, "yyyymmdd")
        concat_parts = [
            country_code.upper(),
            dob.strftime("%Y%m%d"),  # YYYYMMDD format from VBA
            clean_first_name,
            clean_surname,
        ]
        
        concat_id = ''.join(concat_parts)
        return concat_id
    
    def _clean_name_for_concat(self, name_value: str, is_surname: bool) -> str:
        """
        Clean name for CONCAT generation following VBA CleanNameForCONCAT logic.
        
        IMPORTANT: For surnames, ALL parts (except prefixes) should be included.
        Multi-part surnames like "ROIG-MEYN" become "ROIGMEYN" then truncated to "ROIGM".
        
        Args:
            name_value: Name to clean
            is_surname: True if surname (applies prefix removal, keeps ALL parts), 
                       False if first name (takes FIRST word only)
            
        Returns:
            5-character cleaned name padded with #
            
        Examples:
            >>> _clean_name_for_concat("ROIG-MEYN", True)   # surname
            "ROIGM"  # All parts included: ROIG-MEYN → ROIGMEYN → ROIGM
            
            >>> _clean_name_for_concat("VON SMITH", True)  # surname with prefix
            "SMITH"  # Prefix removed: VON SMITH → SMITH → SMITH
            
            >>> _clean_name_for_concat("JEAN PAUL", False)  # first name
            "JEAN#"  # Only first word: JEAN PAUL → JEAN → JEAN#
        """
        if not name_value or not name_value.strip():
            return "#####"

        cleaned_name = name_value.strip().upper()

        # Known prefix/particle words that should be stripped when they appear
        # as standalone comma-delimited parts (e.g. "MAHN,DE,AZETU" → "MAHNAZETU").
        # These are the same particles removed by _remove_name_prefixes(), expressed
        # as individual words so they can be identified wherever commas occur.
        _PREFIX_WORDS = frozenset(
            {"VON", "VAN", "DE", "DA", "DI", "MC", "MAC", "O", "DER", "LA"}
        )

        # Handle comma delimiters: treat commas as part separators, not suffix
        # markers.  Known prefix/particle words are removed from the part list so
        # that a name like "MAHN,DE,AZETU" yields "MAHN AZETU" (not just "MAHN").
        if "," in cleaned_name:
            parts = [p.strip() for p in cleaned_name.split(",") if p.strip()]
            parts = [p for p in parts if p not in _PREFIX_WORDS]
            cleaned_name = " ".join(parts)

        if is_surname:
            # Remove common surname prefixes (VON, VAN, DE, etc.)
            # IMPORTANT: After prefix removal, ALL remaining parts of the surname 
            # are kept (including parts separated by hyphens, spaces, apostrophes)
            cleaned_name = self._remove_name_prefixes(cleaned_name)
            
            # DO NOT split or truncate multi-part surnames here
            # Examples:
            #   "ROIG-MEYN" stays as "ROIG-MEYN" (not split to "ROIG")
            #   "O'BRIEN" stays as "O'BRIEN" (not split to "O")
            #   "VAN DER BERG" (after prefix removal) → "BERG"
            
        else:
            # For first names, take ONLY the first word (split on whitespace)
            # This handles cases like "JEAN PAUL" → "JEAN"
            # Note: Hyphens are NOT treated as word separators here
            # "JEAN-PAUL" is one word → "JEAN-PAUL" (hyphen removed later)
            name_parts = cleaned_name.split()
            if name_parts:
                cleaned_name = name_parts[0]
        
        # Remove ALL special characters (hyphens, apostrophes, dots, spaces)
        # This happens AFTER prefix removal and AFTER first-word extraction
        # Ensures multi-part surnames like "ROIG-MEYN" → "ROIGMEYN" (not "ROIG")
        for char in ["-", "'", ".", " "]:
            cleaned_name = cleaned_name.replace(char, "")
        
        if not cleaned_name:
            return "#####"
        
        # Take first 5 characters and pad with # if needed
        return (cleaned_name + "#####")[:5]
    
    def _remove_name_prefixes(self, surname: str) -> str:
        """
        Remove common surname prefixes (VON, VAN, DE, etc.) following VBA logic.
        
        IMPORTANT: This only removes the PREFIX, not any other parts of the surname.
        Multi-part surnames after prefix removal keep ALL remaining parts.
        
        Args:
            surname: Surname to process
            
        Returns:
            Surname with prefix removed (all other parts intact)
            
        Examples:
            >>> _remove_name_prefixes("VON SMITH")      → "SMITH"
            >>> _remove_name_prefixes("VAN DER BERG")   → "BERG"
            >>> _remove_name_prefixes("DE ROIG-MEYN")   → "ROIG-MEYN"  # All parts kept!
            >>> _remove_name_prefixes("ROIG-MEYN")      → "ROIG-MEYN"  # No prefix, unchanged
        """
        prefixes = [
            "VON DER ", "VAN DER ", "VAN DE ", "DE LA ",
            "VON ", "VAN ", "DE ", "DI ", "DA ", "MC ", "MAC ", "O "
        ]
        
        surname_upper = surname.upper().strip()
        
        # Check each prefix in order (longer prefixes first to avoid partial matches)
        for prefix in prefixes:
            if surname_upper.startswith(prefix):
                # Remove ONLY the prefix, keep all remaining parts
                remaining = surname_upper[len(prefix):].strip()
                return remaining
        
        # No prefix found, return surname unchanged
        return surname_upper
    
    def process_batch(
        self, 
        records: List[ClientRecord]
    ) -> List[ClientRecord]:
        """
        Process a batch of records.
        
        Args:
            records: List of ClientRecord objects
            
        Returns:
            List of processed ClientRecord objects
        """
        processed = []
        
        for record in records:
            try:
                processed_record = self.process_record(record)
                processed.append(processed_record)
            except Exception as e:
                record.validation_error = f"Processing error: {str(e)}"
                record.actions_taken.append(f"ERROR: {str(e)}")
                self.stats.errors += 1
                processed.append(record)
        
        return processed    
    # ============================================================================
    # Tracker and Template Lookup Methods
    # ============================================================================
    
    def _load_italian_tracker(self, file_path: str):
        """Load Italian tracker data from CSV file."""
        try:
            if self.logger:
                self.logger.info(f"Loading Italian tracker: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                # Italian tracker: Column C (index 2) = Person Code, Column G (index 6) = Status
                for row in reader:
                    if len(row) >= 7 and row[2]:
                        person_code = row[2].strip()
                        status = row[6].strip() if row[6] else "Not On tracker"
                        self.italian_tracker_data[person_code] = status
            
            if self.logger:
                self.logger.info(f"Loaded {len(self.italian_tracker_data)} Italian tracker records")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to load Italian tracker: {e}")
    
    def _load_main_tracker(self, file_path: str):
        """Load main tracker data from CSV file."""
        try:
            if self.logger:
                self.logger.info(f"Loading main tracker: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                # Main tracker: Column J (index 9) = Person Code, Column N (index 13) = Status
                for row in reader:
                    if len(row) >= 14 and row[9]:
                        person_code = row[9].strip()
                        status = row[13].strip() if row[13] else "Not On tracker"
                        self.main_tracker_data[person_code] = status
            
            if self.logger:
                self.logger.info(f"Loaded {len(self.main_tracker_data)} main tracker records")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to load main tracker: {e}")
    
    def _load_template(self, file_path: str):
        """Load template data from CSV file for Kaizen error lookup."""
        try:
            if self.logger:
                self.logger.info(f"Loading template file: {file_path}")
                self.logger.info(f"Using column names: ID='{self.template_id_column}', Type='{self.template_type_column}'")

            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Verify required columns exist
                if not reader.fieldnames:
                    raise ValueError("Template file has no header row")

                fieldnames: list[str] = list(reader.fieldnames)

                # Resolve column names dynamically when the configured name is absent.
                # This handles templates that use shortform headers such as
                # "Buyer ID Code" instead of "Buyer identification code".
                id_col = self._resolve_template_column(
                    self.template_id_column, fieldnames, kind="id"
                )
                type_col = self._resolve_template_column(
                    self.template_type_column, fieldnames, kind="type"
                )

                if id_col != self.template_id_column and self.logger:
                    self.logger.info(
                        f"Column '{self.template_id_column}' not found; "
                        f"resolved to '{id_col}' via keyword match."
                    )
                if type_col != self.template_type_column and self.logger:
                    self.logger.info(
                        f"Column '{self.template_type_column}' not found; "
                        f"resolved to '{type_col}' via keyword match."
                    )

                for row in reader:
                    txn_ref = row.get('Transaction Reference', '').strip()
                    if txn_ref:
                        expected_id = row.get(id_col, '').strip()
                        expected_type = row.get(type_col, '').strip()
                        # Store both ID and type for flexible formatting
                        self.template_data[txn_ref] = {
                            'id': expected_id,
                            'type': expected_type
                        }

            if self.logger:
                self.logger.info(f"Loaded {len(self.template_data)} template records")
                # Show a sample of what was loaded for debugging
                sample_count = 0
                for txn_ref, data in list(self.template_data.items())[:5]:
                    if sample_count < 3:
                        self.logger.info(f"  Sample: {txn_ref} -> id='{data['id']}', type='{data['type']}'")
                        sample_count += 1
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to load template file: {e}")

    @staticmethod
    def _resolve_template_column(
        configured: str,
        fieldnames: list[str],
        kind: str,
    ) -> str:
        """Return the best-matching column name from *fieldnames*.

        If *configured* is present exactly it is returned immediately.  Otherwise
        a case-insensitive keyword search is used to find the most appropriate
        column:

        - ``kind="id"``: prefers columns whose normalised name contains *id* or
          *identification* but does **not** contain *type*.
        - ``kind="type"``: prefers columns whose normalised name contains *type*
          and also *id* or *identification*.

        The search intentionally ignores role prefixes (``buyer``/``seller``) so
        that both ``"Buyer identification code"`` and ``"Buyer ID Code"`` resolve
        correctly regardless of which role the script uses.

        Args:
            configured: The originally configured column name.
            fieldnames: Actual column names read from the CSV header.
            kind: Either ``"id"`` or ``"type"``.

        Returns:
            The resolved column name.  Falls back to *configured* (and lets the
            caller raise) if no suitable match is found.
        """
        if configured in fieldnames:
            return configured

        lower_fields = {f.lower(): f for f in fieldnames}

        if kind == "id":
            # Match columns that contain "id" or "identification" but not "type"
            for norm, original in lower_fields.items():
                if ("identification" in norm or " id " in f" {norm} ") and "type" not in norm:
                    return original
            # Broader fallback: any column ending in " code" that isn't a type col
            for norm, original in lower_fields.items():
                if norm.endswith("code") and "type" not in norm:
                    return original

        elif kind == "type":
            # Match columns containing both "type" and ("id" or "identification")
            for norm, original in lower_fields.items():
                if "type" in norm and ("identification" in norm or " id " in f" {norm} "):
                    return original
            # Broader fallback: any "type of …" column
            for norm, original in lower_fields.items():
                if norm.startswith("type of"):
                    return original

        # No match found — return configured so the existing error path triggers
        return configured


        """
        Get tracker status for a person code.
        Checks Italian tracker first, then main tracker.
        
        Args:
            person_code: Client person code
            
        Returns:
            Tracker status or "Not On tracker"
        """
        # Check Italian tracker first (higher priority)
        if person_code in self.italian_tracker_data:
            return self.italian_tracker_data[person_code]
        
        # Check main tracker
        if person_code in self.main_tracker_data:
            return self.main_tracker_data[person_code]
        
        return "Not On tracker"
    
    def _apply_italian_tracker_logic(self, record: ClientRecord, country_code: str):
        """
        Apply Italian tracker logic for IT fiscal codes.
        
        Logic:
        - Populate tracker status for all records (for reporting)
        - For IT records that passed validation:
          - If tracker status is "Not On Tracker" or "#N/A" → Replace with fallback
          - Else if tracker status is an IT NIDN:
            - Compare with record's NIDN (ISO-2 stripped)
            - If match → "Checked Tracker - NIDN Confirmed"
            - If no match → "Checked Tracker - NIDN Updated"
        
        Args:
            record: Client record
            country_code: Country code
        """
        # Always get and populate tracker status (for all records, for reporting)
        tracker_status = self._get_tracker_status(record.person_code)
        record.tracker_status = tracker_status
        
        # Only apply Italian-specific logic for IT country code
        if country_code != "IT":
            return
        
        # Only process IT records that passed validation (not failed records)
        if not record.is_valid:
            return
        
        # Normalize tracker status
        normalized_status = tracker_status.strip()
        
        # Check if tracker status indicates "not found" (includes #N/A variants)
        if normalized_status.upper().replace("#", "").replace("/", "").replace(" ", "") in ["NA", "NOTONTRACKER"]:
            # Replace with fallback ID (no colon between ISO-2 and person code)
            fallback_id = country_code.upper() + record.person_code.strip()
            record.correction = fallback_id
            record.correction_type = "NIDN"
            record.correction_output = f"{fallback_id}:NIDN"
            record.correction_fields = "ID:IDT"
            record.actions_taken = ["Checked Tracker - Replaced With Fallback"]
            self.stats.corrected_records += 1
            return
        
        # If we have a non-empty tracker status, assume it's an IT NIDN (without ISO-2 prefix)
        if normalized_status and len(normalized_status) >= 11:  # IT NIDN is 16 chars, but be lenient
            # Prepend ISO-2 code to tracker NIDN for comparison with record ID
            tracker_nidn_with_prefix = country_code.upper() + normalized_status
            
            # Compare tracker NIDN (with prefix) with record NIDN (case-insensitive)
            if tracker_nidn_with_prefix.upper() == record.id_value.upper():
                # NIDN matches - confirmed
                record.actions_taken = ["Checked Tracker - NIDN Confirmed"]
                record.correction = ""
                record.correction_type = ""
                record.correction_output = ""
                record.correction_fields = ""
                return  # Exit early - no correction needed
            else:
                # NIDN doesn't match - update with tracker value (prepend ISO-2, no colon)
                corrected_id = tracker_nidn_with_prefix
                record.correction = corrected_id
                record.correction_type = "NIDN"
                record.correction_output = f"{corrected_id}:NIDN"
                record.correction_fields = "ID:IDT"
                record.actions_taken = ["Checked Tracker - NIDN Updated"]
                self.stats.corrected_records += 1
                return  # Exit early - correction applied
        
        # Handle case where there's a correction but country is IT
        # This covers situations where tracker might have provided a corrected NIDN
        if country_code == "IT" and record.correction and record.correction_type:
            # If we have a correction for IT client, it came from tracker or alternative validation
            if "Replaced With CONCAT" in " | ".join(record.actions_taken):
                # Keep CONCAT message as-is
                pass
            elif "Replaced With fallback" in " | ".join(record.actions_taken):
                # Change to tracker-checked fallback
                record.actions_taken = ["Checked Tracker - Replaced With Fallback"]
            elif record.correction == record.id_value:
                # Tracker lookup result matches the ID on record - confirmed
                record.actions_taken = ["Checked Tracker - NIDN Confirmed"]
            elif record.correction != record.id_value:
                # Different ID found - likely from tracker or validation
                record.actions_taken = ["Checked Tracker - NIDN Updated"]
    
    def _perform_template_validation(self, record: ClientRecord) -> None:
        """
        Perform Kaizen template validation by comparing correction output
        with expected ID values from the template.
        
        This implements the VBA's Formula1, Formula2, Formula3 logic:
        - kaizen_error (Formula2): VLOOKUP result from template (ID:TYPE format)
        - match (Formula3): TRUE if correction matches template, FALSE if not
        - error (Formula1): Y if mismatch, N if match
        
        Args:
            record: Client record
        """
        # Default values
        record.error = "N"
        record.kaizen_error = ""
        record.match = ""
        
        # Only perform validation if template is loaded
        if not self.template_data:
            if self.verbose and self.logger:
                self.logger.debug(f"[TEMPLATE] No template data loaded")
            return
        
        # Look up expected ID from template by transaction reference
        template_entry = self.template_data.get(record.transaction_ref)
        
        if self.logger and record.row_index in [2, 4, 7]:
            self.logger.info(f"[TEMPLATE] Row {record.row_index}: txn_ref='{record.transaction_ref}', found={template_entry is not None}")
        
        if template_entry:
            expected_id = template_entry.get('id', '')
            expected_type = template_entry.get('type', '')
            
            # DIAGNOSTIC: Log what we got from template
            if self.logger and record.row_index in [2, 4, 7]:
                self.logger.info(f"[TEMPLATE] Row {record.row_index} ({record.transaction_ref}): Raw template data - id='{expected_id}', type='{expected_type}'")
            
            # Build template lookup result (Formula2)
            if expected_id and expected_type:
                record.kaizen_error = f"{expected_id}:{expected_type}"
            elif expected_id:
                record.kaizen_error = f"{expected_id}:"
            elif expected_type:
                record.kaizen_error = f":{expected_type}"
            
            if self.logger and record.row_index in [2, 4, 7]:
                self.logger.info(f"[TEMPLATE] Row {record.row_index} ({record.transaction_ref}): Template found - kaizen_error='{record.kaizen_error}', correction_output='{record.correction_output}'")
        
        # Compare correction output with template lookup (Formula3)
        if record.correction_output:
            if record.kaizen_error:
                if self.logger and record.row_index in [2, 4, 7]:
                    self.logger.info(f"[TEMPLATE] Row {record.row_index} ({record.transaction_ref}): correction='{record.correction_output}' vs template='{record.kaizen_error}'")
                
                if record.correction_output == record.kaizen_error:
                    record.match = "TRUE"
                    record.error = "N"
                else:
                    record.match = "FALSE"
                    record.error = "Y"
            else:
                # No template entry found, no comparison possible
                record.match = ""
                record.error = "N"
        else:
            # No correction output, no comparison needed
            record.match = ""
            record.error = "N"
    
    @staticmethod
    def aggregate_jnt_accounts(records: List[ClientRecord]) -> List[ClientRecord]:
        """
        Aggregate joint account (JNT) records with matching transaction references.
        
        Combines JNT pairs by:
        - Grouping by transaction reference
        - Combining fields with pipe delimiter (|)
        - Keeping only the first record of each pair
        - Properly formatting correction outputs as "ID1:TYPE1|ID2:TYPE2"
        
        Args:
            records: List of client records
            
        Returns:
            List of records with JNT accounts aggregated
        """
        # Track which JNT records have been processed
        jnt_processed = set()
        jnt_by_txn = defaultdict(list)
        
        # Group JNT records by transaction reference
        for i, record in enumerate(records):
            if record.account_type.upper() == "JNT":
                jnt_by_txn[record.transaction_ref].append((i, record))
        
        # Build result list maintaining original order
        result = []
        for i, record in enumerate(records):
            if record.account_type.upper() != "JNT":
                # Non-JNT record - keep as is
                result.append(record)
            elif i in jnt_processed:
                # Already processed as part of a pair - skip
                continue
            else:
                # JNT record - check if it has a pair
                txn_jnts = jnt_by_txn[record.transaction_ref]
                if len(txn_jnts) == 1:
                    # Single JNT (no pair) - keep as is
                    result.append(record)
                    jnt_processed.add(i)
                else:
                    # Find the pair (first unprocessed JNT with same txn ref)
                    current_idx = i
                    pair_idx = None
                    for idx, rec in txn_jnts:
                        if idx != current_idx and idx not in jnt_processed:
                            pair_idx = idx
                            break
                    
                    if pair_idx is not None:
                        # Aggregate the pair - create a new record
                        rec1 = record
                        rec2 = records[pair_idx]
                        # Create a copy of rec1 to avoid modifying original
                        from copy import deepcopy
                        aggregated = deepcopy(rec1)
                        # Now aggregate rec2 into the copy
                        aggregated = IDValidationProcessor._aggregate_jnt_pair(aggregated, rec2)
                        result.append(aggregated)
                        jnt_processed.add(i)
                        jnt_processed.add(pair_idx)
                    else:
                        # No unprocessed pair found - keep as is
                        result.append(record)
                        jnt_processed.add(i)
        
        return result
    
    @staticmethod
    def _aggregate_jnt_pair(rec1: ClientRecord, rec2: ClientRecord) -> ClientRecord:
        """
        Aggregate two JNT records into a single combined record.
        
        Args:
            rec1: First JNT record (will be modified and returned)
            rec2: Second JNT record (data will be merged into rec1)
            
        Returns:
            Combined record (rec1 with rec2's data merged in)
        """
        def combine_with_pipe(val1: str, val2: str) -> str:
            """Combine two values with pipe delimiter, handling empty values."""
            s1, s2 = val1.strip(), val2.strip()
            if not s1 and not s2:
                return ""
            elif not s1:
                return s2
            elif not s2:
                return s1
            else:
                return f"{s1}|{s2}"
        
        # FIRST: Capture original ID values before aggregation (for correction output)
        orig_id1 = rec1.id_value
        orig_type1 = rec1.id_type
        orig_id2 = rec2.id_value
        orig_type2 = rec2.id_type
        
        # SECOND: Aggregate regular data fields
        rec1.person_code = combine_with_pipe(rec1.person_code, rec2.person_code)
        rec1.id_value = combine_with_pipe(rec1.id_value, rec2.id_value)
        rec1.id_type = combine_with_pipe(rec1.id_type, rec2.id_type)
        rec1.first_name = combine_with_pipe(rec1.first_name, rec2.first_name)
        rec1.surname = combine_with_pipe(rec1.surname, rec2.surname)
        rec1.date_of_birth = combine_with_pipe(rec1.date_of_birth, rec2.date_of_birth)
        rec1.gender = combine_with_pipe(rec1.gender, rec2.gender)
        rec1.primary_nationality = combine_with_pipe(rec1.primary_nationality, rec2.primary_nationality)
        rec1.secondary_nationality = combine_with_pipe(rec1.secondary_nationality, rec2.secondary_nationality)
        
        # THIRD: Build proper correction output format: ID1|ID2:TYPE1|TYPE2
        # For JNT pairs, correction_output shows the FINAL STATE (corrected or original values)
        # correction_fields always uses the same structure: ID:IDT|ID:IDT
        # IMPORTANT: Only set correction_output if at least one record has a correction
        
        # Extract ID and TYPE from individual correction (format is ID:TYPE)
        def extract_id_from_correction(correction):
            """Extract ID from 'ID:TYPE' format."""
            if not correction:
                return None
            parts = correction.split(':', 1)
            return parts[0] if parts else None
        
        def extract_type_from_correction(correction):
            """Extract TYPE from 'ID:TYPE' format."""
            if not correction:
                return None
            parts = correction.split(':', 1)
            return parts[1] if len(parts) > 1 else None
        
        # Check if either record has a correction (non-empty correction_output)
        has_correction1 = bool(rec1.correction_output and rec1.correction_output.strip())
        has_correction2 = bool(rec2.correction_output and rec2.correction_output.strip())
        
        if has_correction1 or has_correction2:
            # At least one record has a correction - build aggregated correction_output
            # Get final IDs and types (corrected if available, otherwise original)
            final_id1 = extract_id_from_correction(rec1.correction_output) or orig_id1
            final_id2 = extract_id_from_correction(rec2.correction_output) or orig_id2
            final_type1 = extract_type_from_correction(rec1.correction_output) or orig_type1
            final_type2 = extract_type_from_correction(rec2.correction_output) or orig_type2
            
            # Build correction_output showing final state of both clients
            rec1.correction_output = f"{final_id1}|{final_id2}:{final_type1}|{final_type2}"
            
            # correction_fields follows the same structure as correction_output
            # Format: ID|ID:IDT|IDT (matching the ID1|ID2:TYPE1|TYPE2 structure)
            rec1.correction_fields = "ID|ID:IDT|IDT"
        else:
            # Both records passed validation - no correction needed
            rec1.correction_output = ""
            rec1.correction_fields = ""
        
        # Aggregate tracker status and actions
        rec1.tracker_status = combine_with_pipe(rec1.tracker_status, rec2.tracker_status)
        rec1.actions_taken = [
            combine_with_pipe(
                " | ".join(rec1.actions_taken) if rec1.actions_taken else "",
                " | ".join(rec2.actions_taken) if rec2.actions_taken else ""
            )
        ]
        
        # Aggregate template validation fields
        # Template lookup happens per-record, so need to aggregate kaizen_error properly
        # Format should be: ID1|ID2:TYPE1|TYPE2 (same as correction_output)
        if rec1.kaizen_error or rec2.kaizen_error:
            # Extract IDs and types from kaizen_error (format: ID:TYPE or ID1|ID2:TYPE1|TYPE2)
            def extract_from_kaizen(kaizen_text):
                """Extract ID and TYPE from kaizen_error."""
                if not kaizen_text:
                    return None, None
                if ':' not in kaizen_text:
                    return kaizen_text, None
                parts = kaizen_text.split(':', 1)
                return parts[0], parts[1] if len(parts) > 1 else None
            
            k1_id, k1_type = extract_from_kaizen(rec1.kaizen_error)
            k2_id, k2_type = extract_from_kaizen(rec2.kaizen_error)
            
            # If both have the same value (common for JNT pairs), use it
            if rec1.kaizen_error == rec2.kaizen_error and rec1.kaizen_error:
                # Same template value - keep as is (already in correct format)
                pass
            elif k1_id and k2_id and k1_type and k2_type:
                # Both have template values - combine into ID1|ID2:TYPE1|TYPE2
                rec1.kaizen_error = f"{k1_id}|{k2_id}:{k1_type}|{k2_type}"
            elif k1_id and k1_type:
                # Only first has template value
                rec1.kaizen_error = rec1.kaizen_error
            elif k2_id and k2_type:
                # Only second has template value
                rec1.kaizen_error = rec2.kaizen_error
            else:
                # Fallback to simple pipe combination
                rec1.kaizen_error = combine_with_pipe(rec1.kaizen_error, rec2.kaizen_error)
        
        
        # For match, need order-independent comparison
        if rec1.correction_output and rec1.kaizen_error:
            # Parse both into sets for order-independent comparison
            # Correction format: ID1|ID2:TYPE1|TYPE2
            # Template format: ID1|ID2:TYPE1|TYPE2 (same)
            def parse_jnt_correction(text):
                """Parse JNT correction format 'ID1|ID2:TYPE1|TYPE2' into normalized set."""
                if not text:
                    return set()
                # Split by colon to get ID part and TYPE part
                if ':' not in text:
                    return set()
                id_part, type_part = text.split(':', 1)
                ids = [i.strip() for i in id_part.split('|') if i.strip()]
                types = [t.strip() for t in type_part.split('|') if t.strip()]
                # Create set of ID:TYPE pairs (order-independent)
                pairs = set()
                for i, (id_val, type_val) in enumerate(zip(ids, types)):
                    pairs.add(f"{id_val}:{type_val}")
                return pairs
            
            correction_set = parse_jnt_correction(rec1.correction_output)
            template_set = parse_jnt_correction(rec1.kaizen_error)
            
            if correction_set == template_set:
                rec1.match = "TRUE"
                rec1.error = "N"
            else:
                rec1.match = "FALSE"
                rec1.error = "Y"
        else:
            # Combine match values if both exist
            rec1.match = combine_with_pipe(rec1.match, rec2.match)
        
        # Error field: "Y" if either has error (unless we just recalculated it above)
        if rec1.error == "Y" or rec2.error == "Y":
            rec1.error = "Y"
        else:
            rec1.error = "N"
        
        return rec1