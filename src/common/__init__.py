"""
Common Utilities Module
=======================

Shared utilities used across both replay and accuracy testing modules.

DEPRECATED: This module re-exports from core for backward compatibility.
Please import directly from core in new code:
    from core.logging import StructuredLogger, create_logger
    from core.utils import DateParser, CharacterReplacement, FileDiscovery, safe_open_csv
"""

# Re-export from canonical locations for backward compatibility
from core.logging import StructuredLogger, create_logger
from core.utils import (
    DateParser,
    CharacterReplacement,
    FileDiscovery,
    safe_open_csv
)

__all__ = [
    'StructuredLogger',
    'create_logger',
    'DateParser',
    'CharacterReplacement',
    'FileDiscovery',
    'safe_open_csv',
]
