"""
Logging Infrastructure Module
==============================

Unified structured logging for all replay processing scripts.
"""

import logging
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from .data_structures import ProcessingStats


class StructuredLogger:
    """
    Unified structured logging for all processors.
    
    Provides consistent logging format and functionality across all scripts.
    Supports both file and console logging with structured data.
    """
    
    def __init__(self, name: str, log_dir: str, log_level: str = "INFO"):
        """
        Initialize logger.
        
        Args:
            name: Logger name (used in log messages and filename)
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        self.log_dir = log_dir
        self.log_filepath: Optional[str] = None
        self.logger: Optional[logging.Logger] = None
        self.setup_logging(log_level)
    
    def setup_logging(self, log_level: str) -> None:
        """
        Setup logging with consistent format.
        
        Creates both file and console handlers with the same format.
        
        Args:
            log_level: Logging level string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{self.name}_{timestamp}.log"
        self.log_filepath = os.path.join(self.log_dir, log_filename)
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create custom formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(self.log_filepath, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with optional structured data"""
        if self.logger:
            # Extract special logging parameters
            exc_info = kwargs.pop('exc_info', False)
            stack_info = kwargs.pop('stack_info', False)
            self.logger.debug(message, extra=kwargs, exc_info=exc_info, stack_info=stack_info)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with optional structured data"""
        if self.logger:
            # Extract special logging parameters
            exc_info = kwargs.pop('exc_info', False)
            stack_info = kwargs.pop('stack_info', False)
            self.logger.info(message, extra=kwargs, exc_info=exc_info, stack_info=stack_info)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with optional structured data"""
        if self.logger:
            # Extract special logging parameters
            exc_info = kwargs.pop('exc_info', False)
            stack_info = kwargs.pop('stack_info', False)
            self.logger.warning(message, extra=kwargs, exc_info=exc_info, stack_info=stack_info)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with optional structured data"""
        if self.logger:
            # Extract exc_info if present (special logging parameter)
            exc_info = kwargs.pop('exc_info', False)
            self.logger.error(message, extra=kwargs, exc_info=exc_info)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with optional structured data"""
        if self.logger:
            # Extract special logging parameters
            exc_info = kwargs.pop('exc_info', False)
            stack_info = kwargs.pop('stack_info', False)
            self.logger.critical(message, extra=kwargs, exc_info=exc_info, stack_info=stack_info)
    
    def log_stats(self, stats: ProcessingStats) -> None:
        """
        Log statistics in structured format.
        
        Args:
            stats: ProcessingStats object to log
        """
        stats_dict = stats.to_dict()
        if self.logger:
            self.logger.info(f"Processing Statistics: {json.dumps(stats_dict, indent=2)}")
    
    def log_header(self, title: str, width: int = 80) -> None:
        """
        Log a header section.
        
        Args:
            title: Header title
            width: Width of the header line
        """
        if self.logger:
            self.logger.info("=" * width)
            self.logger.info(title)
            self.logger.info("=" * width)
    
    def log_section(self, title: str) -> None:
        """
        Log a section header.
        
        Args:
            title: Section title
        """
        if self.logger:
            self.logger.info("")
            self.logger.info(f"--- {title} ---")
    
    def log_dict(self, data: Dict[str, Any], title: Optional[str] = None) -> None:
        """
        Log a dictionary in readable format.
        
        Args:
            data: Dictionary to log
            title: Optional title for the data
        """
        if self.logger:
            if title:
                self.logger.info(f"{title}:")
            self.logger.info(json.dumps(data, indent=2))
    
    def get_log_path(self) -> Optional[str]:
        """Get the path to the log file"""
        return self.log_filepath


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
