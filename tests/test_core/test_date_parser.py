"""
Tests for DateParser utility
"""

import pytest
from common.utils import DateParser


class TestDateParser:
    """Test DateParser functionality"""
    
    def setup_method(self):
        """Clear cache before each test"""
        DateParser.clear_cache()
    
    def test_parse_iso_format(self):
        """Test parsing ISO format dates (YYYY-MM-DD)"""
        assert DateParser.parse_date("2023-12-01") == "2023-12-01"
        assert DateParser.parse_date("2024-01-15") == "2024-01-15"
    
    def test_parse_uk_format(self):
        """Test parsing UK format dates (DD/MM/YYYY)"""
        assert DateParser.parse_date("01/12/2023") == "2023-12-01"
        assert DateParser.parse_date("15/01/2024") == "2024-01-15"
    
    def test_parse_us_format(self):
        """Test parsing US format dates (MM/DD/YYYY)"""
        # Note: US format is ambiguous, but parser tries it
        result = DateParser.parse_date("12/01/2023")
        # Could be either 2023-12-01 or 2023-01-12
        assert result in ["2023-12-01", "2023-01-12"]
    
    def test_parse_with_timestamp(self):
        """Test parsing dates with time portions"""
        assert DateParser.parse_date("01/12/2023 00:00:00") == "2023-12-01"
        assert DateParser.parse_date("01/12/2023 14:30:15") == "2023-12-01"
        assert DateParser.parse_date("2023-12-01 23:59:59") == "2023-12-01"
    
    def test_parse_empty_string(self):
        """Test parsing empty strings"""
        assert DateParser.parse_date("") is None
        assert DateParser.parse_date("   ") is None
    
    def test_parse_invalid_date(self):
        """Test parsing invalid dates"""
        assert DateParser.parse_date("invalid") is None
        assert DateParser.parse_date("2023-13-45") is None
        assert DateParser.parse_date("99/99/9999") is None
    
    def test_parse_none(self):
        """Test parsing None"""
        assert DateParser.parse_date(None) is None
    
    def test_caching(self):
        """Test that caching works"""
        DateParser.clear_cache()
        assert DateParser.cache_size() == 0
        
        # Parse a date
        DateParser.parse_date("01/12/2023")
        assert DateParser.cache_size() == 1
        
        # Parse same date again (should use cache)
        DateParser.parse_date("01/12/2023")
        assert DateParser.cache_size() == 1
        
        # Parse different date
        DateParser.parse_date("02/12/2023")
        assert DateParser.cache_size() == 2
        
        # Clear cache
        DateParser.clear_cache()
        assert DateParser.cache_size() == 0
    
    def test_cache_invalid_dates(self):
        """Test that invalid dates are cached too (to avoid repeated parsing)"""
        DateParser.clear_cache()
        
        # Parse invalid date
        result1 = DateParser.parse_date("invalid")
        assert result1 is None
        assert DateParser.cache_size() == 1
        
        # Parse same invalid date again
        result2 = DateParser.parse_date("invalid")
        assert result2 is None
        assert DateParser.cache_size() == 1  # Should not increase
