"""
TXR Core Library
================

Shared foundation for all TXR automation modules.
Provides common utilities, configuration, logging, reference data, and validation.

Subpackages:
    config: Unified configuration management
    data: Reference data (country codes, ID formats, incident codes, data structures)
    logging: Structured logging infrastructure
    utils: Common utilities (date parsing, CSV operations, file discovery)
    validation: Core validation functions and ID validators

Version: 1.1.0
"""

__version__ = "1.1.0"
__author__ = "Transaction Reporting Team"

# Config
from .config import ConfigManager, PathConfig, ProcessorConfig

# Data - Constants (magic number replacements)
# Data - Incident codes
# Data - ID formats
# Data - Country codes
# Data structures
from .data import (
    COUNTRIES,
    FI_CENTURY_MARKERS,
    ID_LENGTHS,
    ID_PATTERNS,
    INCIDENT_CODE_MATRIX,
    IT_MONTH_LETTERS,
    LT_CENTURY_GENDER_CODES,
    LV_CENTURY_CODES,
    ClientErrorColumns,
    Country,
    CountryDataManager,
    IDFormatManager,
    IDPattern,
    IncidentMetadata,
    LookupResult,
    Phase2CombinedColumns,
    Phase2SingleColumns,
    Phase3Columns,
    ProcessingStats,
    ReplayRecord,
    UnaVistaTransaction,
    ValidationThresholds,
    country_manager,
    get_all_incident_codes,
    get_buyer_incident_codes,
    get_client_types,
    get_incident_description,
    get_inconsistent_buyer_incident_codes,
    get_inconsistent_seller_incident_codes,
    get_seller_incident_codes,
    get_validation_type,
    id_format_manager,
    is_buyer_incident,
    is_inconsistent_id_incident,
    is_seller_incident,
)

# Logging
from .logging import StatsProtocol, StructuredLogger, create_logger

# Progress tracking
from .progress import ProgressTracker

# Utils
from .utils import CharacterReplacement, DateParser, FileDiscovery, safe_open_csv

__all__ = [
    # Logging
    "StructuredLogger",
    "StatsProtocol",
    "create_logger",
    # Utils
    "DateParser",
    "CharacterReplacement",
    "FileDiscovery",
    "safe_open_csv",
    # Config
    "ConfigManager",
    "PathConfig",
    "ProcessorConfig",
    # Progress tracking
    "ProgressTracker",
    "LookupResult",
    "UnaVistaTransaction",
    "ProcessingStats",
    # Country codes
    "Country",
    "CountryDataManager",
    "country_manager",
    "COUNTRIES",
    # ID formats
    "IDPattern",
    "IDFormatManager",
    "id_format_manager",
    "ID_PATTERNS",
    # Incident codes
    "IncidentMetadata",
    "INCIDENT_CODE_MATRIX",
    "get_client_types",
    "is_buyer_incident",
    "is_seller_incident",
    "get_all_incident_codes",
    "get_buyer_incident_codes",
    "get_seller_incident_codes",
    "get_validation_type",
    "get_incident_description",
    "get_inconsistent_buyer_incident_codes",
    "get_inconsistent_seller_incident_codes",
    "is_inconsistent_id_incident",
    # Constants
    "ID_LENGTHS",
    "Phase3Columns",
    "Phase2SingleColumns",
    "Phase2CombinedColumns",
    "ClientErrorColumns",
    "ValidationThresholds",
    "IT_MONTH_LETTERS",
    "FI_CENTURY_MARKERS",
    "LT_CENTURY_GENDER_CODES",
    "LV_CENTURY_CODES",
]
