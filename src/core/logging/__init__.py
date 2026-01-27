"""
Logging Infrastructure
======================

Structured logging for all TXR automation scripts.

Classes:
    StructuredLogger: Unified logging with file and console output

Functions:
    create_logger: Factory function for creating loggers

This module consolidates:
- common.logger
- txr_replay_core.logger
"""

from .structured_logger import StructuredLogger, StatsProtocol, create_logger

__all__ = [
    'StructuredLogger',
    'StatsProtocol',
    'create_logger',
]
