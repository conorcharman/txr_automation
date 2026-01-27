"""
Logging Infrastructure Module
==============================

Unified structured logging for all replay processing scripts.

DEPRECATED: This module re-exports from core.logging for backward compatibility.
Please import directly from core.logging in new code:
    from core.logging import StructuredLogger, create_logger
"""

from .data_structures import ProcessingStats

# Re-export from canonical location for backward compatibility
from core.logging import StructuredLogger as _StructuredLogger, create_logger as _create_logger


# Backward compatibility wrapper that accepts ProcessingStats
class StructuredLogger(_StructuredLogger):
    """
    Unified structured logging for all processors.
    
    Provides consistent logging format and functionality across all scripts.
    Supports both file and console logging with structured data.
    
    Note: This is a compatibility wrapper. Use core.logging.StructuredLogger instead.
    """
    
    def __init__(self, name: str, log_dir: str, log_level: str = "INFO"):
        """
        Initialize logger.
        
        Args:
            name: Logger name (used in log messages and filename)
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        super().__init__(name, log_dir, log_level)
    
    def log_stats(self, stats: ProcessingStats) -> None:
        """
        Log statistics in structured format.
        
        Args:
            stats: ProcessingStats object to log
        """
        super().log_stats(stats)


def create_logger(name: str, log_dir: str, log_level: str = "INFO") -> StructuredLogger:
    """
    Factory function to create a StructuredLogger.
    
    Args:
        name: Logger name
        log_dir: Log directory
        log_level: Logging level
        
    Returns:
        Configured StructuredLogger instance
    """
    return StructuredLogger(name, log_dir, log_level)


__all__ = ['StructuredLogger', 'create_logger']

