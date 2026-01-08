"""
Tests for incident code matrix functionality
"""

import pytest
from txr_replay_core.incident_codes import (
    INCIDENT_CODE_MATRIX,
    get_client_types,
    is_buyer_incident,
    is_seller_incident,
    get_all_incident_codes,
    get_buyer_incident_codes,
    get_seller_incident_codes,
)


class TestIncidentCodeMatrix:
    """Tests for incident code matrix"""
    
    def test_matrix_not_empty(self):
        """Incident matrix should contain codes"""
        assert len(INCIDENT_CODE_MATRIX) > 0
    
    def test_buyer_only_incidents(self):
        """Test buyer-only incident codes"""
        assert get_client_types(['7_3']) == {'buyer'}
        assert get_client_types(['7_35', '7_36']) == {'buyer'}
        assert is_buyer_incident('7_3')
        assert not is_seller_incident('7_3')
    
    def test_seller_only_incidents(self):
        """Test seller-only incident codes"""
        assert get_client_types(['7_11']) == {'seller'}
        assert get_client_types(['16_3', '16_18']) == {'seller'}
        assert is_seller_incident('7_11')
        assert not is_buyer_incident('7_11')
    
    def test_dual_side_incidents(self):
        """Test incidents that appear on both sides"""
        # Codes that appear in both buyer and seller columns
        dual_codes = ['8_6', '8_17', '8_19', '12_2', '21_2']
        for code in dual_codes:
            types = get_client_types([code])
            assert 'buyer' in types, f"{code} should be buyer incident"
            assert 'seller' in types, f"{code} should be seller incident"
            assert is_buyer_incident(code)
            assert is_seller_incident(code)
    
    def test_mixed_incident_list(self):
        """Test with mixed buyer and seller incidents"""
        # Mix of buyer and seller
        types = get_client_types(['7_3', '7_11'])
        assert types == {'buyer', 'seller'}
        
        # Multiple buyers
        types = get_client_types(['7_3', '7_35', '7_36'])
        assert types == {'buyer'}
        
        # Multiple sellers
        types = get_client_types(['7_11', '16_3', '16_18'])
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
        assert len(all_codes) > 0
        assert '7_3' in all_codes
        assert '7_11' in all_codes
    
    def test_get_buyer_codes(self):
        """Test getting buyer incident codes"""
        buyer_codes = get_buyer_incident_codes()
        assert len(buyer_codes) > 0
        assert '7_3' in buyer_codes
        assert '7_35' in buyer_codes
        # Dual-side codes should also be included
        assert '8_6' in buyer_codes
    
    def test_get_seller_codes(self):
        """Test getting seller incident codes"""
        seller_codes = get_seller_incident_codes()
        assert len(seller_codes) > 0
        assert '7_11' in seller_codes
        assert '16_3' in seller_codes
        # Dual-side codes should also be included
        assert '8_6' in seller_codes
    
    def test_matrix_structure(self):
        """Test the structure of the incident matrix"""
        for code, sides in INCIDENT_CODE_MATRIX.items():
            # Each entry should be a set
            assert isinstance(sides, set)
            # Each side should be 'buyer' or 'seller'
            for side in sides:
                assert side in {'buyer', 'seller'}
            # Should have at least one side
            assert len(sides) > 0
    
    def test_specific_known_mappings(self):
        """Test specific known mappings from the original CSV"""
        # From original CSV: 7_3 is buyer, 7_11 is seller
        assert '7_3' in INCIDENT_CODE_MATRIX
        assert 'buyer' in INCIDENT_CODE_MATRIX['7_3']
        
        assert '7_11' in INCIDENT_CODE_MATRIX
        assert 'seller' in INCIDENT_CODE_MATRIX['7_11']
        
        # Last entry: 36_23 is seller only
        assert '36_23' in INCIDENT_CODE_MATRIX
        assert 'seller' in INCIDENT_CODE_MATRIX['36_23']
        assert 'buyer' not in INCIDENT_CODE_MATRIX['36_23']
