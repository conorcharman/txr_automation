"""
Tests for ESMA Regex Pattern Fixes
==================================

Tests for the corrected NL, ES, and GB ID format patterns.
"""

import pytest
from core.data.id_formats import IDFormatManager


class TestNLPatternFixes:
    """Test Netherlands ID pattern corrections."""
    
    def test_nl_patterns_9_characters(self):
        """Test NL patterns accept 9-character IDs."""
        manager = IDFormatManager()
        
        # User's real example - should validate
        assert manager.validate("NL", "CCPT", "NPPD7P215")
        assert manager.validate("NL", "NIDN", "NPPD7P215")
        
        # Valid 9-character formats (last char must be digit)
        assert manager.validate("NL", "CCPT", "AB1234569")
        assert manager.validate("NL", "NIDN", "XY9876540")
    
    def test_nl_excludes_O(self):
        """Test NL patterns exclude 'O' from letter positions."""
        manager = IDFormatManager()
        
        # 'O' not allowed in first 2 positions
        assert not manager.validate("NL", "CCPT", "OB123456C")
        assert not manager.validate("NL", "CCPT", "AO123456C")
    
    def test_nl_correct_length(self):
        """Test NL patterns report correct expected length."""
        manager = IDFormatManager()
        
        is_valid, error = manager.validate_with_details("NL", "CCPT", "AB1234")
        
        assert not is_valid
        # Should mention 9 characters
        assert "9" in error


class TestESPatternFixes:
    """Test Spanish ID pattern corrections."""
    
    def test_es_patterns_9_characters(self):
        """Test ES patterns accept 9-character IDs."""
        manager = IDFormatManager()
        
        # Valid Spanish IDs
        assert manager.validate("ES", "NIDN", "12345678A")
        assert manager.validate("ES", "NIDN", "L1234567Z")
        assert manager.validate("ES", "NIDN", "K9876543H")
    
    def test_es_excludes_I_O_U(self):
        """Test ES patterns exclude I, O, U from control letter."""
        manager = IDFormatManager()
        
        # These should all fail
        assert not manager.validate("ES", "NIDN", "12345678I")
        assert not manager.validate("ES", "NIDN", "12345678O")
        assert not manager.validate("ES", "NIDN", "12345678U")


class TestGBPatternImprovements:
    """Test Great Britain NINO pattern improvements."""
    
    def test_gb_valid_ninos(self):
        """Test GB patterns accept valid NINOs."""
        manager = IDFormatManager()
        
        # Valid NINOs including 'S'
        assert manager.validate("GB", "NIDN", "SG500496A")
        assert manager.validate("GB", "NIDN", "AB123456C")
        assert manager.validate("GB", "NIDN", "CE123456D")
    
    def test_gb_excludes_invalid_letters(self):
        """Test GB patterns exclude invalid prefix letters."""
        manager = IDFormatManager()
        
        # Invalid letters: D, F, I, Q, U, V
        assert not manager.validate("GB", "NIDN", "DB123456C")
        assert not manager.validate("GB", "NIDN", "FB123456C")
        assert not manager.validate("GB", "NIDN", "IB123456C")
        assert not manager.validate("GB", "NIDN", "QB123456C")
        
    def test_gb_excludes_O_suffix(self):
        """Test GB patterns exclude 'O' from suffix."""
        manager = IDFormatManager()
        
        # 'O' not allowed in suffix
        assert not manager.validate("GB", "NIDN", "AB123456O")


class TestErrorMessageCalculator:
    """Test error message calculator improvements."""
    
    def test_nl_error_message_correct_length(self):
        """Test NL error messages report 9 characters."""
        manager = IDFormatManager()
        patterns = manager.get_patterns("NL", "CCPT")
        
        assert len(patterns) > 0
        pattern = patterns[0]
        
        reason = pattern.get_mismatch_reason("AB12345")  # 7 chars
        
        # Should mention 9 characters (not 11)
        assert "9" in reason
        assert "11" not in reason
    
    def test_es_error_message_correct_length(self):
        """Test ES error messages report 9 characters."""
        manager = IDFormatManager()
        patterns = manager.get_patterns("ES", "NIDN")
        
        pattern = patterns[0]
        reason = pattern.get_mismatch_reason("1234567A")  # 8 chars
        
        # Should mention 9 characters (not 10)
        assert "9" in reason
        assert "10" not in reason


class TestIntegrationValidation:
    """Integration tests for regex fixes."""
    
    def test_nl_id_after_prefix_stripping(self):
        """Test NL IDs validate after prefix removal."""
        manager = IDFormatManager()
        
        # User's actual scenario
        full_id = "NLNPPD7P215"
        stripped_id = full_id[2:]  # Remove "NL" prefix
        
        # Should validate as 9-char ID
        assert len(stripped_id) == 9
        assert manager.validate("NL", "CCPT", stripped_id)
    
    def test_es_valid_formats(self):
        """Test ES patterns with various valid formats."""
        manager = IDFormatManager()
        
        # Standard format
        assert manager.validate("ES", "NIDN", "12345678A")
        
        # L prefix (non-resident)
        assert manager.validate("ES", "NIDN", "L1234567Z")
        
        # K prefix (under 14)
        assert manager.validate("ES", "NIDN", "K1234567H")
    
    def test_gb_with_various_prefixes(self):
        """Test GB pattern with various valid prefixes."""
        manager = IDFormatManager()
        
        # Various valid prefix combinations
        assert manager.validate("GB", "NIDN", "AB123456C")
        assert manager.validate("GB", "NIDN", "SG500496A")
        assert manager.validate("GB", "NIDN", "CE123456D")
        assert manager.validate("GB", "NIDN", "GH500496A")
        
        # Invalid prefixes (HMRC-disallowed administrative prefixes)
        assert not manager.validate("GB", "NIDN", "OO123456C")
        # CR is a valid NINO prefix per HMRC — previously excluded in error
        assert manager.validate("GB", "NIDN", "CR123456C")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
