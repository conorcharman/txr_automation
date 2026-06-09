"""
Tests for ProcessingStats data structure
"""

import pytest

from core import ProcessingStats


class TestProcessingStats:
    """Test ProcessingStats functionality"""

    def test_initialization(self):
        """Test default initialization"""
        stats = ProcessingStats()
        assert stats.processed_files == 0
        assert stats.processed_records == 0
        assert stats.successful_matches == 0
        assert stats.not_found == 0
        assert stats.no_corrections == 0
        assert stats.inconsistent_corrections == 0
        assert stats.errors == 0
        assert stats.custom_stats == {}

    def test_increment_standard_stat(self):
        """Test incrementing standard statistics"""
        stats = ProcessingStats()

        stats.increment("processed_records")
        assert stats.processed_records == 1

        stats.increment("processed_records", 5)
        assert stats.processed_records == 6

        stats.increment("successful_matches", 3)
        assert stats.successful_matches == 3

    def test_increment_custom_stat(self):
        """Test incrementing custom statistics"""
        stats = ProcessingStats()

        # First increment creates the stat
        stats.increment("custom_stat_1")
        assert stats.custom_stats["custom_stat_1"] == 1

        # Subsequent increments update it
        stats.increment("custom_stat_1", 5)
        assert stats.custom_stats["custom_stat_1"] == 6

        # Multiple custom stats
        stats.increment("custom_stat_2", 10)
        assert stats.custom_stats["custom_stat_2"] == 10

    def test_to_dict(self):
        """Test converting stats to dictionary"""
        stats = ProcessingStats()
        stats.processed_records = 100
        stats.successful_matches = 95
        stats.not_found = 5
        stats.increment("custom_stat", 42)

        result = stats.to_dict()

        # Check standard stats
        assert result["processed_records"] == 100
        assert result["successful_matches"] == 95
        assert result["not_found"] == 5

        # Check custom stat
        assert result["custom_stat"] == 42

    def test_repr(self):
        """Test string representation"""
        stats = ProcessingStats()
        stats.processed_records = 100
        stats.successful_matches = 95
        stats.not_found = 3
        stats.errors = 2

        result = repr(stats)
        assert "ProcessingStats" in result
        assert "records=100" in result
        assert "matches=95" in result
        assert "not_found=3" in result
        assert "errors=2" in result
