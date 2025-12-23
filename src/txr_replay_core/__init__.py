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
from .utils import DateParser, CharacterReplacement, FileDiscovery

__all__ = [
    "ReplayRecord",
    "LookupResult",
    "UnaVistaTransaction",
    "ProcessingStats",
    "DateParser",
    "CharacterReplacement",
    "FileDiscovery",
]
