"""
Tests for CharacterReplacement utility
"""

import pytest
from common.utils import CharacterReplacement


class TestCharacterReplacement:
    """Test CharacterReplacement functionality"""
    
    def test_colon_to_not_sign(self):
        """Test replacing colons with NOT SIGN"""
        result = CharacterReplacement.colon_to_not_sign("Field:Value:123")
        assert ":" not in result
        assert chr(172) in result  # NOT SIGN character
        assert result == f"Field{chr(172)}Value{chr(172)}123"
    
    def test_colon_to_not_sign_no_colons(self):
        """Test strings without colons"""
        result = CharacterReplacement.colon_to_not_sign("FieldValue123")
        assert result == "FieldValue123"
    
    def test_colon_to_not_sign_empty(self):
        """Test empty string"""
        result = CharacterReplacement.colon_to_not_sign("")
        assert result == ""
    
    def test_colon_to_not_sign_none(self):
        """Test None value"""
        result = CharacterReplacement.colon_to_not_sign(None)
        assert result is None
    
    def test_colon_to_not_sign_special_markers(self):
        """Test that special markers are not modified"""
        assert CharacterReplacement.colon_to_not_sign("No Change") == "No Change"
        assert CharacterReplacement.colon_to_not_sign("Client not found") == "Client not found"
        assert CharacterReplacement.colon_to_not_sign("Processing Error") == "Processing Error"
    
    def test_not_sign_to_colon(self):
        """Test reversing NOT SIGN back to colon"""
        input_str = f"Field{chr(172)}Value{chr(172)}123"
        result = CharacterReplacement.not_sign_to_colon(input_str)
        assert result == "Field:Value:123"
        assert chr(172) not in result
    
    def test_not_sign_to_colon_no_not_signs(self):
        """Test strings without NOT SIGN"""
        result = CharacterReplacement.not_sign_to_colon("FieldValue123")
        assert result == "FieldValue123"
    
    def test_not_sign_to_colon_empty(self):
        """Test empty string"""
        result = CharacterReplacement.not_sign_to_colon("")
        assert result == ""
    
    def test_not_sign_to_colon_none(self):
        """Test None value"""
        result = CharacterReplacement.not_sign_to_colon(None)
        assert result is None
    
    def test_round_trip_conversion(self):
        """Test converting colon to NOT SIGN and back"""
        original = "Field:Value:123:Test"
        
        # Convert to NOT SIGN
        with_not_sign = CharacterReplacement.colon_to_not_sign(original)
        assert ":" not in with_not_sign
        assert chr(172) in with_not_sign
        
        # Convert back to colon
        back_to_colon = CharacterReplacement.not_sign_to_colon(with_not_sign)
        assert back_to_colon == original
