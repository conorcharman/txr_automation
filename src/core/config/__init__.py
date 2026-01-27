"""
Configuration Management
========================

Unified configuration loading from YAML files and environment variables.

Classes:
    ConfigManager: Load and merge configurations
    PathConfig: File path configuration dataclass
    ProcessorConfig: Processor behavior configuration dataclass

This is the canonical location for configuration management.
For backward compatibility, these are also re-exported from:
- txr_replay_core.config
"""

from core.config.config_manager import (
    ConfigManager,
    PathConfig,
    ProcessorConfig,
)

__all__ = [
    "ConfigManager",
    "PathConfig",
    "ProcessorConfig",
]
