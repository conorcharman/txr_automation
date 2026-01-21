"""
Unit Tests for ID Formats Module
=================================

Tests for IDFormatManager and ID pattern validation.
"""

import pytest
from src.accuracy_testing.core.id_formats import (
    IDPattern,
    IDFormatManager,
    id_format_manager,
    ID_PATTERNS
)


class TestIDPattern:
    """Test IDPattern dataclass."""
    
    def test_id_pattern_creation(self):
        """Test creating an IDPattern object."""
        import re
        pattern = IDPattern(
            country_code="GB",
            id_type="NIDN",
            regex_pattern=r"^[A-Z]{2}\d{6}[A-Z]$",
            compiled_pattern=re.compile(r"^[A-Z]{2}\d{6}[A-Z]$")
        )
        assert pattern.country_code == "GB"
        assert pattern.id_type == "NIDN"
    
    def test_id_pattern_matches(self):
        """Test pattern matching."""
        import re
        pattern = IDPattern(
            country_code="GB",
            id_type="NIDN",
            regex_pattern=r"^[A-Z]{2}\d{6}[A-Z]$",
            compiled_pattern=re.compile(r"^[A-Z]{2}\d{6}[A-Z]$")
        )
        
        assert pattern.matches("AB123456C") is True
        assert pattern.matches("XY999999Z") is True
        assert pattern.matches("123456789") is False


class TestIDFormatManager:
    """Test IDFormatManager singleton."""
    
    def test_singleton_pattern(self):
        """Test that IDFormatManager is a singleton."""
        manager1 = IDFormatManager()
        manager2 = IDFormatManager()
        assert manager1 is manager2
    
    def test_total_patterns(self):
        """Test total pattern count."""
        manager = IDFormatManager()
        assert manager.total_patterns == 67
        assert len(ID_PATTERNS) == 67
    
    def test_supported_countries(self):
        """Test supported countries list."""
        manager = IDFormatManager()
        countries = manager.supported_countries
        
        assert "GB" in countries
        assert "DE" in countries
        assert "FR" in countries
        assert len(countries) > 0
    
    def test_supported_id_types(self):
        """Test supported ID types."""
        manager = IDFormatManager()
        types = manager.supported_id_types
        
        assert "NIDN" in types
        assert "CONCAT" in types
        assert "CCPT" in types
        assert "LEI" in types


class TestIDValidation:
    """Test ID validation methods."""
    
    def test_validate_gb_nidn_valid(self):
        """Test validating valid GB NIDN."""
        manager = IDFormatManager()
        
        # GB NIDN pattern: ^(?!OO|CR|FY|NW|NC|PP|PZ|TN)(?![A-Z]*[DFIQUV])[A-Z]{2}\d{6}(?!O)[A-Z]$
        result = manager.validate("GB", "NIDN", "AB123456C")
        assert result is True
    
    def test_validate_gb_concat_valid(self):
        """Test validating valid GB CONCAT."""
        manager = IDFormatManager()
        
        # CONCAT pattern: ^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$
        result = manager.validate("GB", "CONCAT", "GB12345678ABCDE#####")
        assert result is True
    
    def test_validate_be_nidn_valid(self):
        """Test validating valid BE NIDN."""
        manager = IDFormatManager()
        
        # BE NIDN pattern: ^\d{6}\d{3}\d{2}$
        result = manager.validate("BE", "NIDN", "12345678901")
        assert result is True
    
    def test_validate_invalid_format(self):
        """Test validating with wrong format."""
        manager = IDFormatManager()
        
        result = manager.validate("GB", "NIDN", "123456789")
        assert result is False
    
    def test_validate_case_insensitive(self):
        """Test that validation is case-insensitive for codes."""
        manager = IDFormatManager()
        
        result1 = manager.validate("GB", "CONCAT", "GB12345678ABCDE#####")
        result2 = manager.validate("gb", "concat", "GB12345678ABCDE#####")
        
        assert result1 == result2


class TestAutoDetection:
    """Test ID type auto-detection."""
    
    def test_validate_any_type_concat(self):
        """Test auto-detecting CONCAT type."""
        manager = IDFormatManager()
        
        result = manager.validate_any_type("GB", "GB12345678ABCDE#####")
        assert result == "CONCAT"
    
    def test_validate_any_type_no_match(self):
        """Test auto-detection with no match."""
        manager = IDFormatManager()
        
        result = manager.validate_any_type("GB", "INVALID123")
        assert result is None


class TestPatternQueries:
    """Test pattern query methods."""
    
    def test_get_patterns_for_country(self):
        """Test getting patterns for a country."""
        manager = IDFormatManager()
        
        gb_patterns = manager.get_patterns_for_country("GB")
        assert len(gb_patterns) > 0
        assert all(p.country_code == "GB" for p in gb_patterns)
    
    def test_get_patterns_for_type(self):
        """Test getting patterns for an ID type."""
        manager = IDFormatManager()
        
        nidn_patterns = manager.get_patterns_for_type("NIDN")
        assert len(nidn_patterns) > 0
        assert all(p.id_type == "NIDN" for p in nidn_patterns)
    
    def test_get_patterns_specific(self):
        """Test getting patterns for country and type."""
        manager = IDFormatManager()
        
        patterns = manager.get_patterns("GB", "NIDN")
        assert len(patterns) > 0
        assert all(p.country_code == "GB" and p.id_type == "NIDN" for p in patterns)
    
    def test_get_id_types_for_country(self):
        """Test getting ID types for a country."""
        manager = IDFormatManager()
        
        gb_types = manager.get_id_types_for_country("GB")
        assert "NIDN" in gb_types
        assert "CONCAT" in gb_types
    
    def test_get_countries_for_type(self):
        """Test getting countries for an ID type."""
        manager = IDFormatManager()
        
        concat_countries = manager.get_countries_for_type("CONCAT")
        assert "GB" in concat_countries
        assert "FR" in concat_countries
        assert "DE" in concat_countries


class TestLEIValidation:
    """Test LEI-specific validation."""
    
    def test_validate_lei_valid(self):
        """Test validating valid LEI."""
        manager = IDFormatManager()
        
        # LEI pattern: ^[A-Z0-9]{18}\d{2}$
        result = manager.validate_lei("ABCDEFGHIJKLMNOPQR12")
        assert result is True
    
    def test_validate_lei_invalid_length(self):
        """Test validating LEI with wrong length."""
        manager = IDFormatManager()
        
        result = manager.validate_lei("ABC123")
        assert result is False
    
    def test_validate_lei_invalid_format(self):
        """Test validating LEI with wrong format."""
        manager = IDFormatManager()
        
        result = manager.validate_lei("abcdefghijklmnopqr12")  # lowercase not allowed
        assert result is False


class TestMultiplePatterns:
    """Test countries with multiple patterns per type."""
    
    def test_cy_multiple_ccpt_patterns(self):
        """Test Cyprus CCPT with multiple patterns."""
        manager = IDFormatManager()
        
        # Cyprus has two CCPT patterns: ^E\d{6}$ and ^K\d{8}$
        patterns = manager.get_patterns("CY", "CCPT")
        assert len(patterns) == 2
        
        # Test both patterns work
        assert manager.validate("CY", "CCPT", "E123456") is True
        assert manager.validate("CY", "CCPT", "K12345678") is True
    
    def test_es_multiple_nidn_patterns(self):
        """Test Spain NIDN with multiple patterns."""
        manager = IDFormatManager()
        
        # Spain has multiple NIDN patterns
        patterns = manager.get_patterns("ES", "NIDN")
        assert len(patterns) >= 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_country_code_lei(self):
        """Test LEI with empty country code."""
        manager = IDFormatManager()
        
        # LEI has empty country code in data
        result = manager.validate("", "LEI", "ABCDEFGHIJKLMNOPQR12")
        assert result is True
    
    def test_get_patterns_invalid_country(self):
        """Test getting patterns for invalid country."""
        manager = IDFormatManager()
        
        patterns = manager.get_patterns_for_country("XX")
        assert len(patterns) == 0
    
    def test_get_patterns_invalid_type(self):
        """Test getting patterns for invalid type."""
        manager = IDFormatManager()
        
        patterns = manager.get_patterns_for_type("INVALID")
        assert len(patterns) == 0


class TestSpecificCountryFormats:
    """Test specific country ID formats."""
    
    @pytest.mark.parametrize("country,id_type,valid_id", [
        ("AT", "CONCAT", "AT12345678ABCDE#####"),
        ("BE", "NIDN", "12345678901"),
        ("FI", "NIDN", "123456+1234"),
        ("IT", "NIDN", "RSSMRA80A01H501U"),
        ("SE", "NIDN", "123456781234"),
    ])
    def test_country_id_formats(self, country, id_type, valid_id):
        """Test specific country ID format validation."""
        manager = IDFormatManager()
        result = manager.validate(country, id_type, valid_id)
        assert result is True


class TestPreInstantiatedManager:
    """Test the pre-instantiated id_format_manager singleton."""
    
    def test_id_format_manager_available(self):
        """Test that id_format_manager is available."""
        assert id_format_manager is not None
        assert isinstance(id_format_manager, IDFormatManager)
    
    def test_id_format_manager_is_singleton(self):
        """Test that id_format_manager is the singleton instance."""
        new_manager = IDFormatManager()
        assert id_format_manager is new_manager
