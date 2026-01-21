"""
ID Code Validation
==================

High-level ID validation logic that combines country codes, ID formats,
and core validators to provide comprehensive ID validation.

Validates identification codes (NIDN, CONCAT, CCPT, LEI) against:
- Country-specific format patterns
- Country code validity
- ID type compatibility
- Business rules and edge cases
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from .country_codes import CountryDataManager, country_manager
from .id_formats import IDFormatManager, id_format_manager
from .validators import ValidationResult, validate_not_empty, validate_length


class IDType(Enum):
    """Supported ID types for validation."""
    NIDN = "NIDN"  # National Identity Number
    CONCAT = "CONCAT"  # Concatenated identifier
    CCPT = "CCPT"  # Client Code/Passport
    LEI = "LEI"  # Legal Entity Identifier
    
    @classmethod
    def from_string(cls, value: str) -> Optional['IDType']:
        """Convert string to IDType enum."""
        try:
            return cls(value.upper())
        except (ValueError, AttributeError):
            return None


@dataclass
class IDValidationResult:
    """
    Comprehensive ID validation result.
    
    Attributes:
        is_valid: Whether ID passed all validations
        id_value: The ID value that was validated
        country_code: Country code used for validation
        id_type: ID type used for validation
        detected_type: Auto-detected ID type (if any)
        errors: List of validation error messages
        warnings: List of validation warnings
    """
    is_valid: bool
    id_value: str
    country_code: Optional[str] = None
    id_type: Optional[str] = None
    detected_type: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        """Initialize empty lists if not provided."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def __bool__(self) -> bool:
        """Allow IDValidationResult to be used in boolean context."""
        return self.is_valid
    
    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    @property
    def primary_error(self) -> Optional[str]:
        """Get the first error message."""
        return self.errors[0] if self.errors else None
    
    def __repr__(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return (f"IDValidationResult({status}, id={self.id_value!r}, "
                f"country={self.country_code}, type={self.id_type})")


class IDValidator:
    """
    High-level ID validator using country and format managers.
    
    Usage:
        validator = IDValidator()
        
        # Validate with known country and type
        result = validator.validate("GB", "NIDN", "AB123456C")
        
        # Auto-detect ID type
        result = validator.validate_auto_detect("GB", "AB123456C")
        
        # Validate LEI
        result = validator.validate_lei("12345678901234567890")
    """
    
    def __init__(
        self,
        country_manager: CountryDataManager = None,
        format_manager: IDFormatManager = None
    ):
        """
        Initialize validator with managers.
        
        Args:
            country_manager: Country data manager (uses singleton if not provided)
            format_manager: ID format manager (uses singleton if not provided)
        """
        from .country_codes import country_manager as default_country_manager
        from .id_formats import id_format_manager as default_format_manager
        
        self.country_manager = country_manager or default_country_manager
        self.format_manager = format_manager or default_format_manager
    
    def validate(
        self,
        country_code: str,
        id_type: str,
        id_value: str,
        strict: bool = True
    ) -> IDValidationResult:
        """
        Validate an ID code against specific country and type.
        
        Args:
            country_code: Two-letter country code (e.g., "GB")
            id_type: ID type (NIDN, CONCAT, CCPT, LEI)
            id_value: The ID value to validate
            strict: If True, enforce strict validation rules
        
        Returns:
            IDValidationResult with validation details
        """
        result = IDValidationResult(
            is_valid=True,
            id_value=id_value,
            country_code=country_code.upper() if country_code else None,
            id_type=id_type.upper() if id_type else None
        )
        
        # Basic validation
        empty_check = validate_not_empty(id_value, "ID value")
        if not empty_check:
            result.add_error(empty_check.error_message)
            return result
        
        # Use trimmed value
        id_value = empty_check.corrected_value
        result.id_value = id_value
        
        # Validate country code (skip for LEI)
        if id_type.upper() != "LEI" and country_code:
            if not self.country_manager.validate_code(country_code):
                result.add_error(f"Invalid country code: {country_code}")
                return result
        
        # Validate ID type
        id_type_enum = IDType.from_string(id_type)
        if not id_type_enum:
            result.add_error(f"Invalid ID type: {id_type}")
            return result
        
        # Check format patterns with detailed error reporting
        is_valid, error_detail = self.format_manager.validate_with_details(country_code or "", id_type, id_value)
        if not is_valid:
            # Use detailed error message
            result.add_error(error_detail if error_detail else f"ID value does not match {id_type} format for country {country_code}")
            
            # Suggest alternative if not strict
            if not strict:
                detected = self.format_manager.validate_any_type(country_code, id_value)
                if detected:
                    result.add_warning(
                        f"ID matches {detected} format instead of {id_type}"
                    )
                    result.detected_type = detected
        
        return result
    
    def validate_auto_detect(
        self,
        country_code: str,
        id_value: str
    ) -> IDValidationResult:
        """
        Validate an ID and auto-detect its type.
        
        Args:
            country_code: Two-letter country code
            id_value: The ID value to validate
        
        Returns:
            IDValidationResult with detected type
        """
        result = IDValidationResult(
            is_valid=False,
            id_value=id_value,
            country_code=country_code.upper() if country_code else None
        )
        
        # Basic validation
        empty_check = validate_not_empty(id_value, "ID value")
        if not empty_check:
            result.add_error(empty_check.error_message)
            return result
        
        id_value = empty_check.corrected_value
        result.id_value = id_value
        
        # Validate country code
        if not self.country_manager.validate_code(country_code):
            result.add_error(f"Invalid country code: {country_code}")
            return result
        
        # Try to detect ID type
        detected_type = self.format_manager.validate_any_type(country_code, id_value)
        
        if detected_type:
            result.is_valid = True
            result.id_type = detected_type
            result.detected_type = detected_type
        else:
            result.add_error(
                f"ID value does not match any known format for country {country_code}"
            )
            
            # List available types for this country
            available_types = self.format_manager.get_id_types_for_country(country_code)
            if available_types:
                result.add_warning(
                    f"Available ID types for {country_code}: {', '.join(available_types)}"
                )
        
        return result
    
    def validate_lei(self, lei_value: str) -> IDValidationResult:
        """
        Validate a Legal Entity Identifier (LEI).
        
        Args:
            lei_value: The LEI to validate (20 characters)
        
        Returns:
            IDValidationResult for LEI
        """
        result = IDValidationResult(
            is_valid=True,
            id_value=lei_value,
            id_type="LEI"
        )
        
        # Basic validation
        empty_check = validate_not_empty(lei_value, "LEI")
        if not empty_check:
            result.add_error(empty_check.error_message)
            return result
        
        lei_value = empty_check.corrected_value
        result.id_value = lei_value
        
        # Length check
        length_check = validate_length(lei_value, 20, 20, "LEI")
        if not length_check:
            result.add_error(length_check.error_message)
            return result
        
        # Format validation
        if not self.format_manager.validate_lei(lei_value):
            result.add_error("LEI does not match required format")
        
        return result
    
    def validate_batch(
        self,
        validations: List[Tuple[str, str, str]]
    ) -> List[IDValidationResult]:
        """
        Validate multiple IDs in batch.
        
        Args:
            validations: List of (country_code, id_type, id_value) tuples
        
        Returns:
            List of IDValidationResult objects
        """
        return [
            self.validate(country, id_type, id_value)
            for country, id_type, id_value in validations
        ]
    
    def get_supported_types_for_country(self, country_code: str) -> List[str]:
        """
        Get all supported ID types for a country.
        
        Args:
            country_code: Two-letter country code
        
        Returns:
            List of supported ID type strings
        """
        return self.format_manager.get_id_types_for_country(country_code)
    
    def is_eea_country(self, country_code: str) -> bool:
        """
        Check if country is in European Economic Area.
        
        Args:
            country_code: Two-letter country code
        
        Returns:
            True if country is in EEA
        """
        return self.country_manager.is_eea(country_code)


# Pre-instantiate validator for convenient imports
id_validator = IDValidator()


# ============================================================================
# Convenience Functions
# ============================================================================

def validate_id(
    country_code: str,
    id_type: str,
    id_value: str,
    strict: bool = True
) -> IDValidationResult:
    """
    Convenience function for ID validation.
    
    Args:
        country_code: Two-letter country code
        id_type: ID type (NIDN, CONCAT, CCPT, LEI)
        id_value: The ID value to validate
        strict: If True, enforce strict validation
    
    Returns:
        IDValidationResult
    """
    return id_validator.validate(country_code, id_type, id_value, strict)


def validate_id_auto(country_code: str, id_value: str) -> IDValidationResult:
    """
    Convenience function for auto-detecting ID type.
    
    Args:
        country_code: Two-letter country code
        id_value: The ID value to validate
    
    Returns:
        IDValidationResult with detected type
    """
    return id_validator.validate_auto_detect(country_code, id_value)


def validate_lei(lei_value: str) -> IDValidationResult:
    """
    Convenience function for LEI validation.
    
    Args:
        lei_value: The LEI to validate
    
    Returns:
        IDValidationResult
    """
    return id_validator.validate_lei(lei_value)
