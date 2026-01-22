"""
Logging Infrastructure Module
==============================

Unified structured logging for all replay processing scripts.

Note: This module is deprecated. Import from common.logger instead.
      Kept for backward compatibility.
"""

import logging
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from .data_structures import ProcessingStats

# Re-export from common for backward compatibility
from common.logger import StructuredLogger as _StructuredLogger, create_logger as _create_logger


# Backward compatibility wrapper
class StructuredLogger(_StructuredLogger):
    """
    Unified structured logging for all processors.
    
    Provides consistent logging format and functionality across all scripts.
    Supports both file and console logging with structured data.
    
    Note: This is a compatibility wrapper. Use common.logger.StructuredLogger instead.
    """
    
    def __init__(self, name: str, log_dir: str, log_level: str = "INFO"):
        """
        Initialize logger.
        
        Args:
            name: Logger name (used in log messages and filename)
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        # Call parent constructor
        super().__init__(name, log_dir, log_level)
    
    def log_stats(self, stats: ProcessingStats) -> None:
        """
        Log statistics in structured format.
        
        Args:
            stats: ProcessingStats object to log
        """
        # Call parent's generic version
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

