"""
ID Format Validation Patterns
==============================

Embedded ID format regex patterns for validating identification codes
across different countries and ID types (NIDN, CONCAT, CCPT, LEI).

This is the canonical location for ID format patterns.
For backward compatibility, this is also re-exported from:
- accuracy_testing.core.id_formats

ID Types:
    - NIDN: National Identity Number
    - CONCAT: Concatenated identifier format
    - CCPT: Client Code/Passport format
    - LEI: Legal Entity Identifier

Data source: Internal regulatory requirements
Last updated: January 2026
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

# Import country manager for generic CONCAT validation
try:
    from .country_codes import country_manager
    COUNTRY_MANAGER_AVAILABLE = True
except ImportError:
    COUNTRY_MANAGER_AVAILABLE = False
    country_manager = None

# Generic CONCAT pattern for universal validation (rest-of-world countries)
# Format: 2-letter country code + 8 digits (YYYYMMDD) + 5 chars (first name) + 5 chars (last name)
GENERIC_CONCAT_PATTERN = re.compile(r'^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$')


@dataclass(frozen=True)
class IDPattern:
    """Immutable ID pattern structure."""
    
    country_code: str
    id_type: str
    regex_pattern: str
    compiled_pattern: re.Pattern
    
    def matches(self, value: str) -> bool:
        """Check if value matches this pattern."""
        return bool(self.compiled_pattern.match(value))
    
    def get_mismatch_reason(self, value: str) -> Optional[str]:
        """Get detailed reason why value doesn't match pattern."""
        if self.matches(value):
            return None
        
        reasons = []
        actual_len = len(value)
        total_length = 0
        
        # Calculate expected length by parsing pattern
        # Remove anchors and negative lookaheads for counting
        pattern_for_counting = self.regex_pattern.replace('^', '').replace('$', '')
        pattern_for_counting = re.sub(r'\(\?![^)]+\)', '', pattern_for_counting)
        
        # Find all \d{n} patterns
        digit_groups = re.findall(r'\\d\{(\d+)\}', pattern_for_counting)
        if digit_groups:
            total_length += sum(int(n) for n in digit_groups)
        
        # Find all [character_class]{n} patterns
        char_class_groups = re.findall(r'\[(?:[^\]]+)\]\{(\d+)\}', pattern_for_counting)
        if char_class_groups:
            total_length += sum(int(n) for n in char_class_groups)
        
        # Find single \d (without quantifier)
        single_digits = len(re.findall(r'\\d(?!\{)', pattern_for_counting))
        total_length += single_digits
        
        # Find single character classes [xxx] (without quantifier)
        single_char_classes = len(re.findall(r'\[(?:[^\]]+)\](?!\{)', pattern_for_counting))
        total_length += single_char_classes
        
        # Find literal single characters (e.g., E, K, L in patterns)
        # Count uppercase letters not in brackets or after backslash
        literal_chars = re.findall(r'(?<!\[)(?<!\\)(?<![A-Z-])[A-Z](?![A-Z-]|\])', pattern_for_counting)
        total_length += len(literal_chars)
        
        expected_len = total_length if total_length > 0 else None
        
        if expected_len and actual_len != expected_len:
            reasons.append(f"Expected {expected_len} characters, got {actual_len}")
        
        if r'^\d' in self.regex_pattern or self.regex_pattern.startswith(r'^\d'):
            if not value.isdigit():
                for i, ch in enumerate(value):
                    if not ch.isdigit():
                        reasons.append(f"Contains non-digit character '{ch}' at position {i+1}")
                        break
        
        if r'^[A-Z]{' in self.regex_pattern:
            match = re.search(r'^\[A-Z\]\{(\d+)\}', self.regex_pattern)
            if match:
                prefix_len = int(match.group(1))
                if len(value) < prefix_len or not value[:prefix_len].isalpha():
                    reasons.append(f"Must start with {prefix_len} letters")
        
        if not reasons:
            if expected_len:
                reasons.append(f"Does not match expected {expected_len}-character format")
            else:
                reasons.append(f"Does not match expected format pattern")
        
        return "; ".join(reasons)
    
    def __str__(self) -> str:
        return f"{self.country_code}-{self.id_type}: {self.regex_pattern}"


# ID format patterns dataset - 67 patterns
_RAW_PATTERNS = [
    ("AT", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("BE", "NIDN", r"^\d{6}\d{3}\d{2}$"),
    ("BE", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("BG", "NIDN", r"^\d{6}\d{2}\d{1}\d{1}$"),
    ("BG", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("CY", "CCPT", r"^E\d{6}$"),
    ("CY", "CCPT", r"^K\d{8}$"),
    ("CY", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("CZ", "NIDN", r"^\d{6}\d{3}$"),
    ("CZ", "NIDN", r"^\d{6}\d{3}\d{1}$"),
    ("CZ", "CCPT", r"^\d{8,}$"),
    ("CZ", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("DE", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("DK", "NIDN", r"^\d{6}\d{4}$"),
    ("DK", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("EE", "NIDN", r"^\d{1}\d{6}\d{3}\d{1}$"),
    ("ES", "NIDN", r"^\d{8}[A-HJ-NP-TV-Z]$"),
    ("ES", "NIDN", r"^L\d{7}[A-HJ-NP-TV-Z]$"),
    ("ES", "NIDN", r"^K\d{7}[A-HJ-NP-TV-Z]$"),
    ("FI", "NIDN", r"^\d{6}[+\-A]\d{3}\d{1}$"),
    ("FI", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("FR", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("GB", "NIDN", r"^(?!BG|GB|KN|NK|NT|OO|TN|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NP-TW-Z]\d{6}[A-NP-Z]$"),
    ("GB", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("GR", "NIDN", r"^\d{10}$"),
    ("GR", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("HR", "NIDN", r"^\d{10}\d{1}$"),
    ("HR", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("HU", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("IE", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("IS", "NIDN", r"^\d{6}\d{4}$"),
    ("IT", "NIDN", r"^[A-Z]{3}[A-Z]{3}[A-Z0-9]{5}[A-Z0-9]{4}[A-Z0-9]{1}$"),
    ("LI", "CCPT", r"^[A-Z]{1}\d{5}$"),
    ("LI", "NIDN", r"^[A-Z]{2}\d{8}$"),
    ("LI", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("LT", "NIDN", r"^\d{1}\d{6}\d{3}\d{1}$"),
    ("LT", "CCPT", r"^\d{8}$"),
    ("LT", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("LU", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("LV", "NIDN", r"^\d{6}\d{1}\d{4}$"),
    ("LV", "NIDN", r"^\d{11}$"),
    ("LV", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("MT", "NIDN", r"^\d{7}[A-Z]{1}$"),
    ("MT", "CCPT", r"^\d{7}$"),
    ("MT", "CCPT", r"^[A-Z]{2}\d{6}$"),
    ("NL", "CCPT", r"^[A-NP-Z]{2}[A-NP-Z0-9]{6}\d{1}$"),
    ("NL", "NIDN", r"^[A-NP-Z]{2}[A-NP-Z0-9]{6}\d{1}$"),
    ("NL", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("NO", "NIDN", r"^\d{6}\d{5}$"),
    ("NO", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("PL", "NIDN", r"^\d{11}$"),
    ("PL", "NIDN", r"^\d{10}$"),
    ("PT", "NIDN", r"^\d{8}\d{1}$"),
    ("PT", "CCPT", r"^[A-Z]{1}\d{6}$"),
    ("PT", "CCPT", r"^[A-Z]{2}\d{6}$"),
    ("PT", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("RO", "NIDN", r"^\d{1}\d{6}\d{2}\d{3}\d{1}$"),
    ("RO", "CCPT", r"^\d{9}$"),
    ("RO", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("SE", "NIDN", r"^\d{8}\d{3}\d{1}$"),  # 12-digit format: CCYYMMDDBBBC
    ("SE", "NIDN", r"^\d{6}\d{3}\d{1}$"),  # 10-digit format: YYMMDDBBBC (without century)
    ("SE", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("SI", "NIDN", r"^\d{7}\d{2}\d{3}\d{1}$"),
    ("SI", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("SK", "NIDN", r"^\d{6}\d{3}\d{1}$"),
    ("SK", "CCPT", r"^[A-Z]{2}\d{7}$"),
    ("SK", "CONCAT", r"^[A-Z]{2}\d{8}[A-Z#]{5}[A-Z#]{5}$"),
    ("", "LEI", r"^[A-Z0-9]{18}\d{2}$"),
]


# Build IDPattern objects with compiled regex
ID_PATTERNS = [
    IDPattern(
        country_code=country,
        id_type=id_type,
        regex_pattern=pattern,
        compiled_pattern=re.compile(pattern)
    )
    for country, id_type, pattern in _RAW_PATTERNS
]


class IDFormatManager:
    """
    Singleton manager for ID format validation.
    Provides efficient pattern matching with precompiled regex patterns.
    
    Usage:
        manager = IDFormatManager()
        is_valid = manager.validate("GB", "NIDN", "AB123456C")
        patterns = manager.get_patterns_for_country("GB")
    """
    
    _instance: Optional['IDFormatManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'IDFormatManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize pattern lookups (only once)."""
        if IDFormatManager._initialized:
            return
        
        self._patterns_by_key: Dict[Tuple[str, str], List[IDPattern]] = defaultdict(list)
        self._patterns_by_country: Dict[str, List[IDPattern]] = defaultdict(list)
        self._patterns_by_type: Dict[str, List[IDPattern]] = defaultdict(list)
        
        for pattern in ID_PATTERNS:
            key = (pattern.country_code.upper(), pattern.id_type.upper())
            self._patterns_by_key[key].append(pattern)
            
            if pattern.country_code:
                self._patterns_by_country[pattern.country_code.upper()].append(pattern)
            
            self._patterns_by_type[pattern.id_type.upper()].append(pattern)
        
        IDFormatManager._initialized = True
    
    def validate(self, country_code: str, id_type: str, id_value: str) -> bool:
        """Validate an ID value against country and type-specific patterns."""
        key = (country_code.upper(), id_type.upper())
        patterns = self._patterns_by_key.get(key, [])
        
        # Try specific patterns first
        if any(pattern.matches(id_value) for pattern in patterns):
            return True
        
        # Fallback: If no specific pattern exists for CONCAT, use generic validation
        if not patterns and id_type.upper() == "CONCAT" and COUNTRY_MANAGER_AVAILABLE:
            # Check generic CONCAT format with valid country prefix
            if len(id_value) == 20 and GENERIC_CONCAT_PATTERN.match(id_value.upper()):
                prefix = id_value[:2].upper()
                return country_manager.validate_code(prefix)
        
        return False
    
    def validate_with_details(self, country_code: str, id_type: str, id_value: str) -> Tuple[bool, Optional[str]]:
        """Validate an ID value and provide detailed error message if it fails."""
        key = (country_code.upper(), id_type.upper())
        patterns = self._patterns_by_key.get(key, [])
        
        # If no specific patterns exist, check for generic CONCAT validation
        if not patterns:
            if id_type.upper() == "CONCAT" and COUNTRY_MANAGER_AVAILABLE:
                # Use generic CONCAT validation for rest-of-world countries
                if len(id_value) != 20:
                    return (False, f"Invalid CONCAT format for {country_code}: Expected 20 characters, got {len(id_value)}")
                
                if not GENERIC_CONCAT_PATTERN.match(id_value.upper()):
                    return (False, f"Invalid CONCAT format for {country_code}: Does not match pattern [CC][YYYYMMDD][FFFFF][LLLLL] where CC=country, YYYY=year, MM=month, DD=day, F=first name chars, L=last name chars")
                
                prefix = id_value[:2].upper()
                if not country_manager.validate_code(prefix):
                    return (False, f"Invalid CONCAT format for {country_code}: Invalid country code prefix '{prefix}'")
                
                # Passed generic CONCAT validation
                return (True, None)
            else:
                return (False, f"No {id_type} format patterns defined for {country_code}")
        
        # Try specific patterns
        for pattern in patterns:
            if pattern.matches(id_value):
                return (True, None)
        
        # Specific patterns exist but none matched
        if len(patterns) == 1:
            reason = patterns[0].get_mismatch_reason(id_value)
            return (False, f"Invalid {id_type} format for {country_code}: {reason}")
        else:
            reasons = [p.get_mismatch_reason(id_value) for p in patterns]
            return (False, f"Invalid {id_type} format for {country_code} (tried {len(patterns)} patterns): {reasons[0]}")
    
    def validate_any_type(self, country_code: str, id_value: str) -> Optional[str]:
        """Validate an ID against all types for a country. Returns the ID type if valid."""
        patterns = self._patterns_by_country.get(country_code.upper(), [])
        for pattern in patterns:
            if pattern.matches(id_value):
                return pattern.id_type
        return None
    
    def get_patterns_for_country(self, country_code: str) -> List[IDPattern]:
        """Get all ID patterns for a specific country."""
        return self._patterns_by_country.get(country_code.upper(), [])
    
    def get_patterns_for_type(self, id_type: str) -> List[IDPattern]:
        """Get all ID patterns for a specific type."""
        return self._patterns_by_type.get(id_type.upper(), [])
    
    def get_patterns(self, country_code: str, id_type: str) -> List[IDPattern]:
        """Get patterns for a specific country and type combination."""
        key = (country_code.upper(), id_type.upper())
        return self._patterns_by_key.get(key, [])
    
    def get_id_types_for_country(self, country_code: str) -> List[str]:
        """Get all ID types available for a country."""
        patterns = self._patterns_by_country.get(country_code.upper(), [])
        seen = set()
        types = []
        for pattern in patterns:
            if pattern.id_type not in seen:
                types.append(pattern.id_type)
                seen.add(pattern.id_type)
        return types
    
    def get_countries_for_type(self, id_type: str) -> List[str]:
        """Get all countries that support a specific ID type."""
        patterns = self._patterns_by_type.get(id_type.upper(), [])
        countries = set(p.country_code for p in patterns if p.country_code)
        return sorted(countries)
    
    def validate_lei(self, lei_value: str) -> bool:
        """Validate a Legal Entity Identifier (LEI)."""
        return self.validate("", "LEI", lei_value)
    
    def get_all_patterns(self) -> List[IDPattern]:
        """Get all ID patterns."""
        return ID_PATTERNS.copy()
    
    @property
    def total_patterns(self) -> int:
        """Get total number of patterns."""
        return len(ID_PATTERNS)
    
    @property
    def supported_countries(self) -> List[str]:
        """Get list of all supported country codes."""
        return sorted(self._patterns_by_country.keys())
    
    @property
    def supported_id_types(self) -> List[str]:
        """Get list of all supported ID types."""
        return sorted(self._patterns_by_type.keys())


# Pre-instantiate singleton for convenient imports
id_format_manager = IDFormatManager()
