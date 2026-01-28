"""
ID Logic Validation Module

Validates identification codes by extracting embedded information (DOB, gender)
and comparing against provided client data. Implements comprehensive logic checks
based on Check Logic Conditions specification.

Supports:
- DOB extraction and validation (various formats: YYMMDD, DDMMYY, CCYYMMDD, DDMMYYY)
- Gender code validation (odd/even, specific codes, ranges)
- Century code validation
- Check digit algorithms (Modulus 97, Modulus 11, Luhn, weighted sums)

Covers: BE, BG, CZ, DK, EE, FI, IS, IT, LT, LV, NO, RO, SE, SI, SK
"""

from datetime import datetime
from typing import Optional, Tuple, List
import re
import logging


# Module logger
logger = logging.getLogger(__name__)


class IDLogicValidator:
    """Validates ID codes by extracting and comparing embedded information."""
    
    # Italian fiscal code month encoding
    ITALIAN_MONTHS = {
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'H': 6,
        'L': 7, 'M': 8, 'P': 9, 'R': 10, 'S': 11, 'T': 12
    }
    
    # Finnish check digit character mapping (mod 31)
    FINNISH_CHECK_CHARS = '0123456789ABCDEFHJKLMNPRSTUVWXY'
    
    def __init__(self, verbose: bool = False):
        """
        Initialize ID logic validator.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.last_failure_reason = ""  # Stores reason for most recent validation failure
        self.validation_warnings: List[str] = []  # Track validation exceptions/warnings
    
    def validate_id_logic(
        self,
        id_value: str,
        id_type: str,
        country_code: str,
        provided_dob: str,
        provided_gender: str
    ) -> bool:
        """
        Validate ID code by checking embedded logic against provided data.
        
        Args:
            id_value: The identification code value
            id_type: The type of ID (NIDN, CCPT, CONCAT)
            country_code: ISO country code
            provided_dob: Date of birth from client data (YYYY-MM-DD)
            provided_gender: Gender from client data (M/F)
            
        Returns:
            True if ID logic validates successfully, False otherwise
        """
        if not id_value or not id_type or id_type.upper() != "NIDN":
            if self.verbose:
                print(f"[LOGIC VALIDATOR] Skipping: id_value={bool(id_value)}, id_type={id_type}, is_NIDN={id_type.upper() == 'NIDN' if id_type else False}")
            self.last_failure_reason = ""
            return True  # Only validate NIDN types
        
        # Clear previous failure reason
        self.last_failure_reason = ""
        
        # Strip country code prefix if present (e.g., "RO1690403203131" -> "1690403203131")
        clean_id = id_value
        if country_code and len(id_value) > 2 and id_value[:2].upper() == country_code.upper():
            clean_id = id_value[2:]
            if self.verbose:
                print(f"[LOGIC VALIDATOR] Stripped country prefix: '{id_value}' -> '{clean_id}'")
        
        if self.verbose:
            print(f"[LOGIC VALIDATOR] Validating {country_code} NIDN: {clean_id}, DOB={provided_dob}, Gender={provided_gender}")
        
        # Route to specific validation based on country
        validators = {
            "BE": self._validate_belgian_nidn,
            "BG": self._validate_bulgarian_nidn,
            "CZ": self._validate_czech_nidn,
            "DK": self._validate_danish_nidn,
            "EE": self._validate_estonian_nidn,
            "FI": self._validate_finnish_nidn,
            "IS": self._validate_icelandic_nidn,
            "IT": self._validate_italian_nidn,
            "LT": self._validate_lithuanian_nidn,
            "LV": self._validate_latvian_nidn,
            "NO": self._validate_norwegian_nidn,
            "RO": self._validate_romanian_nidn,
            "SE": self._validate_swedish_nidn,
            "SI": self._validate_slovenian_nidn,
            "SK": self._validate_slovak_nidn,
        }
        
        validator = validators.get(country_code)
        if validator:
            result = validator(clean_id, provided_dob, provided_gender)
            if self.verbose:
                print(f"[LOGIC VALIDATOR] {country_code} validator returned: {result}")
            return result
        
        # No specific validation rules - pass by default
        if self.verbose:
            print(f"[LOGIC VALIDATOR] No validator for country {country_code}, passing by default")
        return True
    
    def _log_validation_exception(self, country: str, nidn: str, error: Exception, context: str = "") -> None:
        """
        Log a validation exception for tracking.
        
        Args:
            country: Country code being validated
            nidn: The NIDN value
            error: The exception that occurred
            context: Additional context about what was being validated
        """
        warning_msg = f"Validation exception for {country} NIDN '{nidn}': {error}"
        if context:
            warning_msg = f"{context} - {warning_msg}"
        
        self.validation_warnings.append(warning_msg)
        logger.warning(warning_msg)
        
        if self.verbose:
            print(f"[VALIDATION WARNING] {warning_msg}")
    
    def get_warnings(self) -> List[str]:
        """Get list of validation warnings encountered."""
        return self.validation_warnings.copy()
    
    def clear_warnings(self) -> None:
        """Clear the list of validation warnings."""
        self.validation_warnings.clear()
    
    # ========================================================================
    # BELGIAN NIDN VALIDATION (BE)
    # Format: YYMMDD-XXX-CD (11 digits)
    # ========================================================================
    
    def _validate_belgian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Belgian NIDN: YYMMDD + sequence (odd=M, even=F) + check digit (mod 97).
        Regex: ``^\\d{6}\\d{3}\\d{2}$``
        """
        if len(nidn) != 11 or not nidn.isdigit():
            return True
        
        try:
            # Extract DOB (YYMMDD)
            extracted_dob = self._extract_dob_yymmdd(nidn[0:6])
            if extracted_dob and not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            # Gender code: positions 7-9, odd=male, even=female
            sequence = int(nidn[6:9])
            extracted_gender = 'M' if sequence % 2 == 1 else 'F'
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check digit: modulus 97
            # For birth years 2000+, prepend '2'
            year_2digit = int(nidn[0:2])
            if year_2digit < 50:  # Born in 2000s
                base_number = int('2' + nidn[0:9])
            else:
                base_number = int(nidn[0:9])
            
            check_digit_expected = 97 - (base_number % 97)
            check_digit_actual = int(nidn[9:11])
            
            if check_digit_expected != check_digit_actual:
                self.last_failure_reason = f"Check digit failed (expected: {check_digit_expected:02d}, actual: {check_digit_actual:02d})"
                if self.verbose:
                    print(f"Belgian NIDN check digit failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("BE", nidn, e, "Belgian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # BULGARIAN NIDN VALIDATION (BG)
    # Format: YYMMDD-RR-S-C (10 digits)
    # ========================================================================
    
    def _validate_bulgarian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Bulgarian NIDN: YYMMDD + region + sequence (even=M, odd=F) + check digit.
        Regex: ``^\\d{6}\\d{2}\\d{1}\\d{1}$``
        """
        if len(nidn) != 10 or not nidn.isdigit():
            return True
        
        try:
            # Extract DOB (YYMMDD)
            extracted_dob = self._extract_dob_yymmdd(nidn[0:6])
            if extracted_dob and not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            # Gender code: position 9, even=male, odd=female
            gender_digit = int(nidn[8])
            extracted_gender = 'M' if gender_digit % 2 == 0 else 'F'
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check digit: weighted sum modulus 11
            weights = [2, 4, 8, 5, 10, 9, 7, 3, 6]
            weighted_sum = sum(int(nidn[i]) * weights[i] for i in range(9))
            check_digit_expected = weighted_sum % 11
            if check_digit_expected == 10:
                check_digit_expected = 0
            
            check_digit_actual = int(nidn[9])
            if check_digit_expected != check_digit_actual:
                if self.verbose:
                    print(f"Bulgarian NIDN check digit failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("BG", nidn, e, "Bulgarian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # CZECH NIDN VALIDATION (CZ)
    # Format: YYMMDD/XXX or YYMMDD/XXXC (9 or 10 digits)
    # ========================================================================
    
    def _validate_czech_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Czech NIDN: YYMMDD + sequence + optional check digit.
        MM offset: +50 or +70 for females.
        Regex: ``^\\d{6}\\d{3}$`` or ``^\\d{6}\\d{3}\\d{1}$``
        """
        if len(nidn) not in [9, 10] or not nidn.isdigit():
            return True
        
        try:
            # Extract year, month, day
            year_2digit = int(nidn[0:2])
            month = int(nidn[2:4])
            day = int(nidn[4:6])
            
            # Determine gender and actual month
            if month > 70:
                extracted_gender = 'F'
                actual_month = month - 70
            elif month > 50:
                extracted_gender = 'F'
                actual_month = month - 50
            else:
                extracted_gender = 'M'
                actual_month = month
            
            # Build date
            year = 1900 + year_2digit if year_2digit >= 50 else 2000 + year_2digit
            try:
                dob_obj = datetime(year, actual_month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check digit validation (only for 10-digit, born after 1954-01-01)
            if len(nidn) == 10:
                base_number = int(nidn[0:9])
                check_digit_expected = base_number % 11
                if check_digit_expected == 10:
                    check_digit_expected = 0
                
                check_digit_actual = int(nidn[9])
                if check_digit_expected != check_digit_actual:
                    if self.verbose:
                        print(f"Czech NIDN check digit failed: {nidn}")
                    return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("CZ", nidn, e, "Czech NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # DANISH NIDN VALIDATION (DK)
    # Format: DDMMYY-XXXX (10 digits)
    # ========================================================================
    
    def _validate_danish_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Danish NIDN: DDMMYY + sequence.
        Regex: ``^\\d{6}\\d{4}$``
        """
        if len(nidn) != 10 or not nidn.isdigit():
            return True
        
        extracted_dob = self._extract_dob_ddmmyy(nidn[0:6])
        if extracted_dob and not self._compare_dob(extracted_dob, provided_dob):
            return False
        
        return True
    
    # ========================================================================
    # ESTONIAN NIDN VALIDATION (EE)
    # Format: S-YYMMDD-XXX-C (11 digits)
    # ========================================================================
    
    def _validate_estonian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Estonian NIDN: Gender+Century code + YYMMDD + sequence + check digit.
        Regex: ``^\\d{1}\\d{6}\\d{3}\\d{1}$``
        """
        if len(nidn) != 11 or not nidn.isdigit():
            return True
        
        try:
            # First digit: gender + century
            gender_century = int(nidn[0])
            if gender_century in [1, 3, 5]:
                extracted_gender = 'M'
            elif gender_century in [2, 4, 6]:
                extracted_gender = 'F'
            else:
                return True  # Invalid code
            
            # Determine century
            if gender_century in [1, 2]:
                century = 1800
            elif gender_century in [3, 4]:
                century = 1900
            elif gender_century in [5, 6]:
                century = 2000
            else:
                return True
            
            # Extract DOB
            year_2digit = int(nidn[1:3])
            month = int(nidn[3:5])
            day = int(nidn[5:7])
            year = century + year_2digit
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Two-stage modulus 11 check digit
            weights_stage1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1]
            weighted_sum = sum(int(nidn[i]) * weights_stage1[i] for i in range(10))
            check_digit_expected = weighted_sum % 11
            
            if check_digit_expected == 10:
                # Stage 2
                weights_stage2 = [3, 4, 5, 6, 7, 8, 9, 1, 2, 3]
                weighted_sum = sum(int(nidn[i]) * weights_stage2[i] for i in range(10))
                check_digit_expected = weighted_sum % 11
                if check_digit_expected == 10:
                    check_digit_expected = 0
            
            check_digit_actual = int(nidn[10])
            if check_digit_expected != check_digit_actual:
                if self.verbose:
                    print(f"Estonian NIDN check digit failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("EE", nidn, e, "Estonian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # FINNISH NIDN VALIDATION (FI)
    # Format: DDMMYY[+/-/A]XXX[C] (11 characters)
    # ========================================================================
    
    def _validate_finnish_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Finnish NIDN: DDMMYY + century marker + sequence (odd=M, even=F) + check char.
        """
        if len(nidn) != 11:
            return True
        
        try:
            # Extract DOB
            day = int(nidn[0:2])
            month = int(nidn[2:4])
            year_2digit = int(nidn[4:6])
            century_char = nidn[6]
            
            # Determine century
            if century_char == '+':
                century = 1800
            elif century_char == '-':
                century = 1900
            elif century_char == 'A':
                century = 2000
            else:
                return True
            
            year = century + year_2digit
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            # Gender: sequence number (positions 7-9), odd=male, even=female
            sequence = int(nidn[7:10])
            extracted_gender = 'M' if sequence % 2 == 1 else 'F'
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check character: modulus 31 character mapping
            concat_digits = nidn[0:6] + nidn[7:10]  # DDMMYY + XXX
            check_number = int(concat_digits) % 31
            check_char_expected = self.FINNISH_CHECK_CHARS[check_number]
            check_char_actual = nidn[10]
            
            if check_char_expected != check_char_actual:
                if self.verbose:
                    print(f"Finnish NIDN check character failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("FI", nidn, e, "Finnish NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # ICELANDIC NIDN VALIDATION (IS)
    # Format: DDMMYY-XXXX (10 digits)
    # ========================================================================
    
    def _validate_icelandic_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Icelandic NIDN: DDMMYY + sequence (no check digit).
        """
        if len(nidn) != 10 or not nidn.isdigit():
            return True
        
        extracted_dob = self._extract_dob_ddmmyy(nidn[0:6])
        if extracted_dob and not self._compare_dob(extracted_dob, provided_dob):
            return False
        
        return True
    
    # ========================================================================
    # ITALIAN NIDN VALIDATION (IT)
    # Format: 16 characters (fiscal code)
    # ========================================================================
    
    def _validate_italian_nidn(
        self,
        fiscal_code: str,
        provided_dob: str,
        provided_gender: str
    ) -> bool:
        """
        Validate Italian fiscal code against provided DOB and gender.
        
        Italian fiscal code format: RSSMRA85T10A562S
        - Positions 1-3: Surname consonants
        - Positions 4-6: First name consonants
        - Position 7-8: Year (last 2 digits)
        - Position 9: Month (letter code A-T, excluding I/J/K/N/O/Q/U/W/X/Y/Z)
        - Position 10-11: Day (01-31 for males, 41-71 for females)
        - Position 12-15: Municipality code
        - Position 16: Check character
        
        Args:
            fiscal_code: 16-character Italian fiscal code
            provided_dob: Date of birth (YYYY-MM-DD or similar)
            provided_gender: Gender (M/F)
            
        Returns:
            True if DOB and gender match the fiscal code, False otherwise
        """
        if not fiscal_code or len(fiscal_code) != 16:
            return True  # Can't validate malformed code
        
        fiscal_code = fiscal_code.upper()
        
        try:
            # Extract embedded information
            extracted_dob = self._extract_italian_dob(fiscal_code)
            extracted_gender = self._extract_italian_gender(fiscal_code)
            
            if extracted_dob is None or extracted_gender is None:
                return True  # Can't validate if extraction failed
            
            # Normalize provided values
            normalized_dob = self._normalize_date(provided_dob)
            normalized_gender = provided_gender.strip().upper() if provided_gender else ""
            
            # Compare DOB
            dob_match = (normalized_dob == extracted_dob) if normalized_dob else True
            
            # Compare gender
            gender_match = (normalized_gender == extracted_gender) if normalized_gender and normalized_gender in ['M', 'F'] else True
            
            if self.verbose and not (dob_match and gender_match):
                print(f"Italian fiscal code mismatch: {fiscal_code}")
                print(f"  Extracted DOB: {extracted_dob}, Provided: {normalized_dob}, Match: {dob_match}")
                print(f"  Extracted Gender: {extracted_gender}, Provided: {normalized_gender}, Match: {gender_match}")
            
            return dob_match and gender_match
            
        except Exception as e:
            self._log_validation_exception("IT", fiscal_code, e, "Italian fiscal code validation")
            return True  # Pass with warning logged
    
    def _extract_italian_dob(self, fiscal_code: str) -> Optional[str]:
        """
        Extract date of birth from Italian fiscal code.
        
        Args:
            fiscal_code: 16-character fiscal code
            
        Returns:
            Date in YYYY-MM-DD format, or None if extraction fails
        """
        try:
            # Extract year (positions 7-8, 0-indexed: 6-7)
            year_2digit = fiscal_code[6:8]
            
            # Extract month (position 9, 0-indexed: 8)
            month_letter = fiscal_code[8]
            if month_letter not in self.ITALIAN_MONTHS:
                return None
            month = self.ITALIAN_MONTHS[month_letter]
            
            # Extract day (positions 10-11, 0-indexed: 9-10)
            day_encoded = int(fiscal_code[9:11])
            
            # For females, day is encoded as actual day + 40
            if day_encoded > 40:
                day = day_encoded - 40
            else:
                day = day_encoded
            
            # Determine century (assume 1900s for 50-99, 2000s for 00-49)
            year_2digit_int = int(year_2digit)
            if year_2digit_int >= 50:
                year = 1900 + year_2digit_int
            else:
                year = 2000 + year_2digit_int
            
            # Validate and format
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                return None
                
        except (ValueError, IndexError):
            return None
    
    def _extract_italian_gender(self, fiscal_code: str) -> Optional[str]:
        """
        Extract gender from Italian fiscal code.
        
        Args:
            fiscal_code: 16-character fiscal code
            
        Returns:
            'M' for male, 'F' for female, or None if extraction fails
        """
        try:
            # Extract day encoding (positions 10-11, 0-indexed: 9-10)
            day_encoded = int(fiscal_code[9:11])
            
            # Males: 01-31, Females: 41-71
            if day_encoded > 40:
                return 'F'
            else:
                return 'M'
                
        except (ValueError, IndexError):
            return None
    
    # ========================================================================
    # LITHUANIAN NIDN VALIDATION (LT)
    # Format: GYYMMDDXXXX (11 digits)
    # ========================================================================
    
    def _validate_lithuanian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Lithuanian NIDN: Gender code (3/5=M, 4/6=F) + YYMMDD + sequence.
        """
        if len(nidn) != 11 or not nidn.isdigit():
            return True
        
        try:
            # Gender and century code
            gender_code = int(nidn[0])
            if gender_code in [3, 5]:
                extracted_gender = 'M'
                century = 1900 if gender_code == 3 else 2000
            elif gender_code in [4, 6]:
                extracted_gender = 'F'
                century = 1900 if gender_code == 4 else 2000
            else:
                return True
            
            # Extract DOB
            year_2digit = int(nidn[1:3])
            month = int(nidn[3:5])
            day = int(nidn[5:7])
            year = century + year_2digit
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("LT", nidn, e, "Lithuanian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # LATVIAN NIDN VALIDATION (LV)
    # Format: DDMMYY-CXXXX (11 characters)
    # ========================================================================
    
    def _validate_latvian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Latvian NIDN: DDMMYY + century digit (0/1/2) + sequence.
        """
        if len(nidn) != 11 or not nidn[0:6].isdigit() or not nidn[7:11].isdigit():
            return True
        
        try:
            # Extract DOB
            day = int(nidn[0:2])
            month = int(nidn[2:4])
            year_2digit = int(nidn[4:6])
            century_code = int(nidn[7])
            
            # Determine century
            if century_code == 0:
                century = 1800
            elif century_code == 1:
                century = 1900
            elif century_code == 2:
                century = 2000
            else:
                return True
            
            year = century + year_2digit
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("LV", nidn, e, "Latvian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # NORWEGIAN NIDN VALIDATION (NO)
    # Format: DDMMYYXXXXX (11 digits)
    # ========================================================================
    
    def _validate_norwegian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Norwegian NIDN: DDMMYY + sequence (no check digit validation).
        """
        if len(nidn) != 11 or not nidn.isdigit():
            return True
        
        extracted_dob = self._extract_dob_ddmmyy(nidn[0:6])
        if extracted_dob and not self._compare_dob(extracted_dob, provided_dob):
            return False
        
        return True
    
    # ========================================================================
    # ROMANIAN NIDN VALIDATION (RO)
    # Format: GYYMMDDRRXXX (13 digits)
    # ========================================================================
    
    def _validate_romanian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Romanian NIDN: Gender+century (1/2=1900s M/F, 3/4=1800s M/F, 5/6=2000s M/F) + YYMMDD + region + check digit.
        """
        if len(nidn) != 13 or not nidn.isdigit():
            return True
        
        try:
            # Gender and century code
            gender_code = int(nidn[0])
            if gender_code in [1, 3, 5]:
                extracted_gender = 'M'
            elif gender_code in [2, 4, 6]:
                extracted_gender = 'F'
            else:
                return True
            
            # Determine century
            if gender_code in [3, 4]:
                century = 1800
            elif gender_code in [1, 2]:
                century = 1900
            elif gender_code in [5, 6]:
                century = 2000
            else:
                return True
            
            # Extract DOB
            year_2digit = int(nidn[1:3])
            month = int(nidn[3:5])
            day = int(nidn[5:7])
            year = century + year_2digit
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check digit: weighted sum modulus 11
            weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
            weighted_sum = sum(int(nidn[i]) * weights[i] for i in range(12))
            check_digit_expected = weighted_sum % 11
            if check_digit_expected == 10:
                check_digit_expected = 1
            
            check_digit_actual = int(nidn[12])
            if check_digit_expected != check_digit_actual:
                self.last_failure_reason = f"Check digit failed (expected: {check_digit_expected}, actual: {check_digit_actual})"
                if self.verbose:
                    print(f"Romanian NIDN check digit failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("RO", nidn, e, "Romanian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # SWEDISH NIDN VALIDATION (SE)
    # Format: CCYYMMDDXXXX (12 digits)
    # ========================================================================
    
    def _validate_swedish_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Swedish NIDN: CCYYMMDD + sequence (odd=M, even=F) + Luhn check digit.
        """
        if len(nidn) != 12 or not nidn.isdigit():
            return True
        
        try:
            # Extract DOB
            year = int(nidn[0:4])
            month = int(nidn[4:6])
            day = int(nidn[6:8])
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            # Gender: penultimate digit (position 10), odd=male, even=female
            gender_digit = int(nidn[10])
            extracted_gender = 'M' if gender_digit % 2 == 1 else 'F'
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Luhn algorithm check digit
            digits = [int(d) for d in nidn[:11]]  # Exclude check digit
            doubled_sum = 0
            for i, digit in enumerate(digits):
                if i % 2 == 0:
                    doubled = digit * 2
                    doubled_sum += doubled if doubled < 10 else doubled - 9
                else:
                    doubled_sum += digit
            
            check_digit_expected = (10 - (doubled_sum % 10)) % 10
            check_digit_actual = int(nidn[11])
            
            if check_digit_expected != check_digit_actual:
                if self.verbose:
                    print(f"Swedish NIDN Luhn check failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("SE", nidn, e, "Swedish NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # SLOVENIAN NIDN VALIDATION (SI)
    # Format: DDMMYYYXXXXX (13 digits)
    # ========================================================================
    
    def _validate_slovenian_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Slovenian NIDN: DDMMYYY + sequence (000-499=M, 500-999=F) + weighted check digit.
        """
        if len(nidn) != 13 or not nidn.isdigit():
            return True
        
        try:
            # Extract DOB
            day = int(nidn[0:2])
            month = int(nidn[2:4])
            year = int(nidn[4:7]) + 1000  # YYY represents year - 1000
            
            try:
                dob_obj = datetime(year, month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            
            # Gender: sequence number (positions 8-10), 000-499=male, 500-999=female
            sequence = int(nidn[7:10])
            extracted_gender = 'M' if sequence < 500 else 'F'
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check digit: weighted sum
            weights = [7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
            weighted_sum = sum(int(nidn[i]) * weights[i] for i in range(12))
            remainder = weighted_sum % 11
            
            # Reject if remainder is 1
            if remainder == 1:
                if self.verbose:
                    print(f"Slovenian NIDN invalid (remainder=1): {nidn}")
                return False
            
            # If remainder is 11, check digit should be 0
            check_digit_expected = 0 if remainder == 11 else remainder
            check_digit_actual = int(nidn[12])
            
            if check_digit_expected != check_digit_actual:
                if self.verbose:
                    print(f"Slovenian NIDN check digit failed: {nidn}")
                return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("SI", nidn, e, "Slovenian NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # SLOVAK NIDN VALIDATION (SK)
    # Format: YYMMDDXXXX (10 digits)
    # ========================================================================
    
    def _validate_slovak_nidn(self, nidn: str, provided_dob: str, provided_gender: str) -> bool:
        """
        Slovak NIDN: YYMMDD (MM+50 for F) + sequence, entire number divisible by 11 for post-1954.
        """
        if len(nidn) != 10 or not nidn.isdigit():
            return True
        
        try:
            # Extract year and month
            year_2digit = int(nidn[0:2])
            month = int(nidn[2:4])
            day = int(nidn[4:6])
            
            # Gender: month offset
            if month > 50:
                extracted_gender = 'F'
                actual_month = month - 50
            else:
                extracted_gender = 'M'
                actual_month = month
            
            # Determine century (assume 1900s for 54-99, 2000s for 00-53)
            if year_2digit >= 54:
                year = 1900 + year_2digit
            else:
                year = 2000 + year_2digit
            
            try:
                dob_obj = datetime(year, actual_month, day)
                extracted_dob = dob_obj.strftime('%Y-%m-%d')
            except ValueError:
                return True
            
            if not self._compare_dob(extracted_dob, provided_dob):
                return False
            if not self._compare_gender(extracted_gender, provided_gender):
                return False
            
            # Check divisibility by 11 (for post-1954 births)
            if year >= 1954:
                nidn_number = int(nidn)
                if nidn_number % 11 != 0:
                    if self.verbose:
                        print(f"Slovak NIDN not divisible by 11: {nidn}")
                    return False
            
            return True
        except (ValueError, IndexError) as e:
            self._log_validation_exception("SK", nidn, e, "Slovak NIDN validation")
            return True  # Pass with warning logged
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _extract_dob_yymmdd(self, digits: str) -> Optional[str]:
        """Extract DOB from YYMMDD format, returning YYYY-MM-DD."""
        if len(digits) != 6 or not digits.isdigit():
            return None
        
        try:
            year_2digit = int(digits[0:2])
            month = int(digits[2:4])
            day = int(digits[4:6])
            
            # Assume 1900s for 50-99, 2000s for 00-49
            year = 1900 + year_2digit if year_2digit >= 50 else 2000 + year_2digit
            
            dob_obj = datetime(year, month, day)
            return dob_obj.strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    def _extract_dob_ddmmyy(self, digits: str) -> Optional[str]:
        """Extract DOB from DDMMYY format, returning YYYY-MM-DD."""
        if len(digits) != 6 or not digits.isdigit():
            return None
        
        try:
            day = int(digits[0:2])
            month = int(digits[2:4])
            year_2digit = int(digits[4:6])
            
            # Assume 1900s for 50-99, 2000s for 00-49
            year = 1900 + year_2digit if year_2digit >= 50 else 2000 + year_2digit
            
            dob_obj = datetime(year, month, day)
            return dob_obj.strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    def _compare_dob(self, extracted: str, provided: str) -> bool:
        """Compare extracted DOB against provided DOB."""
        if not provided:
            return True  # Can't validate if no DOB provided
        
        normalized_provided = self._normalize_date(provided)
        if not normalized_provided:
            return True  # Can't validate if normalization fails
        
        if extracted != normalized_provided:
            self.last_failure_reason = f"DOB mismatch (ID: {extracted}, Client: {normalized_provided})"
            return False
        return True
    
    def _compare_gender(self, extracted: str, provided: str) -> bool:
        """Compare extracted gender against provided gender."""
        if not provided:
            return True  # Can't validate if no gender provided
        
        normalized_provided = provided.strip().upper()
        if normalized_provided not in ['M', 'F']:
            return True  # Can't validate invalid gender
        
        if extracted != normalized_provided:
            self.last_failure_reason = f"Gender mismatch (ID: {extracted}, Client: {normalized_provided})"
            return False
        return True
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Normalize date string to YYYY-MM-DD format.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Normalized date in YYYY-MM-DD format, or None if invalid
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        if not date_str:
            return None
        
        # Try common formats
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%Y%m%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
