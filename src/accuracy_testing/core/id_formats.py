"""
ID Format Validation Patterns
==============================

BACKWARD COMPATIBILITY MODULE
-----------------------------
This module now re-exports from the canonical location: core.data.id_formats

All classes and data are maintained for backward compatibility.
New code should import directly from core.data:
    from core.data import id_format_manager, IDPattern, IDFormatManager, ID_PATTERNS
"""

# Try different import paths for flexibility (installed package vs development)
try:
    # When imported as installed package (accuracy_testing.core.id_formats)
    from core.data.id_formats import (
        ID_PATTERNS,
        IDFormatManager,
        IDPattern,
        id_format_manager,
    )
except ImportError:
    # When imported from workspace root (src.accuracy_testing.core.id_formats)
    from src.core.data.id_formats import (
        ID_PATTERNS,
        IDFormatManager,
        IDPattern,
        id_format_manager,
    )

__all__ = [
    "IDPattern",
    "IDFormatManager",
    "id_format_manager",
    "ID_PATTERNS",
]
