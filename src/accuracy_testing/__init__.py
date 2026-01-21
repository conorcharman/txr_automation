"""
Accuracy Testing Module
=======================

Scripts for quarterly accuracy testing (converted from VBA).

Version 3.0: Independent configuration management
"""

__version__ = "3.0.0"

from .processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
    ClientRecord,
    IDValidationProcessor,
    ProcessingStats,
)

__all__ = [
    "AccuracyConfigManager",
    "AccuracyPathConfig",
    "AccuracyProcessorConfig",
    "ClientRecord",
    "IDValidationProcessor",
    "ProcessingStats",
]
