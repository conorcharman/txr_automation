"""
Integration tests for configuration loading across all refactored scripts.

Tests verify that all scripts can correctly load configuration from:
- YAML files
- Environment variables
- Command-line argument overrides
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core import ConfigManager


class TestConfigurationLoading:
    """Test configuration loading for all scripts."""
    
    def test_phase2_config_from_yaml(self, sample_phase2_config, temp_data_dir):
        """Test Phase 2 config loads correctly from YAML."""
        config_dict = ConfigManager.load_from_yaml(sample_phase2_config)
        
        assert 'paths' in config_dict
        assert 'processing' in config_dict
        assert 'replace_pattern' in config_dict
        
        # Verify paths
        assert str(temp_data_dir / "input") in config_dict['paths']['replay_input']
        assert str(temp_data_dir / "incident") in config_dict['paths']['incident_files']
        assert str(temp_data_dir / "output") in config_dict['paths']['replay_output']
        assert str(temp_data_dir / "logs") in config_dict['paths']['log_output']
        
        # Verify processing settings
        assert config_dict['processing']['batch_size'] == 50
        assert config_dict['processing']['log_level'] == 'INFO'
    
    def test_phase3_config_from_yaml(self, sample_phase3_config, temp_data_dir):
        """Test Phase 3 config loads correctly from YAML."""
        config_dict = ConfigManager.load_from_yaml(sample_phase3_config)
        
        assert 'paths' in config_dict
        assert 'processing' in config_dict
        assert 'replay_files' in config_dict
        
        # Verify processing settings
        assert config_dict['processing']['batch_size'] == 100
        assert config_dict['processing']['similarity_threshold'] == 0.85
        
        # Verify replay files list
        assert len(config_dict['replay_files']) == 4
        assert 'inconsistent_buyer_ids.csv' in config_dict['replay_files']
    
    def test_phase3_final_config_from_yaml(self, sample_phase3_final_config, temp_data_dir):
        """Test Phase 3 Final config loads correctly from YAML."""
        config_dict = ConfigManager.load_from_yaml(sample_phase3_final_config)
        
        assert 'paths' in config_dict
        assert 'file_patterns' in config_dict
        assert 'processing' in config_dict
        
        # Verify file patterns
        assert config_dict['file_patterns']['unavista_pattern'] == "UnaVista*.csv"
        assert config_dict['file_patterns']['replay_ids_pattern'] == "*_ids_replay*.csv"
        
        # Verify processing settings
        assert config_dict['processing']['skip_duplicates'] is True
    
    def test_xlsx_converter_config_from_yaml(self, sample_xlsx_config, temp_data_dir):
        """Test XLSX Converter config loads correctly from YAML."""
        config_dict = ConfigManager.load_from_yaml(sample_xlsx_config)
        
        assert 'paths' in config_dict
        assert 'processing' in config_dict
        assert 'logging' in config_dict
        
        # Verify paths
        assert str(temp_data_dir / "input") in config_dict['paths']['input_dir']
        assert str(temp_data_dir / "output") in config_dict['paths']['output_dir']
        
        # Verify processing settings
        assert config_dict['processing']['encoding'] == 'utf-8-sig'
        assert config_dict['processing']['split_multiline'] is True
    
    def test_config_from_environment_variables(self, clean_env, temp_data_dir):
        """Test configuration loading from environment variables."""
        # Set environment variables
        os.environ['TXR_REPLAY_INPUT'] = str(temp_data_dir / "input")
        os.environ['TXR_INCIDENT_FILES'] = str(temp_data_dir / "incident")
        os.environ['TXR_REPLAY_OUTPUT'] = str(temp_data_dir / "output")
        os.environ['TXR_LOG_OUTPUT'] = str(temp_data_dir / "logs")
        os.environ['TXR_BATCH_SIZE'] = '75'
        
        config_dict = ConfigManager.load_from_env(prefix='TXR_')
        
        # Path-related vars go into 'paths' section
        assert config_dict['paths']['replay_input'] == str(temp_data_dir / "input")
        assert config_dict['paths']['incident_files'] == str(temp_data_dir / "incident")
        assert config_dict['paths']['replay_output'] == str(temp_data_dir / "output")
        assert config_dict['paths']['log_output'] == str(temp_data_dir / "logs")
        # Non-path vars go into 'processing' section
        assert config_dict['processing']['batch_size'] == '75'
    
    def test_config_merge_yaml_and_env(self, sample_phase2_config, clean_env, temp_data_dir):
        """Test configuration merge (YAML + environment variables)."""
        # Load from YAML
        yaml_config = ConfigManager.load_from_yaml(sample_phase2_config)
        
        # Set environment variable to override
        os.environ['TXR_BATCH_SIZE'] = '200'
        env_config = ConfigManager.load_from_env(prefix='TXR_')
        
        # Merge (env should override)
        merged = ConfigManager.merge_configs(yaml_config, env_config)
        
        # Verify merge
        assert 'paths' in merged  # From YAML
        assert merged['processing']['batch_size'] == '200'  # From env (overridden)
    
    def test_missing_config_file_raises_error(self):
        """Test that loading a missing config file raises an error."""
        with pytest.raises(FileNotFoundError):
            ConfigManager.load_from_yaml('/nonexistent/config.yaml')
    
    def test_invalid_yaml_raises_error(self, temp_config_dir):
        """Test that invalid YAML raises an error."""
        invalid_config = temp_config_dir / "invalid.yaml"
        invalid_config.write_text("invalid: yaml: content: [")
        
        with pytest.raises(Exception):  # yaml.YAMLError or similar
            ConfigManager.load_from_yaml(str(invalid_config))


class TestPathConfig:
    """Test PathConfig dataclass functionality."""
    
    def test_path_config_creation(self, temp_data_dir):
        """Test creating PathConfig from dictionary."""
        config_dict = {
            'paths': {
                'replay_input': str(temp_data_dir / "input"),
                'incident_files': str(temp_data_dir / "incident"),
                'replay_output': str(temp_data_dir / "output"),
                'log_output': str(temp_data_dir / "logs")
            }
        }
        
        path_config = ConfigManager.get_path_config(config_dict)
        
        assert path_config.replay_input == str(temp_data_dir / "input")
        assert path_config.incident_files == str(temp_data_dir / "incident")
        assert path_config.replay_output == str(temp_data_dir / "output")
        assert path_config.log_output == str(temp_data_dir / "logs")
    
    def test_path_config_missing_keys(self):
        """Test PathConfig with missing required keys."""
        config_dict = {
            'paths': {
                'replay_input': '/some/path'
                # Missing other required paths
            }
        }
        
        with pytest.raises(ValueError):  # Raises ValueError, not KeyError
            ConfigManager.get_path_config(config_dict)


class TestProcessorConfig:
    """Test ProcessorConfig validation."""
    
    def test_processor_config_valid(self):
        """Test creating valid ProcessorConfig."""
        config_dict = {
            'processing': {
                'batch_size': 100,
                'log_level': 'DEBUG'
            }
        }
        
        proc_config = ConfigManager.get_processor_config(config_dict)
        
        assert proc_config.batch_size == 100
        assert proc_config.log_level == 'DEBUG'
    
    def test_processor_config_defaults(self):
        """Test ProcessorConfig uses defaults when not specified."""
        config_dict = {'processing': {}}
        
        proc_config = ConfigManager.get_processor_config(config_dict)
        
        assert proc_config.batch_size == 50  # Default
        assert proc_config.log_level == 'INFO'  # Default
    
    def test_processor_config_invalid_batch_size(self):
        """Test ProcessorConfig rejects invalid batch size."""
        config_dict = {
            'processing': {
                'batch_size': 0  # Invalid: must be > 0
            }
        }
        
        with pytest.raises(ValueError):
            ConfigManager.get_processor_config(config_dict)
    
    def test_processor_config_invalid_log_level(self):
        """Test ProcessorConfig rejects invalid log level."""
        config_dict = {
            'processing': {
                'log_level': 'INVALID'  # Not a valid log level
            }
        }
        
        with pytest.raises(ValueError):
            ConfigManager.get_processor_config(config_dict)
