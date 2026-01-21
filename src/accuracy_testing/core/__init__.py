"""
Accuracy Testing Core Library
==============================

Phase 1 foundation for accuracy testing workflows.
Provides embedded reference data and validation utilities for:
- Country code lookups (ISO 3166-1 with EEA status)
- ID format validation patterns
- ID validation logic (NIDN, CONCAT, CCPT, LEI)
- Core validators

Version: 1.0.0
Last Updated: January 2026
"""

from .country_codes import Country, CountryDataManager, country_manager
from .id_formats import IDFormatManager, id_format_manager
from .id_validation import (
    IDType,
    IDValidationResult,
    validate_id,
    validate_id_auto,
)
from .validators import (
    ValidationResult,
    validate_not_empty,
    validate_length,
    validate_date_format,
    validate_pattern,
    validate_alphanumeric,
    validate_in_list,
)

__all__ = [
    # Country codes
    "Country",
    "CountryDataManager",
    "country_manager",
    # ID formats
    "IDFormatManager",
    "id_format_manager",
    # ID validation
    "IDType",
    "IDValidationResult",
    "validate_id",
    "validate_id_auto",
    # Validators
    "ValidationResult",
    "validate_not_empty",
    "validate_length",
    "validate_date_format",
    "validate_pattern",
    "validate_alphanumeric",
    "validate_in_list",
]

__version__ = "1.0.0"
