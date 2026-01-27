"""
Incident Code Matrix Module
============================

BACKWARD COMPATIBILITY MODULE
-----------------------------
This module now re-exports from the canonical location: core.data.incident_codes

All functions and data are maintained for backward compatibility.
New code should import directly from core.data:
    from core.data import INCIDENT_CODE_MATRIX, get_client_types, ...
"""

# Try different import paths for flexibility (installed package vs development)
try:
    # When imported as installed package (txr_replay_core.incident_codes)
    from core.data.incident_codes import (
        IncidentMetadata,
        INCIDENT_CODE_MATRIX,
        get_client_types,
        is_buyer_incident,
        is_seller_incident,
        get_all_incident_codes,
        get_buyer_incident_codes,
        get_seller_incident_codes,
        get_standard_buyer_incident_codes,
        get_standard_seller_incident_codes,
        get_decision_maker_buyer_codes,
        get_decision_maker_seller_codes,
        is_decision_maker_incident,
        get_validation_type,
        get_incidents_by_validation_type,
        get_incident_description,
        get_available_validation_types,
    )
except ImportError:
    # When imported from workspace root (src.txr_replay_core.incident_codes)
    from src.core.data.incident_codes import (
        IncidentMetadata,
        INCIDENT_CODE_MATRIX,
        get_client_types,
        is_buyer_incident,
        is_seller_incident,
        get_all_incident_codes,
        get_buyer_incident_codes,
        get_seller_incident_codes,
        get_standard_buyer_incident_codes,
        get_standard_seller_incident_codes,
        get_decision_maker_buyer_codes,
        get_decision_maker_seller_codes,
        is_decision_maker_incident,
        get_validation_type,
        get_incidents_by_validation_type,
        get_incident_description,
        get_available_validation_types,
    )

__all__ = [
    "IncidentMetadata",
    "INCIDENT_CODE_MATRIX",
    "get_client_types",
    "is_buyer_incident",
    "is_seller_incident",
    "get_all_incident_codes",
    "get_buyer_incident_codes",
    "get_seller_incident_codes",
    "get_standard_buyer_incident_codes",
    "get_standard_seller_incident_codes",
    "get_decision_maker_buyer_codes",
    "get_decision_maker_seller_codes",
    "is_decision_maker_incident",
    "get_validation_type",
    "get_incidents_by_validation_type",
    "get_incident_description",
    "get_available_validation_types",
]
