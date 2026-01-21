"""
Core Validation Functions
==========================

Shared validation logic used across transaction reporting automation scripts.
Provides common validation functions for dates, names, fields, and business rules.

These validators are designed to be:
- Pure functions (no side effects)
- Type-hinted for clarity
- Composable and reusable
- Well-documented with examples
"""

from typing import Optional, List, Tuple, Any
from datetime import datetime, date
import re


class ValidationResult:
    """
    Result of a validation operation.
    
    Attributes:
        is_valid: Whether validation passed
        error_message: Optional error message if validation failed
        corrected_value: Optional corrected value if validation can suggest a fix
    """
    
    def __init__(
        self,
        is_valid: bool,
        error_message: Optional[str] = None,
        corrected_value: Optional[Any] = None
    ):
        self.is_valid = is_valid
        self.error_message = error_message
        self.corrected_value = corrected_value
    
    def __bool__(self) -> bool:
        """Allow ValidationResult to be used in boolean context."""
        return self.is_valid
    
    def __repr__(self) -> str:
        return (f"ValidationResult(is_valid={self.is_valid}, "
                f"error_message={self.error_message!r}, "
                f"corrected_value={self.corrected_value!r})")
    
    @classmethod
    def success(cls, corrected_value: Optional[Any] = None) -> 'ValidationResult':
        """Create a successful validation result."""
        return cls(True, None, corrected_value)
    
    @classmethod
    def failure(cls, error_message: str) -> 'ValidationResult':
        """Create a failed validation result."""
        return cls(False, error_message, None)


# ============================================================================
# Date Validation
# ============================================================================

def validate_date_format(
    date_string: str,
    format_string: str = "%Y-%m-%d"
) -> ValidationResult:
    """
    Validate date string matches expected format.
    
    Args:
        date_string: Date string to validate
        format_string: Expected date format (default: ISO format)
    
    Returns:
        ValidationResult with parsed date as corrected_value if valid
    
    Example:
        >>> result = validate_date_format("2024-01-15")
        >>> result.is_valid
        True
        >>> result.corrected_value
        datetime.date(2024, 1, 15)
    """
    if not date_string or not isinstance(date_string, str):
        return ValidationResult.failure("Date string is empty or not a string")
    
    try:
        parsed_date = datetime.strptime(date_string.strip(), format_string).date()
        return ValidationResult.success(parsed_date)
    except ValueError as e:
        return ValidationResult.failure(f"Invalid date format: {e}")


def validate_date_range(
    date_value: date,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None
) -> ValidationResult:
    """
    Validate date falls within specified range.
    
    Args:
        date_value: Date to validate
        min_date: Minimum allowed date (inclusive)
        max_date: Maximum allowed date (inclusive)
    
    Returns:
        ValidationResult indicating if date is in range
    """
    if min_date and date_value < min_date:
        return ValidationResult.failure(
            f"Date {date_value} is before minimum date {min_date}"
        )
    
    if max_date and date_value > max_date:
        return ValidationResult.failure(
            f"Date {date_value} is after maximum date {max_date}"
        )
    
    return ValidationResult.success()


def validate_date_not_future(date_value: date) -> ValidationResult:
    """
    Validate date is not in the future.
    
    Args:
        date_value: Date to validate
    
    Returns:
        ValidationResult indicating if date is not future
    """
    today = date.today()
    if date_value > today:
        return ValidationResult.failure(
            f"Date {date_value} is in the future (today: {today})"
        )
    return ValidationResult.success()


# ============================================================================
# String Validation
# ============================================================================

def validate_not_empty(value: str, field_name: str = "Field") -> ValidationResult:
    """
    Validate string is not empty or whitespace-only.
    
    Args:
        value: String to validate
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult with trimmed value if valid
    """
    if not value or not isinstance(value, str):
        return ValidationResult.failure(f"{field_name} is empty or not a string")
    
    trimmed = value.strip()
    if not trimmed:
        return ValidationResult.failure(f"{field_name} contains only whitespace")
    
    return ValidationResult.success(trimmed)


def validate_length(
    value: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    field_name: str = "Field"
) -> ValidationResult:
    """
    Validate string length is within specified bounds.
    
    Args:
        value: String to validate
        min_length: Minimum length (inclusive)
        max_length: Maximum length (inclusive)
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if length is valid
    """
    length = len(value)
    
    if min_length is not None and length < min_length:
        return ValidationResult.failure(
            f"{field_name} length ({length}) is less than minimum ({min_length})"
        )
    
    if max_length is not None and length > max_length:
        return ValidationResult.failure(
            f"{field_name} length ({length}) exceeds maximum ({max_length})"
        )
    
    return ValidationResult.success()


def validate_pattern(
    value: str,
    pattern: str,
    field_name: str = "Field"
) -> ValidationResult:
    """
    Validate string matches regex pattern.
    
    Args:
        value: String to validate
        pattern: Regex pattern to match
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if pattern matches
    """
    try:
        compiled = re.compile(pattern)
        if compiled.match(value):
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                f"{field_name} does not match pattern: {pattern}"
            )
    except re.error as e:
        return ValidationResult.failure(f"Invalid regex pattern: {e}")


def validate_alphanumeric(
    value: str,
    allow_spaces: bool = False,
    field_name: str = "Field"
) -> ValidationResult:
    """
    Validate string contains only alphanumeric characters.
    
    Args:
        value: String to validate
        allow_spaces: Whether to allow space characters
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if string is alphanumeric
    """
    if allow_spaces:
        is_valid = all(c.isalnum() or c.isspace() for c in value)
    else:
        is_valid = value.isalnum()
    
    if not is_valid:
        allowed = "alphanumeric" + (" and spaces" if allow_spaces else "")
        return ValidationResult.failure(
            f"{field_name} contains non-{allowed} characters"
        )
    
    return ValidationResult.success()


# ============================================================================
# Numeric Validation
# ============================================================================

def validate_numeric_range(
    value: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    field_name: str = "Field"
) -> ValidationResult:
    """
    Validate numeric value falls within specified range.
    
    Args:
        value: Numeric value to validate
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if value is in range
    """
    if min_value is not None and value < min_value:
        return ValidationResult.failure(
            f"{field_name} ({value}) is less than minimum ({min_value})"
        )
    
    if max_value is not None and value > max_value:
        return ValidationResult.failure(
            f"{field_name} ({value}) exceeds maximum ({max_value})"
        )
    
    return ValidationResult.success()


def validate_positive(value: float, field_name: str = "Field") -> ValidationResult:
    """
    Validate numeric value is positive (> 0).
    
    Args:
        value: Numeric value to validate
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if value is positive
    """
    if value <= 0:
        return ValidationResult.failure(f"{field_name} must be positive (got {value})")
    return ValidationResult.success()


def validate_non_negative(value: float, field_name: str = "Field") -> ValidationResult:
    """
    Validate numeric value is non-negative (>= 0).
    
    Args:
        value: Numeric value to validate
        field_name: Name of field for error messages
    
    Returns:
        ValidationResult indicating if value is non-negative
    """
    if value < 0:
        return ValidationResult.failure(
            f"{field_name} must be non-negative (got {value})"
        )
    return ValidationResult.success()


# ============================================================================
# List/Choice Validation
# ============================================================================

def validate_in_list(
    value: Any,
    valid_values: List[Any],
    field_name: str = "Field",
    case_sensitive: bool = True
) -> ValidationResult:
    """
    Validate value is in a list of allowed values.
    
    Args:
        value: Value to validate
        valid_values: List of allowed values
        field_name: Name of field for error messages
        case_sensitive: Whether comparison is case-sensitive (for strings)
    
    Returns:
        ValidationResult with normalized value if valid
    """
    if not case_sensitive and isinstance(value, str):
        # Case-insensitive comparison for strings
        value_upper = value.upper()
        valid_upper = [v.upper() if isinstance(v, str) else v for v in valid_values]
        
        if value_upper in valid_upper:
            # Return the canonical value from valid_values
            idx = valid_upper.index(value_upper)
            return ValidationResult.success(valid_values[idx])
        else:
            return ValidationResult.failure(
                f"{field_name} '{value}' is not in allowed values: {valid_values}"
            )
    else:
        if value in valid_values:
            return ValidationResult.success(value)
        else:
            return ValidationResult.failure(
                f"{field_name} '{value}' is not in allowed values: {valid_values}"
            )


# ============================================================================
# Combined Validation
# ============================================================================

def validate_all(*validators: ValidationResult) -> ValidationResult:
    """
    Combine multiple validation results with AND logic.
    Returns first failure, or success if all pass.
    
    Args:
        *validators: Variable number of ValidationResult objects
    
    Returns:
        First failed ValidationResult, or success if all pass
    """
    for validator in validators:
        if not validator.is_valid:
            return validator
    return ValidationResult.success()


def validate_any(*validators: ValidationResult) -> ValidationResult:
    """
    Combine multiple validation results with OR logic.
    Returns first success, or combined failure if all fail.
    
    Args:
        *validators: Variable number of ValidationResult objects
    
    Returns:
        First successful ValidationResult, or combined failure
    """
    errors = []
    for validator in validators:
        if validator.is_valid:
            return validator
        if validator.error_message:
            errors.append(validator.error_message)
    
    combined_error = " AND ".join(errors) if errors else "All validations failed"
    return ValidationResult.failure(combined_error)


# ============================================================================
# Special Field Validators
# ============================================================================

def validate_gender(gender: str) -> ValidationResult:
    """
    Validate gender code.
    
    Args:
        gender: Gender code to validate (M, F, or other accepted values)
    
    Returns:
        ValidationResult with normalized gender code
    """
    valid_genders = ["M", "F", "MALE", "FEMALE", "X", "OTHER"]
    result = validate_in_list(gender, valid_genders, "Gender", case_sensitive=False)
    
    # Normalize to single character codes
    if result.is_valid and result.corrected_value:
        normalized = result.corrected_value.upper()
        if normalized in ["M", "MALE"]:
            return ValidationResult.success("M")
        elif normalized in ["F", "FEMALE"]:
            return ValidationResult.success("F")
        else:
            return ValidationResult.success("X")
    
    return result


def validate_email(email: str) -> ValidationResult:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
    
    Returns:
        ValidationResult indicating if email format is valid
    """
    # Simple email pattern (not RFC 5322 compliant, but practical)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return validate_pattern(email, pattern, "Email")


def validate_phone(phone: str, allow_international: bool = True) -> ValidationResult:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        allow_international: Whether to allow international format (+XXX)
    
    Returns:
        ValidationResult with normalized phone number
    """
    # Remove common separators
    normalized = re.sub(r'[\s\-\(\)\.]+', '', phone)
    
    if allow_international:
        pattern = r'^\+?[0-9]{7,15}$'
    else:
        pattern = r'^[0-9]{7,15}$'
    
    result = validate_pattern(normalized, pattern, "Phone number")
    if result.is_valid:
        return ValidationResult.success(normalized)
    return result
