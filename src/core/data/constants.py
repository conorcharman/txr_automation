"""
Shared Constants
================

Central location for magic numbers and configuration constants
used across the txr_automation package.

This file consolidates hardcoded values to improve maintainability,
readability, and consistency across modules.

Categories:
    - ID_LENGTHS: National ID length requirements by country
    - INCIDENT_FILE_COLUMNS: Column indices for incident file parsing
    - ID_SLICE_POSITIONS: Slice positions for ID component extraction
    - VALIDATION_THRESHOLDS: Numeric thresholds for validation logic
"""

from dataclasses import dataclass
from typing import Dict


# =============================================================================
# NATIONAL ID LENGTHS BY COUNTRY
# =============================================================================

@dataclass(frozen=True)
class IDLength:
    """ID length specification for a country."""
    country: str
    length: int
    description: str = ""


# Standard ID lengths by country code
ID_LENGTHS: Dict[str, int] = {
    # 10-digit IDs
    "BG": 10,  # Bulgaria EGN (Unified Civil Number)
    "EE": 10,  # Estonia Isikukood
    "GR": 10,  # Greece (non-standard - typically 8-12)
    "PT": 10,  # Portugal (fallback length)
    
    # 11-digit IDs
    "BE": 11,  # Belgium National Number (NN)
    "FI": 11,  # Finland Personal Identity Code
    "LT": 11,  # Lithuania Asmens Kodas
    "LV": 11,  # Latvia Personal Code (old format with dash)
    "PL": 11,  # Poland PESEL
    "SE": 11,  # Sweden Personnummer (without century)
    "SI": 11,  # Slovenia EMŠO
    
    # 12-digit IDs
    "SK": 12,  # Slovakia Birth Number (Rodné Číslo) - 10 digits + 2 optional
    "SE_FULL": 12,  # Sweden Personnummer (with century)
    
    # 13-digit IDs
    "RO": 13,  # Romania CNP (Personal Numerical Code)
    "ES": 13,  # Spain (NIE with letter prefix)
    
    # 16-character IDs
    "IT": 16,  # Italy Codice Fiscale
    
    # Special formats
    "NL": 9,   # Netherlands BSN (Burgerservicenummer)
    "DE": 11,  # Germany Steuer-ID
    "CZ": 10,  # Czech Republic Birth Number (Rodné Číslo)
}


# =============================================================================
# ID COMPONENT SLICE POSITIONS
# =============================================================================

@dataclass(frozen=True)
class IDSlice:
    """Define slice positions for extracting ID components."""
    start: int
    end: int


# Common DOB extraction positions
class DOBSlices:
    """Date of birth slice positions by format type."""
    
    # YYMMDD format (Belgium, Bulgaria, etc.)
    YYMMDD = IDSlice(0, 6)
    
    # DDMMYY format (Estonia, Latvia, etc.)
    DDMMYY = IDSlice(0, 6)


# Belgium (BE) National Number: YYMMDD-XXX-CC (11 digits)
class BE_SLICES:
    """Belgium National Number component positions."""
    DOB = IDSlice(0, 6)        # YYMMDD
    SEQUENCE = IDSlice(6, 9)   # XXX (sequence number)
    CHECK_DIGIT = IDSlice(9, 11)  # CC (check digit)
    YEAR = IDSlice(0, 2)


# Bulgaria (BG) EGN: YYMMDDXXXC (10 digits)
class BG_SLICES:
    """Bulgaria EGN component positions."""
    DOB = IDSlice(0, 6)        # YYMMDD
    GENDER_DIGIT = IDSlice(8, 9)  # Position 8
    CHECK_DIGIT = IDSlice(9, 10)  # Position 9


# Czech Republic (CZ) Birth Number: YYMMDD/XXXX (10 digits, slash removed)
class CZ_SLICES:
    """Czech Republic Birth Number component positions."""
    YEAR = IDSlice(0, 2)       # YY
    MONTH = IDSlice(2, 4)      # MM (may be +50 for females)
    DAY = IDSlice(4, 6)        # DD
    SEQUENCE = IDSlice(6, 10)  # XXXX


# Estonia (EE) Isikukood: GYYMMDDXXXC (11 digits) - treated as 10 without century
class EE_SLICES:
    """Estonia Isikukood component positions."""
    DOB = IDSlice(0, 6)        # DDMMYY


# Finland (FI) Personal Identity Code: DDMMYY-XXXC (11 chars)
class FI_SLICES:
    """Finland Personal Identity Code component positions."""
    DAY = IDSlice(0, 2)        # DD
    MONTH = IDSlice(2, 4)      # MM
    YEAR = IDSlice(4, 6)       # YY
    CENTURY_CHAR = IDSlice(6, 7)  # Century separator (-, A, +)
    SEQUENCE = IDSlice(7, 10)  # XXX
    CHECK_CHAR = IDSlice(10, 11)  # C


# Italy (IT) Codice Fiscale: SSSNNNYYMDDCXXXZ (16 chars)
class IT_SLICES:
    """Italy Codice Fiscale component positions."""
    SURNAME_CODE = IDSlice(0, 3)    # SSS
    NAME_CODE = IDSlice(3, 6)       # NNN
    YEAR = IDSlice(6, 8)            # YY
    MONTH_LETTER = IDSlice(8, 9)    # M (letter encoding month)
    DAY_ENCODED = IDSlice(9, 11)    # DD (day, +40 for females)
    MUNICIPALITY = IDSlice(11, 15)  # CXXX
    CHECK_CHAR = IDSlice(15, 16)    # Z


# Lithuania (LT) Asmens Kodas: GYYMMDDXXXC (11 digits)
class LT_SLICES:
    """Lithuania Asmens Kodas component positions."""
    GENDER_CENTURY = IDSlice(0, 1)  # G (encodes gender and century)
    YEAR = IDSlice(1, 3)           # YY
    MONTH = IDSlice(3, 5)          # MM
    DAY = IDSlice(5, 7)            # DD
    SEQUENCE = IDSlice(7, 10)      # XXX
    CHECK_DIGIT = IDSlice(10, 11)  # C


# Latvia (LV) Personal Code: DDMMYY-CXXXX (11 digits with dash, or 11 without)
class LV_SLICES:
    """Latvia Personal Code component positions."""
    DAY = IDSlice(0, 2)            # DD
    MONTH = IDSlice(2, 4)          # MM
    YEAR = IDSlice(4, 6)           # YY
    CENTURY_CODE = IDSlice(7, 8)   # C (after dash)


# Poland (PL) PESEL: YYMMDDZZZXQ (11 digits)
class PL_SLICES:
    """Poland PESEL component positions."""
    DOB = IDSlice(0, 6)           # YYMMDD
    # Note: Month has century encoding (+80 for 1800s, +0 for 1900s, +20 for 2000s)


# Romania (RO) CNP: SYYMMDDJJNNNC (13 digits)
class RO_SLICES:
    """Romania CNP component positions."""
    GENDER_CODE = IDSlice(0, 1)    # S (1-8: encodes gender and century)
    YEAR = IDSlice(1, 3)           # YY
    MONTH = IDSlice(3, 5)          # MM
    DAY = IDSlice(5, 7)            # DD
    COUNTY = IDSlice(7, 9)         # JJ
    SEQUENCE = IDSlice(9, 12)      # NNN
    CHECK_DIGIT = IDSlice(12, 13)  # C


# Sweden (SE) Personnummer: YYMMDD-XXXX (10 or 12 digits)
class SE_SLICES:
    """Sweden Personnummer component positions."""
    YEAR = IDSlice(0, 4)           # YYYY (full format) or YYMMDD (short)
    DOB_SHORT = IDSlice(0, 6)      # YYMMDD (short format)
    MONTH = IDSlice(4, 6)          # MM
    DAY = IDSlice(6, 8)            # DD


# Slovakia (SK) Birth Number: YYMMDDXXXX (10 digits)
class SK_SLICES:
    """Slovakia Birth Number component positions."""
    YEAR = IDSlice(0, 2)           # YY
    MONTH = IDSlice(2, 4)          # MM (may be +50 for females)
    DAY = IDSlice(4, 6)            # DD
    SEQUENCE = IDSlice(6, 10)      # XXXX


# Slovenia (SI) EMŠO: DDMMYYYSSSCC (13 digits but often 11 used)
class SI_SLICES:
    """Slovenia EMŠO component positions."""
    DOB = IDSlice(0, 6)            # DDMMYY


# =============================================================================
# INCIDENT FILE COLUMN INDICES (PHASE 3)
# =============================================================================

class Phase3Columns:
    """Column indices for Phase 3 incident file processing.
    
    These indices correspond to the standardized incident file format
    used in Phase 3 replay processing.
    """
    
    # Minimum columns required
    MIN_COLS = 22
    
    # Buyer information
    BUYER_ID = 21
    BUYER_FIRST_NAME = 24
    BUYER_LAST_NAME = 25
    BUYER_DOB = 26
    BUYER_DM_ID = 27  # Decision Maker ID
    BUYER_DM_FIRST_NAME = 29
    BUYER_DM_LAST_NAME = 30
    BUYER_DM_DOB = 31
    
    # Seller information  
    SELLER_ID = 32
    SELLER_FIRST_NAME = 35
    SELLER_LAST_NAME = 36
    SELLER_DOB = 37
    SELLER_DM_ID = 38  # Decision Maker ID
    SELLER_DM_FIRST_NAME = 40
    SELLER_DM_LAST_NAME = 41
    SELLER_DM_DOB = 42


# =============================================================================
# PHASE 2 COLUMN MAPPINGS
# =============================================================================

class Phase2SingleColumns:
    """Column indices for Phase 2 single incident files."""
    INCIDENT_CODE = 0
    AGREES = 8
    CORRECTION_FIELD = 9
    CORRECTION_VALUE = 10
    TRANSACTION_REF = 13


class Phase2CombinedColumns:
    """Column indices for Phase 2 combined incident files."""
    INCIDENT_CODE = 0
    AGREES = 7
    CORRECTION_FIELD = 8
    CORRECTION_VALUE = 9
    TRANSACTION_REF = 12


# =============================================================================
# CLIENT ERROR FILE COLUMNS
# =============================================================================

class ClientErrorColumns:
    """Column indices for client error file parsing."""
    TRANSACTION_REF = 0
    ERROR_FLAG = 4
    CORRECTION = 5
    CORRECTION_FIELD = 6


# =============================================================================
# VALIDATION THRESHOLDS
# =============================================================================

class ValidationThresholds:
    """Numeric thresholds used in validation logic."""
    
    # Gender encoding thresholds
    FEMALE_DAY_OFFSET = 40  # Italy: Day + 40 for females
    FEMALE_MONTH_OFFSET = 50  # CZ/SK: Month + 50 for females
    
    # Century determination
    CENTURY_1800_MAX_YEAR = 99
    CENTURY_1900_MIN_YEAR = 0
    CENTURY_2000_THRESHOLD = 30  # If year < 30, assume 2000s
    
    # Check digit calculation
    BELGIUM_2000_PREFIX = 2  # Prefix for 2000+ year in BE check digit calc


# =============================================================================
# ITALIAN FISCAL CODE MAPPINGS
# =============================================================================

# Month letter encoding for Italian Codice Fiscale
IT_MONTH_LETTERS: Dict[str, int] = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5,
    'H': 6, 'L': 7, 'M': 8, 'P': 9, 'R': 10,
    'S': 11, 'T': 12
}

# Reverse mapping: month number to letter
IT_MONTH_NUMBERS: Dict[int, str] = {v: k for k, v in IT_MONTH_LETTERS.items()}


# =============================================================================
# CENTURY MARKER MAPPINGS
# =============================================================================

# Finnish century markers
FI_CENTURY_MARKERS: Dict[str, int] = {
    '+': 1800,
    '-': 1900,
    'A': 2000,
}

# Lithuanian/Romanian gender-century codes
# Odd numbers = male, even numbers = female
# 1-2 = 1800s, 3-4 = 1900s, 5-6 = 2000s
LT_CENTURY_GENDER_CODES: Dict[int, tuple] = {
    1: (1800, 'M'),
    2: (1800, 'F'),
    3: (1900, 'M'),
    4: (1900, 'F'),
    5: (2000, 'M'),
    6: (2000, 'F'),
}

# Latvian century codes
LV_CENTURY_CODES: Dict[int, int] = {
    0: 1900,
    1: 2000,
    2: 2100,  # Future-proofing
}
