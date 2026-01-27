"""
Logging Infrastructure Module
==============================

Unified structured logging for all processing scripts.
Shared across replay and accuracy testing modules.

DEPRECATED: This module re-exports from core.logging for backward compatibility.
Please import directly from core.logging in new code:
    from core.logging import StructuredLogger, create_logger
"""

# Re-export from canonical location for backward compatibility
from core.logging import StructuredLogger, StatsProtocol, create_logger

__all__ = ['StructuredLogger', 'StatsProtocol', 'create_logger']
