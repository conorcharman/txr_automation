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
"""

__version__ = "1.0.0"
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

__all__ = [
    "ReplayRecord",
    "LookupResult",
    "UnaVistaTransaction",
    "ProcessingStats",
    "DateParser",
    "CharacterReplacement",
    "FileDiscovery",
    "safe_open_csv",
    "ConfigManager",
    "PathConfig",
    "ProcessorConfig",
    "StructuredLogger",
    "create_logger",
    "INCIDENT_CODE_MATRIX",
    "get_client_types",
    "is_buyer_incident",
    "is_seller_incident",
    "get_all_incident_codes",
    "get_buyer_incident_codes",
    "get_seller_incident_codes",
]
