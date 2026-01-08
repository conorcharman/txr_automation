"""
Configuration Management Module
================================

Handles configuration loading from YAML files and environment variables.
"""

import os
import yaml
from dataclasses import dataclass
from typing import Dict, Any, Optional
from functools import lru_cache


@dataclass
class PathConfig:
    """
    Configuration for file paths.
    
    All scripts use this standardized path configuration.
    """
    replay_input: str
    incident_files: str
    replay_output: str
    log_output: str
    unavista_file: Optional[str] = None
    
    def __post_init__(self):
        """Validate paths exist (for input paths)"""
        # We don't validate unavista_file here as it's optional
        pass


@dataclass
class ProcessorConfig:
    """
    Configuration for processor behavior.
    
    Controls how processors execute (batch size, logging, etc.)
    """
    batch_size: int = 50
    log_level: str = "INFO"
    enable_progress_reporting: bool = True
    encoding: str = "utf-8"
    
    def __post_init__(self):
        """Validate configuration values"""
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"log_level must be one of {valid_log_levels}")
        
        self.log_level = self.log_level.upper()


class ConfigManager:
    """
    Manages configuration from YAML files and environment variables.
    
    Priority order (highest to lowest):
    1. Environment variables (TXR_*)
    2. YAML configuration file
    3. Default values
    """
    
    # Cache for loaded YAML configs to avoid re-parsing
    _config_cache: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def load_from_yaml(cls, config_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Load configuration from YAML file with optional caching.
        
        Args:
            config_path: Path to YAML configuration file
            use_cache: If True, cache the parsed config for subsequent calls (default: True)
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Get absolute path for consistent cache keys
        abs_path = os.path.abspath(config_path)
        
        # Check cache first
        if use_cache and abs_path in cls._config_cache:
            return cls._config_cache[abs_path]
        
        # Load from file
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        result = config if config else {}
        
        # Cache the result
        if use_cache:
            cls._config_cache[abs_path] = result
        
        return result
    
    @classmethod
    def clear_cache(cls):
        """Clear the configuration cache. Useful for testing or when configs change."""
        cls._config_cache.clear()
    
    @classmethod
    def load_from_env(cls, prefix: str = "TXR_") -> Dict[str, Any]:
        """
        Load configuration from environment variables.
        
        Args:
            prefix: Prefix for environment variables (default: "TXR_")
            
        Returns:
            Configuration dictionary
            
        Example:
            Environment variables:
                TXR_REPLAY_INPUT=/path/to/input
                TXR_LOG_LEVEL=DEBUG
            
            Returns:
                {'replay_input': '/path/to/input', 'log_level': 'DEBUG'}
        """
        config = {'paths': {}, 'processing': {}}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and convert to lowercase
                config_key = key[len(prefix):].lower()
                
                # Categorize configuration
                path_keys = ['replay_input', 'incident_files', 'replay_output', 'log_output', 'unavista_file']
                if config_key in path_keys:
                    config['paths'][config_key] = value
                else:
                    config['processing'][config_key] = value
        
        return config
    
    @classmethod
    def merge_configs(cls, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.
        
        Later configs override earlier ones.
        
        Args:
            *configs: Variable number of config dictionaries
            
        Returns:
            Merged configuration dictionary
        """
        merged = {}
        
        for config in configs:
            for key, value in config.items():
                if isinstance(value, dict) and key in merged:
                    # Recursively merge nested dictionaries
                    merged[key] = {**merged[key], **value}
                else:
                    merged[key] = value
        
        return merged
    
    @classmethod
    def get_path_config(cls, config_dict: Dict[str, Any]) -> PathConfig:
        """
        Create PathConfig from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary with 'paths' section
            
        Returns:
            PathConfig instance
            
        Raises:
            ValueError: If required paths are missing
        """
        paths = config_dict.get('paths', {})
        
        required_keys = ['replay_input', 'incident_files', 'replay_output', 'log_output']
        missing_keys = [key for key in required_keys if key not in paths]
        
        if missing_keys:
            raise ValueError(f"Missing required path configuration: {', '.join(missing_keys)}")
        
        return PathConfig(
            replay_input=paths['replay_input'],
            incident_files=paths['incident_files'],
            replay_output=paths['replay_output'],
            log_output=paths['log_output'],
            unavista_file=paths.get('unavista_file')
        )
    
    @classmethod
    def get_processor_config(cls, config_dict: Dict[str, Any]) -> ProcessorConfig:
        """
        Create ProcessorConfig from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary with 'processing' section
            
        Returns:
            ProcessorConfig instance with defaults for missing values
        """
        processing = config_dict.get('processing', {})
        
        return ProcessorConfig(
            batch_size=processing.get('batch_size', 50),
            log_level=processing.get('log_level', 'INFO'),
            enable_progress_reporting=processing.get('enable_progress_reporting', True),
            encoding=processing.get('encoding', 'utf-8')
        )
