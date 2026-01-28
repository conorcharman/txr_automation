"""
Reference Data
==============

Embedded reference data for validation and processing.

Modules:
    country_codes: ISO 3166-1 country codes with EEA status
    id_formats: ID format validation regex patterns
    incident_codes: Incident code matrix with buyer/seller mappings
    data_structures: Common dataclasses for replay and accuracy testing

This is the canonical location for reference data.
"""

# Data structures
from core.data.data_structures import (
    ReplayRecord,
    LookupResult,
    UnaVistaTransaction,
    ProcessingStats,
)

# Country codes reference data
from core.data.country_codes import (
    Country,
    CountryDataManager,
    country_manager,
    COUNTRIES,
)

# ID format validation patterns
from core.data.id_formats import (
    IDPattern,
    IDFormatManager,
    id_format_manager,
    ID_PATTERNS,
)

# Incident code matrix
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
    get_inconsistent_buyer_incident_codes,
    get_inconsistent_seller_incident_codes,
    is_inconsistent_id_incident,
    get_validation_type,
    get_incidents_by_validation_type,
    get_incident_description,
    get_available_validation_types,
)

# Constants - magic number replacements
from core.data.constants import (
    # ID lengths by country
    ID_LENGTHS,
    IDLength,
    IDSlice,
    # ID slice positions by country
    DOBSlices,
    BE_SLICES,
    BG_SLICES,
    CZ_SLICES,
    EE_SLICES,
    FI_SLICES,
    IT_SLICES,
    LT_SLICES,
    LV_SLICES,
    PL_SLICES,
    RO_SLICES,
    SE_SLICES,
    SK_SLICES,
    SI_SLICES,
    # Column indices
    Phase3Columns,
    Phase2SingleColumns,
    Phase2CombinedColumns,
    ClientErrorColumns,
    # Validation thresholds
    ValidationThresholds,
    # Country-specific mappings
    IT_MONTH_LETTERS,
    IT_MONTH_NUMBERS,
    FI_CENTURY_MARKERS,
    LT_CENTURY_GENDER_CODES,
    LV_CENTURY_CODES,
)

__all__ = [
    # Data structures
    "ReplayRecord",
    "LookupResult",
    "UnaVistaTransaction",
    "ProcessingStats",
    # Country codes
    "Country",
    "CountryDataManager",
    "country_manager",
    "COUNTRIES",
    # ID formats
    "IDPattern",
    "IDFormatManager",
    "id_format_manager",
    "ID_PATTERNS",
    # Incident codes
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
    "get_inconsistent_buyer_incident_codes",
    "get_inconsistent_seller_incident_codes",
    "is_inconsistent_id_incident",
    # Constants
    "ID_LENGTHS",
    "IDLength",
    "IDSlice",
    "DOBSlices",
    "BE_SLICES",
    "BG_SLICES",
    "CZ_SLICES",
    "EE_SLICES",
    "FI_SLICES",
    "IT_SLICES",
    "LT_SLICES",
    "LV_SLICES",
    "PL_SLICES",
    "RO_SLICES",
    "SE_SLICES",
    "SK_SLICES",
    "SI_SLICES",
    "Phase3Columns",
    "Phase2SingleColumns",
    "Phase2CombinedColumns",
    "ClientErrorColumns",
    "ValidationThresholds",
    "IT_MONTH_LETTERS",
    "IT_MONTH_NUMBERS",
    "FI_CENTURY_MARKERS",
    "LT_CENTURY_GENDER_CODES",
    "LV_CENTURY_CODES",
]
