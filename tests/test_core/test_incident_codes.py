"""
Tests for incident code matrix functionality

Tests the implemented incident codes:
- Buyer ID: 7_35, 7_37, 7_39 (standard_id)
- Buyer Decision Maker: 12_17 (decision_maker)
- Buyer Pending: 7_66 (pending)
- Seller ID: 16_19, 16_21, 16_23 (standard_id)
- Seller Decision Maker: 21_17 (decision_maker)
- Seller Pending: 16_20 (pending)
- Pricing: 35_3 (pricing)
"""

import pytest
from core import (
    INCIDENT_CODE_MATRIX,
    get_client_types,
    is_buyer_incident,
    is_seller_incident,
    get_all_incident_codes,
    get_buyer_incident_codes,
    get_seller_incident_codes,
    get_validation_type,
)


class TestIncidentCodeMatrix:
    """Tests for incident code matrix"""
    
    def test_matrix_not_empty(self):
        """Incident matrix should contain codes"""
        assert len(INCIDENT_CODE_MATRIX) > 0
        # Currently 13 implemented codes
        assert len(INCIDENT_CODE_MATRIX) == 13
    
    def test_buyer_only_incidents(self):
        """Test buyer-only incident codes"""
        # Standard ID buyer codes
        assert get_client_types(['7_35']) == {'buyer'}
        assert get_client_types(['7_37']) == {'buyer'}
        assert get_client_types(['7_39']) == {'buyer'}
        assert get_client_types(['7_35', '7_37', '7_39']) == {'buyer'}
        
        # Decision maker buyer code
        assert get_client_types(['12_17']) == {'buyer'}
        
        assert is_buyer_incident('7_35')
        assert not is_seller_incident('7_35')
    
    def test_seller_only_incidents(self):
        """Test seller-only incident codes"""
        # Standard ID seller codes
        assert get_client_types(['16_19']) == {'seller'}
        assert get_client_types(['16_21']) == {'seller'}
        assert get_client_types(['16_23']) == {'seller'}
        
        # Decision maker seller code
        assert get_client_types(['21_17']) == {'seller'}
        
        # Pricing code (seller side)
        assert get_client_types(['35_3']) == {'seller'}
        
        assert is_seller_incident('16_19')
        assert not is_buyer_incident('16_19')
    
    def test_mixed_incident_list(self):
        """Test with mixed buyer and seller incidents"""
        # Mix of buyer and seller
        types = get_client_types(['7_35', '16_19'])
        assert types == {'buyer', 'seller'}
        
        # Multiple buyers
        types = get_client_types(['7_35', '7_37', '12_17'])
        assert types == {'buyer'}
        
        # Multiple sellers
        types = get_client_types(['16_19', '16_21', '35_3'])
        assert types == {'seller'}
    
    def test_unknown_incident_code(self):
        """Test with unknown incident code"""
        assert get_client_types(['999_999']) == set()
        assert not is_buyer_incident('999_999')
        assert not is_seller_incident('999_999')
    
    def test_empty_list(self):
        """Test with empty incident code list"""
        assert get_client_types([]) == set()
    
    def test_get_all_codes(self):
        """Test getting all incident codes"""
        all_codes = get_all_incident_codes()
        assert len(all_codes) == 13
        # Buyer codes
        assert '7_35' in all_codes
        assert '7_37' in all_codes
        assert '7_39' in all_codes
        assert '7_66' in all_codes
        assert '12_17' in all_codes
        # Seller codes
        assert '16_19' in all_codes
        assert '16_21' in all_codes
        assert '16_23' in all_codes
        assert '16_20' in all_codes
        assert '21_17' in all_codes
        # Pricing
        assert '35_3' in all_codes
        # Non-Zero Net incidents (buyer+seller)
        assert '7_6' in all_codes
        assert '7_42' in all_codes
    
    def test_get_buyer_codes(self):
        """Test getting buyer incident codes"""
        buyer_codes = get_buyer_incident_codes()
        assert len(buyer_codes) == 7
        assert '7_35' in buyer_codes
        assert '7_37' in buyer_codes
        assert '7_39' in buyer_codes
        assert '7_66' in buyer_codes
        assert '12_17' in buyer_codes
        assert '7_6' in buyer_codes
        assert '7_42' in buyer_codes
    
    def test_get_seller_codes(self):
        """Test getting seller incident codes"""
        seller_codes = get_seller_incident_codes()
        assert len(seller_codes) == 8
        assert '16_19' in seller_codes
        assert '16_21' in seller_codes
        assert '16_23' in seller_codes
        assert '16_20' in seller_codes
        assert '21_17' in seller_codes
        assert '35_3' in seller_codes
        assert '7_6' in seller_codes
        assert '7_42' in seller_codes
    
    def test_matrix_structure(self):
        """Test the structure of the incident matrix"""
        for code, metadata in INCIDENT_CODE_MATRIX.items():
            # Each entry should be a dict with required keys
            assert isinstance(metadata, dict)
            assert 'sides' in metadata
            assert 'validation_type' in metadata
            assert 'description' in metadata
            
            # Sides should be a set
            assert isinstance(metadata['sides'], set)
            # Each side should be 'buyer' or 'seller'
            for side in metadata['sides']:
                assert side in {'buyer', 'seller'}
    
    def test_validation_types(self):
        """Test validation type assignments"""
        # Standard ID codes
        assert get_validation_type('7_35') == 'standard_id'
        assert get_validation_type('7_37') == 'standard_id'
        assert get_validation_type('16_19') == 'standard_id'
        
        # Decision maker codes
        assert get_validation_type('12_17') == 'decision_maker'
        assert get_validation_type('21_17') == 'decision_maker'
        
        # Inconsistent ID codes (Phase 4 implementation)
        assert get_validation_type('7_66') == 'inconsistent_id'
        assert get_validation_type('16_20') == 'inconsistent_id'
        
        # Pricing code
        assert get_validation_type('35_3') == 'pricing'
    
    def test_specific_known_mappings(self):
        """Test specific known mappings"""
        # Buyer CONCAT
        assert '7_35' in INCIDENT_CODE_MATRIX
        assert 'buyer' in INCIDENT_CODE_MATRIX['7_35']['sides']
        assert INCIDENT_CODE_MATRIX['7_35']['description'] == 'Incorrect CONCAT value within Buyer identification code field'
        
        # Seller NIDN
        assert '16_21' in INCIDENT_CODE_MATRIX
        assert 'seller' in INCIDENT_CODE_MATRIX['16_21']['sides']
        assert INCIDENT_CODE_MATRIX['16_21']['description'] == 'Incorrect NIDN value within Seller identification code field'
        
        # Pricing
        assert '35_3' in INCIDENT_CODE_MATRIX
        assert 'seller' in INCIDENT_CODE_MATRIX['35_3']['sides']
        assert INCIDENT_CODE_MATRIX['35_3']['description'] == 'Incorrect net amount'
