"""
Incident Code Matrix Module
============================

Static incident code mappings for determining client side (buyer/seller).
This replaces the need for an external CSV file.

Data source: incident_code_matrix.csv (legacy)
Last updated: January 2026
"""

from typing import Dict, Set


# Incident code mappings
# Format: incident_code -> set of sides ('buyer', 'seller', or both)
INCIDENT_CODE_MATRIX: Dict[str, Set[str]] = {
    # Buyer incidents
    '7_3': {'buyer'},
    '7_35': {'buyer'},
    '7_36': {'buyer'},
    '7_37': {'buyer'},
    '7_39': {'buyer'},
    '7_43': {'buyer'},
    '7_45': {'buyer'},
    '7_66': {'buyer'},
    '7_68': {'buyer'},
    '7_74': {'buyer'},
    '8_1': {'buyer'},
    '8_2': {'buyer'},
    '8_3': {'buyer'},
    '8_4': {'buyer'},
    '8_6': {'buyer'},
    '8_7': {'buyer'},
    '8_17': {'buyer'},
    '8_19': {'buyer'},
    '8_61': {'buyer'},
    '9_1': {'buyer'},
    '10_1': {'buyer'},
    '11_2': {'buyer'},
    '11_4': {'buyer'},
    '12_1': {'buyer'},
    '12_2': {'buyer'},
    '12_11': {'buyer'},
    '12_17': {'buyer'},
    '12_18': {'buyer'},
    '12_22': {'buyer'},
    '12_24': {'buyer'},
    '12_29': {'buyer'},
    '12_31': {'buyer'},
    '12_35': {'buyer'},
    '12_43': {'buyer'},
    '12_75': {'buyer'},
    '13_1': {'buyer'},
    '14_1': {'buyer'},
    '15_2': {'buyer'},
    '15_4': {'buyer'},
    '21_2': {'buyer'},
    
    # Seller incidents
    '7_11': {'seller'},
    '8_6': {'seller'},  # Note: Also appears as buyer incident
    '8_17': {'seller'},  # Note: Also appears as buyer incident
    '8_19': {'seller'},  # Note: Also appears as buyer incident
    '12_2': {'seller'},  # Note: Also appears as buyer incident
    '16_3': {'seller'},
    '16_18': {'seller'},
    '16_19': {'seller'},
    '16_20': {'seller'},
    '16_21': {'seller'},
    '16_22': {'seller'},
    '16_23': {'seller'},
    '16_24': {'seller'},
    '16_27': {'seller'},
    '16_29': {'seller'},
    '16_37': {'seller'},
    '16_64': {'seller'},
    '17_2': {'seller'},
    '17_7': {'seller'},
    '17_59': {'seller'},
    '18_1': {'seller'},
    '19_1': {'seller'},
    '20_2': {'seller'},
    '20_4': {'seller'},
    '21_1': {'seller'},
    '21_2': {'seller'},  # Note: Also appears as buyer incident
    '21_11': {'seller'},
    '21_16': {'seller'},
    '21_17': {'seller'},
    '21_20': {'seller'},
    '21_22': {'seller'},
    '21_29': {'seller'},
    '21_35': {'seller'},
    '21_43': {'seller'},
    '21_55': {'seller'},
    '21_75': {'seller'},
    '22_1': {'seller'},
    '23_1': {'seller'},
    '24_2': {'seller'},
    '24_4': {'seller'},
    '36_23': {'seller'},
}

# Merge duplicate codes that appear on both sides
_BOTH_SIDE_CODES = {'8_6', '8_17', '8_19', '12_2', '21_2'}
for code in _BOTH_SIDE_CODES:
    INCIDENT_CODE_MATRIX[code] = {'buyer', 'seller'}


def get_client_types(incident_codes: list) -> Set[str]:
    """
    Determine client types (buyer/seller) from a list of incident codes.
    
    Args:
        incident_codes: List of incident code strings (e.g., ['7_3', '16_22'])
        
    Returns:
        Set of client types: {'buyer'}, {'seller'}, or {'buyer', 'seller'}
        Returns empty set if no codes match.
        
    Example:
        >>> get_client_types(['7_3', '7_35'])
        {'buyer'}
        >>> get_client_types(['16_22', '21_1'])
        {'seller'}
        >>> get_client_types(['8_6'])
        {'buyer', 'seller'}
    """
    types = set()
    for code in incident_codes:
        if code in INCIDENT_CODE_MATRIX:
            types.update(INCIDENT_CODE_MATRIX[code])
    return types


def is_buyer_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with buyers."""
    return 'buyer' in INCIDENT_CODE_MATRIX.get(incident_code, set())


def is_seller_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with sellers."""
    return 'seller' in INCIDENT_CODE_MATRIX.get(incident_code, set())


def get_all_incident_codes() -> Set[str]:
    """Get all known incident codes."""
    return set(INCIDENT_CODE_MATRIX.keys())


def get_buyer_incident_codes() -> Set[str]:
    """Get all buyer incident codes."""
    return {code for code, sides in INCIDENT_CODE_MATRIX.items() if 'buyer' in sides}


def get_seller_incident_codes() -> Set[str]:
    """Get all seller incident codes."""
    return {code for code, sides in INCIDENT_CODE_MATRIX.items() if 'seller' in sides}
