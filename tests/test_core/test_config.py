"""
Tests for ConfigManager
"""

import pytest
import os
from txr_replay_core.config import ConfigManager, PathConfig, ProcessorConfig


class TestConfigManager:
    """Test ConfigManager functionality"""
    
    def test_load_from_yaml(self, sample_yaml_config):
        """Test loading configuration from YAML file"""
        config = ConfigManager.load_from_yaml(sample_yaml_config)
        
        assert 'paths' in config
        assert 'processing' in config
        assert config['paths']['replay_input'] == '/test/input'
        assert config['processing']['batch_size'] == 100
    
    def test_load_from_yaml_missing_file(self):
        """Test loading from non-existent file raises error"""
        with pytest.raises(FileNotFoundError):
            ConfigManager.load_from_yaml('/nonexistent/file.yaml')
    
    def test_merge_configs(self):
        """Test merging multiple configurations"""
        config1 = {
            'paths': {'replay_input': '/path1', 'replay_output': '/output1'},
            'processing': {'batch_size': 50}
        }
        
        config2 = {
            'paths': {'replay_input': '/path2'},  # Override replay_input
            'processing': {'log_level': 'DEBUG'}  # Add new key
        }
        
        merged = ConfigManager.merge_configs(config1, config2)
        
        # config2 should override replay_input
        assert merged['paths']['replay_input'] == '/path2'
        # config1's replay_output should remain
        assert merged['paths']['replay_output'] == '/output1'
        # Both processing keys should exist
        assert merged['processing']['batch_size'] == 50
        assert merged['processing']['log_level'] == 'DEBUG'
    
    def test_get_path_config(self, sample_config_dict):
        """Test creating PathConfig from dict"""
        path_config = ConfigManager.get_path_config(sample_config_dict)
        
        assert isinstance(path_config, PathConfig)
        assert path_config.replay_input == '/test/input'
        assert path_config.incident_files == '/test/incident'
        assert path_config.replay_output == '/test/output'
        assert path_config.log_output == '/test/logs'
    
    def test_get_path_config_missing_keys(self):
        """Test that missing required paths raise error"""
        incomplete_config = {
            'paths': {
                'replay_input': '/test/input',
                # Missing other required keys
            }
        }
        
        with pytest.raises(ValueError, match="Missing required path configuration"):
            ConfigManager.get_path_config(incomplete_config)
    
    def test_get_processor_config(self, sample_config_dict):
        """Test creating ProcessorConfig from dict"""
        proc_config = ConfigManager.get_processor_config(sample_config_dict)
        
        assert isinstance(proc_config, ProcessorConfig)
        assert proc_config.batch_size == 100
        assert proc_config.log_level == 'DEBUG'
        assert proc_config.enable_progress_reporting is True
        assert proc_config.encoding == 'utf-8'
    
    def test_get_processor_config_defaults(self):
        """Test that ProcessorConfig uses defaults for missing values"""
        empty_config = {'processing': {}}
        
        proc_config = ConfigManager.get_processor_config(empty_config)
        
        assert proc_config.batch_size == 50  # Default
        assert proc_config.log_level == 'INFO'  # Default
        assert proc_config.enable_progress_reporting is True  # Default
        assert proc_config.encoding == 'utf-8'  # Default


class TestProcessorConfig:
    """Test ProcessorConfig validation"""
    
    def test_valid_config(self):
        """Test valid configuration"""
        config = ProcessorConfig(
            batch_size=100,
            log_level='DEBUG',
            enable_progress_reporting=True,
            encoding='utf-8'
        )
        
        assert config.batch_size == 100
        assert config.log_level == 'DEBUG'
    
    def test_invalid_batch_size(self):
        """Test that batch_size must be >= 1"""
        with pytest.raises(ValueError, match="batch_size must be at least 1"):
            ProcessorConfig(batch_size=0)
    
    def test_invalid_log_level(self):
        """Test that log_level must be valid"""
        with pytest.raises(ValueError, match="log_level must be one of"):
            ProcessorConfig(log_level='INVALID')
    
    def test_log_level_case_insensitive(self):
        """Test that log_level is normalized to uppercase"""
        config = ProcessorConfig(log_level='debug')
        assert config.log_level == 'DEBUG'
        
        config = ProcessorConfig(log_level='info')
        assert config.log_level == 'INFO'
