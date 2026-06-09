"""
Integration tests for logger initialization across all refactored scripts.

Tests verify that:
- StructuredLogger initializes correctly
- Log files are created in the correct location
- Log levels are respected
- Logging output is formatted correctly
"""

import logging
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core import ProcessingStats, StructuredLogger, create_logger


class TestStructuredLogger:
    """Test StructuredLogger functionality."""

    def test_logger_initialization(self, temp_data_dir):
        """Test StructuredLogger initializes correctly."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        assert logger.name == "test_logger"
        assert logger.log_dir == str(log_dir)
        assert logger.logger is not None
        assert Path(logger.log_filepath).exists()

    def test_logger_creates_log_directory(self, temp_data_dir):
        """Test logger creates log directory if it doesn't exist."""
        log_dir = temp_data_dir / "new_logs"
        assert not log_dir.exists()

        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        assert log_dir.exists()
        assert Path(logger.log_filepath).exists()

    def test_logger_respects_log_level_info(self, temp_data_dir):
        """Test logger respects INFO log level."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        assert logger.logger.level == logging.INFO

    def test_logger_respects_log_level_debug(self, temp_data_dir):
        """Test logger respects DEBUG log level."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "DEBUG")

        assert logger.logger.level == logging.DEBUG

    def test_logger_respects_log_level_warning(self, temp_data_dir):
        """Test logger respects WARNING log level."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "WARNING")

        assert logger.logger.level == logging.WARNING

    def test_logger_respects_log_level_error(self, temp_data_dir):
        """Test logger respects ERROR log level."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "ERROR")

        assert logger.logger.level == logging.ERROR

    def test_logger_info_method(self, temp_data_dir):
        """Test logger.info() method works."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        # Should not raise exception
        logger.info("Test message")

        # Check log file contains message
        log_content = Path(logger.log_filepath).read_text()
        assert "Test message" in log_content

    def test_logger_log_section_header(self, temp_data_dir):
        """Test logger section header logging."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        # Use info() to log section header manually
        logger.info("=" * 50)
        logger.info("Test Section")
        logger.info("=" * 50)

        log_content = Path(logger.log_filepath).read_text()
        assert "Test Section" in log_content
        assert "=" in log_content  # Section headers use separators

    def test_logger_log_stats(self, temp_data_dir):
        """Test logger.log_stats() method with ProcessingStats."""
        log_dir = temp_data_dir / "logs"
        logger = StructuredLogger("test_logger", str(log_dir), "INFO")

        stats = ProcessingStats()
        stats.processed_records = 100
        stats.successful_matches = 85
        stats.errors = 5

        logger.log_stats(stats)

        log_content = Path(logger.log_filepath).read_text()
        assert "100" in log_content  # processed_records
        assert "85" in log_content  # successful_matches
        assert "5" in log_content  # errors


class TestLoggerFactory:
    """Test create_logger() factory function."""

    def test_create_logger_info_level(self, temp_data_dir):
        """Test create_logger() with INFO level."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "INFO")

        assert isinstance(logger, StructuredLogger)
        assert logger.name == "test_logger"
        assert logger.logger.level == logging.INFO

    def test_create_logger_debug_level(self, temp_data_dir):
        """Test create_logger() with DEBUG level."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "DEBUG")

        assert logger.logger.level == logging.DEBUG

    def test_create_logger_creates_unique_log_files(self, temp_data_dir):
        """Test that each logger instance creates a unique log file."""
        log_dir = temp_data_dir / "logs"

        logger1 = create_logger("logger1", str(log_dir), "INFO")
        logger2 = create_logger("logger2", str(log_dir), "INFO")

        assert logger1.log_filepath != logger2.log_filepath
        assert Path(logger1.log_filepath).exists()
        assert Path(logger2.log_filepath).exists()


class TestLoggerIntegration:
    """Test logger integration with configuration."""

    def test_logger_from_config(self, sample_phase2_config, temp_data_dir):
        """Test creating logger from configuration."""
        from core import ConfigManager

        config_dict = ConfigManager.load_from_yaml(sample_phase2_config)
        log_output = config_dict["paths"]["log_output"]
        log_level = config_dict["processing"]["log_level"]

        logger = create_logger("phase2_test", log_output, log_level)

        assert logger.logger.level == logging.INFO
        assert Path(logger.log_filepath).exists()
        assert str(temp_data_dir / "logs") in logger.log_filepath

    def test_logger_with_different_names(self, temp_data_dir):
        """Test loggers with different names create different log files."""
        log_dir = temp_data_dir / "logs"

        phase2_logger = create_logger("phase_2_processor", str(log_dir), "INFO")
        phase3_logger = create_logger("phase_3_processor", str(log_dir), "INFO")

        assert "phase_2_processor" in phase2_logger.log_filepath
        assert "phase_3_processor" in phase3_logger.log_filepath
        assert phase2_logger.log_filepath != phase3_logger.log_filepath


class TestLoggerFileOutput:
    """Test logger file output formatting."""

    def test_log_file_contains_timestamp(self, temp_data_dir):
        """Test log entries contain timestamps."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "INFO")

        logger.info("Test message with timestamp")

        log_content = Path(logger.log_filepath).read_text()
        # Check for timestamp format (YYYY-MM-DD HH:MM:SS)
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, log_content)

    def test_log_file_contains_log_level(self, temp_data_dir):
        """Test log entries contain log level."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "INFO")

        logger.info("Info message")
        logger.logger.warning("Warning message")
        logger.logger.error("Error message")

        log_content = Path(logger.log_filepath).read_text()
        assert "INFO" in log_content
        assert "WARNING" in log_content
        assert "ERROR" in log_content

    def test_log_file_contains_logger_name(self, temp_data_dir):
        """Test log entries contain logger name."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("my_custom_logger", str(log_dir), "INFO")

        logger.info("Test message")

        log_content = Path(logger.log_filepath).read_text()
        assert "my_custom_logger" in log_content


class TestLoggerErrorHandling:
    """Test logger error handling."""

    def test_logger_handles_unicode_characters(self, temp_data_dir):
        """Test logger can handle Unicode characters."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "INFO")

        # Should not raise exception
        logger.info("Unicode test: ¬ £ € ü")

        log_content = Path(logger.log_filepath).read_text()
        assert "Unicode test" in log_content

    def test_logger_handles_special_characters(self, temp_data_dir):
        """Test logger can handle special characters."""
        log_dir = temp_data_dir / "logs"
        logger = create_logger("test_logger", str(log_dir), "INFO")

        # NOT SIGN character (chr(172))
        logger.info(f"Special character: {chr(172)}")

        log_content = Path(logger.log_filepath).read_text()
        assert "Special character" in log_content
