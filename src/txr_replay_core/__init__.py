"""
TXR Replay Core Library
=======================

Shared utilities and core functionality for transaction replay processing scripts.

This package provides:
- Common data structures (dataclasses)
- Configuration management
- Logging infrastructure
- CSV schema validation
- Index management (O(1) lookups)
- Utility functions (date parsing, character replacement, etc.)
- Country code reference data (embedded)
- ID format validation patterns (embedded)
- Core validation functions
- ID-specific validation logic
"""

__version__ = "1.1.0"
__author__ = "Transaction Reporting Team"

from .data_structures import (
    ReplayRecord,
    LookupResult,
    UnaVistaTransaction,
    ProcessingStats,
)
from .utils import DateParser, CharacterReplacement, FileDiscovery, safe_open_csv
from .config import ConfigManager, PathConfig, ProcessorConfig
from .logger import StructuredLogger, create_logger
from .incident_codes import (
    INCIDENT_CODE_MATRIX,
    get_client_types,
    is_buyer_incident,
    is_seller_incident,
    get_all_incident_codes,
    get_buyer_incident_codes,
    get_seller_incident_codes,
)
from .country_codes import Country, CountryDataManager, country_manager
from .id_formats import IDPattern, IDFormatManager, id_format_manager
from .validators import ValidationResult, validate_date_format, validate_not_empty
from .id_validation import (
    IDType,
    IDValidationResult,
    IDValidator,
    id_validator,
    validate_id,
    validate_id_auto,
    validate_lei,
)
from .csv_utils import (
    ColumnType,
    ColumnDefinition,
    CSVSchema,
    CSVValidationError,
    CSVReader,
    CSVWriter,
    read_csv_with_schema,
    write_csv_with_schema,
    validate_csv_file,
)
from .schema import (
    BUYER_ID_VALIDATION_SCHEMA,
    SELLER_ID_VALIDATION_SCHEMA,
    PRICING_DATA_VALIDATION_SCHEMA,
    SCHEMA_REGISTRY,
    get_schema,
    list_schemas,
)

__all__ = [
    # Data structures
    "ReplayRecord",
    "LookupResult",
    "UnaVistaTransaction",
    "ProcessingStats",
    # Utils
    "DateParser",
    "CharacterReplacement",
    "FileDiscovery",
    "safe_open_csv",
    # Config
    "ConfigManager",
    "PathConfig",
    "ProcessorConfig",
    # Logging
    "StructuredLogger",
    "create_logger",
    # Incident codes
    "INCIDENT_CODE_MATRIX",
    "get_client_types",
    "is_buyer_incident",
    "is_seller_incident",
    "get_all_incident_codes",
    "get_buyer_incident_codes",
    "get_seller_incident_codes",
    # Country codes
    "Country",
    "CountryDataManager",
    "country_manager",
    # ID formats
    "IDPattern",
    "IDFormatManager",
    "id_format_manager",
    # Validators
    "ValidationResult",
    "validate_date_format",
    "validate_not_empty",
    # ID validation
    "IDType",
    "IDValidationResult",
    "IDValidator",
    "id_validator",
    "validate_id",
    "validate_id_auto",
    "validate_lei",
    # CSV utilities
    "ColumnType",
    "ColumnDefinition",
    "CSVSchema",
    "CSVValidationError",
    "CSVReader",
    "CSVWriter",
    "read_csv_with_schema",
    "write_csv_with_schema",
    "validate_csv_file",
    # Schemas
    "BUYER_ID_VALIDATION_SCHEMA",
    "SELLER_ID_VALIDATION_SCHEMA",
    "PRICING_DATA_VALIDATION_SCHEMA",
    "SCHEMA_REGISTRY",
    "get_schema",
    "list_schemas",
]
