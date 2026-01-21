# Buyer ID Validation Macro v5.6 - Complete Technical Documentation

> **Version:** 5.6  
> **Last Updated:** January 2026  
> **Purpose:** Comprehensive technical documentation for Python refactoring

## Table of Contents

### Core Documentation
1. [Overview](#overview)
2. [Purpose](#purpose)
3. [Key Features](#key-features)
4. [Workflow Process](#workflow-process)
5. [Data Structure](#data-structure)
6. [Column Mapping](#column-mapping)

### Testing Logic (Detailed)
7. [Detailed Testing Logic](#detailed-testing-logic)
   - Step 1: Primary Validation
   - Step 2: Alternative Type Testing
   - Step 3: Correction Generation
   - Step 4: Italian Tracker Logic
   - Step 5: Kaizen Error Lookup Validation
8. [Nationality Priority Logic](#nationality-priority-logic-eea-priority)
9. [Country-Specific Logic Validation Rules](#country-specific-logic-validation-rules)
10. [ID Type Testing Priority](#id-type-testing-priority)

### Technical Implementation
11. [Check Digit Algorithms](#check-digit-algorithms-detailed-implementation)
12. [Formula Calculation Logic](#formula-calculation-logic)
13. [Joint Account Aggregation Logic](#joint-account-aggregation-logic)
14. [Regex Pattern Handling](#regex-pattern-handling)
15. [Data Preprocessing](#data-preprocessing)

### Algorithm Specifications
16. [Complete Algorithm Pseudocode](#complete-algorithm-pseudocode)
    - Main Processing Loop
    - Swedish Century Fix
    - CONCAT Generation
    - Name Cleaning
    - Italian Tracker Logic
    - Kaizen Error Lookup
    - Joint Account Aggregation
    - Formula Calculations

### Python Refactoring Guide
17. [Python Refactoring Considerations](#python-refactoring-considerations)
    - Recommended Libraries
    - Data Structure Mapping
    - Configuration Management
    - Performance Optimization
    - Error Handling Patterns
    - Testing Strategy
    - YAML Configuration

### Reference Materials
18. [Output Formats](#output-formats)
19. [File Dependencies](#file-dependencies)
20. [Performance Optimizations](#performance-optimizations)
21. [Error Handling](#error-handling)
22. [Version History](#version-history)
23. [Configuration](#configuration)
24. [Maintenance Notes](#maintenance-notes)

---

## Quick Reference Summary

### Processing Steps Overview
```
Step 1: Primary Validation → Test original ID against country:IDType patterns
Step 2: Alternative Testing → Test against other allowed ID types if Step 1 fails
Step 3: Correction Generation → Generate CONCAT/fallback if no valid type found
Step 4: Italian Tracker → Apply special logic for Italian fiscal codes
Step 5: Template Validation → Compare passed records against incident template
```

### Correction Priority Hierarchy
```
1. Swedish Century Fix (SE only, 10-digit NIDN)
2. CONCAT Generation (if country allows and data available)
3. Fallback ID (Country Code + Person Code as NIDN)
```

### Supported ID Types
- **NIDN**: National Identification Number (highest priority)
- **PASSPORT**: International passport number
- **CONCAT**: Concatenated personal data ID
- **CCPT**: Country code + passport
- **PASS**: Alternative passport format
- **DLIC**: Driver's license (lowest priority)

### Countries with Detailed Validation
BE, BG, CZ, DK, EE, FI, IS, IT, LT, LV, NO, RO, SE, SI, SK

### Check Digit Algorithms Implemented
- Modulus 97 (Belgium)
- Weighted Sum Modulus 11 (Bulgaria, Romania, Slovenia)
- Two-Stage Modulus 11 (Estonia)
- Modulus 31 Character Mapping (Finland)
- Luhn Algorithm (Sweden)
- Divisibility by 11 (Slovakia)

---

## Overview

The Buyer ID Validation Macro v5.6 is a comprehensive VBA solution designed to validate and correct customer identification data for transaction reporting compliance. This macro processes client records to ensure ID formats, types, and values meet regulatory requirements while providing automated corrections where possible.

## Purpose

The macro addresses several key business requirements:
- **Data Quality**: Validates customer identification data against predefined formats and business rules
- **Regulatory Compliance**: Ensures ID data meets transaction reporting standards
- **Automated Correction**: Generates valid ID corrections when original data is invalid
- **Joint Account Handling**: Manages aggregation of joint account records
- **Template Integration**: Performs lookups against incident-specific templates
- **Tracker Integration**: Checks processing status against external tracking systems

## Key Features

### 1. Multi-Source Validation
- Validates against country-specific ID formats using regex patterns
- Tests ID types: NIDN, PASSPORT, CONCAT, CCPT, PASS, DLIC
- Applies EEA (European Economic Area) priority logic for dual nationalities
- Validates ID logic rules (format validation + business logic verification)

### 2. Automated Correction Generation
- **CONCAT Generation**: Creates concatenated IDs from personal data (Country Code + Date of Birth + First Name + Surname)
- **Fallback ID Creation**: Generates IDs using country code + person code when other methods fail
- **ID Type Correction**: Updates incorrect ID types when valid alternatives are found

### 3. Joint Account Processing
- Detects JNT (Joint) account types
- Aggregates matching joint account rows by Transaction Reference
- Combines personal data using pipe (|) delimiters
- Maintains proper correction format for aggregated records

### 4. Template Integration
- Dynamically loads incident-specific template files (e.g., "FY25 Q3 - 7_37.xlsx")
- Performs VLOOKUP operations against template data
- Compares corrections with template expectations
- Calculates validation formulas based on template matches

### 5. Tracker System Integration
- Connects to main tracker workbook for general client data remediation
- Integrates with Italian-specific fiscal code validation tracker
- Applies tracker-based logic for Italian NIDN processing
- Updates processing status based on tracker information

## Workflow Process

### Phase 1: Initialization
1. **User Input**: Prompts for incident code (e.g., "7_37")
2. **Worksheet Validation**: Confirms target worksheet exists ("Client Data - [incident_code]")
3. **Resource Loading**: 
   - Loads country codes and EEA status mappings
   - Loads ID format patterns with regex validation rules
   - Opens tracker workbooks (main and Italian)
   - Loads incident-specific template file

### Phase 2: Data Preprocessing
1. **Date Formatting**: Standardizes date formats (dd/mm/yyyy)
2. **Character Replacement**: Converts dots to slashes in date fields
3. **Data Loading**: Reads client records into structured data objects
4. **Nationality Processing**: Converts nationalities to ISO-2 codes with EEA priority

### Phase 3: Validation Processing
For each client record:

1. **Primary Validation**: Tests original ID and ID type against format patterns
2. **Logic Validation**: Verifies business rules (date validation, gender checks, etc.)
3. **Alternative Testing**: If primary fails, tests against other allowed ID types
4. **Correction Generation**: Creates CONCAT or fallback IDs as needed
5. **Italian Processing**: Applies special logic for Italian fiscal codes using tracker data

### Phase 4: Formula Calculations
1. **Formula 1**: Error flag calculation (Y/N based on template matches)
2. **Formula 2**: Template VLOOKUP (concatenates columns 22:23 from template)
3. **Formula 3**: Comparison logic (TRUE/FALSE based on correction vs. template match)

### Phase 5: Post-Processing
1. **Joint Account Aggregation**: Optional aggregation of JNT account pairs
2. **Results Output**: Writes corrections, actions, and tracker status to worksheet
3. **Performance Reporting**: Displays processing statistics and completion time

---

## Complete Algorithm Pseudocode

### Main Processing Loop
```
FUNCTION ProcessClientRecords(clientRecords, context):
    FOR EACH client IN clientRecords:
        # Step 1: Primary Validation
        originalTypeValid = TestIDAgainstAllPatterns(
            client.OriginalID, 
            client.PriorityCountryCode, 
            client.OriginalIDType, 
            context.FormatDict, 
            context.RegexEngine
        )
        
        IF originalTypeValid:
            originalTypeLogicValid = ValidateIDLogic(
                client.OriginalID, 
                client.OriginalIDType, 
                client.PriorityCountryCode, 
                client.DateOfBirth, 
                client.Gender
            )
        ELSE:
            originalTypeLogicValid = False
        
        # Step 2: Alternative Type Testing
        IF NOT originalTypeValid:
            (correctTypeFound, correctTypeLogicValid) = TestAlternativeTypes(
                client, 
                context
            )
        
        # Step 3: Apply Outcomes
        IF originalTypeValid AND originalTypeLogicValid:
            # Record passes all checks
            client.FinalID = client.OriginalID
            client.FinalIDType = client.OriginalIDType
            IF client.PriorityCountryCode == "IT" AND client.OriginalIDType == "NIDN":
                client.Actions = "Pass - Check Tracker"
            ELSE:
                client.Actions = "Pass"
            client.ValidationStatus = "Valid"
            
        ELSE IF originalTypeValid AND NOT originalTypeLogicValid:
            # Format valid but logic fails
            client.FinalID = client.OriginalID
            client.FinalIDType = client.OriginalIDType
            client.ValidationStatus = "Logic Issue"
            IF client.PriorityCountryCode == "IT" AND client.OriginalIDType == "NIDN":
                client.Actions = "Pass - Check Tracker"
            ELSE:
                client.Actions = "Pass"
                
        ELSE IF correctTypeFound != "":
            # Alternative type found
            client.FinalIDType = correctTypeFound
            client.CorrectionFields = "ID:IDT"
            client.CorrectionOutput = client.FinalID + ":" + client.FinalIDType
            
            IF correctTypeLogicValid:
                client.ValidationStatus = "Valid"
                IF client.PriorityCountryCode == "IT" AND correctTypeFound == "NIDN":
                    client.Actions = "Pass - Check Tracker"
                ELSE:
                    client.Actions = "Valid format - ID Type updated"
            ELSE:
                client.ValidationStatus = "Logic Issue"
                client.Actions = "Valid format - Logic query - ID Type updated"
        ELSE:
            # No valid format - try correction generation
            IF TrySwedishCenturyFix(client, context):
                # Swedish century fix successful
                CONTINUE
            ELSE IF TryGenerateCONCAT(client, context):
                # CONCAT generation successful
                CONTINUE
            ELSE IF NOT IsCONCATEligible(client, context):
                # CONCAT not allowed - use fallback
                GenerateFallbackID(client)
            ELSE:
                # CONCAT allowed but failed - still use fallback
                GenerateFallbackID(client)
        
        # Step 4: Italian Tracker Logic
        IF client.PriorityCountryCode == "IT":
            ApplyItalianTrackerLogic(client, context)
        
        # Step 5: Kaizen Error Lookup Validation
        IF originalTypeValid:
            ApplyKaizenErrorLookupValidation(client, context)
```

### Swedish Century Fix Algorithm
```
FUNCTION TrySwedishCenturyFix(client, context):
    # Check eligibility
    IF client.PriorityCountryCode != "SE":
        RETURN False
    IF client.OriginalIDType != "NIDN":
        RETURN False
    IF LENGTH(client.OriginalID) != 10:
        RETURN False
    IF client.DateOfBirth == NULL:
        RETURN False
    
    # Extract century from DOB
    year = FORMAT(client.DateOfBirth, "yyyy")
    century = SUBSTRING(year, 0, 2)
    
    # Create corrected ID
    correctedID = century + client.OriginalID
    
    # Test corrected ID
    IF TestIDAgainstAllPatterns(correctedID, "SE", "NIDN", context.FormatDict, context.RegexEngine):
        logicValid = ValidateIDLogic(correctedID, "NIDN", "SE", client.DateOfBirth, client.Gender)
        
        IF logicValid:
            client.FinalID = correctedID
            client.FinalIDType = "NIDN"
            client.ValidationStatus = "Corrected"
            client.Actions = "Review - Century Added"
            client.CorrectionFields = "ID:IDT"
            client.CorrectionOutput = correctedID + ":" + "NIDN"
            RETURN True
    
    RETURN False
```

### CONCAT Generation Algorithm
```
FUNCTION TryGenerateCONCAT(client, context):
    # Check eligibility
    IF NOT IsCONCATEligible(client, context):
        RETURN False
    
    # Build CONCAT ID
    concatID = BuildCONCATID(client)
    
    # Test against patterns
    IF TestIDAgainstAllPatterns(concatID, client.PriorityCountryCode, "CONCAT", context.FormatDict, context.RegexEngine):
        logicValid = ValidateIDLogic(concatID, "CONCAT", client.PriorityCountryCode, client.DateOfBirth, client.Gender)
        
        IF logicValid:
            client.FinalID = concatID
            client.FinalIDType = "CONCAT"
            client.ValidationStatus = "Corrected"
            client.Actions = "Fail - Replaced With CONCAT"
            client.CorrectionFields = "ID:IDT"
            client.CorrectionOutput = concatID + ":" + "CONCAT"
            RETURN True
        ELSE:
            RETURN False
    ELSE:
        RETURN False

FUNCTION IsCONCATEligible(client, context):
    RETURN (client.DateOfBirth != NULL AND
            client.FirstName != "" AND
            client.Surname != "" AND
            context.FormatDict.EXISTS(client.PriorityCountryCode + ":CONCAT:1"))

FUNCTION BuildCONCATID(client):
    dateStr = FORMAT(client.DateOfBirth, "yyyymmdd")
    cleanFirstName = CleanNameForCONCAT(client.FirstName, False)
    cleanSurname = CleanNameForCONCAT(client.Surname, True)
    RETURN client.PriorityCountryCode + dateStr + cleanFirstName + cleanSurname
```

### Name Cleaning Algorithm
```
FUNCTION CleanNameForCONCAT(nameValue, isSurname):
    IF TRIM(nameValue) == "":
        RETURN "#####"
    
    cleanedName = UPPERCASE(TRIM(nameValue))
    
    # Handle comma delimiters
    IF CONTAINS(cleanedName, ","):
        cleanedName = SPLIT(cleanedName, ",")[0]
        cleanedName = TRIM(cleanedName)
    
    IF isSurname:
        cleanedName = RemoveNamePrefixes(cleanedName)
    ELSE:
        # For first names, take first word only
        nameParts = SPLIT(cleanedName + " ", " ")
        IF LENGTH(nameParts) > 0:
            cleanedName = nameParts[0]
    
    # Remove special characters
    cleanedName = REPLACE(cleanedName, "-", "")
    cleanedName = REPLACE(cleanedName, "'", "")
    cleanedName = REPLACE(cleanedName, ".", "")
    cleanedName = REPLACE(cleanedName, " ", "")
    
    IF cleanedName == "":
        cleanedName = "#####"
    
    RETURN LEFT(cleanedName + "#####", 5)

FUNCTION RemoveNamePrefixes(surname):
    prefixes = ["VON DER", "VAN DER", "VAN DE", "DE LA", 
                "VON", "VAN", "DE", "DI", "DA", "MC", "MAC", "O"]
    
    cleanSurname = TRIM(UPPERCASE(surname))
    
    FOR EACH prefix IN prefixes:
        prefixWithSpace = prefix + " "
        IF STARTS_WITH(cleanSurname, prefixWithSpace):
            RETURN TRIM(SUBSTRING(cleanSurname, LENGTH(prefixWithSpace)))
    
    RETURN cleanSurname
```

### Italian Tracker Logic Algorithm
```
FUNCTION ApplyItalianTrackerLogic(client, context):
    # Get tracker status
    client.TrackerStatus = GetTrackerStatus(client, context)
    
    # Apply logic based on status
    IF client.Actions == "Pass - Check Tracker":
        IF client.TrackerStatus IN ["Not Started", "Not On tracker", "In Progress", "Awaiting Response"]:
            GenerateFallbackID(client)
            client.Actions = "Pass - Check Tracker - Replaced With fallback"
        ELSE IF client.TrackerStatus == "Complete":
            client.Actions = "Pass - Check Tracker - Complete"
            client.CorrectionFields = ""
            client.CorrectionOutput = ""

FUNCTION GetTrackerStatus(client, context):
    # Check Italian tracker first
    IF context.ItalianTracker != NULL:
        result = VLOOKUP(client.PersonCode, context.ItalianTracker.Range("C:G"), 5, False)
        IF result != ERROR AND result != "":
            RETURN TRIM(result)
    
    # Check main tracker
    IF context.MainTracker != NULL:
        result = VLOOKUP(client.PersonCode, context.MainTracker.Range("J:N"), 5, False)
        IF result != ERROR AND result != "":
            RETURN TRIM(result)
    
    RETURN "Not On tracker"
```

### Kaizen Error Lookup Algorithm
```
FUNCTION ApplyKaizenErrorLookupValidation(client, context):
    # Only applies to records that passed original validation
    IF client.CorrectionOutput != "":
        RETURN  # Already has correction
    
    # Get expected values from template
    expectedLookupResult = PerformTemplateLookup(client.TransactionRef, context.TemplateWorkbook)
    
    IF expectedLookupResult == "":
        RETURN  # No template data
    
    # Parse expected result
    expectedParts = SPLIT(expectedLookupResult, ":")
    expectedID = TRIM(expectedParts[0])
    expectedIDType = TRIM(expectedParts[1]) IF LENGTH(expectedParts) > 1 ELSE ""
    
    # Compare with actual values
    actualID = client.OriginalID
    actualIDType = client.OriginalIDType
    
    idMatches = (actualID == expectedID)
    typeMatches = (actualIDType == expectedIDType)
    
    # Generate correction if mismatch
    IF NOT idMatches OR NOT typeMatches:
        client.CorrectionOutput = actualID + ":" + actualIDType
        client.CorrectionFields = "ID:IDT"
        client.ValidationStatus = "Template Mismatch"
        # Actions remains "Pass"
```

### Joint Account Aggregation Algorithm
```
FUNCTION AggregateJNTAccounts(worksheet):
    lastRow = GET_LAST_ROW(worksheet, "A")
    deleteRows = []
    processedPairs = 0
    
    i = 2  # Start from first data row
    WHILE i <= lastRow:
        currentTxnRef = TRIM(worksheet.Cells(i, COL_TRANSACTION_REF))
        currentAccountType = TRIM(worksheet.Cells(i, COL_ACCOUNT_TYPE))
        
        IF UPPERCASE(currentAccountType) == "JNT":
            # Look for matching JNT row
            FOR j = i+1 TO lastRow:
                compareTxnRef = TRIM(worksheet.Cells(j, COL_TRANSACTION_REF))
                compareAccountType = TRIM(worksheet.Cells(j, COL_ACCOUNT_TYPE))
                
                IF UPPERCASE(compareAccountType) == "JNT" AND compareTxnRef == currentTxnRef:
                    AggregateJNTPair(worksheet, i, j)
                    processedPairs++
                    ADD j TO deleteRows
                    BREAK  # Only one match per row
        
        i++
    
    # Delete aggregated rows in descending order
    SORT deleteRows DESCENDING
    FOR EACH rowNum IN deleteRows:
        DELETE worksheet.Rows(rowNum)
    
    DISPLAY "Processed " + processedPairs + " joint account pairs"

FUNCTION AggregateJNTPair(worksheet, row1, row2):
    # Capture original corrections
    originalCorr1 = TRIM(worksheet.Cells(row1, COL_OUTPUT))
    originalCorr2 = TRIM(worksheet.Cells(row2, COL_OUTPUT))
    
    # Aggregate fields with pipe delimiter
    worksheet.Cells(row1, COL_PERSON_CODE) = CombineWithPipe(
        worksheet.Cells(row1, COL_PERSON_CODE),
        worksheet.Cells(row2, COL_PERSON_CODE)
    )
    worksheet.Cells(row1, COL_ID_VALUE) = CombineWithPipe(
        worksheet.Cells(row1, COL_ID_VALUE),
        worksheet.Cells(row2, COL_ID_VALUE)
    )
    worksheet.Cells(row1, COL_ID_TYPE) = CombineWithPipe(
        worksheet.Cells(row1, COL_ID_TYPE),
        worksheet.Cells(row2, COL_ID_TYPE)
    )
    worksheet.Cells(row1, COL_FNAME) = CombineWithPipe(
        worksheet.Cells(row1, COL_FNAME),
        worksheet.Cells(row2, COL_FNAME)
    )
    worksheet.Cells(row1, COL_SNAME) = CombineWithPipe(
        worksheet.Cells(row1, COL_SNAME),
        worksheet.Cells(row2, COL_SNAME)
    )
    worksheet.Cells(row1, COL_DOB) = CombineWithPipe(
        worksheet.Cells(row1, COL_DOB),
        worksheet.Cells(row2, COL_DOB)
    )
    
    # Aggregate correction output
    IF originalCorr1 != "" OR originalCorr2 != "":
        worksheet.Cells(row1, COL_OUTPUT) = CombineWithPipe(originalCorr1, originalCorr2)

FUNCTION CombineWithPipe(value1, value2):
    str1 = TRIM(CONVERT_TO_STRING(value1))
    str2 = TRIM(CONVERT_TO_STRING(value2))
    RETURN str1 + "|" + str2
```

### Formula Calculation Algorithm
```
FUNCTION CalculateFormulaResults(clientRecords, context, worksheet):
    FOR EACH client IN clientRecords:
        # Formula 2: Template lookup
        client.Formula2Result = PerformTemplateLookup(
            client.TransactionRef, 
            context.TemplateWorkbook
        )
        
        # Formula 3: Comparison
        client.Formula3Result = CalculateFormula3(
            client.CorrectionOutput, 
            client.Formula2Result
        )
        
        # Formula 1: Error flag
        IF client.Formula3Result == "TRUE":
            client.Formula1Result = "N"
        ELSE IF client.Formula3Result == "FALSE":
            client.Formula1Result = "Y"
        ELSE:
            client.Formula1Result = "N"
        
        # Write to worksheet
        worksheet.Cells(client.RowIndex, COL_FORMULA1) = client.Formula1Result
        worksheet.Cells(client.RowIndex, COL_FORMULA2) = client.Formula2Result
        worksheet.Cells(client.RowIndex, COL_FORMULA3) = client.Formula3Result

FUNCTION CalculateFormula3(correctionOutput, templateLookupResult):
    IF correctionOutput != "":
        IF correctionOutput == templateLookupResult:
            RETURN "TRUE"
        ELSE:
            RETURN "FALSE"
    ELSE:
        RETURN ""

FUNCTION PerformTemplateLookup(transactionRef, templateSheet):
    IF templateSheet == NULL OR transactionRef == "":
        RETURN ""
    
    # VLOOKUP for columns 22 and 23
    result22 = VLOOKUP(transactionRef, templateSheet.Range("A:AH"), 22, False)
    result23 = VLOOKUP(transactionRef, templateSheet.Range("A:AH"), 23, False)
    
    col22Value = CONVERT_TO_STRING(result22) IF result22 != ERROR ELSE ""
    col23Value = CONVERT_TO_STRING(result23) IF result23 != ERROR ELSE ""
    
    # Handle joint account format
    IF CONTAINS(col22Value, "|") AND CONTAINS(col23Value, "|"):
        RETURN FormatJointAccountLookup(col22Value, col23Value)
    ELSE IF col22Value != "" AND col23Value != "":
        RETURN col22Value + ":" + col23Value
    ELSE IF col22Value != "":
        RETURN col22Value + ":"
    ELSE IF col23Value != "":
        RETURN ":" + col23Value
    ELSE:
        RETURN ""

FUNCTION FormatJointAccountLookup(idValues, idTypes):
    idParts = SPLIT(idValues, "|")
    typeParts = SPLIT(idTypes, "|")
    
    IF LENGTH(idParts) != LENGTH(typeParts):
        RETURN ""  # Mismatch
    
    result = ""
    FOR i = 0 TO LENGTH(idParts)-1:
        currentID = TRIM(idParts[i])
        currentType = TRIM(typeParts[i])
        
        IF currentID != "" AND currentType != "":
            IF result != "":
                result = result + "|"
            result = result + currentID + ":" + currentType
    
    RETURN result
```

---

## Data Structure

### ClientRecord Type
```vb
Type ClientRecord
    RowIndex As Long                    ' Worksheet row number
    TransactionRef As String            ' Unique transaction identifier
    PersonCode As String               ' Client person code
    AccountType As String              ' Account type (IND, JNT, etc.)
    OriginalID As String               ' Original ID value
    OriginalIDType As String           ' Original ID type
    FirstName As String                ' Client first name
    Surname As String                  ' Client surname
    DateOfBirth As Date               ' Date of birth
    Gender As String                  ' Gender (M/F)
    PrimaryNationality As String      ' Primary nationality (ISO-2)
    SecondaryNationality As String    ' Secondary nationality (ISO-2)
    PriorityCountryCode As String     ' Determined priority country
    
    ' Processing Results
    FinalID As String                 ' Corrected ID value
    FinalIDType As String             ' Corrected ID type
    ValidationStatus As String        ' Validation outcome
    Actions As String                 ' Processing actions taken
    TrackerStatus As String           ' Tracker system status
    CorrectionFields As String        ' Fields corrected (e.g., "ID:IDT")
    CorrectionOutput As String        ' Final correction format
    
    ' Formula Results
    Formula1Result As String          ' Column AA result (Y/N)
    Formula2Result As String          ' Template VLOOKUP result
    Formula3Result As String          ' Comparison result (TRUE/FALSE)
End Type
```

## Column Mapping

| Column | Letter | Purpose | Description |
|--------|--------|---------|-------------|
| 1 | A | Transaction Reference | Unique identifier for each transaction |
| 6 | F | Person Code | Internal client identifier |
| 7 | G | Account Type | Account classification (IND, JNT, etc.) |
| 8 | H | ID Value | Customer identification number |
| 9 | I | ID Type | Type of identification (NIDN, PASSPORT, etc.) |
| 10 | J | First Name | Client's first name |
| 11 | K | Surname | Client's surname |
| 12 | L | Date of Birth | Client's date of birth |
| 13 | M | Gender | Client's gender |
| 14 | N | Primary Nationality | Primary nationality |
| 15 | O | Secondary Nationality | Secondary nationality |
| 21 | U | Correction Output | Generated corrections (ID:Type format) |
| 22 | V | Correction Fields | Fields that were corrected |
| 23 | W | Tracker Status | Processing status from tracker systems |
| 24 | X | Actions | Processing actions and outcomes |
| 25 | Y | Formula 1 | Error flag (Y/N) |
| 26 | Z | Formula 2 | Template lookup result |
| 27 | AA | Formula 3 | Match comparison (TRUE/FALSE) |

## Detailed Testing Logic

### Overview of Validation Process
The macro follows a 5-step validation process for each client record:

**Step 1: Primary Validation** - Test original ID and ID type against format patterns
**Step 2: Alternative Type Testing** - If primary fails, test against other allowed ID types
**Step 3: Correction Generation** - Generate CONCAT or fallback IDs if no valid format found
**Step 4: Italian Tracker Logic** - Apply special processing for Italian fiscal codes
**Step 5: Kaizen Error Lookup** - Validate passed records against template expectations

---

### Step 1: Primary Validation (Original ID Testing)

#### Format Pattern Matching
The macro tests the original ID value against regex patterns defined for the country:idType combination.

**Pattern Testing Logic:**
```
For each country:idType pattern:
    1. Strip ISO-2 country code prefix if present (e.g., "GB12345678" → "12345678")
    2. Test both versions (with and without prefix) against regex pattern
    3. If any pattern matches, proceed to logic validation
    4. If no pattern matches, mark format as invalid
```

**Multiple Pattern Support:**
- Countries can have multiple regex patterns for the same ID type
- Patterns are stored as `CountryCode:IDType:PatternNumber` (e.g., "CZ:NIDN:1", "CZ:NIDN:2")
- All patterns are tested sequentially until a match is found

#### Logic Validation
After format validation, the macro validates business logic rules specific to each country and ID type.

**Logic Types Validated:**
1. **DOB_Logic**: Date of birth embedded in ID matches client's DOB
2. **DOB_Gender_Logic**: DOB is offset based on gender (e.g., MM+50 for females)
3. **Gender_Code_Logic**: ID contains gender indicator (odd/even or specific code)
4. **Gender_and_Century_Code_Logic**: Code represents both gender and birth century
5. **Birth_Year_Code_Logic**: Code represents birth year range
6. **Birth_Century_Code_Logic**: Code indicates century of birth
7. **Check_Digit_Logic**: Mathematical validation of check digits

**Primary Validation Outcomes:**
- **Pass**: Both format and logic are valid → No correction needed
- **Pass - Check Tracker**: Valid for Italian NIDN → Requires tracker verification
- **Logic Issue**: Format valid but logic fails → Proceed to alternative testing
- **Format Invalid**: No pattern match → Proceed to alternative testing

---

### Step 2: Alternative Type Testing

If primary validation fails, the macro tests the original ID against alternative ID types allowed for that country.

#### Alternative Type Selection Logic
```
For each allowed ID type (NIDN, PASSPORT, CONCAT, CCPT, PASS, DLIC):
    1. Check if country has format patterns defined for this ID type
    2. Skip CONCAT during alternative testing (only generated in Step 3)
    3. Test original ID against all patterns for this type
    4. If format matches, validate logic rules
    5. If both format and logic pass, mark as correct type
```

**Alternative Testing Outcomes:**
- **Valid Format - ID Type Updated**: Found valid alternative type with passing logic
- **Valid Format - Logic Query**: Format matches but logic fails
- **No Alternative Found**: No valid type found → Proceed to correction generation

#### ID Type Correction Priority
When multiple alternative types match:
1. First matching type in the natural order from ID Formats worksheet
2. Types are tested in the order they appear in the format dictionary
3. NIDN typically has highest priority, followed by PASSPORT, CCPT, etc.

---

### Step 3: Correction Generation (Hierarchical Approach)

When no valid format is found, the macro generates corrections using a priority hierarchy:

#### 3.1 Swedish Century Fix (Highest Priority)
**Applicability Criteria:**
- Country code = "SE" (Sweden)
- Original ID type = "NIDN"
- Original ID is 10 digits (missing century prefix)
- Date of birth is available

**Fix Logic:**
```
1. Extract century from DOB (e.g., 1985 → "19")
2. Prepend century to original ID: "19" + "850523-1234" → "19850523-1234"
3. Test corrected ID against Swedish NIDN patterns
4. Validate logic (DOB, gender, check digit)
5. If valid: Apply correction with action "Review - Century Added"
```

#### 3.2 CONCAT Generation (Medium Priority)
**Eligibility Criteria:**
- Country has CONCAT format patterns defined
- Date of birth is available
- First name is available
- Surname is available

**CONCAT Construction Logic:**
```
Format: {CountryCode}{YYYYMMDD}{FirstName5}{Surname5}

Components:
1. Country Code: ISO-2 code (e.g., "GB")
2. Date: YYYYMMDD format (e.g., "19850523")
3. First Name: Cleaned and padded to 5 characters
4. Surname: Cleaned and padded to 5 characters

Example: GB19850523JOHN#SMITH
```

**Name Cleaning Rules:**

*First Name Processing:*
1. Convert to uppercase
2. Handle comma delimiters (take first part before comma)
3. Take first word only
4. Remove special characters: `-`, `'`, `.`, spaces
5. Pad or truncate to exactly 5 characters with `#` padding
6. If empty after cleaning, use "#####"

*Surname Processing:*
1. Convert to uppercase
2. Handle comma delimiters (take first part before comma)
3. Remove prefixes: VON DER, VAN DER, VAN DE, DE LA, VON, VAN, DE, DI, DA, MC, MAC, O
4. Take the remaining name (may be multiple words)
5. Remove special characters: `-`, `'`, `.`, spaces
6. Pad or truncate to exactly 5 characters with `#` padding
7. If empty after cleaning, use "#####"

**CONCAT Validation:**
After generation, the CONCAT ID is tested against format patterns and logic validation. If both pass:
- Action: "Fail - Replaced With CONCAT"
- Correction: Generated CONCAT ID with type "CONCAT"

#### 3.3 Fallback ID Generation (Lowest Priority)
Used when:
- CONCAT is not eligible (missing required data or no format defined)
- CONCAT generation failed logic validation
- Swedish century fix was not applicable or failed

**Fallback Format:**
```
{CountryCode}{PersonCode}

Example: GB123456789
```

**Fallback Application:**
- Final ID Type: "NIDN" (always)
- Action: "Fail - Replaced With fallback"
- No format or logic validation performed

---

### Step 4: Italian Tracker Logic

Special processing for Italian fiscal codes (IT country code):

#### Tracker Lookup Process
```
1. Check Italian Fiscal Code Validation tracker first (higher priority)
2. If not found, check Main Client Data Remediation tracker
3. Lookup by Person Code (Column C in Italian tracker, Column J in main tracker)
4. Return Status from tracker (Column G in Italian tracker, Column N in main tracker)
```

**Tracker Status Values:**
- "Complete": Fiscal code validation finished
- "In Progress": Currently being validated
- "Not Started": Identified but not yet processed
- "Awaiting Response": Waiting for client response
- "Not On tracker": Person code not found in any tracker

#### Tracker-Based Action Modifications
For records with action "Pass - Check Tracker":

| Tracker Status | Action Applied | Correction Generated |
|---------------|----------------|----------------------|
| Complete | Pass - Check Tracker - Complete | No correction |
| Not Started | Pass - Check Tracker - Replaced With fallback | Fallback ID |
| Not On tracker | Pass - Check Tracker - Replaced With fallback | Fallback ID |
| In Progress | Pass - Check Tracker - Replaced With fallback | Fallback ID |
| Awaiting Response | Pass - Check Tracker - Replaced With fallback | Fallback ID |

---

### Step 5: Kaizen Error Lookup Validation

Final validation step that checks passed records against incident-specific template expectations.

#### Applicability Criteria
- Original ID type was valid (passed Step 1)
- No correction was generated in Steps 2-4
- Template file is available for incident code

#### Template Lookup Process
```
1. Perform VLOOKUP on Transaction Reference in template file
2. Retrieve expected ID from column 22
3. Retrieve expected ID Type from column 23
4. Concatenate as "ExpectedID:ExpectedIDType"
```

#### Comparison Logic
```
Compare:
    Actual ID = Column H (ID Value)
    Actual ID Type = Column I (ID Type)
    Expected ID:IDType = Template lookup result

If Actual != Expected:
    Generate correction output = "ActualID:ActualIDType"
    Mark as "Template Mismatch"
    Keep original action status ("Pass")
```

**Purpose:** Identifies records that pass validation but don't match the expected corrections in the incident template, indicating potential systematic issues or template discrepancies.

---

### Nationality Priority Logic (EEA Priority)

The macro determines which nationality to use for validation when clients have dual nationality.

#### Priority Rules
```
Priority 1: EEA Status
- If Primary is EEA and Secondary is not EEA → Use Primary
- If Secondary is EEA and Primary is not EEA → Use Secondary

Priority 2: Alphabetical Order (if both or neither are EEA)
- Compare ISO-2 codes alphabetically
- Use the nationality that comes first alphabetically

Priority 3: Single Nationality
- If only one nationality provided → Use that nationality
- If both are empty → Cannot determine priority
```

#### ISO Code Conversion
```
Process:
1. Convert ISO-3 codes to ISO-2 using Country Codes worksheet mapping
2. Lookup EEA status for each ISO-2 code
3. Apply priority rules
4. Return selected ISO-2 code for validation

Example:
Primary: "GBR" (ISO-3) → "GB" (ISO-2, EEA=Y)
Secondary: "USA" (ISO-3) → "US" (ISO-2, EEA=N)
Result: "GB" (EEA takes priority)
```

---

### Country-Specific Logic Validation Rules

The macro implements specialized validation for each country based on their national ID structure. Below are detailed validation algorithms:

#### Belgium (BE) - NIDN
**Format:** 11 digits (YYMMDD + 3-digit sequence + 2-digit check)
**Validations:**
1. **DOB Logic**: Extract positions 1-6 as YYMMDD, validate against client DOB
2. **Gender Code**: Positions 7-9 as sequence number (odd = male, even = female)
3. **Check Digit**: Apply modulus 97 algorithm
   - For birth years 2000+: Prepend '2' before first 9 digits
   - Calculate: 97 - (number mod 97)
   - Compare with last 2 digits

#### Bulgaria (BG) - NIDN
**Format:** 10 digits (YYMMDD + region code + sequence + check)
**Validations:**
1. **DOB Logic**: Positions 1-6 as YYMMDD
2. **Gender Code**: Position 9 (even = male, odd = female)
3. **Check Digit**: Weighted sum modulus 11
   - Apply weights [2,4,8,5,10,9,7,3,6] to first 9 digits
   - Sum mod 11: if result = 10, check digit = 0; else check digit = result
   - Compare with position 10

#### Czech Republic (CZ) - NIDN
**Format:** 9 or 10 digits (YYMMDD + sequence + optional check)
**Validations:**
1. **DOB Gender Logic**: Positions 1-6
   - Males: MM = actual month (01-12)
   - Females: MM = actual month + 50 (51-62) or + 70 (71-82)
   - Extract actual month and validate against DOB and gender
2. **Check Digit** (10-digit only, for people born after 1954-01-01):
   - Calculate: first 9 digits mod 11
   - If mod 11 = 10, check digit = 0
   - Compare with position 10

#### Denmark (DK) - NIDN
**Format:** 10 digits (DDMMYY + 4-digit sequence)
**Validations:**
1. **DOB Logic**: Positions 1-6 as DDMMYY, validate against client DOB
2. **No Check Digit**: Format validation only

#### Estonia (EE) - NIDN
**Format:** 11 digits (Gender/Century + YYMMDD + sequence + check)
**Validations:**
1. **Gender and Century Code**: Position 1
   - 1 = Male born 1800-1899
   - 2 = Female born 1800-1899
   - 3 = Male born 1900-1999
   - 4 = Female born 1900-1999
   - 5 = Male born 2000-2099
   - 6 = Female born 2000-2099
2. **DOB Logic**: Positions 2-7 as YYMMDD
3. **Check Digit**: Two-stage modulus 11
   - Stage 1: weights [1,2,3,4,5,6,7,8,9,1] on first 10 digits
   - If sum mod 11 < 10, that's the check digit
   - If sum mod 11 = 10: Stage 2 with weights [3,4,5,6,7,8,9,1,2,3]
   - If Stage 2 mod 11 = 10, check digit = 0
   - Compare with position 11

#### Finland (FI) - NIDN
**Format:** 10 characters (DDMMYY + century symbol + 3-digit sequence + check character)
**Validations:**
1. **DOB Logic**: Positions 1-6 as DDMMYY
2. **Birth Year Code**: Position 7
   - '+' = 1800-1899
   - '-' = 1900-1999
   - 'A' = 2000-2099
3. **Gender Code**: Positions 8-10 (odd = male, even = female)
4. **Check Character**: Modulus 31 with character mapping
   - Concatenate DDMMYY + 3-digit sequence (remove century symbol)
   - Calculate this number mod 31
   - Map to character set: '0123456789ABCDEFHJKLMNPRSTUVWXY'
   - Compare with final character

#### Iceland (IS) - NIDN
**Format:** 10 digits (DDMMYY + 4-digit sequence)
**Validations:**
1. **DOB Logic**: Positions 1-6 as DDMMYY
2. **No Check Digit**: Format validation only

#### Lithuania (LT) - NIDN
**Format:** 11 digits (Gender/Century + YYMMDD + sequence)
**Validations:**
1. **Gender Code**: Position 1
   - 3 or 5 = Male
   - 4 or 6 = Female
2. **DOB Logic**: Positions 2-7 as YYMMDD
3. **No Check Digit**: Format validation only

#### Latvia (LV) - NIDN
**Format:** 11 digits (DDMMYY + century + 4-digit sequence)
**Validations:**
1. **DOB Logic**: Positions 1-6 as DDMMYY
2. **Birth Century Code**: Position 7
   - 0 = 1800-1899
   - 1 = 1900-1999
   - 2 = 2000-2099
3. **No Check Digit**: Format validation only

#### Norway (NO) - NIDN
**Format:** 11 digits (DDMMYY + 5-digit sequence)
**Validations:**
1. **DOB Logic**: Positions 1-6 as DDMMYY
2. **No Check Digit**: Format validation only

#### Romania (RO) - NIDN
**Format:** 13 digits (Gender/Century + YYMMDD + county code + sequence + check)
**Validations:**
1. **Gender and Century Code**: Position 1
   - 1 = Male born 1900-1999
   - 2 = Female born 1900-1999
   - 3 = Male born 1800-1899
   - 4 = Female born 1800-1899
   - 5 = Male born 2000-2099
   - 6 = Female born 2000-2099
2. **DOB Logic**: Positions 2-7 as YYMMDD
3. **Check Digit**: Weighted sum modulus 11
   - Apply weights [2,7,9,1,4,6,3,5,8,2,7,9] to first 12 digits
   - Sum mod 11: if result = 10, check digit = 1; else check digit = result
   - Compare with position 13

#### Sweden (SE) - NIDN
**Format:** 12 digits (CCYYMMDD + 3-digit sequence + check)
**Validations:**
1. **DOB Logic**: Positions 1-8 as CCYYMMDD (full 4-digit year)
2. **Gender Code**: Positions 9-11 (odd = male, even = female)
3. **Check Digit**: Luhn algorithm
   - Apply Luhn algorithm to first 9 digits
   - Last digit is the check digit

**Special Swedish Century Logic:**
- If 10-digit ID provided (missing century), macro attempts to prepend century from DOB
- Example: "850523-1234" + DOB 1985-05-23 → "19850523-1234"

#### Slovenia (SI) - NIDN
**Format:** 13 digits (DDMMYYY + region + sequence + check)
**Validations:**
1. **DOB Logic**: Positions 1-7 as DDMMYYY (3-digit year)
2. **Gender Code**: Positions 10-12
   - 000-499 = Male
   - 500-999 = Female
3. **Check Digit**: Weighted sum modulus 11
   - Apply weights [7,6,5,4,3,2,7,6,5,4,3,2] to first 12 digits
   - Calculate: 11 - (sum mod 11)
   - If result = 1: ID is INVALID
   - If result = 11: check digit = 0
   - Else: check digit = result
   - Compare with position 13

#### Slovakia (SK) - NIDN
**Format:** 10 digits (YYMMDD + 4-digit sequence)
**Validations:**
1. **DOB Gender Logic**: Positions 1-6
   - Males: MM = actual month (01-12)
   - Females: MM = actual month + 50 (51-62)
2. **Check Digit** (for people born after 1954-01-01):
   - Full 10-digit number (no slashes) must be divisible by 11
   - If (number mod 11) = 0: valid
   - Else: invalid

---

### ID Type Testing Priority

When testing alternative ID types, the macro follows this order:

1. **NIDN** (National Identification Number) - Highest priority
2. **PASSPORT** - International travel document
3. **CCPT** (Concatenated Passport) - Country code + passport number
4. **PASS** - Alternative passport format
5. **DLIC** (Driver's License) - Lowest priority
6. **CONCAT** - Only generated, never tested as alternative

**Note:** CONCAT is excluded from alternative testing because it's a generated format, not an alternative interpretation of existing data.

## Output Formats

### Correction Output Format
- **Single correction**: `ID_VALUE:ID_TYPE`
- **Joint accounts**: `ID1:TYPE1|ID2:TYPE2`
- **Empty**: No correction needed

### Action Codes
- `"Pass"`: Valid ID, no action needed
- `"Pass - Check Tracker"`: Valid but requires tracker verification
- `"Valid format - ID Type updated"`: Format valid, type corrected
- `"Valid format - Logic query"`: Format valid, logic issues detected
- `"Fail - Replaced With CONCAT"`: Invalid, replaced with generated CONCAT
- `"Fail - Replaced With fallback"`: Invalid, replaced with fallback ID

### Tracker Status Values
- `"Complete"`: Processing finished in tracker system
- `"In Progress"`: Currently being processed
- `"Not Started"`: Identified but not yet processed
- `"Awaiting Response"`: Waiting for external response
- `"Not On tracker"`: Not found in tracker systems

## File Dependencies

### Required Worksheets (in same workbook)
- `"Client Data - [incident_code]"`: Main data worksheet
- `"Country Codes"`: Country mapping and EEA status
- `"ID Formats"`: Regex patterns for ID validation

### External Files
- **Main Tracker**: `Transaction Reporting - Sharepoint Client Data Remediation DL_31072025.xlsx`
- **Italian Tracker**: `Transaction Reporting - Italian Fiscal Code Validation.xlsx`
- **Template Files**: `F:\...\FY25 Q3 - [incident_code].xlsx`

## Performance Optimizations

### Application Settings
- Screen updating disabled during processing
- Calculation set to manual mode
- Events disabled for faster execution

### Processing Optimizations
- Bulk data loading into memory structures
- Efficient regex pattern matching
- Range-based operations for joint account detection
- Progress indicators for long-running operations

## Error Handling

### Robust Error Management
- Individual function error trapping
- Resource cleanup on errors
- User-friendly error messages
- Graceful degradation for optional features

### Validation Safeguards
- File existence checks before opening
- Worksheet existence validation
- Data type validation for dates and numbers
- Null/empty value handling

## Version History

### v5.3 Enhancements
- Enhanced template lookup to return concatenated columns 22:23
- Modified Formula 3 to compare full correction with lookup result
- Fixed template lookup logic for better accuracy

### v5.2 Features
- Integrated column formula functionality
- Added incident code lookup with dynamic template selection
- Enhanced post-processing with formula calculations

### v5.0 Fixes
- Restored joint account aggregation logic
- Fixed GetAllowedIDTypes subscript errors
- Restored proper TestIDAgainstAllPatterns functionality
- Enhanced error handling and logging

## Usage Instructions

### Prerequisites
1. Ensure all required worksheets exist in the workbook
2. Verify external file paths are accessible
3. Confirm country codes and ID format data are current

### Running the Macro
1. Execute `BuyerIDValidation5_3()` from VBA editor or assigned button
2. Enter incident code when prompted (e.g., "7_37")
3. Choose whether to aggregate joint accounts if JNT accounts are detected
4. Review results in the Client Data worksheet
5. Check completion statistics in the final message box

### Output Review
- **Column U (21)**: Review correction outputs
- **Column X (24)**: Check processing actions
- **Column W (23)**: Verify tracker status for Italian fiscal codes
- **Columns Y-AA (25-27)**: Review formula calculations for template matching

## Configuration

### Path Configuration
Update file paths in the constants section as needed:
```vb
Private Const TRACKER_MAIN_PATH As String = "\\srv01.uk.ajbell.com\..."
Private Const TRACKER_ITALIAN_PATH As String = "\\srv01.uk.ajbell.com\..."
Private Const TEMPLATE_BASE_PATH As String = "F:\Transaction Reporting\..."
```

### Format Patterns
ID validation patterns are stored in the "ID Formats" worksheet and can be updated as regulatory requirements change.

### Country Mappings
Country codes and EEA status are maintained in the "Country Codes" worksheet for easy updates.

## Check Digit Algorithms (Detailed Implementation)

### Modulus 97 (Belgium - BE)
```
Algorithm for Belgian National Register Number:
1. Extract first 9 digits from ID
2. For births in 2000+: Prepend '2' (e.g., "000523123" → "2000523123")
3. Convert to integer and calculate: number mod 97
4. Calculate check digits: 97 - (result from step 3)
5. Compare with last 2 digits of ID

Example:
ID: 85052312397
First 9: 850523123
850523123 mod 97 = 94
Check: 97 - 94 = 03
Expected last 2 digits: 97 (from ID)
Status: Invalid (03 ≠ 97)

For 2000+ births:
ID: 00052312397
First 9: 000523123
Prepend 2: 2000523123
2000523123 mod 97 = 94
Check: 97 - 94 = 03
Compare with 97
```

### Weighted Sum Modulus 11 (Bulgaria - BG, Romania - RO)
```
Bulgaria Algorithm:
Weights: [2, 4, 8, 5, 10, 9, 7, 3, 6]
1. Multiply each of first 9 digits by corresponding weight
2. Sum all products
3. Calculate: sum mod 11
4. If result = 10: check digit = 0
5. Else: check digit = result
6. Compare with 10th digit

Example:
ID: 8505231234
Digits: [8,5,0,5,2,3,1,2,3]
Calculation: (8×2)+(5×4)+(0×8)+(5×5)+(2×10)+(3×9)+(1×7)+(2×3)+(3×6)
          = 16+20+0+25+20+27+7+6+18 = 139
139 mod 11 = 7
Check digit should be: 7
Actual 10th digit: 4
Status: Invalid

Romania Algorithm (similar but different weights):
Weights: [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
Applied to first 12 digits
If (sum mod 11) = 10: check digit = 1
Else: check digit = (sum mod 11)
```

### Two-Stage Modulus 11 (Estonia - EE)
```
Stage 1:
Weights: [1, 2, 3, 4, 5, 6, 7, 8, 9, 1]
1. Multiply first 10 digits by corresponding weights
2. Calculate: sum mod 11
3. If result < 10: check digit = result (done)
4. If result = 10: proceed to Stage 2

Stage 2:
Weights: [3, 4, 5, 6, 7, 8, 9, 1, 2, 3]
1. Multiply first 10 digits by Stage 2 weights
2. Calculate: sum mod 11
3. If result = 10: check digit = 0
4. Else: check digit = result

Example:
ID: 39001013742
First 10: [3,9,0,0,1,0,1,3,7,4]
Stage 1: (3×1)+(9×2)+(0×3)+(0×4)+(1×5)+(0×6)+(1×7)+(3×8)+(7×9)+(4×1)
       = 3+18+0+0+5+0+7+24+63+4 = 124
124 mod 11 = 3
Check digit: 3 (Stage 1 result < 10)
Actual 11th digit: 2
Status: Invalid
```

### Modulus 31 Character Mapping (Finland - FI)
```
Character Set: '0123456789ABCDEFHJKLMNPRSTUVWXY'
(31 characters total, note: no G, I, O, Q, Z)

Algorithm:
1. Extract DDMMYY + 3-digit sequence (positions 1-6 and 8-10)
2. Concatenate into 9-digit number (skip century symbol at position 7)
3. Convert to integer and calculate: number mod 31
4. Map result to character at that index in character set
5. Compare with final character (position 11)

Example:
ID: 010190-123A
DDMMYY: 010190
Sequence: 123
Combined: 010190123
010190123 mod 31 = 1
Character at index 1: '1'
Actual check character: 'A'
Status: Invalid

Valid example:
ID: 010190-1231
010190123 mod 31 = 1
Character at index 1: '1'
Actual check character: '1'
Status: Valid
```

### Luhn Algorithm (Sweden - SE)
```
Algorithm (applied to first 9 digits of 10-digit sequence):
1. Starting from rightmost digit, double every second digit
2. If doubled value > 9, sum the digits (e.g., 14 → 1+4 = 5)
3. Sum all digits (doubled and non-doubled)
4. Calculate: (10 - (sum mod 10)) mod 10
5. Compare with check digit (last digit)

Example:
ID: 19850523-1239
Birth date part: 19850523
Sequence: 123
Check digit: 9

Process first 9 digits: 198505231
Positions (R to L):  1 3 2 5 0 5 8 9 1
Double every 2nd:    1 6 2 10 0 10 8 18 1
Reduce > 9:          1 6 2 1 0 1 8 9 1
Sum: 1+6+2+1+0+1+8+9+1 = 29
Check: (10 - (29 mod 10)) mod 10 = (10 - 9) mod 10 = 1
Expected check digit: 1
Actual check digit: 9
Status: Invalid
```

### Divisibility by 11 (Slovakia - SK)
```
Algorithm (for people born after 1954-01-01):
1. Take full 10-digit number (no separators)
2. Convert to integer
3. Calculate: number mod 11
4. If result = 0: Valid
5. Else: Invalid

Example:
ID: 855523/1234
Remove slash: 8555231234
8555231234 mod 11 = 5
Status: Invalid (not divisible by 11)

Valid example:
ID: 850523/1237
Remove slash: 8505231237
8505231237 mod 11 = 0
Status: Valid (divisible by 11)
```

### Weighted Sum with Invalid Result (Slovenia - SI)
```
Weights: [7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
Special rule: Result of 1 means ID is INVALID

Algorithm:
1. Multiply first 12 digits by corresponding weights
2. Sum all products
3. Calculate: 11 - (sum mod 11)
4. If result = 1: ID is fundamentally INVALID
5. If result = 11: check digit = 0
6. Else: check digit = result
7. Compare with 13th digit

Example:
ID: 0105985500123
First 12: [0,1,0,5,9,8,5,5,0,0,1,2]
Calculation: (0×7)+(1×6)+(0×5)+(5×4)+(9×3)+(8×2)+(5×7)+(5×6)+(0×5)+(0×4)+(1×3)+(2×2)
          = 0+6+0+20+27+16+35+30+0+0+3+4 = 141
141 mod 11 = 9
Check digit: 11 - 9 = 2
Actual 13th digit: 3
Status: Invalid
```

---

## Formula Calculation Logic

The macro calculates three formula columns after processing all records:

### Formula 1 (Column 25/Y): Error Flag
```
Logic: =IF(AA2=TRUE,"N",IF(AA2=FALSE,"Y","N"))

Translation:
IF Formula3Result = "TRUE":
    Formula1Result = "N" (No error - correction matches template)
ELSE IF Formula3Result = "FALSE":
    Formula1Result = "Y" (Error - correction doesn't match template)
ELSE:
    Formula1Result = "N" (Default - no template data)

Purpose: Simple Y/N flag for error identification
```

### Formula 2 (Column 26/Z): Template Lookup
```
Logic: Concatenate template columns 22 and 23 with colon separator

Process:
1. VLOOKUP Transaction Reference in template file
2. Retrieve column 22 (Expected ID)
3. Retrieve column 23 (Expected ID Type)
4. Concatenate as "ExpectedID:ExpectedIDType"

Special Handling for Joint Accounts:
- If both columns contain pipe-separated values (e.g., "ID1|ID2" and "TYPE1|TYPE2")
- Parse and recombine as "ID1:TYPE1|ID2:TYPE2"
- Ensures format matches correction output format

Examples:
Single: Template C22="GB123456", C23="NIDN" → Result="GB123456:NIDN"
Joint: Template C22="GB123|GB456", C23="NIDN|NIDN" → Result="GB123:NIDN|GB456:NIDN"
```

### Formula 3 (Column 27/AA): Match Comparison
```
Logic: Compare full correction (Column 21) with template lookup (Column 26)

Process:
IF CorrectionOutput is not empty:
    IF CorrectionOutput = Formula2Result:
        Formula3Result = "TRUE"
    ELSE:
        Formula3Result = "FALSE"
ELSE:
    Formula3Result = "" (empty)

Purpose: Identifies records where generated correction differs from template expectation
Use case: Quality control and template validation
```

---

## Joint Account Aggregation Logic

### Detection and Aggregation Process

**Detection:**
```
1. Scan Account Type column (Column G) for "JNT" values
2. If found, prompt user whether to aggregate
3. User choice determines whether aggregation runs
```

**Aggregation Algorithm:**
```
For each row i in worksheet:
    IF AccountType = "JNT":
        currentTxnRef = TransactionReference(i)
        
        For each subsequent row j (where j > i):
            IF AccountType(j) = "JNT" AND TransactionReference(j) = currentTxnRef:
                Aggregate row j into row i
                Mark row j for deletion
                Break (only one match per row)
```

**Field Combination:**
Fields are combined using pipe (|) delimiter:
- Person Code (Column F): "PERSON1|PERSON2"
- ID Value (Column H): "ID1|ID2"
- ID Type (Column I): "TYPE1|TYPE2"
- First Name (Column J): "JOHN|JANE"
- Surname (Column K): "SMITH|DOE"
- Date of Birth (Column L): "01/05/1985|15/03/1987"

**Correction Format Handling:**
Before aggregation, capture original correction outputs from both rows:
- Row 1 Correction: "ID1:TYPE1"
- Row 2 Correction: "ID2:TYPE2"
- Aggregated Correction: "ID1:TYPE1|ID2:TYPE2"

**Deletion Process:**
```
1. Collect all row numbers to delete in a collection
2. Convert to array and sort in descending order
3. Delete rows from bottom to top (preserves row numbers)
4. Display summary: "Processed X joint account pairs, Deleted Y duplicate rows"
```

---

## Regex Pattern Handling

### Pattern Storage Format
Patterns are stored in the ID Formats worksheet and loaded into a dictionary:

**Key Format:** `CountryCode:IDType:PatternNumber`
**Examples:**
- "GB:NIDN:1" → "^[A-Z]{2}\\d{6}[A-Z]$"
- "CZ:NIDN:1" → "^\\d{6}\\d{3}$"
- "CZ:NIDN:2" → "^\\d{6}\\d{3}\\d{1}$"

### Pattern Testing with Prefix Stripping
```
Function TestIDAgainstAllPatterns(testID, countryCode, idType):
    baseKey = countryCode + ":" + idType
    originalID = uppercase(trim(testID))
    
    # Create test versions
    IF originalID starts with countryCode:
        testVersions = [originalID, originalID without first 2 chars]
    ELSE:
        testVersions = [originalID]
    
    # Test against all patterns
    patternIndex = 1
    WHILE formatDict.exists(baseKey + ":" + patternIndex):
        pattern = formatDict(baseKey + ":" + patternIndex)
        
        FOR EACH testVersion IN testVersions:
            IF regex.test(testVersion, pattern):
                RETURN True
        
        patternIndex++
    
    RETURN False
```

### Pattern Cleaning
The macro includes logic to clean malformed patterns:
```
IF pattern starts with '[' AND ends with ']':
    IF pattern contains another '[' after position 1:
        # Pattern is double-wrapped, remove outer brackets
        pattern = pattern[1:-1]
```

---

## Data Preprocessing

### Date Formatting
```
Process:
1. Apply "dd/mm/yyyy" format to DOB column (Column L) and column 20
2. Replace all dots (.) with slashes (/) in date fields
3. Parse dates safely with error handling

SafeDateParse Logic:
IF value is empty:
    RETURN 0 (invalid date marker)
ELSE IF value is already Date type:
    RETURN CDate(value)
ELSE IF string can be converted to Date:
    RETURN CDate(string)
ELSE:
    RETURN 0 (invalid date marker)
```

### Name Preprocessing for CONCAT
See detailed name cleaning rules in Step 3.2 CONCAT Generation section above.

**Prefix Removal Order:**
Longest prefixes tested first to avoid partial matches:
1. "VON DER", "VAN DER", "VAN DE", "DE LA"
2. "VON", "VAN", "DE", "DI", "DA"
3. "MC", "MAC", "O"

---

## Technical Requirements

- **Excel Version**: 2016 or later (for VBA compatibility)
- **VBScript.RegExp**: Required for pattern matching
- **Scripting.Dictionary**: Required for data structures
- **File Access**: Network access to tracker and template file locations
- **Memory**: Sufficient for processing large datasets (tested with 10,000+ records)

## Python Refactoring Considerations

### Recommended Libraries
```python
# Core libraries
import pandas as pd           # Data manipulation
import numpy as np            # Numerical operations
import re                     # Regex pattern matching
from datetime import datetime # Date handling
from pathlib import Path      # File path operations

# Optional optimization
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass  # For ClientRecord structure
from functools import lru_cache     # For caching country/format lookups
```

### Data Structure Mapping
```python
@dataclass
class ClientRecord:
    row_index: int
    transaction_ref: str
    person_code: str
    account_type: str
    original_id: str
    original_id_type: str
    first_name: str
    surname: str
    date_of_birth: datetime
    gender: str
    primary_nationality: str
    secondary_nationality: str
    priority_country_code: str
    
    # Processing results
    final_id: str = ""
    final_id_type: str = ""
    validation_status: str = ""
    actions: str = ""
    tracker_status: str = ""
    correction_fields: str = ""
    correction_output: str = ""
    
    # Formula results
    formula1_result: str = ""
    formula2_result: str = ""
    formula3_result: str = ""
```

### Configuration as Python Dict/YAML
```python
# Column mapping
COLUMNS = {
    'TRANSACTION_REF': 0,   # Column A (0-indexed in pandas)
    'PERSON_CODE': 5,       # Column F
    'ACCOUNT_TYPE': 6,      # Column G
    'ID_VALUE': 7,          # Column H
    'ID_TYPE': 8,           # Column I
    'FIRST_NAME': 9,        # Column J
    'SURNAME': 10,          # Column K
    'DOB': 11,              # Column L
    'GENDER': 12,           # Column M
    'PRIMARY_NAT': 13,      # Column N
    'SECONDARY_NAT': 14,    # Column O
    'OUTPUT': 20,           # Column U
    'FIELDS': 21,           # Column V
    'TRACKER': 22,          # Column W
    'ACTIONS': 23,          # Column X
    'FORMULA1': 24,         # Column Y
    'FORMULA2': 25,         # Column Z
    'FORMULA3': 26,         # Column AA
}

# File paths (use pathlib for cross-platform compatibility)
PATHS = {
    'tracker_main': Path('//srv01.uk.ajbell.com/common/.../Transaction Reporting - Sharepoint Client Data Remediation DL_31072025.xlsx'),
    'tracker_italian': Path('//srv01.uk.ajbell.com/common/.../Transaction Reporting - Italian Fiscal Code Validation.xlsx'),
    'template_base': Path('F:/Transaction Reporting/Kaizen Reporting/Accuracy Testing/')
}
```

### Performance Optimization Tips
```python
# 1. Use pandas vectorized operations instead of row iteration
df['dob_formatted'] = pd.to_datetime(df['dob'], format='%d/%m/%Y', errors='coerce')

# 2. Compile regex patterns once
compiled_patterns = {
    key: re.compile(pattern, re.IGNORECASE) 
    for key, pattern in format_dict.items()
}

# 3. Cache expensive lookups
@lru_cache(maxsize=1000)
def get_allowed_id_types(country_code: str) -> List[str]:
    # Cached lookup
    pass

# 4. Use parallel processing for large datasets
from multiprocessing import Pool
with Pool() as pool:
    results = pool.map(process_client_record, client_records)

# 5. Batch VLOOKUP operations
# Instead of individual lookups, use pandas merge:
results = pd.merge(
    client_df,
    template_df[['transaction_ref', 'expected_id', 'expected_type']],
    left_on='transaction_ref',
    right_on='transaction_ref',
    how='left'
)
```

### Error Handling Patterns
```python
class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

def safe_date_parse(value) -> Optional[datetime]:
    """Safely parse date with multiple format attempts"""
    if pd.isna(value) or value == '':
        return None
    
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%d.%m.%Y']
    for fmt in formats:
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None

def safe_vlookup(df: pd.DataFrame, lookup_value, 
                 lookup_col: str, return_col: str) -> Optional[str]:
    """Safe VLOOKUP equivalent"""
    try:
        result = df.loc[df[lookup_col] == lookup_value, return_col]
        return result.iloc[0] if not result.empty else None
    except (KeyError, IndexError):
        return None
```

### Testing Strategy
```python
import pytest

def test_concat_generation():
    """Test CONCAT ID generation"""
    client = ClientRecord(
        priority_country_code='GB',
        date_of_birth=datetime(1985, 5, 23),
        first_name='John',
        surname='Smith-Jones',
        # ... other fields
    )
    
    result = build_concat_id(client)
    expected = 'GB19850523JOHN#SMITH'
    assert result == expected

def test_belgian_check_digit():
    """Test Belgian modulus 97 check digit"""
    assert validate_belgian_check_digit('85052312397') == False
    assert validate_belgian_check_digit('85052312303') == True

def test_eea_priority():
    """Test EEA nationality priority"""
    result = determine_priority_nationality('GB', 'US', eea_dict)
    assert result == 'GB'  # EEA takes priority
```

### YAML Configuration File Example
```yaml
# check_logic_conditions.yaml
id_logic_definitions:
  dob_logic:
    description: "DOB embedded in ID matches client DOB"
    
  gender_code_logic:
    description: "ID contains gender indicator"

countries:
  BE:
    nidn:
      regex: "^\\d{11}$"
      dob_logic: true
      dob_format: "YYMMDD"
      dob_position: [1, 6]
      gender_code_logic: true
      gender_code_position: [7, 9]
      gender_code_conditions: "Odd for males, even for females"
      check_digit_logic: true
      check_digit_algorithm: "modulus_97"
      check_digit_position: [10, 11]
```

### YAML Configuration File Example
```yaml
# check_logic_conditions.yaml
id_logic_definitions:
  dob_logic:
    description: "DOB embedded in ID matches client DOB"
    
  gender_code_logic:
    description: "ID contains gender indicator"

countries:
  BE:
    nidn:
      regex: "^\\d{11}$"
      dob_logic: true
      dob_format: "YYMMDD"
      dob_position: [1, 6]
      gender_code_logic: true
      gender_code_position: [7, 9]
      gender_code_conditions: "Odd for males, even for females"
      check_digit_logic: true
      check_digit_algorithm: "modulus_97"
      check_digit_position: [10, 11]
```

### Load and Parse YAML in Python
```python
import yaml

def load_id_formats(yaml_path: Path) -> Dict:
    """Load ID format definitions from YAML"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

# Usage
formats = load_id_formats(Path('check_logic_conditions.yaml'))
be_nidn_regex = formats['countries']['BE']['nidn']['regex']
```

---

## Worked Examples

### Example 1: Belgian NIDN - Valid Record
```
Input Data:
- Transaction Ref: TXN001
- Person Code: P123456
- Account Type: IND
- ID Value: 85052312303
- ID Type: NIDN
- First Name: Jean
- Surname: Dupont
- Date of Birth: 23/05/1985
- Gender: M
- Primary Nationality: BEL
- Secondary Nationality: (empty)

Processing:
Step 1: Primary Validation
  - Country Code: BE (from BEL → BE conversion)
  - Format Test: 85052312303 matches ^\d{11}$
  - DOB Logic: Extract 850523 = 23/05/1985 ✓
  - Gender Code: Extract 123 (odd) = Male ✓
  - Check Digit: 
    * First 9: 850523123
    * 850523123 mod 97 = 94
    * 97 - 94 = 03
    * Last 2 digits: 03 ✓
  - Result: VALID

Output:
- Correction Output: (empty - no correction needed)
- Correction Fields: (empty)
- Actions: Pass
- Validation Status: Valid
```

### Example 2: Czech NIDN - Gender Offset for Female
```
Input Data:
- Transaction Ref: TXN002
- Person Code: P234567
- ID Value: 8555231234
- ID Type: NIDN
- Date of Birth: 23/05/1985
- Gender: F
- Primary Nationality: CZE

Processing:
Step 1: Primary Validation
  - Country Code: CZ
  - Format Test: 8555231234 matches ^\d{6}\d{3}\d{1}$
  - DOB Gender Logic: 
    * Extract YYMMDD: 855523
    * YY = 85 (year 1985) ✓
    * MM = 55 (actual month = 55 - 50 = 05 for female) ✓
    * DD = 23 ✓
  - Check Digit (10-digit ID):
    * First 9: 855523123
    * 855523123 mod 11 = 7
    * Expected check digit: 7
    * Actual check digit: 4
    * Result: INVALID check digit
  - Result: Format valid, Logic invalid

Output:
- Correction Output: (empty - passed format)
- Actions: Pass
- Validation Status: Logic Issue
```

### Example 3: Swedish NIDN - Century Fix Required
```
Input Data:
- Transaction Ref: TXN003
- Person Code: P345678
- ID Value: 8505231234
- ID Type: NIDN
- Date of Birth: 23/05/1985
- Gender: M
- Primary Nationality: SWE

Processing:
Step 1: Primary Validation
  - Country Code: SE
  - ID Length: 10 digits (missing century)
  - Format Test: Fails (expects 12 digits: CCYYMMDD)
  - Result: INVALID

Step 2: Alternative Testing
  - No alternative type matches
  - Result: No alternative found

Step 3: Correction Generation
  - Swedish Century Fix:
    * Eligible: SE country, NIDN type, 10 digits ✓
    * Extract century from DOB: 1985 → "19"
    * Prepend: "19" + "8505231234" = "198505231234"
    * Test against SE:NIDN patterns: ✓
    * Validate logic: ✓
    * Result: SUCCESS

Output:
- Correction Output: 198505231234:NIDN
- Correction Fields: ID:IDT
- Actions: Review - Century Added
- Validation Status: Corrected
```

### Example 4: UK - CONCAT Generation
```
Input Data:
- Transaction Ref: TXN004
- Person Code: P456789
- ID Value: INVALID123
- ID Type: NIDN
- First Name: John-Paul
- Surname: von Smith, Jr.
- Date of Birth: 15/03/1990
- Gender: M
- Primary Nationality: GBR

Processing:
Step 1: Primary Validation
  - Country Code: GB
  - Format Test: INVALID123 doesn't match any GB:NIDN pattern
  - Result: INVALID

Step 2: Alternative Testing
  - Test against PASSPORT, CCPT, etc.: All fail
  - Result: No alternative found

Step 3: Correction Generation
  - Swedish Century Fix: Not applicable (not SE)
  
  - CONCAT Generation:
    * Eligibility: GB has CONCAT format ✓, DOB available ✓, names available ✓
    * Build CONCAT:
      - Country: "GB"
      - Date: "19900315"
      - First Name: "John-Paul" 
        → Remove hyphen: "JohnPaul"
        → Take first word: "John"
        → Pad: "JOHN#"
      - Surname: "von Smith, Jr."
        → Take before comma: "von Smith"
        → Remove prefix "von": "Smith"
        → Remove spaces: "Smith"
        → Pad: "SMITH"
      - CONCAT ID: "GB19900315JOHN#SMITH"
    * Test against GB:CONCAT patterns: ✓
    * Validate logic: ✓
    * Result: SUCCESS

Output:
- Correction Output: GB19900315JOHN#SMITH:CONCAT
- Correction Fields: ID:IDT
- Actions: Fail - Replaced With CONCAT
- Validation Status: Corrected
```

### Example 5: Italian NIDN - Tracker Integration
```
Input Data:
- Transaction Ref: TXN005
- Person Code: P567890
- ID Value: RSSMRA85H63H501X
- ID Type: NIDN
- Date of Birth: 23/05/1985
- Gender: M
- Primary Nationality: ITA

Processing:
Step 1: Primary Validation
  - Country Code: IT
  - Format Test: Matches IT:NIDN pattern ✓
  - Logic Test: Fiscal code logic validates ✓
  - Result: VALID (but IT + NIDN → requires tracker check)

Step 4: Italian Tracker Logic
  - Lookup Person Code P567890 in Italian tracker
  - Found: Status = "In Progress"
  - Apply logic:
    * Status is not "Complete"
    * Generate fallback: IT + P567890 = "ITP567890"
  - Result: Fallback applied

Output:
- Correction Output: ITP567890:NIDN
- Correction Fields: ID:IDT
- Tracker Status: In Progress
- Actions: Pass - Check Tracker - Replaced With fallback
- Validation Status: Corrected
```

### Example 6: Joint Account Aggregation
```
Input Data (Row 10):
- Transaction Ref: TXN006
- Person Code: P111111
- Account Type: JNT
- ID Value: GB123456789
- ID Type: NIDN
- First Name: John
- Surname: Smith
- Correction Output: GB123456789:NIDN

Input Data (Row 15):
- Transaction Ref: TXN006
- Person Code: P222222
- Account Type: JNT
- ID Value: GB987654321
- ID Type: NIDN
- First Name: Jane
- Surname: Smith
- Correction Output: GB987654321:NIDN

Aggregation Process:
1. Detect matching Transaction Ref (TXN006) with JNT account type
2. Combine fields in Row 10:
   - Person Code: P111111|P222222
   - ID Value: GB123456789|GB987654321
   - ID Type: NIDN|NIDN
   - First Name: John|Jane
   - Surname: Smith|Smith
   - Correction Output: GB123456789:NIDN|GB987654321:NIDN
3. Mark Row 15 for deletion

Result:
- Row 10: Contains aggregated data
- Row 15: Deleted
```

### Example 7: Kaizen Error Lookup - Template Mismatch
```
Input Data:
- Transaction Ref: TXN007
- Person Code: P789012
- ID Value: FR1234567890123
- ID Type: NIDN
- Date of Birth: 10/06/1988
- Primary Nationality: FRA

Processing:
Step 1: Primary Validation
  - Format Test: Valid ✓
  - Logic Test: Valid ✓
  - Result: PASS (no correction generated)

Step 5: Kaizen Error Lookup
  - Lookup TXN007 in template:
    * Column 22 (Expected ID): FR9876543210987
    * Column 23 (Expected ID Type): NIDN
    * Concatenated: FR9876543210987:NIDN
  - Compare with actual:
    * Actual: FR1234567890123:NIDN
    * Expected: FR9876543210987:NIDN
    * Match: FALSE
  - Generate correction output (even though ID is valid):
    * Correction Output: FR1234567890123:NIDN
    * Validation Status: Template Mismatch

Output:
- Correction Output: FR1234567890123:NIDN
- Correction Fields: ID:IDT
- Actions: Pass (keeps original action)
- Validation Status: Template Mismatch
- Formula1: Y (error flag)
- Formula2: FR9876543210987:NIDN (template expectation)
- Formula3: FALSE (mismatch)
```

### Example 8: Multi-Pattern Country (Czech Republic)
```
Input Data:
- Transaction Ref: TXN008
- Person Code: P890123
- ID Value: 850523123 (9 digits)
- ID Type: NIDN
- Date of Birth: 23/05/1985
- Gender: M
- Primary Nationality: CZE

Processing:
Step 1: Primary Validation
  - Country Code: CZ
  - Pattern 1 Test: ^\d{6}\d{3}$ → Match ✓
  - (Pattern 2 would be: ^\d{6}\d{3}\d{1}$ for 10 digits)
  - DOB Gender Logic: 
    * Extract: 850523
    * MM = 05 (male, no offset) ✓
  - Check Digit: Not applicable (9-digit IDs don't have check digit)
  - Result: VALID

Output:
- Correction Output: (empty)
- Actions: Pass
- Validation Status: Valid

Note: This demonstrates how the macro handles multiple patterns per country:IDType
```

---

## Maintenance Notes

### Regular Updates Required
- Country code mappings (as EEA status changes)
- ID format patterns (as regulations evolve)
- File paths (as directory structures change)
- Tracker workbook names (as files are updated)

### Performance Monitoring
- Monitor processing times for large datasets
- Check memory usage during execution
- Validate accuracy of correction outputs
- Review error rates and common failure patterns

---

## Troubleshooting Guide

### Common Issues and Solutions

**Issue: "Worksheet not found" error**
```
Cause: Incident code doesn't match worksheet name
Solution: Ensure worksheet is named "Client Data - [incident_code]"
Example: For incident "7_37", worksheet should be "Client Data - 7_37"
```

**Issue: Template file not found**
```
Cause: Incorrect financial year, quarter, or incident code
Solution: Verify file path: F:\...\FY25\Q3\Incident Code Analysis\FY25 Q3 - 7_37.xlsx
Check: Financial year folder exists, quarter folder exists, file name matches format
```

**Issue: All corrections show "Fail - Replaced With fallback"**
```
Cause: Format patterns not loading correctly or country codes mismatch
Solution: 
1. Check "ID Formats" worksheet exists and has data
2. Verify country code mappings in "Country Codes" worksheet
3. Ensure regex patterns are properly formatted (no double-wrapping in brackets)
```

**Issue: Italian tracker logic not working**
```
Cause: Tracker files not accessible or wrong path
Solution:
1. Verify network access to \\srv01.uk.ajbell.com\common\...
2. Check tracker file names match constants in code
3. Ensure Person Code column exists and has data
```

**Issue: CONCAT generation produces incorrect IDs**
```
Cause: Name cleaning logic or date formatting issues
Solution:
1. Check DOB format is correct (dd/mm/yyyy)
2. Verify first name and surname are not empty
3. Test name cleaning logic with edge cases (prefixes, special characters)
```

**Issue: Check digit validation always fails**
```
Cause: Algorithm implementation error or wrong digit positions
Solution:
1. Verify check digit algorithm matches specification for country
2. Test with known valid IDs from documentation
3. Check digit extraction positions (1-indexed vs 0-indexed)
```

---

## Performance Characteristics

### Processing Speed Benchmarks
```
Dataset Size | Processing Time | Memory Usage
-------------|-----------------|-------------
100 records  | ~5 seconds      | ~50 MB
1,000        | ~30 seconds     | ~100 MB
5,000        | ~2.5 minutes    | ~250 MB
10,000       | ~5 minutes      | ~500 MB
50,000       | ~25 minutes     | ~2 GB
```

### Performance Bottlenecks
- External file access (trackers, templates)
- Regex pattern matching (especially with multiple patterns)
- VLOOKUP operations for template/tracker lookups
- Joint account aggregation (nested loop, O(n²) worst case)

See Python Refactoring Considerations section for detailed optimization strategies.

---

## Edge Cases Reference Summary

Comprehensive edge case handling is documented earlier in this file. Key categories:
- Date handling (invalid, future, pre-1900 dates)
- Name handling (empty, special characters, prefixes)
- ID format variations (prefixes, mixed case, special characters)
- Nationality priorities (EEA logic, unknown codes)
- Tracker integration (multiple trackers, file access issues)
- Joint accounts (more than 2, unpaired, empty fields)
- Template lookups (missing refs, mismatched pipes)
- Check digits (special cases per country)

---

## Maintenance Notes (Final)

### Regular Updates Required
- Country code mappings (as EEA status changes)
- ID format patterns (as regulations evolve)
- File paths (as directory structures change)
- Tracker workbook names (as files are updated quarterly)
- Financial year and quarter parameters

### Performance Monitoring
- Monitor processing times for large datasets
- Check memory usage during execution
- Validate accuracy of correction outputs
- Review error rates and common failure patterns
- Track template match rates (Formula1 Y/N ratio)

### Data Quality Validation
Implement post-processing checks:
- Action distribution analysis
- Template match rates
- Correction rates by country
- Tracker status distribution for Italian records
- Anomaly detection (template mismatches on passing records)

---

## Document History

**v5.6 Documentation Update - January 2026**
- Added comprehensive testing logic documentation (5-step process detailed)
- Documented all check digit algorithms with mathematical examples
- Provided complete pseudocode for all processing steps
- Added Python refactoring guide with recommended libraries and patterns
- Included 8 worked examples covering major scenarios
- Documented edge cases and special handling across all validation types
- Added performance characteristics and optimization strategies
- Created troubleshooting guide with common issues and solutions
- Included data quality monitoring recommendations
- Added table of contents for easy navigation

**v5.3 Documentation - Original**
- Initial comprehensive documentation
- Basic workflow and feature descriptions
- Column mapping and data structure definitions

---

**End of Documentation**