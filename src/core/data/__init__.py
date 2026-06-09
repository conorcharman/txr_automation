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

# Constants - magic number replacements
from core.data.constants import (  # ID lengths by country; ID slice positions by country; Column indices; Validation thresholds; Country-specific mappings
    BE_SLICES,
    BG_SLICES,
    CZ_SLICES,
    EE_SLICES,
    FI_CENTURY_MARKERS,
    FI_SLICES,
    ID_LENGTHS,
    IT_MONTH_LETTERS,
    IT_MONTH_NUMBERS,
    IT_SLICES,
    LT_CENTURY_GENDER_CODES,
    LT_SLICES,
    LV_CENTURY_CODES,
    LV_SLICES,
    PL_SLICES,
    RO_SLICES,
    SE_SLICES,
    SI_SLICES,
    SK_SLICES,
    ClientErrorColumns,
    DOBSlices,
    IDLength,
    IDSlice,
    Phase2CombinedColumns,
    Phase2SingleColumns,
    Phase3Columns,
    ValidationThresholds,
)

# Country codes reference data
from core.data.country_codes import (
    COUNTRIES,
    Country,
    CountryDataManager,
    country_manager,
)

# Data structures
from core.data.data_structures import (
    LookupResult,
    ProcessingStats,
    ReplayRecord,
    UnaVistaTransaction,
)

# ID format validation patterns
from core.data.id_formats import (
    ID_PATTERNS,
    IDFormatManager,
    IDPattern,
    id_format_manager,
)

# Incident code matrix
from core.data.incident_codes import (
    INCIDENT_CODE_MATRIX,
    IncidentMetadata,
    get_all_incident_codes,
    get_available_validation_types,
    get_buyer_incident_codes,
    get_client_types,
    get_decision_maker_buyer_codes,
    get_decision_maker_seller_codes,
    get_incident_description,
    get_incidents_by_validation_type,
    get_inconsistent_buyer_incident_codes,
    get_inconsistent_seller_incident_codes,
    get_seller_incident_codes,
    get_standard_buyer_incident_codes,
    get_standard_seller_incident_codes,
    get_validation_type,
    is_buyer_incident,
    is_decision_maker_incident,
    is_inconsistent_id_incident,
    is_seller_incident,
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
