"""
Phase 1 Demo - Core Library Functionality
==========================================

Demonstrates the new Phase 1 functionality:
- Country code lookups (embedded data, no CSV)
- ID format validation (embedded patterns, no CSV)
- Core validation functions
- ID validation with auto-detection
"""

from src.txr_replay_core import (
    country_manager,
    id_format_manager,
    validate_id,
    validate_id_auto,
    validate_date_format,
    validate_not_empty,
)


def demo_country_codes():
    """Demonstrate country code functionality."""
    print("=" * 70)
    print("COUNTRY CODES DEMO")
    print("=" * 70)
    
    # Lookup by Alpha-2
    print("\n1. Lookup by Alpha-2 code:")
    uk = country_manager.get_by_alpha2("GB")
    print(f"   GB → {uk.name}")
    print(f"   EEA Member: {uk.is_eea}")
    
    # Check EEA status
    print("\n2. Check EEA membership:")
    countries = ["GB", "US", "DE", "CN", "FR"]
    for code in countries:
        is_eea = "✓ EEA" if country_manager.is_eea(code) else "✗ Non-EEA"
        print(f"   {code}: {is_eea}")
    
    # Convert codes
    print("\n3. Convert between code formats:")
    print(f"   GB → {country_manager.get_alpha3_from_alpha2('GB')}")
    print(f"   GBR → {country_manager.get_alpha2_from_alpha3('GBR')}")
    
    # Summary stats
    print(f"\n4. Dataset stats:")
    print(f"   Total countries: {country_manager.total_countries}")
    print(f"   EEA countries: {country_manager.eea_count}")


def demo_id_formats():
    """Demonstrate ID format validation."""
    print("\n" + "=" * 70)
    print("ID FORMAT VALIDATION DEMO")
    print("=" * 70)
    
    # Validate specific formats
    print("\n1. Validate against known format:")
    test_cases = [
        ("GB", "NIDN", "AB123456C", "Valid GB NIDN"),
        ("GB", "CONCAT", "GB12345678ABCDE#####", "Valid GB CONCAT"),
        ("BE", "NIDN", "12345678901", "Valid BE NIDN"),
        ("GB", "NIDN", "123456789", "Invalid format"),
    ]
    
    for country, id_type, value, description in test_cases:
        is_valid = id_format_manager.validate(country, id_type, value)
        status = "✓ VALID" if is_valid else "✗ INVALID"
        print(f"   {status}: {description}")
    
    # Auto-detect type
    print("\n2. Auto-detect ID type:")
    auto_tests = [
        ("GB", "AB123456C"),
        ("GB", "GB12345678ABCDE#####"),
        ("BE", "12345678901"),
    ]
    
    for country, value in auto_tests:
        detected = id_format_manager.validate_any_type(country, value)
        if detected:
            print(f"   {country} '{value[:15]}...' → {detected}")
        else:
            print(f"   {country} '{value}' → No match")
    
    # Get available types
    print("\n3. Supported ID types by country:")
    for country in ["GB", "CY", "ES"]:
        types = id_format_manager.get_id_types_for_country(country)
        print(f"   {country}: {', '.join(types)}")
    
    print(f"\n4. Dataset stats:")
    print(f"   Total patterns: {id_format_manager.total_patterns}")
    print(f"   Supported countries: {len(id_format_manager.supported_countries)}")


def demo_core_validation():
    """Demonstrate core validation functions."""
    print("\n" + "=" * 70)
    print("CORE VALIDATION DEMO")
    print("=" * 70)
    
    # Date validation
    print("\n1. Date validation:")
    dates = ["2024-01-15", "invalid", "2025-12-31"]
    for date_str in dates:
        result = validate_date_format(date_str)
        if result.is_valid:
            print(f"   ✓ '{date_str}' → {result.corrected_value}")
        else:
            print(f"   ✗ '{date_str}' → {result.error_message[:40]}...")
    
    # String validation
    print("\n2. String validation (trim whitespace):")
    strings = ["  Hello  ", "", "   "]
    for string in strings:
        result = validate_not_empty(string, "Value")
        if result.is_valid:
            print(f"   ✓ '{string}' → '{result.corrected_value}'")
        else:
            print(f"   ✗ '{string}' → {result.error_message}")


def demo_id_validation():
    """Demonstrate high-level ID validation."""
    print("\n" + "=" * 70)
    print("HIGH-LEVEL ID VALIDATION DEMO")
    print("=" * 70)
    
    # Validate with known type
    print("\n1. Validate with known country and type:")
    result = validate_id("GB", "NIDN", "AB123456C")
    if result.is_valid:
        print(f"   ✓ Valid GB NIDN: AB123456C")
    else:
        print(f"   ✗ Error: {result.primary_error}")
    
    # Auto-detect type
    print("\n2. Auto-detect ID type:")
    result = validate_id_auto("GB", "AB123456C")
    if result.is_valid:
        print(f"   ✓ Detected type: {result.detected_type}")
        print(f"   ✓ Valid ID: AB123456C")
    else:
        print(f"   ✗ Error: {result.primary_error}")
    
    # Invalid ID
    print("\n3. Invalid ID example:")
    result = validate_id("GB", "NIDN", "INVALID123")
    if not result.is_valid:
        print(f"   ✗ Validation failed")
        print(f"   Error: {result.primary_error}")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("PHASE 1 FOUNDATION - CORE LIBRARY DEMO")
    print("Version 1.1.0")
    print("=" * 70)
    
    demo_country_codes()
    demo_id_formats()
    demo_core_validation()
    demo_id_validation()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("\nAll reference data is embedded - no CSV files required!")
    print("Ready for Phase 2: VBA migration scripts\n")


if __name__ == "__main__":
    main()
