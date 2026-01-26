"""
Incident Code Matrix Module
============================

Comprehensive incident code mappings with validation type routing.
This serves as the single source of truth for all incident metadata.

Data source: incident_code_matrix.csv (legacy)
Last updated: January 2026

Validation Types:
- 'standard_id': Standard identification validation (buyer or seller determined by 'sides')
- 'decision_maker': Inconsistent decision maker validation (requires chronological analysis)
- 'pricing': Pricing data validation

The 'sides' parameter determines whether validation is buyer/seller focused.
"""

from typing import Dict, Set, Optional, TypedDict


class IncidentMetadata(TypedDict):
    """Metadata for an incident code."""
    sides: Set[str]  # {'buyer', 'seller', or both}
    validation_type: str  # Type of validation required
    description: str  # Human-readable description


# Incident code mappings with full metadata
# Format: incident_code -> IncidentMetadata
INCIDENT_CODE_MATRIX: Dict[str, IncidentMetadata] = {
    # Standard Buyer ID Incidents (applicable for validation)
    '7_35': {'sides': {'buyer'}, 'validation_type': 'standard_id', 'description': 'Invalid buyer ID format'},
    '7_37': {'sides': {'buyer'}, 'validation_type': 'standard_id', 'description': 'FTBDM - standard txr'},
    '7_39': {'sides': {'buyer'}, 'validation_type': 'standard_id', 'description': 'FTBDM - Financing Trx ID, Seller DUNS'},
    
    # Decision Maker Buyer Incidents (requires chronological analysis)
    '7_66': {'sides': {'buyer'}, 'validation_type': 'decision_maker', 'description': 'Inconsistent buyer decision maker ID'},
    '7_68': {'sides': {'buyer'}, 'validation_type': 'decision_maker', 'description': 'Inconsistent buyer decision maker ID'},
    
    # Standard Seller ID Incidents (applicable for validation)
    '16_19': {'sides': {'seller'}, 'validation_type': 'standard_id', 'description': 'Invalid seller ID format'},
    '16_21': {'sides': {'seller'}, 'validation_type': 'standard_id', 'description': 'FTSDM - standard txr'},
    '16_23': {'sides': {'seller'}, 'validation_type': 'standard_id', 'description': 'FTSDM - Financing Trx ID, Buyer DUNS'},
    
    # Decision Maker Seller Incidents (requires chronological analysis)
    '16_20': {'sides': {'seller'}, 'validation_type': 'decision_maker', 'description': 'Inconsistent seller decision maker ID'},
    '16_64': {'sides': {'seller'}, 'validation_type': 'decision_maker', 'description': 'Inconsistent seller decision maker ID'},
    
    # Pricing Incidents
    '35_3': {'sides': set(), 'validation_type': 'pricing', 'description': 'SCR pricing data validation'},
}


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
            types.update(INCIDENT_CODE_MATRIX[code]['sides'])
    return types


def is_buyer_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with buyers."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return 'buyer' in code_data['sides']
    return False


def is_seller_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with sellers."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return 'seller' in code_data['sides']
    return False


def get_all_incident_codes() -> Set[str]:
    """Get all known incident codes."""
    return set(INCIDENT_CODE_MATRIX.keys())


def get_buyer_incident_codes() -> Set[str]:
    """Get all buyer incident codes."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() if 'buyer' in data['sides']}


def get_seller_incident_codes() -> Set[str]:
    """Get all seller incident codes."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() if 'seller' in data['sides']}


def get_standard_buyer_incident_codes() -> Set[str]:
    """Get buyer incident codes excluding decision maker incidents."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() 
            if 'buyer' in data['sides'] and data['validation_type'] != 'decision_maker'}


def get_standard_seller_incident_codes() -> Set[str]:
    """Get seller incident codes excluding decision maker incidents."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() 
            if 'seller' in data['sides'] and data['validation_type'] != 'decision_maker'}


def get_decision_maker_buyer_codes() -> Set[str]:
    """Get buyer decision maker incident codes (7_66, 7_68)."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() 
            if 'buyer' in data['sides'] and data['validation_type'] == 'decision_maker'}


def get_decision_maker_seller_codes() -> Set[str]:
    """Get seller decision maker incident codes (16_20, 16_64)."""
    return {code for code, data in INCIDENT_CODE_MATRIX.items() 
            if 'seller' in data['sides'] and data['validation_type'] == 'decision_maker'}


def is_decision_maker_incident(incident_code: str) -> bool:
    """Check if an incident code is a decision maker incident."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data['validation_type'] == 'decision_maker'
    return False


# New validation type routing functions

def get_validation_type(incident_code: str) -> Optional[str]:
    """
    Get the validation type for an incident code.
    
    Args:
        incident_code: Incident code string (e.g., '7_37')
        
    Returns:
        Validation type string ('standard_id', 'decision_maker', 'pricing')
        or None if code not found.
        
    Example:
        >>> get_validation_type('7_37')
        'standard_id'
        >>> get_validation_type('7_66')
        'decision_maker'
        >>> get_validation_type('35_3')
        'pricing'
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data['validation_type']
    return None


def get_incidents_by_validation_type(validation_type: str) -> Set[str]:
    """
    Get all incident codes requiring a specific validation type.
    
    Args:
        validation_type: Type of validation ('standard_id', 'decision_maker', 'pricing')
        
    Returns:
        Set of incident codes matching the validation type.
        
    Example:
        >>> sorted(get_incidents_by_validation_type('decision_maker'))
        ['16_20', '16_64', '7_66', '7_68']
        >>> get_incidents_by_validation_type('pricing')
        {'35_3'}
        >>> sorted(get_incidents_by_validation_type('standard_id'))
        ['16_19', '16_21', '16_23', '7_35', '7_37', '7_39']
    """
    return {code for code, data in INCIDENT_CODE_MATRIX.items() 
            if data['validation_type'] == validation_type}


def get_incident_description(incident_code: str) -> Optional[str]:
    """
    Get the description for an incident code.
    
    Args:
        incident_code: Incident code string (e.g., '7_37')
        
    Returns:
        Description string or None if code not found.
        
    Example:
        >>> get_incident_description('7_37')
        'FTBDM - standard txr'
        >>> get_incident_description('7_66')
        'Inconsistent buyer decision maker ID'
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data['description']
    return None


def get_available_validation_types() -> Set[str]:
    """
    Get all available validation types in the system.
    
    Returns:
        Set of validation type strings.
        
    Example:
        >>> sorted(get_available_validation_types())
        ['decision_maker', 'pricing', 'standard_id']
    """
    return {data['validation_type'] for data in INCIDENT_CODE_MATRIX.values()}

