"""
Unit Tests for Country Codes Module
====================================

Tests for CountryDataManager and country code lookups.
"""

import pytest
from src.accuracy_testing.core.country_codes import (
    Country,
    CountryDataManager,
    country_manager,
    COUNTRIES
)


class TestCountry:
    """Test Country dataclass."""
    
    def test_country_creation(self):
        """Test creating a Country object."""
        country = Country("United Kingdom", "GB", "GBR", True)
        assert country.name == "United Kingdom"
        assert country.alpha2 == "GB"
        assert country.alpha3 == "GBR"
        assert country.is_eea is True
    
    def test_country_immutable(self):
        """Test that Country is immutable (frozen)."""
        country = Country("France", "FR", "FRA", True)
        with pytest.raises(AttributeError):
            country.name = "Germany"
    
    def test_country_string_repr(self):
        """Test string representation."""
        country = Country("Spain", "ES", "ESP", True)
        assert str(country) == "Spain (ES)"


class TestCountryDataManager:
    """Test CountryDataManager singleton."""
    
    def test_singleton_pattern(self):
        """Test that CountryDataManager is a singleton."""
        manager1 = CountryDataManager()
        manager2 = CountryDataManager()
        assert manager1 is manager2
    
    def test_total_countries(self):
        """Test total country count."""
        manager = CountryDataManager()
        assert manager.total_countries == 249
        assert len(COUNTRIES) == 249
    
    def test_eea_count(self):
        """Test EEA country count."""
        manager = CountryDataManager()
        # Known EEA countries include GB, FR, DE, etc.
        assert manager.eea_count > 0
        assert manager.eea_count < manager.total_countries


class TestCountryLookups:
    """Test country lookup methods."""
    
    def test_get_by_alpha2_valid(self):
        """Test lookup by valid Alpha-2 code."""
        manager = CountryDataManager()
        
        gb = manager.get_by_alpha2("GB")
        assert gb is not None
        assert gb.alpha2 == "GB"
        assert gb.alpha3 == "GBR"
        assert gb.is_eea is True
        
        us = manager.get_by_alpha2("US")
        assert us is not None
        assert us.alpha2 == "US"
        assert us.is_eea is False
    
    def test_get_by_alpha2_case_insensitive(self):
        """Test that Alpha-2 lookup is case-insensitive."""
        manager = CountryDataManager()
        
        upper = manager.get_by_alpha2("GB")
        lower = manager.get_by_alpha2("gb")
        mixed = manager.get_by_alpha2("Gb")
        
        assert upper == lower == mixed
    
    def test_get_by_alpha2_invalid(self):
        """Test lookup by invalid Alpha-2 code."""
        manager = CountryDataManager()
        result = manager.get_by_alpha2("XX")
        assert result is None
    
    def test_get_by_alpha3_valid(self):
        """Test lookup by valid Alpha-3 code."""
        manager = CountryDataManager()
        
        gbr = manager.get_by_alpha3("GBR")
        assert gbr is not None
        assert gbr.alpha2 == "GB"
        assert gbr.alpha3 == "GBR"
    
    def test_get_by_alpha3_case_insensitive(self):
        """Test that Alpha-3 lookup is case-insensitive."""
        manager = CountryDataManager()
        
        upper = manager.get_by_alpha3("GBR")
        lower = manager.get_by_alpha3("gbr")
        
        assert upper == lower
    
    def test_get_by_alpha3_invalid(self):
        """Test lookup by invalid Alpha-3 code."""
        manager = CountryDataManager()
        result = manager.get_by_alpha3("XXX")
        assert result is None
    
    def test_get_by_name(self):
        """Test lookup by country name."""
        manager = CountryDataManager()
        
        uk = manager.get_by_name("United Kingdom of Great Britain and Northern Ireland (the)")
        assert uk is not None
        assert uk.alpha2 == "GB"


class TestEEAValidation:
    """Test EEA-related validation."""
    
    def test_is_eea_alpha2(self):
        """Test EEA check with Alpha-2 code."""
        manager = CountryDataManager()
        
        # Known EEA countries
        assert manager.is_eea("GB") is True
        assert manager.is_eea("DE") is True
        assert manager.is_eea("FR") is True
        
        # Non-EEA countries
        assert manager.is_eea("US") is False
        assert manager.is_eea("CN") is False
    
    def test_is_eea_alpha3(self):
        """Test EEA check with Alpha-3 code."""
        manager = CountryDataManager()
        
        assert manager.is_eea("GBR") is True
        assert manager.is_eea("USA") is False
    
    def test_get_eea_countries(self):
        """Test getting all EEA countries."""
        manager = CountryDataManager()
        eea_countries = manager.get_eea_countries()
        
        assert len(eea_countries) > 0
        assert all(c.is_eea for c in eea_countries)
        
        # Check specific countries
        alpha2_codes = [c.alpha2 for c in eea_countries]
        assert "GB" in alpha2_codes
        assert "DE" in alpha2_codes
        assert "FR" in alpha2_codes


class TestCodeConversion:
    """Test code conversion methods."""
    
    def test_alpha2_to_alpha3(self):
        """Test converting Alpha-2 to Alpha-3."""
        manager = CountryDataManager()
        
        assert manager.get_alpha3_from_alpha2("GB") == "GBR"
        assert manager.get_alpha3_from_alpha2("US") == "USA"
        assert manager.get_alpha3_from_alpha2("DE") == "DEU"
    
    def test_alpha3_to_alpha2(self):
        """Test converting Alpha-3 to Alpha-2."""
        manager = CountryDataManager()
        
        assert manager.get_alpha2_from_alpha3("GBR") == "GB"
        assert manager.get_alpha2_from_alpha3("USA") == "US"
        assert manager.get_alpha2_from_alpha3("DEU") == "DE"
    
    def test_code_conversion_invalid(self):
        """Test code conversion with invalid codes."""
        manager = CountryDataManager()
        
        assert manager.get_alpha3_from_alpha2("XX") is None
        assert manager.get_alpha2_from_alpha3("XXX") is None


class TestCodeValidation:
    """Test code validation."""
    
    def test_validate_code_alpha2(self):
        """Test validating Alpha-2 codes."""
        manager = CountryDataManager()
        
        assert manager.validate_code("GB") is True
        assert manager.validate_code("US") is True
        assert manager.validate_code("XX") is False
    
    def test_validate_code_alpha3(self):
        """Test validating Alpha-3 codes."""
        manager = CountryDataManager()
        
        assert manager.validate_code("GBR") is True
        assert manager.validate_code("USA") is True
        assert manager.validate_code("XXX") is False
    
    def test_validate_code_case_insensitive(self):
        """Test that validation is case-insensitive."""
        manager = CountryDataManager()
        
        assert manager.validate_code("gb") is True
        assert manager.validate_code("GBR") is True
        assert manager.validate_code("usa") is True


class TestSpecificCountries:
    """Test specific country data accuracy."""
    
    @pytest.mark.parametrize("alpha2,alpha3,is_eea", [
        ("GB", "GBR", True),
        ("US", "USA", False),
        ("DE", "DEU", True),
        ("FR", "FRA", True),
        ("CN", "CHN", False),
        ("IT", "ITA", True),
        ("ES", "ESP", True),
        ("SE", "SWE", True),
        ("NO", "NOR", True),
        ("CH", "CHE", False),  # Switzerland not in EEA
    ])
    def test_country_data(self, alpha2, alpha3, is_eea):
        """Test specific country data."""
        manager = CountryDataManager()
        
        country_a2 = manager.get_by_alpha2(alpha2)
        country_a3 = manager.get_by_alpha3(alpha3)
        
        assert country_a2 is not None
        assert country_a3 is not None
        assert country_a2 == country_a3
        assert country_a2.alpha2 == alpha2
        assert country_a2.alpha3 == alpha3
        assert country_a2.is_eea == is_eea


class TestPreInstantiatedManager:
    """Test the pre-instantiated country_manager singleton."""
    
    def test_country_manager_available(self):
        """Test that country_manager is available."""
        assert country_manager is not None
        assert isinstance(country_manager, CountryDataManager)
    
    def test_country_manager_is_singleton(self):
        """Test that country_manager is the singleton instance."""
        new_manager = CountryDataManager()
        assert country_manager is new_manager
