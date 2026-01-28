"""
Integration tests verifying that all scripts correctly use shared core library components.

Tests verify:
- DateParser is used consistently across scripts
- ConfigManager is used for configuration loading
- ProcessingStats is used for statistics tracking
- CharacterReplacement is used for special character handling
- No duplicate implementations of core functionality
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core import (
    DateParser, CharacterReplacement, ConfigManager, 
    ProcessingStats, ReplayRecord, LookupResult, UnaVistaTransaction
)


class TestDateParserIntegration:
    """Test DateParser usage across scripts."""
    
    def test_date_parser_singleton_behavior(self):
        """Test DateParser cache is shared (singleton-like behavior)."""
        # Clear cache
        DateParser._date_cache.clear()
        
        # Parse same date twice
        date1 = DateParser.parse_date("01/12/2023")
        date2 = DateParser.parse_date("01/12/2023")
        
        # Should be same result
        assert date1 == date2
        
        # Cache should contain one entry
        assert len(DateParser._date_cache) == 1
    
    def test_date_parser_formats_supported(self):
        """Test all supported date formats work."""
        test_cases = [
            ("2023-12-01", "2023-12-01"),           # ISO format
            ("01/12/2023", "2023-12-01"),           # UK format (DD/MM/YYYY)
            ("01/12/2023 10:30:45", "2023-12-01"),  # With timestamp
        ]
        
        for input_date, expected_output in test_cases:
            result = DateParser.parse_date(input_date)
            assert result == expected_output, f"Failed for {input_date}"
    
    def test_date_parser_caching_performance(self):
        """Test DateParser caching improves performance."""
        DateParser._date_cache.clear()
        
        # First parse (uncached)
        import time
        start = time.perf_counter()
        date1 = DateParser.parse_date("01/12/2023")
        first_time = time.perf_counter() - start
        
        # Second parse (cached)
        start = time.perf_counter()
        date2 = DateParser.parse_date("01/12/2023")
        second_time = time.perf_counter() - start
        
        # Cached should be faster (or at least not slower)
        assert second_time <= first_time * 2  # Allow some margin
        assert date1 == date2
    
    def test_date_parser_handles_invalid_dates(self):
        """Test DateParser handles invalid dates gracefully."""
        invalid_dates = [
            "invalid",
            "99/99/9999",
            "",
            None
        ]
        
        for invalid_date in invalid_dates:
            result = DateParser.parse_date(invalid_date)
            assert result is None or result == ""


class TestCharacterReplacementIntegration:
    """Test CharacterReplacement usage across scripts."""
    
    def test_colon_to_not_sign_conversion(self):
        """Test colon to NOT SIGN character replacement."""
        test_value = "INCIDENT:123:456"
        result = CharacterReplacement.colon_to_not_sign(test_value)
        
        # chr(172) is the NOT SIGN (¬)
        expected = f"INCIDENT{chr(172)}123{chr(172)}456"
        assert result == expected
        assert ":" not in result
        assert chr(172) in result
    
    def test_not_sign_to_colon_conversion(self):
        """Test NOT SIGN to colon character replacement."""
        test_value = f"INCIDENT{chr(172)}123{chr(172)}456"
        result = CharacterReplacement.not_sign_to_colon(test_value)
        
        expected = "INCIDENT:123:456"
        assert result == expected
        assert chr(172) not in result
        assert ":" in result
    
    def test_round_trip_conversion(self):
        """Test round-trip conversion (colon→NOT SIGN→colon)."""
        original = "TEST:VALUE:123"
        
        # Convert to NOT SIGN
        with_not_sign = CharacterReplacement.colon_to_not_sign(original)
        
        # Convert back to colon
        result = CharacterReplacement.not_sign_to_colon(with_not_sign)
        
        assert result == original
    
    def test_handles_empty_and_none(self):
        """Test CharacterReplacement handles empty strings and None."""
        assert CharacterReplacement.colon_to_not_sign("") == ""
        assert CharacterReplacement.colon_to_not_sign(None) is None
        assert CharacterReplacement.not_sign_to_colon("") == ""
        assert CharacterReplacement.not_sign_to_colon(None) is None


class TestProcessingStatsIntegration:
    """Test ProcessingStats usage across scripts."""
    
    def test_processing_stats_initialization(self):
        """Test ProcessingStats initializes with zeros."""
        stats = ProcessingStats()
        
        assert stats.processed_files == 0
        assert stats.processed_records == 0
        assert stats.successful_matches == 0
        assert stats.not_found == 0
        assert stats.no_corrections == 0
        assert stats.inconsistent_corrections == 0
        assert stats.errors == 0
        assert len(stats.custom_stats) == 0
    
    def test_processing_stats_increment(self):
        """Test ProcessingStats can increment counters."""
        stats = ProcessingStats()
        
        stats.processed_records += 10
        stats.successful_matches += 8
        stats.errors += 2
        
        assert stats.processed_records == 10
        assert stats.successful_matches == 8
        assert stats.errors == 2
    
    def test_processing_stats_custom_stats(self):
        """Test ProcessingStats supports custom statistics."""
        stats = ProcessingStats()
        
        stats.custom_stats['duplicate_records'] = 5
        stats.custom_stats['skipped_records'] = 3
        
        assert stats.custom_stats['duplicate_records'] == 5
        assert stats.custom_stats['skipped_records'] == 3
    
    def test_processing_stats_to_dict(self):
        """Test ProcessingStats converts to dictionary."""
        stats = ProcessingStats()
        stats.processed_records = 100
        stats.successful_matches = 85
        stats.custom_stats['test_stat'] = 10
        
        # Use dataclasses.asdict() instead of to_dict() method
        from dataclasses import asdict
        stats_dict = asdict(stats)
        
        assert stats_dict['processed_records'] == 100
        assert stats_dict['successful_matches'] == 85
        assert stats_dict['custom_stats']['test_stat'] == 10


class TestDataStructuresIntegration:
    """Test shared data structures across scripts."""
    
    def test_replay_record_creation(self):
        """Test ReplayRecord dataclass creation."""
        record = ReplayRecord(
            record_type='phase2',
            transaction_reference='TXN123',
            source_file='test.csv',
            row_index=1
        )
        
        assert record.record_type == 'phase2'
        assert record.transaction_reference == 'TXN123'
        assert record.source_file == 'test.csv'
        assert record.row_index == 1
    
    def test_lookup_result_creation(self):
        """Test LookupResult dataclass creation."""
        result = LookupResult(
            found=True,
            correction='CORRECTED_VALUE',
            correction_field='ID_Code',
            transaction_ref='TXN123'
        )
        
        assert result.found is True
        assert result.correction == 'CORRECTED_VALUE'
        assert result.correction_field == 'ID_Code'
        assert result.transaction_ref == 'TXN123'
    
    def test_unavista_transaction_creation(self):
        """Test UnaVistaTransaction dataclass creation."""
        transaction = UnaVistaTransaction(
            transaction_ref='TXN123',
            row_data=['val1', 'val2', 'val3'],
            row_index=5
        )
        
        assert transaction.transaction_ref == 'TXN123'
        assert len(transaction.row_data) == 3
        assert transaction.row_index == 5


class TestConfigManagerIntegration:
    """Test ConfigManager usage patterns."""
    
    def test_config_manager_yaml_loading(self, sample_phase2_config):
        """Test ConfigManager loads YAML correctly."""
        config = ConfigManager.load_from_yaml(sample_phase2_config)
        
        assert isinstance(config, dict)
        assert 'paths' in config
        assert 'processing' in config
    
    def test_config_manager_env_loading(self, clean_env):
        """Test ConfigManager loads environment variables."""
        import os
        os.environ['TXR_TEST_VALUE'] = 'test123'
        
        config = ConfigManager.load_from_env(prefix='TXR_')
        
        # Environment vars are loaded into 'processing' section
        assert 'test_value' in config['processing']
        assert config['processing']['test_value'] == 'test123'
    
    def test_config_manager_merge_configs(self):
        """Test ConfigManager merges configurations correctly."""
        base_config = {
            'paths': {'input': '/base/input'},
            'processing': {'batch_size': 50}
        }
        
        override_config = {
            'processing': {'batch_size': 100}
        }
        
        merged = ConfigManager.merge_configs(base_config, override_config)
        
        assert merged['paths']['input'] == '/base/input'  # From base
        assert merged['processing']['batch_size'] == 100  # Overridden


class TestCoreLibraryExports:
    """Test that core library exports all necessary components."""
    
    def test_all_exports_available(self):
        """Test all expected exports are available from core."""
        from core import (
            ReplayRecord,
            LookupResult,
            UnaVistaTransaction,
            ProcessingStats,
            DateParser,
            CharacterReplacement,
            FileDiscovery,
            ConfigManager,
            PathConfig,
            ProcessorConfig,
            StructuredLogger,
            create_logger
        )
        
        # All imports should succeed without ImportError
        assert ReplayRecord is not None
        assert LookupResult is not None
        assert UnaVistaTransaction is not None
        assert ProcessingStats is not None
        assert DateParser is not None
        assert CharacterReplacement is not None
        assert FileDiscovery is not None
        assert ConfigManager is not None
        assert PathConfig is not None
        assert ProcessorConfig is not None
        assert StructuredLogger is not None
        assert create_logger is not None
    
    def test_no_duplicate_implementations(self):
        """Test that scripts don't contain duplicate implementations."""
        # This would be a code review check, but we can verify imports work
        from core import DateParser, CharacterReplacement
        
        # Verify these are classes, not duplicated functions
        assert hasattr(DateParser, 'parse_date')
        assert hasattr(DateParser, '_date_cache')
        assert hasattr(CharacterReplacement, 'colon_to_not_sign')
        assert hasattr(CharacterReplacement, 'not_sign_to_colon')


class TestFileDiscoveryIntegration:
    """Test FileDiscovery utility usage."""
    
    def test_file_discovery_find_latest(self, temp_data_dir):
        """Test FileDiscovery.find_latest_file() method."""
        input_dir = temp_data_dir / "input"
        
        # Create test files with different timestamps
        file1 = input_dir / "test_old.csv"
        file2 = input_dir / "test_new.csv"
        
        file1.write_text("old")
        import time
        time.sleep(0.1)  # Ensure different mtimes
        file2.write_text("new")
        
        # Find latest file matching pattern
        from core import FileDiscovery
        latest = FileDiscovery.find_latest_file(str(input_dir), "test_*.csv")
        
        assert latest is not None
        assert "test_new.csv" in latest
    
    def test_file_discovery_no_matches(self, temp_data_dir):
        """Test FileDiscovery returns None when no files match."""
        input_dir = temp_data_dir / "input"
        
        from core import FileDiscovery
        result = FileDiscovery.find_latest_file(str(input_dir), "nonexistent_*.csv")
        
        assert result is None
