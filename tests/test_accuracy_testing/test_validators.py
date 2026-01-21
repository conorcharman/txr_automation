"""
Unit Tests for Validators Module
=================================

Tests for core validation functions.
"""

import pytest
from datetime import date, datetime
from src.accuracy_testing.core.validators import (
    ValidationResult,
    validate_date_format,
    validate_date_range,
    validate_date_not_future,
    validate_not_empty,
    validate_length,
    validate_pattern,
    validate_alphanumeric,
    validate_numeric_range,
    validate_positive,
    validate_non_negative,
    validate_in_list,
    validate_all,
    validate_any,
    validate_gender,
    validate_email,
    validate_phone,
)


class TestValidationResult:
    """Test ValidationResult class."""
    
    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        result = ValidationResult(True, None, "corrected")
        assert result.is_valid is True
        assert result.error_message is None
        assert result.corrected_value == "corrected"
    
    def test_validation_result_boolean(self):
        """Test using ValidationResult in boolean context."""
        success = ValidationResult(True)
        failure = ValidationResult(False, "Error")
        
        assert bool(success) is True
        assert bool(failure) is False
    
    def test_validation_result_success_factory(self):
        """Test success factory method."""
        result = ValidationResult.success("value")
        assert result.is_valid is True
        assert result.corrected_value == "value"
    
    def test_validation_result_failure_factory(self):
        """Test failure factory method."""
        result = ValidationResult.failure("Error message")
        assert result.is_valid is False
        assert result.error_message == "Error message"


class TestDateValidation:
    """Test date validation functions."""
    
    def test_validate_date_format_valid(self):
        """Test validating valid date string."""
        result = validate_date_format("2024-01-15")
        assert result.is_valid is True
        assert result.corrected_value == date(2024, 1, 15)
    
    def test_validate_date_format_invalid(self):
        """Test validating invalid date string."""
        result = validate_date_format("invalid")
        assert result.is_valid is False
        assert "Invalid date format" in result.error_message
    
    def test_validate_date_format_empty(self):
        """Test validating empty date string."""
        result = validate_date_format("")
        assert result.is_valid is False
    
    def test_validate_date_format_custom_format(self):
        """Test validating date with custom format."""
        result = validate_date_format("15/01/2024", "%d/%m/%Y")
        assert result.is_valid is True
        assert result.corrected_value == date(2024, 1, 15)
    
    def test_validate_date_range_valid(self):
        """Test validating date in range."""
        test_date = date(2024, 6, 15)
        min_date = date(2024, 1, 1)
        max_date = date(2024, 12, 31)
        
        result = validate_date_range(test_date, min_date, max_date)
        assert result.is_valid is True
    
    def test_validate_date_range_before_min(self):
        """Test validating date before minimum."""
        test_date = date(2023, 12, 31)
        min_date = date(2024, 1, 1)
        
        result = validate_date_range(test_date, min_date=min_date)
        assert result.is_valid is False
        assert "before minimum" in result.error_message
    
    def test_validate_date_range_after_max(self):
        """Test validating date after maximum."""
        test_date = date(2025, 1, 1)
        max_date = date(2024, 12, 31)
        
        result = validate_date_range(test_date, max_date=max_date)
        assert result.is_valid is False
        assert "after maximum" in result.error_message
    
    def test_validate_date_not_future_valid(self):
        """Test validating past date."""
        past_date = date(2020, 1, 1)
        result = validate_date_not_future(past_date)
        assert result.is_valid is True
    
    def test_validate_date_not_future_today(self):
        """Test validating today's date."""
        today = date.today()
        result = validate_date_not_future(today)
        assert result.is_valid is True


class TestStringValidation:
    """Test string validation functions."""
    
    def test_validate_not_empty_valid(self):
        """Test validating non-empty string."""
        result = validate_not_empty("Hello")
        assert result.is_valid is True
        assert result.corrected_value == "Hello"
    
    def test_validate_not_empty_with_whitespace(self):
        """Test validating string with leading/trailing whitespace."""
        result = validate_not_empty("  Hello  ")
        assert result.is_valid is True
        assert result.corrected_value == "Hello"
    
    def test_validate_not_empty_empty_string(self):
        """Test validating empty string."""
        result = validate_not_empty("")
        assert result.is_valid is False
    
    def test_validate_not_empty_whitespace_only(self):
        """Test validating whitespace-only string."""
        result = validate_not_empty("   ")
        assert result.is_valid is False
        assert "whitespace" in result.error_message
    
    def test_validate_length_valid(self):
        """Test validating string length."""
        result = validate_length("Hello", 1, 10)
        assert result.is_valid is True
    
    def test_validate_length_too_short(self):
        """Test validating string too short."""
        result = validate_length("Hi", min_length=5)
        assert result.is_valid is False
        assert "less than minimum" in result.error_message
    
    def test_validate_length_too_long(self):
        """Test validating string too long."""
        result = validate_length("Hello World", max_length=5)
        assert result.is_valid is False
        assert "exceeds maximum" in result.error_message
    
    def test_validate_pattern_valid(self):
        """Test validating string against regex pattern."""
        result = validate_pattern("ABC123", r"^[A-Z]{3}\d{3}$")
        assert result.is_valid is True
    
    def test_validate_pattern_invalid(self):
        """Test validating string that doesn't match pattern."""
        result = validate_pattern("123ABC", r"^[A-Z]{3}\d{3}$")
        assert result.is_valid is False
    
    def test_validate_alphanumeric_valid(self):
        """Test validating alphanumeric string."""
        result = validate_alphanumeric("ABC123")
        assert result.is_valid is True
    
    def test_validate_alphanumeric_with_spaces(self):
        """Test validating alphanumeric with spaces."""
        result = validate_alphanumeric("ABC 123", allow_spaces=True)
        assert result.is_valid is True
    
    def test_validate_alphanumeric_invalid(self):
        """Test validating non-alphanumeric string."""
        result = validate_alphanumeric("ABC-123")
        assert result.is_valid is False


class TestNumericValidation:
    """Test numeric validation functions."""
    
    def test_validate_numeric_range_valid(self):
        """Test validating number in range."""
        result = validate_numeric_range(50, 0, 100)
        assert result.is_valid is True
    
    def test_validate_numeric_range_below_min(self):
        """Test validating number below minimum."""
        result = validate_numeric_range(-5, min_value=0)
        assert result.is_valid is False
    
    def test_validate_numeric_range_above_max(self):
        """Test validating number above maximum."""
        result = validate_numeric_range(150, max_value=100)
        assert result.is_valid is False
    
    def test_validate_positive_valid(self):
        """Test validating positive number."""
        result = validate_positive(10.5)
        assert result.is_valid is True
    
    def test_validate_positive_zero(self):
        """Test validating zero (not positive)."""
        result = validate_positive(0)
        assert result.is_valid is False
    
    def test_validate_positive_negative(self):
        """Test validating negative number."""
        result = validate_positive(-5)
        assert result.is_valid is False
    
    def test_validate_non_negative_valid(self):
        """Test validating non-negative numbers."""
        assert validate_non_negative(0).is_valid is True
        assert validate_non_negative(10).is_valid is True
    
    def test_validate_non_negative_negative(self):
        """Test validating negative number."""
        result = validate_non_negative(-1)
        assert result.is_valid is False


class TestListValidation:
    """Test list/choice validation."""
    
    def test_validate_in_list_valid(self):
        """Test validating value in list."""
        result = validate_in_list("RED", ["RED", "GREEN", "BLUE"])
        assert result.is_valid is True
    
    def test_validate_in_list_invalid(self):
        """Test validating value not in list."""
        result = validate_in_list("YELLOW", ["RED", "GREEN", "BLUE"])
        assert result.is_valid is False
    
    def test_validate_in_list_case_insensitive(self):
        """Test case-insensitive validation."""
        result = validate_in_list("red", ["RED", "GREEN", "BLUE"], case_sensitive=False)
        assert result.is_valid is True
        assert result.corrected_value == "RED"


class TestCombinedValidation:
    """Test combined validation logic."""
    
    def test_validate_all_success(self):
        """Test all validations pass."""
        v1 = ValidationResult.success()
        v2 = ValidationResult.success()
        v3 = ValidationResult.success()
        
        result = validate_all(v1, v2, v3)
        assert result.is_valid is True
    
    def test_validate_all_one_failure(self):
        """Test one validation fails."""
        v1 = ValidationResult.success()
        v2 = ValidationResult.failure("Error 2")
        v3 = ValidationResult.success()
        
        result = validate_all(v1, v2, v3)
        assert result.is_valid is False
        assert result.error_message == "Error 2"
    
    def test_validate_any_all_pass(self):
        """Test any validation with all passing."""
        v1 = ValidationResult.success()
        v2 = ValidationResult.success()
        
        result = validate_any(v1, v2)
        assert result.is_valid is True
    
    def test_validate_any_one_pass(self):
        """Test any validation with one passing."""
        v1 = ValidationResult.failure("Error 1")
        v2 = ValidationResult.success()
        v3 = ValidationResult.failure("Error 3")
        
        result = validate_any(v1, v2, v3)
        assert result.is_valid is True
    
    def test_validate_any_all_fail(self):
        """Test any validation with all failing."""
        v1 = ValidationResult.failure("Error 1")
        v2 = ValidationResult.failure("Error 2")
        
        result = validate_any(v1, v2)
        assert result.is_valid is False


class TestSpecialFieldValidators:
    """Test special field validators."""
    
    def test_validate_gender_male(self):
        """Test validating male gender."""
        result = validate_gender("M")
        assert result.is_valid is True
        assert result.corrected_value == "M"
    
    def test_validate_gender_female(self):
        """Test validating female gender."""
        result = validate_gender("F")
        assert result.is_valid is True
        assert result.corrected_value == "F"
    
    def test_validate_gender_case_insensitive(self):
        """Test gender validation is case-insensitive."""
        result = validate_gender("male")
        assert result.is_valid is True
        assert result.corrected_value == "M"
    
    def test_validate_email_valid(self):
        """Test validating valid email."""
        result = validate_email("user@example.com")
        assert result.is_valid is True
    
    def test_validate_email_invalid(self):
        """Test validating invalid email."""
        result = validate_email("invalid-email")
        assert result.is_valid is False
    
    def test_validate_phone_valid(self):
        """Test validating valid phone number."""
        result = validate_phone("+44 20 1234 5678")
        assert result.is_valid is True
        # Normalized without spaces/separators
        assert result.corrected_value == "+442012345678"
    
    def test_validate_phone_normalized(self):
        """Test phone normalization."""
        result = validate_phone("(123) 456-7890")
        assert result.is_valid is True
        assert result.corrected_value == "1234567890"
