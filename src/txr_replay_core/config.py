"""
Configuration Management Module
================================

BACKWARD COMPATIBILITY MODULE
-----------------------------
This module now re-exports from the canonical location: core.config

All classes are maintained for backward compatibility.
New code should import directly from core.config:
    from core.config import ConfigManager, PathConfig, ProcessorConfig
"""

# Try different import paths for flexibility (installed package vs development)
try:
    # When imported as installed package (txr_replay_core.config)
    from core.config.config_manager import (
        ConfigManager,
        PathConfig,
        ProcessorConfig,
    )
except ImportError:
    # When imported from workspace root (src.txr_replay_core.config)
    from src.core.config.config_manager import (
        ConfigManager,
        PathConfig,
        ProcessorConfig,
    )

__all__ = [
    "ConfigManager",
    "PathConfig",
    "ProcessorConfig",
]
