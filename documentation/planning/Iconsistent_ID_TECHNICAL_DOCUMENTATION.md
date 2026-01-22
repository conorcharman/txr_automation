# Inconsistent Identification Code Validation - Technical Documentation

## Document Overview
**Version:** 1.3  
**Date:** January 22, 2026  
**Purpose:** Comprehensive technical documentation for Python refactoring  
**Incident Codes:** 
- Buyer: 7_66
- Seller: 16_20

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Data Model](#data-model)
4. [Core Validation Logic](#core-validation-logic)
5. [Inconsistent ID Validation](#inconsistent-id-validation)
6. [ID Format & Logic Validation](#id-format--logic-validation)
7. [Correction Generation Logic](#correction-generation-logic)
8. [Data Processing Pipeline](#data-processing-pipeline)
9. [Database Queries](#database-queries)
10. [Python Refactoring Guidelines](#python-refactoring-guidelines)
11. [Error Handling](#error-handling)
12. [Appendices](#appendices)

---

## Executive Summary

### Purpose
These macros validate identification codes (IDs) for buyers and sellers in financial transactions, specifically testing for **inconsistent IDs across the same individual over time**. The core principle is:

> **"If an ID changes from one valid type/format/logic to another valid type/format/logic, there is no error. If an ID changes from invalid to valid, or from fallback ID to valid, there IS an error requiring correction."**

### Key Features
- **Person Code Grouping:** Groups records by Person Code (unique client identifier)
- **Chronological Analysis:** Sorts by Trade_Date_Time to analyze ID evolution
- **Smart Correction:** Only corrects invalid IDs using most recent valid ID
- **v5.6 Validation:** Full format and logic validation from base validation suite
- **Joint Account Handling:** Aggregates joint account data with pipe delimiters
- **Tracker Integration:** Checks Italian fiscal codes against external trackers
- **Template Validation:** Compares results against expected values from Kaizen templates

### Version History
- **v1.0:** Initial inconsistent ID logic
- **v1.1:** Added data sorting and visual highlighting
- **v1.2:** Added v5.6 validation logic, Swedish century fix, enhanced CONCAT
- **v1.3:** **Current** - Only corrects invalid IDs, not valid but different IDs

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Main Validation Engine                     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Initialization & Data Loading                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Inconsistent ID Validation (NEW in v1.x)         │  │
│  │     - Group by Person Code                            │  │
│  │     - Sort by Trade_Date_Time                         │  │
│  │     - Validate each ID                                │  │
│  │     - Apply correction logic                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Standard v5.6 Validation                          │  │
│  │     - Format validation (regex patterns)              │  │
│  │     - Logic validation (checksum, DOB, gender)        │  │
│  │     - Alternative type testing                        │  │
│  │     - Correction generation (Swedish/CONCAT/Fallback) │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Post-Processing                                   │  │
│  │     - Italian tracker logic                           │  │
│  │     - Kaizen error lookup validation                  │  │
│  │     - Joint account aggregation                       │  │
│  │     - Template comparison                             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. Output & Reporting                                │  │
│  │     - Write results to worksheet                      │  │
│  │     - Sort by Person Code + Trade_Date_Time           │  │
│  │     - Apply alternating block highlighting            │  │
│  │     - Calculate formula results                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### External Dependencies

#### Reference Data Sources
1. **Country Codes Worksheet**
   - ISO-2 and ISO-3 country code mappings
   - EEA status flags
   - Used for nationality prioritization

2. **ID Formats Worksheet**
   - Regex patterns for each country:ID_type combination
   - Multiple patterns per combination (indexed with :1, :2, :3)
   - Format: `CountryCode:IDType:PatternIndex`

3. **Tracker Files** (Network Paths)
   - Main Tracker: `\\srv01.uk.ajbell.com\common\...\Transaction Reporting - Sharepoint Client Data Remediation DL_31072025.xlsx`
   - Italian Tracker: `\\srv01.uk.ajbell.com\common\...\Transaction Reporting - Italian Fiscal Code Validation.xlsx`

4. **Template Files** (Dynamic Path)
   - Base Path: `F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\`
   - Structure: `{FinancialYear}\{Quarter}\Incident Code Analysis\{FY} {Q} - {IncidentCode}.xlsx`
   - Example: `FY25\Q3\Incident Code Analysis\FY25 Q3 - 7_66.xlsx`

5. **Person Code Gender Matrix**
   - Path: `F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\Automated Accuracy Testing\Data\Reference\Person Code Gender Matrix.xlsx`
   - Used to fill N/A gender values via VLOOKUP

---

## Data Model

### ClientRecord Structure

```python
@dataclass
class ClientRecord:
    """
    Core data structure representing a single transaction record
    Maps to one row in the Excel data
    """
    # Primary identifiers
    row_index: int                    # Excel row number (1-based)
    transaction_ref: str              # Transaction Reference (Column 1)
    person_code: str                  # Person Code (Column 5/6)
    account_type: str                 # Account Type (IND/JNT/etc.) (Column 6/7)
    
    # ID fields
    original_id: str                  # Original ID Code (Column 7/8)
    original_id_type: str             # Original ID Type (Column 8/9)
    final_id: str                     # Corrected/validated ID (computed)
    final_id_type: str                # Corrected/validated ID Type (computed)
    
    # Personal information
    first_name: str                   # First Name(s) (Column 9/10)
    surname: str                      # Surname(s) (Column 10/11)
    date_of_birth: datetime           # Date of Birth (Column 11/12)
    gender: str                       # Gender M/F/N/A (Column 12/13)
    
    # Nationality fields
    primary_nationality: str          # Nationality 1 (Column 13/14)
    secondary_nationality: str        # Nationality 2 (Column 14/15)
    priority_country_code: str        # Computed priority country (ISO-2)
    
    # Timestamp fields (NEW in v1.x)
    trade_date_time_raw: str          # Raw Trade_Date_Time string (Column 15/16)
    trade_date_time_parsed: datetime  # Parsed datetime for sorting
    
    # Validation results
    validation_status: str            # Valid/Invalid/Corrected/etc.
    actions: str                      # Description of actions taken
    tracker_status: str               # Tracker lookup result
    correction_fields: str            # Fields being corrected (e.g., "ID:IDT")
    correction_output: str            # Correction in format "ID:IDType"
    
    # Inconsistent ID validation flags (NEW in v1.x)
    is_valid_id: bool                 # Whether ID passes format+logic validation
    is_fallback_id: bool              # Whether ID matches ISO2_PersonCode pattern
    requires_correction: bool         # Whether this record needs correction
    correction_source: str            # Description of where correction came from
    
    # Formula calculation results (columns 20-22)
    formula1_result: str              # Kaizen Error Y/N flag
    formula2_result: str              # Template VLOOKUP result
    formula3_result: str              # Comparison TRUE/FALSE
```

### ValidationContext Structure

```python
@dataclass
class ValidationContext:
    """
    Context object containing all reference data and external resources
    Initialized once at start and passed throughout validation
    """
    country_dict: Dict[str, str]      # ISO-3/ISO-2 -> ISO-2 mappings
    eea_dict: Dict[str, bool]         # ISO-2 -> EEA status (True/False)
    format_dict: Dict[str, str]       # "CC:IDTYPE:N" -> regex pattern
    regex_engine: re.Pattern          # Compiled regex engine (if using cache)
    main_tracker: pd.DataFrame        # Main tracker data (optional)
    italian_tracker: pd.DataFrame     # Italian tracker data (optional)
    template_workbook: pd.DataFrame   # Template lookup data (optional)
```

### Column Mapping (20-22 columns)

**NOTE:** Buyer vs Seller versions differ only in column headers. Structure is identical.

| Column | Name | Buyer | Seller | Description |
|--------|------|-------|--------|-------------|
| 1 | Transaction Reference | ✓ | ✓ | Unique transaction ID |
| 2 | Account ID | ✓ | ✓ | Client account identifier |
| 3 | BEN Link | ✓ | ✓ | Beneficial owner link code |
| 4 | OWN Link | ✓ | ✓ | Owner link code |
| 5 | Person Code | ✓ | ✓ | Unique person identifier |
| 6 | Account Type | ✓ | ✓ | IND/JNT/etc. |
| 7 | ID Code | Buyer ID | Seller ID | Identification code |
| 8 | Type of ID Code | Buyer ID Type | Seller ID Type | NIDN/PASSPORT/CONCAT/etc. |
| 9 | First Name(s) | Buyer | Seller | First name(s) |
| 10 | Surname(s) | Buyer | Seller | Surname(s) |
| 11 | DOB | Buyer | Seller | Date of birth |
| 12 | Gender | Buyer | Seller | M/F/N/A |
| 13 | Nationality 1 | ✓ | ✓ | Primary nationality (ISO-2/3) |
| 14 | Nationality 2 | ✓ | ✓ | Secondary nationality (ISO-2/3) |
| 15 | Trade_Date_Time | ✓ | ✓ | Format: YYYY-MM-DD-HH-MM-SS-MSMS |
| 16 | Correction | ✓ | ✓ | Correction output "ID:IDType" |
| 17 | Correction Field | ✓ | ✓ | Fields corrected "ID:IDT" |
| 18 | Tracker Status | ✓ | ✓ | Tracker lookup result |
| 19 | Actions | ✓ | ✓ | Validation actions description |
| 20 | Formula 1 | ✓ | ✓ | Kaizen Error Y/N (calculated) |
| 21 | Formula 2 | ✓ | ✓ | Template VLOOKUP (calculated) |
| 22 | Formula 3 | ✓ | ✓ | Comparison TRUE/FALSE (calculated) |

---

## Core Validation Logic

### Validation Philosophy (v5.6 Base)

The validation follows a **three-step decision tree**:

```
Step 1: Validate Original ID + Type
   ├─> Format valid? (regex test)
   │   ├─> Yes: Logic valid? (checksum/DOB/gender)
   │   │   ├─> Yes: ✓ PASS (originalTypeValid = True)
   │   │   └─> No: Continue to Step 2
   │   └─> No: Continue to Step 2
   
Step 2: Test Alternative ID Types (if Step 1 failed)
   ├─> For each type in [NIDN, PASSPORT, CONCAT, CCPT, PASS, DLIC]:
   │   ├─> Format valid? AND Logic valid?
   │   │   ├─> Yes: Set correctTypeFound, correctTypeLogicValid
   │   │   └─> No: Continue to next type
   │   └─> Stop at first fully valid match
   
Step 3: Generate Correction (if no valid type found)
   ├─> Swedish Century Fix eligible? (SE + NIDN + 10 digits + valid DOB)
   │   ├─> Yes: Try adding century prefix (first 2 digits of birth year)
   │   │   ├─> Valid? Return corrected ID
   │   │   └─> Invalid? Continue
   │   └─> No: Continue
   ├─> CONCAT eligible? (Has DOB + Names + Country allows CONCAT)
   │   ├─> Yes: Generate CONCAT ID
   │   │   ├─> Valid format AND logic? Return CONCAT
   │   │   └─> Invalid? Continue to fallback
   │   └─> No: Continue to fallback
   └─> Generate Fallback ID: CountryCode_PersonCode (always NIDN type)
```

### ID Type Definitions

| Type | Description | Example | Countries |
|------|-------------|---------|-----------|
| **NIDN** | National Identity Number | GB: AB123456C, SE: 19850531-1234 | Most European |
| **PASSPORT** | Passport Number | GB: 123456789 | Universal |
| **CONCAT** | Concatenated ID (DOB+Names) | GB19850531JOHNSSMITH | Generated when no valid ID |
| **CCPT** | Country-Specific Type | IT: Fiscal Code | Specific countries |
| **PASS** | Alternative Passport Type | Varies | Some countries |
| **DLIC** | Driver's License | US states, some EU | Some countries |

### Priority Order for Alternative Testing
The alternative types are tested in the **natural order** from the ID Formats worksheet:
1. NIDN
2. PASSPORT
3. CONCAT
4. CCPT
5. PASS
6. DLIC

This order reflects the hierarchy of ID reliability.

---

## Inconsistent ID Validation

### Conceptual Overview

**Problem Statement:**  
Same person (same Person Code) may have different IDs across multiple transactions over time. This could be due to:
1. Data entry errors in earlier transactions
2. Legitimate change in nationality (new passport)
3. System-generated fallback IDs being replaced with real IDs
4. Incorrect ID type assignments

**Solution Approach:**  
- Group all records by Person Code
- Sort chronologically by Trade_Date_Time
- Validate each ID independently
- Apply correction logic: **only correct invalid IDs, not valid IDs that differ**

### Algorithm Flow

```python
def process_inconsistent_id_validation(records: List[ClientRecord], 
                                      context: ValidationContext) -> None:
    """
    Main inconsistent ID validation logic
    """
    # Step 1: Parse all Trade_Date_Time strings to datetime objects
    for record in records:
        record.trade_date_time_parsed = parse_trade_date_time(
            record.trade_date_time_raw
        )
    
    # Step 2: Group records by Person Code
    person_groups = group_by_person_code(records)
    
    # Step 3: Process each person group
    for person_code, record_indices in person_groups.items():
        # Only process groups with multiple records
        if len(record_indices) <= 1:
            continue
            
        # Sort indices by trade_date_time (chronological order)
        record_indices.sort(key=lambda idx: records[idx].trade_date_time_parsed)
        
        # Check if IDs or ID types differ within this group
        if not has_inconsistent_ids(records, record_indices):
            continue  # All IDs are identical, no inconsistency
        
        # Step 4: Validate each ID in the group
        for idx in record_indices:
            record = records[idx]
            
            # Check if fallback ID pattern
            record.is_fallback_id = is_fallback_id_pattern(
                record.original_id,
                record.person_code,
                record.priority_country_code
            )
            
            # Validate format + logic
            record.is_valid_id = validate_id_complete(
                record.original_id,
                record.original_id_type,
                record.priority_country_code,
                record.date_of_birth,
                record.gender,
                context
            )
            
            # If original type invalid, check if valid with different type
            if not record.is_valid_id and not record.is_fallback_id:
                detect_valid_id_with_wrong_type(record, context)
        
        # Step 5: Apply correction logic
        apply_inconsistent_id_corrections(records, record_indices)
```

### Key Functions

#### 1. Parse Trade_Date_Time

```python
def parse_trade_date_time(raw_string: str) -> datetime:
    """
    Parse Trade_Date_Time format: YYYY-MM-DD-HH-MM-SS-MSMS
    
    Args:
        raw_string: String like "2024-03-15-14-30-45-123456"
    
    Returns:
        datetime object
    
    Examples:
        >>> parse_trade_date_time("2024-03-15-14-30-45-123456")
        datetime(2024, 3, 15, 14, 30, 45)
    """
    clean = raw_string.strip()
    
    # Minimum length check
    if len(clean) < 19:
        return datetime.min
    
    # Extract components
    year = int(clean[0:4])
    month = int(clean[5:7])
    day = int(clean[8:10])
    hour = int(clean[11:13])
    minute = int(clean[14:16])
    second = int(clean[17:19])
    
    return datetime(year, month, day, hour, minute, second)
```

#### 2. Group by Person Code

```python
def group_by_person_code(records: List[ClientRecord]) -> Dict[str, List[int]]:
    """
    Group record indices by Person Code
    
    Returns:
        Dictionary mapping person_code -> list of record indices
    """
    groups = defaultdict(list)
    
    for idx, record in enumerate(records):
        if record.person_code:
            groups[record.person_code].append(idx)
    
    return dict(groups)
```

#### 3. Check for Inconsistent IDs

```python
def has_inconsistent_ids(records: List[ClientRecord], 
                         indices: List[int]) -> bool:
    """
    Check if a group has different IDs or ID types
    
    Returns:
        True if IDs or types differ within the group
    """
    if len(indices) <= 1:
        return False
    
    first_record = records[indices[0]]
    first_id = first_record.original_id.strip()
    first_type = first_record.original_id_type.strip()
    
    for idx in indices[1:]:
        record = records[idx]
        if (record.original_id.strip() != first_id or 
            record.original_id_type.strip() != first_type):
            return True
    
    return False
```

#### 4. Fallback ID Pattern Detection

```python
def is_fallback_id_pattern(id_value: str, 
                           person_code: str, 
                           country_code: str) -> bool:
    """
    Check if ID matches the ISO-2Code_PersonCode fallback pattern
    
    Pattern: {CountryCode}_{PersonCode}
    Examples:
        - "GB_12345" (UK fallback)
        - "SE_98765" (Sweden fallback)
    
    Args:
        id_value: The ID to check
        person_code: The person code for this record
        country_code: ISO-2 country code
    
    Returns:
        True if ID matches fallback pattern
    """
    clean_id = id_value.strip().upper()
    clean_pc = person_code.strip()
    clean_cc = country_code.strip().upper()
    
    if len(clean_cc) == 2 and clean_pc:
        expected = f"{clean_cc}_{clean_pc}"
        return clean_id == expected
    
    return False
```

#### 5. Apply Inconsistent ID Corrections

```python
def apply_inconsistent_id_corrections(records: List[ClientRecord], 
                                     indices: List[int]) -> None:
    """
    Apply correction logic based on v1.3 rules:
    - Only correct INVALID IDs
    - Use most recent VALID ID (search backwards chronologically)
    - Do NOT correct valid IDs even if they differ from earlier IDs
    
    Algorithm:
        For each record in chronological order:
            If record is invalid OR has fallback ID:
                Search backwards from this record
                Find most recent valid ID (not fallback)
                If found: Apply correction
                If not found: Let standard pipeline handle it
    """
    for i, current_idx in enumerate(indices):
        current_record = records[current_idx]
        
        # Only process invalid or fallback IDs
        if not current_record.is_valid_id or current_record.is_fallback_id:
            
            # Search backwards from previous record
            most_recent_valid_id = None
            most_recent_valid_type = None
            most_recent_valid_date = None
            
            for j in range(i - 1, -1, -1):  # Go backwards
                prior_idx = indices[j]
                prior_record = records[prior_idx]
                
                # Found a valid ID that's not a fallback
                if prior_record.is_valid_id and not prior_record.is_fallback_id:
                    most_recent_valid_id = prior_record.original_id
                    most_recent_valid_type = prior_record.original_id_type
                    most_recent_valid_date = prior_record.trade_date_time_parsed
                    break
            
            # Apply correction if we found a valid prior ID
            if most_recent_valid_id:
                current_record.final_id = most_recent_valid_id
                current_record.final_id_type = most_recent_valid_type
                current_record.correction_output = f"{most_recent_valid_id}:{most_recent_valid_type}"
                current_record.correction_fields = "ID:IDT"
                current_record.requires_correction = True
                current_record.correction_source = f"Most recent valid ID from {most_recent_valid_date}"
                current_record.validation_status = "Corrected - Inconsistent ID"
                current_record.actions = "Inconsistent ID - Corrected to most recent valid ID"
            else:
                # No prior valid ID - let standard pipeline handle correction
                current_record.requires_correction = True
                current_record.correction_source = "No prior valid ID - will generate correction"
                current_record.validation_status = "Requires correction generation"
                current_record.actions = "Inconsistent ID - No prior valid ID to use"
```

### Important Edge Cases

#### Case 1: Valid ID Changes to Different Valid ID
```
Record 1: 2024-01-01, ID=AB123456C, Type=NIDN, Valid=True
Record 2: 2024-06-01, ID=123456789, Type=PASSPORT, Valid=True

Result: NO CORRECTION
Reason: Both IDs are valid. Person may have legitimately changed nationality.
```

#### Case 2: Invalid ID Changes to Valid ID
```
Record 1: 2024-01-01, ID=INVALID123, Type=NIDN, Valid=False
Record 2: 2024-06-01, ID=AB123456C, Type=NIDN, Valid=True

Result: CORRECT Record 1 to AB123456C:NIDN
Reason: Earlier ID was invalid, correct it to the valid one.
```

#### Case 3: Fallback ID Changes to Valid ID
```
Record 1: 2024-01-01, ID=GB_12345, Type=NIDN, IsFallback=True
Record 2: 2024-06-01, ID=AB123456C, Type=NIDN, Valid=True

Result: CORRECT Record 1 to AB123456C:NIDN
Reason: Fallback IDs are system-generated placeholders, should be corrected.
```

#### Case 4: Multiple Valid IDs Over Time
```
Record 1: 2024-01-01, ID=AB123456C, Type=NIDN, Valid=True
Record 2: 2024-03-01, ID=INVALID123, Type=NIDN, Valid=False
Record 3: 2024-06-01, ID=123456789, Type=PASSPORT, Valid=True

Result: 
  - Record 1: NO CORRECTION (already valid)
  - Record 2: CORRECT to 123456789:PASSPORT (most recent valid)
  - Record 3: NO CORRECTION (already valid)

Reason: Backwards search finds most recent valid ID before each invalid record.
```

---

## ID Format & Logic Validation

### Format Validation (Regex-Based)

#### ID Formats Worksheet Structure

```
| Country Code | ID Type | Regex Pattern                          |
|--------------|---------|----------------------------------------|
| GB           | NIDN    | ^[A-Z]{2}[0-9]{6}[A-D]$               |
| GB           | NIDN    | ^[0-9]{2}[0-9]{6}[A-D]$               |
| SE           | NIDN    | ^[0-9]{12}$                            |
| SE           | NIDN    | ^[0-9]{10}$                            |
| IT           | NIDN    | ^[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]$ |
```

**Key Points:**
1. Multiple patterns per country:type combination
2. Indexed as `CountryCode:IDType:1`, `CountryCode:IDType:2`, etc.
3. Patterns tested in sequence until match found
4. Both original ID and ID with country prefix stripped are tested

#### Format Testing Algorithm

```python
def test_id_against_all_patterns(test_id: str,
                                country_code: str,
                                id_type: str,
                                format_dict: Dict[str, str]) -> bool:
    """
    Test an ID against all available regex patterns for a country:type
    
    Tests both:
    1. Original ID as-is
    2. ID with country code prefix removed (if present)
    
    Args:
        test_id: The ID to validate
        country_code: ISO-2 country code
        id_type: ID type (NIDN, PASSPORT, etc.)
        format_dict: Dictionary of regex patterns
    
    Returns:
        True if ID matches any pattern
    """
    clean_id = test_id.strip().upper()
    base_key = f"{country_code.upper()}:{id_type.upper()}"
    
    # Create test versions
    test_versions = [clean_id]
    
    # If ID starts with country code, also test without it
    if len(clean_id) > 2 and clean_id[:2] == country_code.upper():
        test_versions.append(clean_id[2:])
    
    # Test against all patterns for this country:type
    pattern_index = 1
    while f"{base_key}:{pattern_index}" in format_dict:
        pattern_key = f"{base_key}:{pattern_index}"
        regex_pattern = format_dict[pattern_key]
        
        # Clean malformed patterns (wrapped in extra brackets)
        if (regex_pattern.startswith('[') and regex_pattern.endswith(']') and
            regex_pattern.count('[') > 1):
            regex_pattern = regex_pattern[1:-1]
        
        # Test each version
        for test_version in test_versions:
            if re.match(regex_pattern, test_version, re.IGNORECASE):
                return True
        
        pattern_index += 1
    
    return False
```

### Logic Validation (Checksum & Business Rules)

**Note:** The VBA code has a placeholder for `ValidateIDLogic()` that returns True. In production, this would contain country-specific validation logic.

#### Common Logic Validation Rules

```python
def validate_id_logic(id_value: str,
                     id_type: str,
                     country_code: str,
                     dob: str,  # Format: YYYYMMDD
                     gender: str) -> bool:
    """
    Validate ID against country-specific business rules
    
    This is a placeholder - actual implementation would contain:
    1. Checksum validation (e.g., Luhn algorithm for GB NINO)
    2. DOB extraction and verification (e.g., Swedish personnummer)
    3. Gender code verification (e.g., Italian fiscal code)
    4. Character position validation
    
    Args:
        id_value: The ID to validate (without country prefix)
        id_type: ID type
        country_code: ISO-2 country code
        dob: Date of birth as YYYYMMDD string
        gender: Gender code (M/F/N/A)
    
    Returns:
        True if ID passes all logic checks
    """
    # Country-specific logic would go here
    # For now, return True (placeholder)
    
    if country_code == "GB" and id_type == "NIDN":
        return validate_gb_nino_logic(id_value, dob, gender)
    elif country_code == "SE" and id_type == "NIDN":
        return validate_se_personnummer_logic(id_value, dob, gender)
    elif country_code == "IT" and id_type == "NIDN":
        return validate_it_fiscal_code_logic(id_value, dob, gender)
    
    # Default: assume valid if format passed
    return True

def validate_gb_nino_logic(nino: str, dob: str, gender: str) -> bool:
    """
    Validate UK National Insurance Number logic
    
    Rules:
    1. No D, F, I, Q, U, V at start
    2. No O at position 2
    3. Suffix must be A, B, C, or D
    4. First 2 chars can be numeric (temp NI numbers)
    """
    # Implementation would include checksum and prefix validation
    return True  # Placeholder

def validate_se_personnummer_logic(personnummer: str, dob: str, gender: str) -> bool:
    """
    Validate Swedish Personnummer logic
    
    Rules:
    1. Format: YYYYMMDDXXXX or YYMMDDXXXX
    2. DOB must match first 6-8 digits
    3. Last digit before checksum indicates gender (odd=male, even=female)
    4. Last digit is Luhn checksum
    """
    # Implementation would include DOB extraction and checksum
    return True  # Placeholder

def validate_it_fiscal_code_logic(fiscal_code: str, dob: str, gender: str) -> bool:
    """
    Validate Italian Fiscal Code (Codice Fiscale) logic
    
    Rules:
    1. Complex encoding of surname, name, DOB, gender, and birth place
    2. Character 9 indicates gender (odd month digit = male, even = female)
    3. Last character is control code
    """
    # Implementation would include complex fiscal code validation
    return True  # Placeholder
```

### Complete Validation Function

```python
def validate_id_complete(id_value: str,
                        id_type: str,
                        country_code: str,
                        dob: datetime,
                        gender: str,
                        context: ValidationContext) -> bool:
    """
    Complete validation: Format + Logic
    
    Returns True only if BOTH format and logic are valid
    """
    # Step 1: Format validation
    if not test_id_against_all_patterns(id_value, country_code, id_type, 
                                       context.format_dict):
        return False
    
    # Step 2: Strip country prefix if present
    id_for_logic = id_value
    if len(id_value) > 2 and id_value[:2].upper() == country_code.upper():
        id_for_logic = id_value[2:]
    
    # Step 3: Logic validation
    dob_str = dob.strftime("%Y%m%d")
    return validate_id_logic(id_for_logic, id_type, country_code, 
                            dob_str, gender)
```

---

## Correction Generation Logic

### Correction Hierarchy (v5.6)

When an ID fails validation, corrections are attempted in this order:

```
1. Swedish Century Fix (SE country + NIDN + 10 digits)
   ↓ (if not applicable or fails)
2. CONCAT ID Generation (if eligible)
   ↓ (if not eligible or fails)
3. Fallback ID (CountryCode_PersonCode)
```

### 1. Swedish Century Logic

**Problem:** Swedish personnummer missing century prefix  
**Solution:** Add first 2 digits of birth year

```python
def try_swedish_century_fix(record: ClientRecord, 
                           context: ValidationContext) -> bool:
    """
    Attempt to fix Swedish NIDNs missing century prefix
    
    Eligibility:
    - Country code = SE
    - ID type = NIDN
    - ID length = 10 digits (missing century)
    - Has valid date of birth
    
    Solution:
    - Extract century from DOB (first 2 digits of year)
    - Prepend to ID (e.g., "850531-1234" -> "19850531-1234")
    - Validate corrected ID
    
    Returns:
        True if correction successful
    """
    # Check eligibility
    if not is_swedish_century_eligible(record):
        return False
    
    # Extract century from DOB
    birth_year = record.date_of_birth.year
    century = str(birth_year)[:2]  # e.g., "19" from 1985
    
    # Build corrected ID
    clean_id = record.original_id.strip()
    
    # Remove SE prefix if present
    if clean_id[:2].upper() == "SE":
        clean_id = clean_id[2:]
    
    corrected_id = century + clean_id
    
    # Test corrected ID
    format_valid = test_id_against_all_patterns(
        corrected_id, "SE", "NIDN", context.format_dict
    )
    
    if not format_valid:
        return False
    
    logic_valid = validate_id_logic(
        corrected_id, "NIDN", "SE",
        record.date_of_birth.strftime("%Y%m%d"),
        record.gender
    )
    
    if logic_valid:
        record.final_id = corrected_id
        record.final_id_type = "NIDN"
        record.validation_status = "Corrected"
        record.actions = "Review - Century Added"
        record.correction_fields = "ID:IDT"
        record.correction_output = f"{corrected_id}:NIDN"
        return True
    
    return False

def is_swedish_century_eligible(record: ClientRecord) -> bool:
    """Check if record eligible for Swedish century fix"""
    if record.priority_country_code != "SE":
        return False
    if record.original_id_type.upper() != "NIDN":
        return False
    if not record.date_of_birth:
        return False
    
    clean_id = record.original_id.strip()
    if clean_id[:2].upper() == "SE":
        clean_id = clean_id[2:]
    
    # Must be exactly 10 digits
    if len(clean_id) != 10 or not clean_id.isdigit():
        return False
    
    return True
```

### 2. CONCAT ID Generation

**CONCAT ID Format:** `{CountryCode}{YYYYMMDD}{FirstName5Chars}{Surname5Chars}`

Example: `GB19850531JOHNSSMITH`

```python
def try_generate_concat(record: ClientRecord, 
                       context: ValidationContext) -> bool:
    """
    Generate and validate CONCAT ID
    
    Eligibility:
    - Has DOB, first name, and surname
    - Country either:
      a) Has CONCAT format defined in ID Formats, OR
      b) Has NO formats defined (rest of world)
    
    Generation:
    - Clean and format names (5 chars each, padded with #)
    - Concatenate: CC + YYYYMMDD + FirstName + Surname
    
    Validation:
    - If country has formats: Test against CONCAT patterns
    - If country has no formats: Accept automatically
    - Both cases: Must pass logic validation
    
    Returns:
        True if CONCAT generated and valid
    """
    # Check eligibility
    if not is_concat_eligible(record, context):
        return False
    
    # Generate CONCAT ID
    concat_id = build_concat_id(record)
    
    # Check if country has defined formats
    has_formats = has_country_formats(record.priority_country_code, 
                                     context.format_dict)
    
    # Format validation
    if has_formats:
        format_valid = test_id_against_all_patterns(
            concat_id, record.priority_country_code, "CONCAT",
            context.format_dict
        )
    else:
        # Rest of world - no format to test against
        format_valid = True
    
    if not format_valid:
        return False
    
    # Logic validation
    logic_valid = validate_id_logic(
        concat_id, "CONCAT", record.priority_country_code,
        record.date_of_birth.strftime("%Y%m%d"),
        record.gender
    )
    
    if logic_valid:
        record.final_id = concat_id
        record.final_id_type = "CONCAT"
        record.validation_status = "Corrected"
        record.actions = "Fail - Replaced With CONCAT"
        record.correction_fields = "ID:IDT"
        record.correction_output = f"{concat_id}:CONCAT"
        return True
    
    return False

def is_concat_eligible(record: ClientRecord, 
                      context: ValidationContext) -> bool:
    """
    Check if record eligible for CONCAT generation
    
    Requirements:
    1. Has DOB, first name, and surname
    2. Either:
       - Country has CONCAT format defined, OR
       - Country has no formats at all (rest of world)
    """
    # Check required data
    has_data = (record.date_of_birth and 
                record.first_name.strip() and 
                record.surname.strip())
    
    if not has_data:
        return False
    
    # Check if CONCAT format exists
    concat_key = f"{record.priority_country_code}:CONCAT:1"
    has_concat_format = concat_key in context.format_dict
    
    # Check if country has any formats
    has_any_format = has_country_formats(record.priority_country_code, 
                                        context.format_dict)
    
    # Eligible if CONCAT format exists OR no formats at all
    return has_concat_format or not has_any_format

def has_country_formats(country_code: str, 
                       format_dict: Dict[str, str]) -> bool:
    """
    Check if a country has ANY format patterns defined
    Used to distinguish countries with defined formats vs rest of world
    """
    id_types = ["NIDN", "CONCAT", "CCPT", "TIN", "PASSPORT", "PASS", "DLIC"]
    
    for id_type in id_types:
        key = f"{country_code}:{id_type}:1"
        if key in format_dict:
            return True
    
    return False

def build_concat_id(record: ClientRecord) -> str:
    """
    Build CONCAT ID from components
    
    Format: {CC}{YYYYMMDD}{FirstName5}{Surname5}
    """
    date_str = record.date_of_birth.strftime("%Y%m%d")
    first_name = clean_name_for_concat(record.first_name, is_surname=False)
    surname = clean_name_for_concat(record.surname, is_surname=True)
    
    return f"{record.priority_country_code}{date_str}{first_name}{surname}"

def clean_name_for_concat(name_value: str, is_surname: bool) -> str:
    """
    Clean and format name for CONCAT ID
    
    Rules:
    1. Convert to uppercase
    2. Handle comma delimiters (take first part)
    3. For surnames: Remove prefixes (VON, VAN, DE, etc.)
    4. For first names: Take first word only
    5. Remove special characters (-, ', ., space)
    6. Pad/truncate to exactly 5 characters with #
    
    Args:
        name_value: Raw name string
        is_surname: True if surname, False if first name
    
    Returns:
        5-character uppercase string padded with #
    
    Examples:
        >>> clean_name_for_concat("John-Paul", False)
        'JOHNP'
        >>> clean_name_for_concat("von Smith", True)
        'SMITH'
        >>> clean_name_for_concat("Lee", False)
        'LEE##'
    """
    if not name_value.strip():
        return "#####"
    
    cleaned = name_value.strip().upper()
    
    # Handle comma delimiters - take first part
    if ',' in cleaned:
        cleaned = cleaned.split(',')[0].strip()
    
    if is_surname:
        # Remove prefixes for surnames
        cleaned = remove_name_prefixes(cleaned)
    else:
        # For first names, take first word only
        words = cleaned.split()
        if words:
            cleaned = words[0]
    
    # Remove special characters
    cleaned = cleaned.replace('-', '')
    cleaned = cleaned.replace("'", '')
    cleaned = cleaned.replace('.', '')
    cleaned = cleaned.replace(' ', '')
    
    if not cleaned:
        cleaned = "#####"
    
    # Pad or truncate to 5 characters
    return (cleaned + "#####")[:5]

def remove_name_prefixes(surname: str) -> str:
    """
    Remove common name prefixes from surnames
    
    Prefixes (in priority order):
    - VON DER, VAN DER, VAN DE, DE LA (two-word)
    - VON, VAN, DE, DI, DA, MC, MAC, O (one-word)
    """
    prefixes = [
        "VON DER ", "VAN DER ", "VAN DE ", "DE LA ",  # Two-word
        "VON ", "VAN ", "DE ", "DI ", "DA ", "MC ", "MAC ", "O "  # One-word
    ]
    
    clean = surname.strip().upper() + " "  # Add space for matching
    
    for prefix in prefixes:
        if clean.startswith(prefix):
            return clean[len(prefix):].strip()
    
    return surname.strip().upper()
```

### 3. Fallback ID Generation

```python
def generate_fallback_id(record: ClientRecord) -> None:
    """
    Generate fallback ID when all other corrections fail
    
    Format: {CountryCode}_{PersonCode}
    Type: Always NIDN
    
    Examples:
        - GB_12345
        - SE_98765
        - IT_54321
    """
    fallback_id = f"{record.priority_country_code}_{record.person_code}"
    
    record.final_id = fallback_id
    record.final_id_type = "NIDN"
    record.validation_status = "Corrected"
    record.actions = "Fail - Replaced With fallback"
    record.correction_fields = "ID:IDT"
    record.correction_output = f"{fallback_id}:NIDN"
```

---

## Data Processing Pipeline

### Complete Processing Flow

```python
def main_validation_pipeline(financial_year: str, 
                            quarter: str, 
                            incident_code: str) -> None:
    """
    Main validation pipeline - coordinates all validation steps
    """
    # ==================================================================
    # PHASE 1: INITIALIZATION
    # ==================================================================
    
    # 1.1 Initialize context
    context = initialize_validation_context()
    
    # 1.2 Load reference data
    load_country_mappings(context)
    load_id_formats(context)
    load_tracker_workbooks(context)  # Optional
    load_template_workbook(context, financial_year, quarter, incident_code)  # Optional
    
    # 1.3 Preprocess data formatting
    preprocess_data_formatting(incident_code)
    
    # 1.4 Load client data
    records = load_client_data(incident_code, context)
    
    # ==================================================================
    # PHASE 2: INCONSISTENT ID VALIDATION (v1.x Logic)
    # ==================================================================
    
    # 2.1 Parse trade date/times
    parse_trade_date_times(records)
    
    # 2.2 Group by person code
    person_groups = group_by_person_code(records)
    
    # 2.3 Process each person group
    for person_code, record_indices in person_groups.items():
        if len(record_indices) > 1:
            # Sort by trade date/time
            record_indices.sort(key=lambda i: records[i].trade_date_time_parsed)
            
            # Check for inconsistencies
            if has_inconsistent_ids(records, record_indices):
                # Validate each ID
                validate_ids_in_group(records, record_indices, context)
                
                # Apply correction logic
                apply_inconsistent_id_corrections(records, record_indices)
    
    # ==================================================================
    # PHASE 3: STANDARD VALIDATION (v5.6 Logic)
    # ==================================================================
    
    for record in records:
        # Skip if already corrected by inconsistent ID logic
        if record.requires_correction and record.correction_output:
            continue
        
        # Skip if no valid country code
        if not record.priority_country_code:
            record.validation_status = "Invalid Country"
            record.actions = "Skip - Invalid Nationality"
            continue
        
        # Process single client validation
        process_single_client(record, context)
    
    # ==================================================================
    # PHASE 4: POST-PROCESSING
    # ==================================================================
    
    # 4.1 Italian tracker logic (for IT country codes only)
    for record in records:
        if record.priority_country_code == "IT":
            apply_italian_tracker_logic(record, context)
    
    # 4.2 Kaizen error lookup validation (for records that passed)
    for record in records:
        if record.validation_status == "Valid" and not record.correction_output:
            apply_kaizen_error_lookup_validation(record, context)
    
    # ==================================================================
    # PHASE 5: OUTPUT & REPORTING
    # ==================================================================
    
    # 5.1 Write results to worksheet
    write_results(records, incident_code)
    
    # 5.2 Sort data by Person Code + Trade_Date_Time
    sort_data_for_review(incident_code)
    
    # 5.3 Calculate formula results (AFTER sorting)
    calculate_formula_results(records, context, incident_code)
    
    # 5.4 Apply alternating block highlighting
    apply_person_code_block_highlighting(incident_code)
    
    # 5.5 Handle joint account aggregation (if needed)
    handle_joint_account_aggregation(incident_code)
    
    # ==================================================================
    # PHASE 6: CLEANUP
    # ==================================================================
    
    cleanup_resources(context)
    
    # Show completion message
    print(f"Validation complete: {len(records)} records processed")
```

### Standard Validation Logic (v5.6)

```python
def process_single_client(record: ClientRecord, 
                         context: ValidationContext) -> None:
    """
    Process a single client record through v5.6 validation pipeline
    """
    original_type_valid = False
    correct_type_found = None
    correct_type_logic_valid = False
    
    # ========================================
    # STEP 1: Validate Original ID + Type
    # ========================================
    
    if record.original_id_type:
        # Test format
        format_valid = test_id_against_all_patterns(
            record.original_id,
            record.priority_country_code,
            record.original_id_type,
            context.format_dict
        )
        
        if format_valid:
            # Strip country prefix for logic validation
            id_for_logic = record.original_id
            if (len(record.original_id) > 2 and 
                record.original_id[:2].upper() == record.priority_country_code.upper()):
                id_for_logic = record.original_id[2:]
            
            # Test logic
            logic_valid = validate_id_logic(
                id_for_logic,
                record.original_id_type,
                record.priority_country_code,
                record.date_of_birth.strftime("%Y%m%d"),
                record.gender
            )
            
            if logic_valid:
                # Original type completely valid
                original_type_valid = True
                record.final_id_type = record.original_id_type
            else:
                # Format valid but logic issues
                record.actions = "Valid format - Logic query"
    
    # ========================================
    # STEP 2: Test Alternative Types
    # ========================================
    
    if not original_type_valid and record.original_id:
        allowed_types = ["NIDN", "PASSPORT", "CONCAT", "CCPT", "PASS", "DLIC"]
        
        for test_type in allowed_types:
            if test_type == record.original_id_type:
                continue  # Already tested in Step 1
            
            # Test format
            format_valid = test_id_against_all_patterns(
                record.original_id,
                record.priority_country_code,
                test_type,
                context.format_dict
            )
            
            if format_valid:
                # Strip country prefix for logic validation
                id_for_logic = record.original_id
                if (len(record.original_id) > 2 and 
                    record.original_id[:2].upper() == record.priority_country_code.upper()):
                    id_for_logic = record.original_id[2:]
                
                # Test logic
                logic_valid = validate_id_logic(
                    id_for_logic,
                    test_type,
                    record.priority_country_code,
                    record.date_of_birth.strftime("%Y%m%d"),
                    record.gender
                )
                
                # Store first match
                if not correct_type_found:
                    correct_type_found = test_type
                    correct_type_logic_valid = logic_valid
                    record.final_id = record.original_id
                    record.final_id_type = test_type
                
                # If fully valid, stop searching
                if logic_valid:
                    correct_type_found = test_type
                    correct_type_logic_valid = True
                    record.final_id = record.original_id
                    record.final_id_type = test_type
                    break
    
    # ========================================
    # STEP 3: Handle Results
    # ========================================
    
    if original_type_valid:
        # Original ID and type completely valid
        if record.priority_country_code == "IT" and record.final_id_type == "NIDN":
            record.actions = "Pass - Check Tracker"
        else:
            record.actions = "Pass"
        record.validation_status = "Valid"
        
    elif correct_type_found:
        # Found alternative valid type
        record.final_id_type = correct_type_found
        record.correction_fields = "ID:IDT"
        record.correction_output = f"{record.final_id}:{record.final_id_type}"
        
        if correct_type_logic_valid:
            record.validation_status = "Valid"
            if record.priority_country_code == "IT" and correct_type_found == "NIDN":
                record.actions = "Pass - Check Tracker"
            else:
                record.actions = "Valid format - ID Type updated"
        else:
            record.validation_status = "Logic Issue"
            record.actions = "Valid format - Logic query - ID Type updated"
    
    else:
        # No valid format found - try correction generation
        if try_swedish_century_fix(record, context):
            pass  # Correction applied
        elif try_generate_concat(record, context):
            pass  # CONCAT generated
        else:
            # Fallback logic
            if is_concat_eligible(record, context):
                # CONCAT is allowed but failed - still use fallback
                generate_fallback_id(record)
            else:
                generate_fallback_id(record)
```

### Italian Tracker Logic

```python
def apply_italian_tracker_logic(record: ClientRecord, 
                               context: ValidationContext) -> None:
    """
    Apply Italian fiscal code tracker logic
    
    Rules:
    - If action is "Pass - Check Tracker":
      - If status is "Not Started", "In Progress", "Awaiting Response", or "Not On tracker":
        → Generate fallback ID
      - If status is "Complete":
        → Keep original values (no correction)
    """
    # Get tracker status
    record.tracker_status = get_tracker_status(record, context)
    
    # Apply specific logic
    if record.actions == "Pass - Check Tracker":
        needs_fallback_statuses = [
            "Not Started",
            "Not On tracker",
            "In Progress",
            "Awaiting Response"
        ]
        
        if record.tracker_status in needs_fallback_statuses:
            # Generate fallback correction
            generate_fallback_id(record)
            record.actions = "Pass - Check Tracker - Replaced With fallback"
        elif record.tracker_status == "Complete":
            record.actions = "Pass - Check Tracker - Complete"
            # Keep original values
            record.correction_fields = ""
            record.correction_output = ""

def get_tracker_status(record: ClientRecord, 
                      context: ValidationContext) -> str:
    """
    Lookup tracker status for a person code
    
    Checks:
    1. Italian tracker (Column C:G, return column G)
    2. Main tracker (Column J:N, return column N)
    
    Returns:
        Tracker status or "Not On tracker"
    """
    # Check Italian tracker first
    if context.italian_tracker is not None:
        result = lookup_value_in_tracker(
            context.italian_tracker,
            record.person_code,
            lookup_col='C',  # Person Code column
            return_col='G'   # Status column
        )
        if result:
            return result
    
    # Check main tracker
    if context.main_tracker is not None:
        result = lookup_value_in_tracker(
            context.main_tracker,
            record.person_code,
            lookup_col='J',  # Person Code column
            return_col='N'   # Status column
        )
        if result:
            return result
    
    return "Not On tracker"
```

### Kaizen Error Lookup Validation

```python
def apply_kaizen_error_lookup_validation(record: ClientRecord, 
                                        context: ValidationContext) -> None:
    """
    New Step 5: Validate passed records against Kaizen error lookup
    
    Only applies to records that:
    - Have originalTypeValid = True
    - No correction already generated
    
    Process:
    1. Perform template lookup on Transaction Reference
    2. Compare actual ID:IDType with expected ID:IDType
    3. If mismatch: Set correction but keep "Pass" action
    """
    # Skip if already has correction
    if record.correction_output:
        return
    
    # Get expected value from template
    expected_lookup = perform_template_lookup(
        record.transaction_ref,
        context.template_workbook
    )
    
    if not expected_lookup:
        return
    
    # Parse expected result (format: "ID:IDType")
    if ':' in expected_lookup:
        parts = expected_lookup.split(':')
        expected_id = parts[0].strip()
        expected_id_type = parts[1].strip() if len(parts) > 1 else ""
    else:
        expected_id = expected_lookup.strip()
        expected_id_type = ""
    
    # Compare with actual values
    actual_id = record.original_id
    actual_id_type = record.original_id_type
    
    # Check for mismatch
    if actual_id != expected_id or actual_id_type != expected_id_type:
        # Set correction (but don't change actions)
        record.correction_output = f"{actual_id}:{actual_id_type}"
        record.correction_fields = "ID:IDT"
        record.validation_status = "Template Mismatch"
        # Note: Actions column remains unchanged (still shows "Pass")
```

---

## Database Queries

### SQL Extract Structure

The data is extracted from a DB2 database using complex queries that:
1. Join multiple tables to get all required fields
2. Use Common Table Expressions (CTEs) for link codes
3. Filter by transaction reference list
4. Apply business logic for derived fields (e.g., gender from title)

### Extract Query Template (Buyer)

```sql
WITH LinkCodes AS (
  -- Aggregate link codes by client number
  SELECT 
    t4.CLINUM, 
    MAX(CASE WHEN t4.RLNKTP = 'BEN' THEN t4.ROTCOD END) AS BEN_LINK, 
    MAX(CASE WHEN t4.RLNKTP = 'OWN' THEN t4.ROTCOD END) AS OWN_LINK
  FROM GLDATA/ROTCLI t4 
  GROUP BY t4.CLINUM
)
SELECT 
  -- Core transaction fields
  t1.REPORTREF,                              -- Transaction Reference
  t2.CLINUM,                                 -- Account ID
  lc.BEN_LINK,                               -- BEN Link
  lc.OWN_LINK,                               -- OWN Link
  t5.UECODE,                                 -- Person Code
  t6b.UETYPE,                                -- Account Type
  
  -- ID fields with conditional logic
  CASE 
    WHEN t5.INDIDCODE <> '' 
    THEN t5.INDIDCODE 
    ELSE t6.UENINO 
  END AS BUYER_ID_CODE,
  
  CASE 
    WHEN t5.INDIDCODE = '' OR t5.INDIDCODE IS NULL 
    THEN 'NINO' 
    ELSE t5.PTYSCHCODE 
  END AS BUYER_ID_TYPE,
  
  -- Personal information
  t5.PTYFORE,                                -- First Name(s)
  t5.PTYSURN,                                -- Surname(s)
  
  -- DOB with validation (exclude unrealistic dates)
  CASE 
    WHEN t5.PTYDOB IS NULL OR t5.PTYDOB <= DATE('1941-01-01') 
    THEN NULL 
    ELSE t5.PTYDOB 
  END AS PTYDOB,
  
  -- Gender derived from client title
  CASE 
    WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) 
      IN ('MR', 'MASTER') 
    THEN 'M' 
    WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) 
      IN ('MRS', 'MISS', 'MS') 
    THEN 'F' 
    WHEN UPPER(SUBSTR(t3.CLNAME, 1, LOCATE(' ', t3.CLNAME) - 1)) 
      IN ('DR', 'PROF') 
    THEN 'N/A' 
    ELSE 'N/A' 
  END AS CLIENT_GENDER,
  
  -- Nationality fields
  t6.UENAT,                                  -- Nationality 1
  t7.NATION,                                 -- Nationality 2
  
  -- Trade date/time
  t1.TRDDATTIM                               -- Trade_Date_Time
  
FROM 
  GLDATA/TXNREPESMA t1                       -- Main transaction table
  
  -- Join client and account tables
  JOIN GLDATA/CONTCT t2 
    ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF 
    AND BUYSEL = 'B'                         -- BUYER filter
  
  JOIN GLDATA/CLIENT t3 
    ON t2.CLINUM = t3.CLINO 
  
  -- Join party information
  JOIN GLDATA/ESMAPTYIND t5 
    ON t1.REPORTREF = t5.REPORTREF
  
  -- Join person information
  LEFT JOIN GLDATA/PERSON t6 
    ON t5.UECODE = t6.UECODE 
  
  LEFT JOIN GLDATA/PERSON t6b    
    ON SUBSTR(t2.CLINUM, 1, LENGTH(t2.CLINUM) - 1) = t6b.UECODE
  
  LEFT JOIN GLDATA/PERSONNAT t7 
    ON t3.UECODE = t7.UECODE 
  
  -- Join link codes CTE
  LEFT JOIN LinkCodes lc 
    ON t2.CLINUM = lc.CLINUM 
  
WHERE 
  t1.REPORTREF IN (
    -- List of transaction references to process
    '44625CH8X1Q1',
    '44625CH1VKM1',
    '44625CF47JW1',
    -- ... (hundreds more)
  )
```

### Key Query Components

#### 1. Link Codes CTE
- Aggregates relationship links (BEN = Beneficial Owner, OWN = Owner)
- Uses MAX with CASE to pivot RLNKTP values into columns

#### 2. Gender Derivation Logic
- Extracts title from CLNAME field
- Maps title to gender:
  - MR, MASTER → M
  - MRS, MISS, MS → F
  - DR, PROF → N/A
  - Other → N/A

#### 3. ID Field Logic
- If INDIDCODE exists: Use it + PTYSCHCODE (actual ID type)
- If INDIDCODE is empty/null: Use UENINO + 'NINO' as default

#### 4. DOB Validation
- Excludes dates before 1941-01-01 (data quality issue)
- Returns NULL for invalid dates

### Seller Query Differences

The Seller query is nearly identical except:
- `BUYSEL = 'S'` instead of `'B'`
- Field names: `SELLER_ID_CODE`, `SELLER_ID_TYPE`
- Different decision maker field: `t1.SELDECIND` instead of `t1.BUYDECIND`

---

## Python Refactoring Guidelines

### Recommended Architecture

```
project/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Entry point
│   ├── config.py                    # Configuration constants
│   ├── models/
│   │   ├── __init__.py
│   │   ├── client_record.py         # ClientRecord dataclass
│   │   └── validation_context.py    # ValidationContext dataclass
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py                # Data loading functions
│   │   ├── reference_data.py        # Reference data loaders
│   │   └── sql_queries.py           # SQL query templates
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── format_validator.py      # Regex-based format validation
│   │   ├── logic_validator.py       # Country-specific logic validation
│   │   ├── inconsistent_id.py       # Inconsistent ID validation logic
│   │   └── standard_validation.py   # v5.6 standard validation
│   ├── correction/
│   │   ├── __init__.py
│   │   ├── swedish_century.py       # Swedish century fix
│   │   ├── concat_generator.py      # CONCAT ID generation
│   │   └── fallback_generator.py    # Fallback ID generation
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── pipeline.py              # Main processing pipeline
│   │   ├── italian_tracker.py       # Italian tracker logic
│   │   ├── kaizen_lookup.py         # Kaizen error lookup
│   │   └── joint_accounts.py        # Joint account aggregation
│   ├── output/
│   │   ├── __init__.py
│   │   ├── writer.py                # Write results to Excel
│   │   ├── formatter.py             # Sorting and highlighting
│   │   └── formula_calculator.py    # Formula calculations
│   └── utils/
│       ├── __init__.py
│       ├── name_cleaner.py          # Name cleaning utilities
│       ├── nationality.py           # Nationality prioritization
│       ├── date_parser.py           # Date parsing utilities
│       └── error_handler.py         # Error handling
├── tests/
│   ├── __init__.py
│   ├── test_format_validation.py
│   ├── test_logic_validation.py
│   ├── test_inconsistent_id.py
│   ├── test_concat_generation.py
│   └── test_integration.py
├── data/
│   ├── reference/
│   │   ├── country_codes.csv
│   │   ├── id_formats.csv
│   │   └── person_code_gender_matrix.csv
│   └── templates/
│       └── .gitkeep
├── config/
│   ├── paths.yaml                   # File paths configuration
│   └── validation_rules.yaml       # Validation rules configuration
├── requirements.txt
├── setup.py
└── README.md
```

### Key Python Libraries

```python
# requirements.txt
pandas>=2.0.0          # Data manipulation
openpyxl>=3.1.0        # Excel file handling
pyyaml>=6.0            # Configuration files
python-dateutil>=2.8.0 # Date parsing
pyodbc>=4.0.0          # Database connectivity (if connecting directly)
pytest>=7.0.0          # Testing
pytest-cov>=4.0.0      # Test coverage
black>=23.0.0          # Code formatting
flake8>=6.0.0          # Linting
mypy>=1.0.0            # Type checking
```

### Implementation Tips

#### 1. Use Type Hints Extensively

```python
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ClientRecord:
    row_index: int
    transaction_ref: str
    person_code: str
    # ... etc.

def validate_id_complete(
    id_value: str,
    id_type: str,
    country_code: str,
    dob: datetime,
    gender: str,
    context: ValidationContext
) -> bool:
    """Complete validation with type hints"""
    pass
```

#### 2. Use Pandas for Data Manipulation

```python
import pandas as pd

def load_client_data(file_path: str, incident_code: str) -> List[ClientRecord]:
    """Load client data from Excel"""
    df = pd.read_excel(
        file_path,
        sheet_name=f"Client Data - {incident_code}",
        dtype={
            'Transaction Reference': str,
            'Person Code': str,
            'Account Type': str,
            # ... etc.
        }
    )
    
    records = []
    for _, row in df.iterrows():
        record = ClientRecord(
            row_index=row.name + 2,  # +2 for Excel 1-based + header
            transaction_ref=row['Transaction Reference'],
            person_code=row['Person Code'],
            # ... etc.
        )
        records.append(record)
    
    return records
```

#### 3. Use Configuration Files

```yaml
# config/paths.yaml
base_path: "F:/Transaction Reporting/Kaizen Reporting/Accuracy Testing/"
tracker_main: "\\\\srv01.uk.ajbell.com\\common\\Transaction Reporting\\..."
tracker_italian: "\\\\srv01.uk.ajbell.com\\common\\Transaction Reporting\\..."
reference_data: "Data/Reference/"

# config/validation_rules.yaml
id_types:
  priority_order:
    - NIDN
    - PASSPORT
    - CONCAT
    - CCPT
    - PASS
    - DLIC

concat_rules:
  name_length: 5
  padding_char: "#"
  
name_prefixes:
  two_word:
    - "VON DER"
    - "VAN DER"
    - "VAN DE"
    - "DE LA"
  one_word:
    - "VON"
    - "VAN"
    - "DE"
    - "DI"
    - "DA"
    - "MC"
    - "MAC"
    - "O"
```

#### 4. Implement Comprehensive Logging

```python
import logging
from pathlib import Path

def setup_logging(log_dir: Path, incident_code: str):
    """Setup logging configuration"""
    log_file = log_dir / f"validation_{incident_code}_{datetime.now():%Y%m%d_%H%M%S}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

# Usage
logger = setup_logging(Path("logs"), "7_66")
logger.info(f"Processing {len(records)} records")
logger.warning(f"Invalid country code for person {person_code}")
logger.error(f"Failed to generate CONCAT for record {record.row_index}")
```

#### 5. Use Context Managers for Resources

```python
from contextlib import contextmanager

@contextmanager
def load_tracker_workbook(file_path: str, sheet_name: str):
    """Context manager for loading tracker workbooks"""
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        yield df
    except FileNotFoundError:
        logging.warning(f"Tracker file not found: {file_path}")
        yield None
    except Exception as e:
        logging.error(f"Error loading tracker: {e}")
        yield None

# Usage
with load_tracker_workbook(TRACKER_MAIN_PATH, "Client Data - Outstanding") as tracker:
    if tracker is not None:
        status = lookup_value_in_tracker(tracker, person_code, 'J', 'N')
```

#### 6. Implement Unit Tests

```python
import pytest
from datetime import datetime
from src.validation.format_validator import test_id_against_all_patterns

def test_gb_nino_format_validation():
    """Test UK NINO format validation"""
    format_dict = {
        "GB:NIDN:1": r"^[A-Z]{2}[0-9]{6}[A-D]$",
        "GB:NIDN:2": r"^[0-9]{2}[0-9]{6}[A-D]$"
    }
    
    # Valid NINOs
    assert test_id_against_all_patterns("AB123456C", "GB", "NIDN", format_dict)
    assert test_id_against_all_patterns("12345678A", "GB", "NIDN", format_dict)
    
    # Invalid NINOs
    assert not test_id_against_all_patterns("A1234567C", "GB", "NIDN", format_dict)
    assert not test_id_against_all_patterns("AB123456E", "GB", "NIDN", format_dict)

def test_inconsistent_id_correction():
    """Test inconsistent ID correction logic"""
    from src.models.client_record import ClientRecord
    from src.validation.inconsistent_id import apply_inconsistent_id_corrections
    
    records = [
        ClientRecord(
            row_index=1,
            person_code="12345",
            original_id="AB123456C",
            original_id_type="NIDN",
            trade_date_time_parsed=datetime(2024, 1, 1),
            is_valid_id=True,
            is_fallback_id=False
        ),
        ClientRecord(
            row_index=2,
            person_code="12345",
            original_id="INVALID123",
            original_id_type="NIDN",
            trade_date_time_parsed=datetime(2024, 6, 1),
            is_valid_id=False,
            is_fallback_id=False
        )
    ]
    
    indices = [0, 1]
    apply_inconsistent_id_corrections(records, indices)
    
    # First record should not be corrected (already valid)
    assert not records[0].requires_correction
    
    # Second record should be corrected to first record's ID
    assert records[1].requires_correction
    assert records[1].final_id == "AB123456C"
    assert records[1].final_id_type == "NIDN"
```

#### 7. Performance Optimization

```python
from functools import lru_cache
import re

class RegexCache:
    """Cache compiled regex patterns for better performance"""
    
    def __init__(self):
        self._cache = {}
    
    @lru_cache(maxsize=1000)
    def get_pattern(self, pattern_str: str) -> re.Pattern:
        """Get or compile regex pattern"""
        return re.compile(pattern_str, re.IGNORECASE)
    
    def test(self, pattern_str: str, test_str: str) -> bool:
        """Test string against pattern"""
        pattern = self.get_pattern(pattern_str)
        return bool(pattern.match(test_str))

# Usage
regex_cache = RegexCache()

def test_id_against_all_patterns_optimized(
    test_id: str,
    country_code: str,
    id_type: str,
    format_dict: Dict[str, str],
    regex_cache: RegexCache
) -> bool:
    """Optimized version using regex cache"""
    # ... implementation using regex_cache.test()
```

#### 8. Parallel Processing for Large Datasets

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List

def process_person_group_wrapper(args):
    """Wrapper for parallel processing"""
    records, indices, context = args
    process_person_group_for_inconsistencies(records, indices, context)
    return indices

def process_inconsistent_id_validation_parallel(
    records: List[ClientRecord],
    context: ValidationContext,
    max_workers: int = 4
) -> None:
    """Parallel version of inconsistent ID validation"""
    # Group by person code
    person_groups = group_by_person_code(records)
    
    # Prepare arguments for parallel processing
    tasks = [
        (records, indices, context)
        for indices in person_groups.values()
        if len(indices) > 1
    ]
    
    # Process in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_person_group_wrapper, task)
            for task in tasks
        ]
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing person group: {e}")
```

### Migration Strategy

1. **Phase 1: Core Infrastructure**
   - Set up project structure
   - Implement data models (ClientRecord, ValidationContext)
   - Create configuration files
   - Set up logging

2. **Phase 2: Data Loading**
   - Implement Excel file reading
   - Load reference data (country codes, ID formats)
   - Parse Trade_Date_Time strings
   - Handle nationality prioritization

3. **Phase 3: Format Validation**
   - Implement regex-based format validation
   - Test against ID Formats patterns
   - Handle country code prefix stripping

4. **Phase 4: Logic Validation**
   - Implement country-specific logic validators
   - Start with placeholder (return True)
   - Gradually add country-specific rules

5. **Phase 5: Inconsistent ID Logic**
   - Implement person code grouping
   - Implement chronological sorting
   - Implement correction logic

6. **Phase 6: Standard Validation**
   - Implement v5.6 three-step validation
   - Implement alternative type testing
   - Integrate with inconsistent ID logic

7. **Phase 7: Correction Generation**
   - Implement Swedish century fix
   - Implement CONCAT generation
   - Implement fallback ID generation

8. **Phase 8: Post-Processing**
   - Implement Italian tracker logic
   - Implement Kaizen lookup validation
   - Implement joint account aggregation

9. **Phase 9: Output & Reporting**
   - Write results to Excel
   - Implement sorting
   - Implement formula calculations
   - Implement highlighting

10. **Phase 10: Testing & Optimization**
    - Write comprehensive unit tests
    - Perform integration testing
    - Optimize performance
    - Add parallel processing if needed

---

## Error Handling

### Error Categories

1. **Data Loading Errors**
   - Missing worksheet
   - Invalid file path
   - Corrupted Excel file

2. **Reference Data Errors**
   - Missing country codes
   - Missing ID formats
   - Invalid tracker files

3. **Validation Errors**
   - Invalid date formats
   - Missing required fields
   - Invalid country codes

4. **Processing Errors**
   - Regex compilation failures
   - CONCAT generation failures
   - Template lookup failures

### Error Handling Strategy

```python
class ValidationError(Exception):
    """Base exception for validation errors"""
    pass

class DataLoadingError(ValidationError):
    """Error loading data files"""
    pass

class ReferenceDataError(ValidationError):
    """Error loading reference data"""
    pass

class ValidationProcessError(ValidationError):
    """Error during validation process"""
    pass

def safe_validate_record(record: ClientRecord, 
                        context: ValidationContext) -> None:
    """Validate a record with comprehensive error handling"""
    try:
        process_single_client(record, context)
    except ValidationProcessError as e:
        logger.error(f"Validation error for record {record.row_index}: {e}")
        record.validation_status = "Error"
        record.actions = f"Validation Error: {str(e)}"
    except Exception as e:
        logger.exception(f"Unexpected error for record {record.row_index}: {e}")
        record.validation_status = "Error"
        record.actions = "Unexpected Error - See Logs"

def main_with_error_handling():
    """Main function with comprehensive error handling"""
    try:
        # Initialize
        context = initialize_validation_context()
        
        # Load data
        try:
            records = load_client_data(incident_code, context)
        except DataLoadingError as e:
            logger.error(f"Failed to load client data: {e}")
            return
        
        # Process records
        for record in records:
            safe_validate_record(record, context)
        
        # Write results
        try:
            write_results(records, incident_code)
        except Exception as e:
            logger.error(f"Failed to write results: {e}")
            # Attempt to save to backup location
            try:
                backup_path = Path("backup") / f"results_{incident_code}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
                write_results_to_path(records, backup_path)
                logger.info(f"Results saved to backup location: {backup_path}")
            except Exception as backup_error:
                logger.error(f"Failed to write to backup: {backup_error}")
        
    except Exception as e:
        logger.exception(f"Fatal error in main processing: {e}")
        raise
    finally:
        # Cleanup resources
        cleanup_resources(context)
```

---

## Appendices

### Appendix A: Complete Column Reference

| # | Column Name | Data Type | Description | Example |
|---|-------------|-----------|-------------|---------|
| 1 | Transaction Reference | String | Unique transaction ID | 44625CH8X1Q1 |
| 2 | Account ID | String | Client account number | 12345A |
| 3 | BEN Link | String | Beneficial owner link | BEN123 |
| 4 | OWN Link | String | Owner link code | OWN456 |
| 5 | Person Code | String | Unique person identifier | 12345 |
| 6 | Account Type | String | IND/JNT/etc. | IND |
| 7 | ID Code | String | Identification number | AB123456C |
| 8 | Type of ID Code | String | NIDN/PASSPORT/etc. | NIDN |
| 9 | First Name(s) | String | First/given names | John Paul |
| 10 | Surname(s) | String | Last/family names | Smith-Jones |
| 11 | DOB | Date | Date of birth | 31/05/1985 |
| 12 | Gender | String | M/F/N/A | M |
| 13 | Nationality 1 | String | Primary nationality | GB |
| 14 | Nationality 2 | String | Secondary nationality | US |
| 15 | Trade_Date_Time | String | Transaction timestamp | 2024-03-15-14-30-45-123456 |
| 16 | Correction | String | Correction output | AB123456C:NIDN |
| 17 | Correction Field | String | Fields corrected | ID:IDT |
| 18 | Tracker Status | String | Tracker lookup result | Complete |
| 19 | Actions | String | Validation actions | Pass |
| 20 | Formula 1 | String | Kaizen Error Y/N | N |
| 21 | Formula 2 | String | Template VLOOKUP | AB123456C:NIDN |
| 22 | Formula 3 | String | Comparison result | TRUE |

### Appendix B: ID Type Reference

| ID Type | Full Name | Description | Example Countries |
|---------|-----------|-------------|-------------------|
| NIDN | National Identity Number | Government-issued national ID | GB, SE, IT, ES, FR |
| PASSPORT | Passport Number | International passport | All countries |
| CONCAT | Concatenated ID | Generated from DOB+Names | Generated |
| CCPT | Country-Specific Type | Special country formats | IT (Fiscal Code) |
| PASS | Alternative Passport | Alternative passport format | Some countries |
| DLIC | Driver's License | Driving license number | US, some EU |
| TIN | Tax Identification Number | Tax ID number | US (SSN), etc. |

### Appendix C: Country Code Reference (Sample)

| Country | ISO-2 | ISO-3 | EEA | Notes |
|---------|-------|-------|-----|-------|
| United Kingdom | GB | GBR | N | Post-Brexit |
| Sweden | SE | SWE | Y | Century logic for NIDN |
| Italy | IT | ITA | Y | Fiscal Code validation |
| Spain | ES | ESP | Y | NIE format |
| France | FR | FRA | Y | INSEE number |
| Germany | DE | DEU | Y | Multiple formats |
| United States | US | USA | N | SSN as TIN |
| Canada | CA | CAN | N | SIN number |

### Appendix D: Validation Actions Reference

| Action | Meaning | Correction | Next Steps |
|--------|---------|------------|------------|
| Pass | ID and type valid | No | None |
| Pass - Check Tracker | IT fiscal code valid | Conditional | Check tracker status |
| Valid format - ID Type updated | Format valid, type wrong | Yes (type only) | Review correction |
| Valid format - Logic query | Format valid, logic issue | No | Manual review |
| Fail - Replaced With CONCAT | No valid format, CONCAT generated | Yes | Review CONCAT |
| Fail - Replaced With fallback | No correction possible | Yes | Manual investigation |
| Review - Century Added | Swedish century fix applied | Yes | Review correction |
| Inconsistent ID - Corrected to most recent valid ID | Invalid ID corrected from prior valid | Yes | Review timeline |
| Inconsistent ID - No prior valid ID to use | No valid prior ID found | Pending | Standard pipeline |

### Appendix E: Common Regex Patterns

```python
# UK National Insurance Number (NINO)
GB_NIDN_1 = r"^[A-Z]{2}[0-9]{6}[A-D]$"
GB_NIDN_2 = r"^[0-9]{2}[0-9]{6}[A-D]$"

# Swedish Personnummer
SE_NIDN_12DIGIT = r"^[0-9]{12}$"  # YYYYMMDDXXXX
SE_NIDN_10DIGIT = r"^[0-9]{10}$"  # YYMMDDXXXX (needs century fix)

# Italian Fiscal Code (Codice Fiscale)
IT_NIDN = r"^[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]$"

# Spanish NIE
ES_NIE = r"^[XYZ][0-9]{7}[A-Z]$"

# French INSEE
FR_NIDN = r"^[1-2][0-9]{14}$"

# German ID Card
DE_NIDN = r"^[A-Z]{9}[0-9]$"

# Generic Passport (varies by country)
PASSPORT_GENERIC = r"^[A-Z0-9]{6,9}$"

# CONCAT Format
CONCAT_FORMAT = r"^[A-Z]{2}[0-9]{8}[A-Z#]{5}[A-Z#]{5}$"
```

### Appendix F: Glossary

| Term | Definition |
|------|------------|
| **Buyer** | Party purchasing securities in a transaction |
| **Seller** | Party selling securities in a transaction |
| **Person Code** | Unique identifier for an individual across transactions |
| **Transaction Reference** | Unique identifier for a single transaction |
| **Fallback ID** | System-generated ID in format CountryCode_PersonCode |
| **CONCAT ID** | Concatenated ID generated from DOB and names |
| **EEA** | European Economic Area - affects nationality prioritization |
| **Kaizen** | Continuous improvement philosophy - refers to error template system |
| **Incident Code** | Regulatory incident identifier (e.g., 7_66, 16_20) |
| **Joint Account** | Account with multiple owners (JNT type) |
| **Tracker** | External spreadsheet tracking remediation status |
| **ISO-2** | Two-letter country code (e.g., GB, SE, IT) |
| **ISO-3** | Three-letter country code (e.g., GBR, SWE, ITA) |
| **NIDN** | National Identity Number - most common ID type |
| **v5.6** | Base validation logic version |
| **v1.3** | Inconsistent ID validation version (current) |

---

## Document Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Initial | Initial documentation creation |
| 1.1 | Jan 22, 2026 | Added Python refactoring guidelines |
| 1.2 | Jan 22, 2026 | Added database query documentation |
| 1.3 | Jan 22, 2026 | Added comprehensive appendices and examples |

---

**End of Technical Documentation**

For questions or clarifications, contact the Transaction Reporting team.
