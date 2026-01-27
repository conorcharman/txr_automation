"""
Common Utilities
================

Shared utility functions used across all TXR automation modules.

Classes:
    DateParser: Date parsing with caching
    CharacterReplacement: Special character handling
    FileDiscovery: Glob-based file discovery

Functions:
    safe_open_csv: Safe CSV file opening with encoding detection

This module consolidates:
- common.utils
- txr_replay_core.utils
"""

from .date_parser import DateParser
from .character_replacement import CharacterReplacement
from .file_discovery import FileDiscovery
from .csv_utils import safe_open_csv

__all__ = [
    'DateParser',
    'CharacterReplacement',
    'FileDiscovery',
    'safe_open_csv',
]
