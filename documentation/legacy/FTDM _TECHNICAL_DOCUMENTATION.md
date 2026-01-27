# Fund Trade Decision Maker Validation - Technical Documentation

## Document Overview
**Version:** 1.0  
**Date:** January 27, 2026  
**Purpose:** Comprehensive technical documentation for Python refactoring  
**Incident Codes:** 12_17 (Buyer), 21_17 (Seller)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Data Model](#data-model)
4. [Validation Logic](#validation-logic)
5. [ID Format Validation](#id-format-validation)
6. [Product Determination](#product-determination)
7. [Database Queries](#database-queries)
8. [Extract Generation](#extract-generation)
9. [Version History](#version-history)
10. [Python Refactoring Guidelines](#python-refactoring-guidelines)
11. [Error Handling](#error-handling)
12. [Appendices](#appendices)

---

## Executive Summary

### Purpose
The Fund Trade Decision Maker validation macros ensure that discretionary trading accounts have the correct decision maker code populated. When a trade is executed on a discretionary basis, the decision maker (typically a fund manager or investment advisor) must be identified separately from the account holder (buyer/seller).

### Business Rule
For **discretionary accounts** (Service Level = "D"):
- The Decision Maker Code **must be populated**
- The Decision Maker Code **must be different** from the Buyer/Seller Code
- If either condition fails, the correct LEI must be looked up and provided as a correction

### Key Validation Scenarios

| Scenario | Decision Maker Code | Same as Buyer Code? | Result |
|----------|---------------------|---------------------|--------|
| Non-discretionary | Any | N/A | No Error |
| SIPP Account | Any | N/A | No Error |
| Discretionary | Empty | N/A | Error - Provide LEI |
| Discretionary | Populated | Yes | Error - Provide correct LEI |
| Discretionary | Populated | No | No Error |

### Macro Variants
- **ValidateFTBDM** (12_17): Validates **Buyer** Decision Maker Code
- **ValidateFTSDM** (21_17): Validates **Seller** Decision Maker Code

Both macros share identical logic; only field names differ (Buyer vs Seller).

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│          Fund Trade Decision Maker Validation System         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Data Extraction                                   │  │
│  │     - SQL query generation (batches of 900)           │  │
│  │     - DB2 database extraction                         │  │
│  │     - Multi-table joins for client/party data         │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Data Loading                                      │  │
│  │     - Load transaction data to "Client Data" sheet    │  │
│  │     - Load LEI reference data to "LEI Data" sheet     │  │
│  │     - Load ID formats to "ID and LEI Formats" sheet   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. ID Format Validation                              │  │
│  │     - Regex pattern matching for ID types             │  │
│  │     - LEI format validation (20-char alphanumeric)    │  │
│  │     - National ID format validation                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Product Determination                             │  │
│  │     - Account ID prefix analysis                      │  │
│  │     - Product categorization (AJB, AJBIC, DODL, etc.) │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. Decision Maker Validation                         │  │
│  │     - Service level check (Discretionary?)            │  │
│  │     - Decision maker population check                 │  │
│  │     - Same-value detection                            │  │
│  │     - LEI lookup and correction generation            │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  6. Output & Reporting                                │  │
│  │     - Write validation results                        │  │
│  │     - Generate corrections                            │  │
│  │     - Format output columns                           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### External Dependencies

#### Worksheets Required
| Sheet Name | Purpose |
|------------|---------|
| Client Data | Main data sheet with transaction records |
| LEI Data | Reference data mapping Branch Code → LEI |
| ID and LEI Formats | Regex patterns for ID type validation |

#### File Paths
- **Extract Generator:** `FTBDM Extract Generator.xlsm` / `FTSDM Extract Generator.xlsm`
- **Validation Workbook:** `FTBDM Validation.xlsm` / `FTSDM Validation.xlsm`
- **SQL Output:** `Extracts/Generated Extracts/ExtractN.sql`

---

## Data Model

### DecisionMakerRecord Structure

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class Product(Enum):
    AJB = "AJB"
    AJBIC = "AJBIC"
    DODL = "DODL"
    CUSTODY_SOLUTIONS = "Custody Solutions"

class ServiceLevel(Enum):
    DISCRETIONARY = "D"
    ADVISORY = "A"
    EXECUTION_ONLY = "E"

@dataclass
class DecisionMakerRecord:
    """
    Core data structure for Decision Maker validation
    
    Attributes:
        transaction_ref: Unique transaction identifier
        account_id: Client account identifier
        buyer_code: Buyer identification code (LEI or National ID)
        buyer_code_type: Type of buyer ID (LEI, NIDN, CONCAT, etc.)
        buyer_dm_code: Buyer decision maker code
        buyer_dm_code_type: Type of decision maker ID
        product: Product type derived from account ID
        account_type: Account category (SIPP, Custody Solutions, etc.)
        service_level: Service level (D=Discretionary, A=Advisory, E=Execution)
        branch_code: Branch/Partner code for LEI lookup
        error: Validation error flag
        correction: Suggested correction value
        correction_field: Field name(s) being corrected
    """
    # Primary identifier
    transaction_ref: str                    # Column 1
    
    # Input fields
    account_id: str                         # Column 2
    buyer_code: str                         # Column 3
    buyer_dm_code: str                      # Column 5
    account_type: str                       # Column 8
    service_level: str                      # Column 9
    branch_code: str                        # Column 10
    
    # Calculated/Output fields
    buyer_code_type: str = ""               # Column 4
    buyer_dm_code_type: str = ""            # Column 6
    product: str = ""                       # Column 7
    error: str = "N"                        # Column 11
    correction: str = ""                    # Column 12
    correction_field: str = ""              # Column 13
```

### Column Mapping (13 columns)

| Column | Name | Type | Direction | Description |
|--------|------|------|-----------|-------------|
| 1 | Transaction Reference | String | Static | Unique transaction ID |
| 2 | Account ID | String | Input | Client account number |
| 3 | Buyer Code | String | Input | Buyer identification code |
| 4 | Type of Buyer ID | String | Output | ID type (LEI, NIDN, etc.) |
| 5 | Buyer DM Code | String | Input | Decision maker code |
| 6 | Type of Buyer DM ID | String | Output | DM ID type |
| 7 | Product | String | Output | Derived product name |
| 8 | Account Type | String | Input | Account category |
| 9 | Service Level | String | Input | D/A/E service level |
| 10 | Branch Code | String | Input | Branch/Partner code |
| 11 | Error | String | Output | Y/N/TBC flag |
| 12 | Correction | String | Output | Correction value |
| 13 | Correction Field | String | Output | Field being corrected |

### Seller Variant Column Differences

For **Seller** validation (21_17), the following columns change:
- Column 3: **Seller Code** (instead of Buyer Code)
- Column 4: **Type of Seller ID**
- Column 5: **Seller DM Code**
- Column 6: **Type of Seller DM ID**

### LEI Reference Data Structure

| Column | Name | Description |
|--------|------|-------------|
| 1 | Branch Code | Branch/Partner identifier |
| 2 | LEI | Legal Entity Identifier (20 chars) |

---

## Validation Logic

### High-Level Decision Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Validation Decision Tree                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Start → Is Account Type "SIPP"?                            │
│              │                                                │
│          Yes │ No                                            │
│              ↓                                                │
│         No Error    Is Account Type "Custody Solutions"?     │
│                         │                                     │
│                     Yes │ No                                 │
│                         ↓                                     │
│              Is Service Level "D"?  →  Same check            │
│                     │                                         │
│                 Yes │ No                                     │
│                     ↓                                         │
│           [Discretionary Logic]    No Error                  │
│                     │                                         │
│           Is DM Code Empty?                                  │
│                     │                                         │
│                 Yes │ No                                     │
│                     ↓                                         │
│        [Lookup LEI + Error]    Is DM = Buyer Code?          │
│                                       │                       │
│                                   Yes │ No                   │
│                                       ↓                       │
│                           [Lookup LEI + Error]   No Error    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Validation Algorithm

```python
def validate_decision_maker(record: DecisionMakerRecord, 
                           lei_lookup: Dict[str, str]) -> None:
    """
    Main validation function for Decision Maker records
    
    Args:
        record: DecisionMakerRecord to validate
        lei_lookup: Dictionary mapping branch_code -> LEI
    
    Business Rules:
    1. SIPP accounts: Always no error
    2. Custody Solutions with Service Level 'D': Check DM
    3. Other accounts with Service Level 'D': Check DM
    4. Non-discretionary accounts: Always no error
    
    Error Conditions:
    - DM Code is empty (for discretionary)
    - DM Code equals Buyer Code (for discretionary)
    
    Correction Format:
    - "<LEI>:L" where L indicates LEI type
    """
    # Default to no error
    record.error = "N"
    record.correction = ""
    record.correction_field = ""
    
    # Step 1: SIPP accounts - no validation needed
    if record.account_type.upper() == "SIPP":
        return
    
    # Step 2: Check if discretionary
    is_discretionary = record.service_level.upper() == "D"
    
    if not is_discretionary:
        # Non-discretionary accounts - no error
        return
    
    # Step 3: Discretionary validation
    validate_discretionary_account(record, lei_lookup)


def validate_discretionary_account(record: DecisionMakerRecord,
                                  lei_lookup: Dict[str, str]) -> None:
    """
    Validate discretionary account decision maker
    
    Three scenarios:
    1. DM Code empty -> Error, provide LEI
    2. DM Code = Buyer Code -> Error, provide correct LEI
    3. DM Code different -> No error
    """
    branch_code = record.branch_code.strip()
    buyer_dm_code = record.buyer_dm_code.strip()
    buyer_code = record.buyer_code.strip()
    
    # Check if branch exists in lookup
    branch_exists = branch_code in lei_lookup
    decision_maker_lei = lei_lookup.get(branch_code, "")
    
    if buyer_dm_code == "":
        # Scenario 1: DM Code is empty
        if branch_exists:
            if decision_maker_lei:
                record.correction = f"{decision_maker_lei}:L"
                record.correction_field = "Buyer decision maker code:Type of buyer decision maker code"
                record.error = "Y"
            else:
                # Branch found but LEI is empty
                record.error = "Y"
        else:
            # Branch not found - needs investigation
            record.error = "TBC - Investigate branch code"
    
    elif buyer_code == buyer_dm_code:
        # Scenario 2: DM Code equals Buyer Code
        if branch_exists:
            if decision_maker_lei and decision_maker_lei != buyer_dm_code:
                record.correction = f"{decision_maker_lei}:L"
                record.correction_field = "Buyer decision maker code:Type of buyer decision maker code"
                record.error = "Y"
            else:
                # Cannot determine correct LEI
                record.error = "TBC - Investigate LEI"
        else:
            record.error = "TBC - Investigate branch code"
    
    else:
        # Scenario 3: DM Code is different from Buyer Code - valid
        record.error = "N"
```

### VBA Implementation (v3.0)

```vba
Sub ValidateDiscretionaryAccount(wsLEI As Worksheet, buyerCode As String, _
                                buyerDMCode As String, branchCode As String, _
                                ByRef isError As String, ByRef correction As String, _
                                ByRef correctionField As String)
    Dim decisionMakerLEI As String
    Dim branchExists As Boolean
    
    If buyerDMCode = "" Then
        ' No DM populated - need correction
        decisionMakerLEI = FindDecisionMakerLEI(wsLEI, branchCode, branchExists)
        If branchExists Then
            If decisionMakerLEI <> "" Then
                correction = decisionMakerLEI & ":L"
                correctionField = "Buyer decision maker code:Type of buyer decision maker code"
                isError = "Y"
            Else
                isError = "Y" ' LEI found but empty
            End If
        Else
            isError = "TBC - Investigate branch code"
        End If
    ElseIf buyerCode = buyerDMCode Then
        ' Same values - potential error, try to find correct DM
        decisionMakerLEI = FindDecisionMakerLEI(wsLEI, branchCode, branchExists)
        If branchExists Then
            If decisionMakerLEI <> "" And decisionMakerLEI <> buyerDMCode Then
                correction = decisionMakerLEI & ":L"
                correctionField = "Buyer decision maker code:Type of buyer decision maker code"
                isError = "Y"
            Else
                isError = "TBC - Investigate LEI"
            End If
        Else
            isError = "TBC - Investigate branch code"
        End If
    Else
        ' Different values - no error
        isError = "N"
    End If
End Sub

Function FindDecisionMakerLEI(wsLEI As Worksheet, branchCode As String, _
                             ByRef branchExists As Boolean) As String
    Dim lastRowLEI As Long, j As Long
    
    branchExists = False
    FindDecisionMakerLEI = ""
    
    ' Validate worksheet and find last row
    If wsLEI Is Nothing Then Exit Function
    lastRowLEI = wsLEI.Cells(wsLEI.Rows.Count, 1).End(xlUp).Row
    If lastRowLEI < 2 Then Exit Function
    
    ' Search for matching branch code
    For j = 2 To lastRowLEI
        If Trim(CStr(wsLEI.Cells(j, 1).Value)) = branchCode Then
            branchExists = True
            FindDecisionMakerLEI = Trim(CStr(wsLEI.Cells(j, 2).Value))
            Exit For
        End If
    Next j
End Function
```

### Validation Examples

#### Example 1: No Error - Different DM Code
```
Input:
  Account ID: A12345678
  Account Type: ISA
  Service Level: D (Discretionary)
  Buyer Code: 549300ABCDEFGHIJ1234
  Buyer DM Code: 549300XYZABC123456HJ
  Branch Code: ABC001

Analysis:
  - Account is discretionary (D)
  - DM Code is populated
  - DM Code ≠ Buyer Code

Result: No Error (N)
```

#### Example 2: Error - Empty DM Code
```
Input:
  Account ID: B98765432
  Account Type: General Investment
  Service Level: D (Discretionary)
  Buyer Code: 549300ABCDEFGHIJ1234
  Buyer DM Code: (empty)
  Branch Code: XYZ002

LEI Lookup:
  XYZ002 → 549300FUNDMANAGER0099

Analysis:
  - Account is discretionary (D)
  - DM Code is empty
  - Branch found with valid LEI

Result: 
  Error: Y
  Correction: 549300FUNDMANAGER0099:L
  Correction Field: Buyer decision maker code:Type of buyer decision maker code
```

#### Example 3: Error - Same Value
```
Input:
  Account ID: X11111111
  Account Type: Trading
  Service Level: D (Discretionary)
  Buyer Code: 549300CLIENTID12345678
  Buyer DM Code: 549300CLIENTID12345678  (Same!)
  Branch Code: DEF003

LEI Lookup:
  DEF003 → 549300CORRECTLEI123456

Analysis:
  - Account is discretionary (D)
  - DM Code = Buyer Code (error condition)
  - Branch found with different LEI

Result:
  Error: Y
  Correction: 549300CORRECTLEI123456:L
  Correction Field: Buyer decision maker code:Type of buyer decision maker code
```

#### Example 4: TBC - Unknown Branch
```
Input:
  Account ID: A99999999
  Account Type: Managed
  Service Level: D (Discretionary)
  Buyer Code: 549300ABCDEFGHIJ1234
  Buyer DM Code: (empty)
  Branch Code: UNKNOWN

LEI Lookup:
  UNKNOWN not found

Result:
  Error: TBC - Investigate branch code
```

#### Example 5: No Error - SIPP Account
```
Input:
  Account ID: A55555555
  Account Type: SIPP
  Service Level: D (Discretionary)
  Buyer Code: 549300ABCDEFGHIJ1234
  Buyer DM Code: 549300ABCDEFGHIJ1234  (Same value)
  Branch Code: ABC001

Analysis:
  - Account is SIPP → Skip validation

Result: No Error (N)
```

---

## ID Format Validation

### Purpose
Validate and classify identification codes using regex pattern matching to determine the ID type (LEI, National ID, CONCAT, etc.).

### LEI Format
Legal Entity Identifiers follow ISO 17442 format:
- **Length:** 20 characters
- **Format:** 18 alphanumeric characters + 2 digit checksum
- **Pattern:** `^[A-Z0-9]{18}\d{2}$`

### VBA Implementation

```vba
Function ValidateIDFormat(wsFormats As Worksheet, idCode As String) As String
    ' This function checks if an ID matches any of the regex patterns
    ' Returns the ID type if match found, empty string if no match
    
    Dim regex As Object
    Dim lastRowFormats As Long, j As Long
    Dim currentPattern As String, currentIDType As String
    
    ValidateIDFormat = "" ' Default to empty if no match
    
    ' Skip validation if ID is empty
    If Trim(idCode) = "" Then Exit Function
    
    ' Create regex object for pattern matching
    Set regex = CreateObject("VBScript.RegExp")
    regex.Global = False ' We only need to know if it matches
    regex.IgnoreCase = False ' Case sensitive matching
    
    ' Find last row in formats sheet
    lastRowFormats = wsFormats.Cells(wsFormats.Rows.Count, 1).End(xlUp).Row
    If lastRowFormats < 2 Then Exit Function
    
    ' Check LEI format first (most common)
    regex.Pattern = "^[A-Z0-9]{18}\d{2}$"
    If regex.Test(Trim(idCode)) Then
        ValidateIDFormat = "LEI"
        Exit Function
    End If
    
    ' Check other patterns in order they appear in the table
    For j = 2 To lastRowFormats
        currentIDType = Trim(CStr(wsFormats.Cells(j, 2).Value)) ' Column B: ID type
        currentPattern = Trim(CStr(wsFormats.Cells(j, 3).Value)) ' Column C: regex
        
        If currentPattern <> "" And currentIDType <> "" Then
            regex.Pattern = currentPattern
            If regex.Test(Trim(idCode)) Then
                ValidateIDFormat = currentIDType
                Exit Function
            End If
        End If
    Next j
End Function
```

### Python Implementation

```python
import re
from typing import Dict, Optional

class IDFormatValidator:
    """Validate and classify identification codes"""
    
    # Built-in LEI pattern (most common)
    LEI_PATTERN = re.compile(r'^[A-Z0-9]{18}\d{2}$')
    
    def __init__(self, patterns: Dict[str, str] = None):
        """
        Initialize validator with ID patterns
        
        Args:
            patterns: Dictionary mapping ID type name to regex pattern
        """
        self.patterns = {}
        if patterns:
            for id_type, pattern_str in patterns.items():
                try:
                    self.patterns[id_type] = re.compile(pattern_str)
                except re.error as e:
                    print(f"Invalid pattern for {id_type}: {e}")
    
    def validate(self, id_code: str) -> Optional[str]:
        """
        Validate an ID code and return its type
        
        Args:
            id_code: The identification code to validate
        
        Returns:
            ID type string if matched, None if no match
        """
        if not id_code or not id_code.strip():
            return None
        
        id_code = id_code.strip()
        
        # Check LEI first (most common)
        if self.LEI_PATTERN.match(id_code):
            return "LEI"
        
        # Check other patterns
        for id_type, pattern in self.patterns.items():
            if pattern.match(id_code):
                return id_type
        
        return None

# Usage
patterns = {
    'NIDN_GB': r'^[A-Z]{2}\d{6}[A-Z]$',      # UK National Insurance
    'NIDN_SE': r'^\d{10,12}$',                # Swedish Personnummer
    'CONCAT': r'^[A-Z0-9]{15,}$',             # Concatenated format
}

validator = IDFormatValidator(patterns)
print(validator.validate("549300ABCDEFGHIJ1234"))  # Returns: "LEI"
```

### Common ID Types

| ID Type | Description | Example Pattern | Example Value |
|---------|-------------|-----------------|---------------|
| LEI | Legal Entity Identifier | `^[A-Z0-9]{18}\d{2}$` | 549300ABCDEF123456XY |
| NIDN | National ID Number | Varies by country | AB123456C (UK NI) |
| CONCAT | Concatenated Name | `^[A-Z]+#[A-Z]+#.*` | SMITH#JOHN#19800101 |
| INTC | Internal Code | Custom format | Various |

---

## Product Determination

### Logic
Product type is determined from the first character of the Account ID:

```python
def determine_product(account_id: str) -> str:
    """
    Determine product type from account ID prefix
    
    Args:
        account_id: Client account identifier
    
    Returns:
        Product name string
    
    Mapping:
        A -> AJB (AJ Bell Youinvest)
        B -> AJBIC (AJ Bell Investment Centre)
        X -> DODL (DODL Platform)
        Other -> Custody Solutions
    """
    if not account_id:
        return "Custody Solutions"
    
    prefix = account_id[0].upper()
    
    product_map = {
        'A': 'AJB',
        'B': 'AJBIC',
        'X': 'DODL'
    }
    
    return product_map.get(prefix, "Custody Solutions")
```

### VBA Implementation

```vba
Function DetermineProduct(accountID As String) As String
    If Len(accountID) > 0 Then
        Select Case UCase(Left(accountID, 1))
            Case "A": DetermineProduct = "AJB"
            Case "B": DetermineProduct = "AJBIC"
            Case "X": DetermineProduct = "DODL"
            Case Else: DetermineProduct = "Custody Solutions"
        End Select
    Else
        DetermineProduct = "Custody Solutions"
    End If
End Function
```

### Product Reference

| Prefix | Product | Full Name |
|--------|---------|-----------|
| A | AJB | AJ Bell Youinvest |
| B | AJBIC | AJ Bell Investment Centre |
| X | DODL | DODL Platform |
| Other | Custody Solutions | Custody Solutions |

---

## Database Queries

### Extract Query Structure

The extraction query retrieves transaction data with client and party information:

```sql
SELECT
    t1.REPORTREF,                           -- Transaction Reference
    t2.CLINO,                               -- Client Number (Account ID)
    CASE
        WHEN t3.INDIDCODE <> '' THEN t3.INDIDCODE
        ELSE t4.ENTIDCODE
    END AS Buyer_ID_Code,                   -- Buyer Identification Code
    CASE
        WHEN t1.BUYDECIND <> '' THEN t1.BUYDECIND
        ELSE t1.BUYDECENT
    END AS Buyer_DM_Code,                   -- Buyer Decision Maker Code
    t2.CLNTTY,                              -- Client Type (Account Type)
    t2.TSATYP,                              -- TSA Type (Service Level)
    CASE
        WHEN t2.BRNCH3 <> ''
        THEN t2.BRNCH3
        ELSE t2.PARTNR
    END AS BGETTER                          -- Branch/Partner Code
FROM
    GLDATA/TXNREPESMA t1
    JOIN GLDATA/CONTCT t7 ON 
        t7.FRMCOD
        || t7.YEAR
        || t7.ACCLTR
        || t7.CONTNO
        || '1' = t1.REPORTREF 
    JOIN GLDATA/CLIENT t2 ON t7.CLINUM = t2.CLINO
    LEFT JOIN GLDATA/ESMAPTYIND t3 ON t1.REPORTREF = t3.REPORTREF
        AND t3.PARTY = 'BUYER'
    LEFT JOIN GLDATA/ESMAPTYENT t4 ON t1.REPORTREF = t4.REPORTREF
        AND t4.PARTY = 'BUYER'
WHERE
    t1.REPORTREF IN (
        -- Transaction references inserted here
    )
LIMIT 50000
```

### Table Descriptions

| Table | Alias | Purpose |
|-------|-------|---------|
| TXNREPESMA | t1 | Main transaction reporting table |
| CONTCT | t7 | Contract details for join key |
| CLIENT | t2 | Client master data |
| ESMAPTYIND | t3 | Individual party identification |
| ESMAPTYENT | t4 | Entity party identification |

### Key Field Mappings

| Query Field | Description | Maps To |
|-------------|-------------|---------|
| REPORTREF | Transaction Reference | Column 1 |
| CLINO | Client Number | Column 2 (Account ID) |
| Buyer_ID_Code | Individual or Entity ID | Column 3 |
| Buyer_DM_Code | Individual or Entity DM | Column 5 |
| CLNTTY | Client Type | Column 8 (Account Type) |
| TSATYP | TSA Type | Column 9 (Service Level) |
| BGETTER | Branch or Partner | Column 10 (Branch Code) |

### Decision Maker Code Logic

The query uses CASE expressions to determine the correct decision maker code:

```sql
-- Individual decision maker takes precedence
CASE
    WHEN t1.BUYDECIND <> '' THEN t1.BUYDECIND
    ELSE t1.BUYDECENT
END AS Buyer_DM_Code
```

**Logic:**
1. If individual decision maker (BUYDECIND) is populated → use it
2. Otherwise → use entity decision maker (BUYDECENT)

### Seller Variant Query

For seller validation, change:
- `t3.PARTY = 'SELLER'` and `t4.PARTY = 'SELLER'`
- Use `SELDECIND` and `SELDECENT` instead of buyer fields

---

## Extract Generation

### Extract Generator Workflow

```
┌─────────────────────────────────────────────────────────┐
│              Extract Generation Process                  │
│                                                           │
│  1. Load Transaction References from "Extract Generator" │
│     ↓                                                     │
│  2. Assign Extract Numbers (900 per batch)               │
│     ↓                                                     │
│  3. Generate SQL Query for Each Batch                    │
│     ↓                                                     │
│  4. Write SQL Files (Extract1.sql, Extract2.sql, etc.)   │
└─────────────────────────────────────────────────────────┘
```

### VBA Extract Generator (v3.0)

```vba
Sub ExtractFTBDM3_0()
    Dim ws As Worksheet
    Dim outputPath As String
    Dim sqlTemplate As String
    Dim sqlBody As String
    Dim lRow As Long
    Dim transactionRef As String
    Dim currentExtract As String
    Dim previousExtract As String
    Dim extractNumber As Long
    Dim transactionCount As Long

    Set ws = ThisWorkbook.Sheets("Extract Generator")
    outputPath = ws.Range("B1").Value

    If Right(outputPath, 1) <> "\" Then
        outputPath = "H:\...\Extracts\Generated Extracts\"
    End If

    ' --- Assign Extract Numbers ---
    ' Clear existing extract numbers
    lRow = 2
    Do While ws.Cells(lRow, 1).Value <> ""
        ws.Cells(lRow, 2).Value = ""
        lRow = lRow + 1
    Loop

    ' Assign numbers in batches of 900
    lRow = 2
    extractNumber = 1
    transactionCount = 0

    Do While ws.Cells(lRow, 1).Value <> ""
        transactionRef = Trim(ws.Cells(lRow, 1).Value)

        If transactionRef <> "" Then
            transactionCount = transactionCount + 1

            If transactionCount > 900 Then
                extractNumber = extractNumber + 1
                transactionCount = 1
            End If

            ws.Cells(lRow, 2).Value = extractNumber
        End If

        lRow = lRow + 1
    Loop
    
    ' Generate SQL files...
    ' (SQL template and file writing logic)
    
End Sub
```

### Python Extract Generator

```python
from pathlib import Path
from typing import List
import pandas as pd

class FTBDMExtractGenerator:
    """Generate SQL extract files for Fund Trade Decision Maker"""
    
    SQL_TEMPLATE = """SELECT
    t1.REPORTREF,
    t2.CLINO,
    CASE
        WHEN t3.INDIDCODE <> '' THEN t3.INDIDCODE
        ELSE t4.ENTIDCODE
    END AS Buyer_ID_Code,
    CASE
        WHEN t1.BUYDECIND <> '' THEN t1.BUYDECIND
        ELSE t1.BUYDECENT
    END AS Buyer_DM_Code,
    t2.CLNTTY,
    t2.TSATYP,
    CASE
        WHEN t2.BRNCH3 <> ''
        THEN t2.BRNCH3
        ELSE t2.PARTNR
    END AS BGETTER
FROM
    GLDATA/TXNREPESMA t1
    JOIN GLDATA/CONTCT t7 ON 
        t7.FRMCOD || t7.YEAR || t7.ACCLTR || t7.CONTNO || '1' = t1.REPORTREF 
    JOIN GLDATA/CLIENT t2 ON t7.CLINUM = t2.CLINO
    LEFT JOIN GLDATA/ESMAPTYIND t3 ON t1.REPORTREF = t3.REPORTREF
        AND t3.PARTY = 'BUYER'
    LEFT JOIN GLDATA/ESMAPTYENT t4 ON t1.REPORTREF = t4.REPORTREF
        AND t4.PARTY = 'BUYER'
WHERE
    t1.REPORTREF IN (
{transaction_refs}
    )
LIMIT 50000"""
    
    def __init__(self, output_dir: Path, batch_size: int = 900):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_extracts(self, transaction_refs: List[str]) -> int:
        """
        Generate SQL extract files from transaction references
        
        Args:
            transaction_refs: List of transaction reference strings
        
        Returns:
            Number of extract files generated
        """
        # Batch the references
        batches = self._create_batches(transaction_refs)
        
        # Generate SQL file for each batch
        for batch_num, batch in enumerate(batches, start=1):
            self._write_extract_file(batch_num, batch)
        
        print(f"Generated {len(batches)} extract files")
        return len(batches)
    
    def _create_batches(self, refs: List[str]) -> List[List[str]]:
        """Split references into batches"""
        batches = []
        for i in range(0, len(refs), self.batch_size):
            batch = refs[i:i + self.batch_size]
            batches.append(batch)
        return batches
    
    def _write_extract_file(self, batch_num: int, refs: List[str]) -> None:
        """Write single SQL extract file"""
        # Format references for IN clause
        formatted_refs = ",\n".join([f"'{ref}'" for ref in refs])
        
        # Build SQL
        sql = self.SQL_TEMPLATE.format(transaction_refs=formatted_refs)
        
        # Write file
        output_file = self.output_dir / f"Extract{batch_num}.sql"
        output_file.write_text(sql, encoding='utf-8')
        print(f"Created {output_file.name} with {len(refs)} references")

# Usage
generator = FTBDMExtractGenerator(
    output_dir=Path("Extracts/Generated Extracts"),
    batch_size=900
)

# Load transaction refs from Excel
df = pd.read_excel("FTBDM Extract Generator.xlsm", sheet_name="Extract Generator")
refs = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()

generator.generate_extracts(refs)
```

---

## Version History

### v1.0 - Initial Implementation
- Basic decision maker validation
- Simple LEI lookup
- Manual error flagging

### v1.1 - Error Handling Enhancement
- Added structured error handling (`On Error GoTo`)
- Introduced helper functions for modularity
- Improved branch code validation with `branchExists` flag
- Added "TBC - Investigate" error states

### v2.0 - ID Format Validation
- Added ID format validation using regex patterns
- New worksheet dependency: "ID and LEI Formats"
- Output ID type classification (LEI, NIDN, etc.)
- Added columns 4 and 6 for ID types

### v3.0 - Current Version
- Refined validation logic
- Performance optimization (screen updating control)
- Consistent column constant definitions
- Improved code organization with dedicated functions
- Better separation of buyer/seller variants

### Key Changes Summary

| Version | Feature | Change |
|---------|---------|--------|
| 1.0→1.1 | Error Handling | Added `On Error GoTo ErrorHandler` |
| 1.0→1.1 | Modularity | Extracted helper functions |
| 1.1→2.0 | ID Validation | Added regex pattern matching |
| 1.1→2.0 | Worksheets | Added "ID and LEI Formats" |
| 2.0→3.0 | Performance | Added `Application.ScreenUpdating` |
| 2.0→3.0 | Structure | Consolidated column constants |

---

## Python Refactoring Guidelines

### Recommended Project Structure

```
fund_trade_dm_validation/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Entry point
│   ├── config.py                    # Configuration constants
│   ├── models/
│   │   ├── __init__.py
│   │   └── decision_maker_record.py # Data models
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py                # Excel data loading
│   │   ├── lei_lookup.py            # LEI reference data
│   │   └── sql_generator.py         # Extract generation
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── dm_validator.py          # Decision maker validation
│   │   ├── id_format_validator.py   # ID format validation
│   │   └── product_determiner.py    # Product classification
│   ├── output/
│   │   ├── __init__.py
│   │   └── writer.py                # Write results to Excel
│   └── utils/
│       ├── __init__.py
│       └── helpers.py               # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_dm_validation.py
│   ├── test_id_format.py
│   └── test_integration.py
├── config/
│   ├── id_patterns.yaml             # ID format patterns
│   └── paths.yaml                   # File paths
├── requirements.txt
└── README.md
```

### Complete Python Implementation

```python
# src/models/decision_maker_record.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DecisionMakerRecord:
    """Decision Maker validation record"""
    
    # Input fields
    transaction_ref: str
    account_id: str
    buyer_code: str
    buyer_dm_code: str
    account_type: str
    service_level: str
    branch_code: str
    
    # Output fields
    buyer_code_type: str = ""
    buyer_dm_code_type: str = ""
    product: str = ""
    error: str = "N"
    correction: str = ""
    correction_field: str = ""
    
    @classmethod
    def from_row(cls, row: dict) -> 'DecisionMakerRecord':
        """Create record from Excel row dictionary"""
        return cls(
            transaction_ref=str(row.get('Transaction Reference', '')).strip(),
            account_id=str(row.get('Account ID', '')).strip(),
            buyer_code=str(row.get('Buyer Code', '')).strip(),
            buyer_dm_code=str(row.get('Buyer DM Code', '')).strip(),
            account_type=str(row.get('Account Type', '')).strip(),
            service_level=str(row.get('Service Level', '')).strip(),
            branch_code=str(row.get('Branch Code', '')).strip()
        )
    
    def to_dict(self) -> dict:
        """Convert record to dictionary for output"""
        return {
            'Transaction Reference': self.transaction_ref,
            'Account ID': self.account_id,
            'Buyer Code': self.buyer_code,
            'Type of Buyer ID': self.buyer_code_type,
            'Buyer DM Code': self.buyer_dm_code,
            'Type of Buyer DM ID': self.buyer_dm_code_type,
            'Product': self.product,
            'Account Type': self.account_type,
            'Service Level': self.service_level,
            'Branch Code': self.branch_code,
            'Error': self.error,
            'Correction': self.correction,
            'Correction Field': self.correction_field
        }
```

```python
# src/validation/dm_validator.py
from typing import Dict, List
from ..models.decision_maker_record import DecisionMakerRecord
import logging

logger = logging.getLogger(__name__)

class DecisionMakerValidator:
    """Validate Decision Maker codes for fund trades"""
    
    def __init__(self, lei_lookup: Dict[str, str], party_type: str = "Buyer"):
        """
        Initialize validator
        
        Args:
            lei_lookup: Dictionary mapping branch_code -> LEI
            party_type: "Buyer" or "Seller" for correction field names
        """
        self.lei_lookup = lei_lookup
        self.party_type = party_type
        self.correction_field_template = f"{party_type} decision maker code:Type of {party_type.lower()} decision maker code"
    
    def validate_record(self, record: DecisionMakerRecord) -> None:
        """
        Validate a single Decision Maker record
        
        Args:
            record: DecisionMakerRecord to validate (modified in place)
        """
        # Initialize defaults
        record.error = "N"
        record.correction = ""
        record.correction_field = ""
        
        # SIPP accounts - no validation
        if record.account_type.upper() == "SIPP":
            return
        
        # Check if discretionary
        if record.service_level.upper() != "D":
            return
        
        # Discretionary validation
        self._validate_discretionary(record)
    
    def _validate_discretionary(self, record: DecisionMakerRecord) -> None:
        """Validate discretionary account decision maker"""
        branch_code = record.branch_code.strip()
        buyer_dm_code = record.buyer_dm_code.strip()
        buyer_code = record.buyer_code.strip()
        
        branch_exists = branch_code in self.lei_lookup
        decision_maker_lei = self.lei_lookup.get(branch_code, "")
        
        if not buyer_dm_code:
            # DM Code is empty
            self._handle_empty_dm(record, branch_exists, decision_maker_lei)
        elif buyer_code == buyer_dm_code:
            # DM Code equals Buyer Code
            self._handle_same_value(record, branch_exists, decision_maker_lei, buyer_dm_code)
        # else: Different values - no error (already set to "N")
    
    def _handle_empty_dm(self, record: DecisionMakerRecord, 
                        branch_exists: bool, lei: str) -> None:
        """Handle case where DM code is empty"""
        if branch_exists:
            if lei:
                record.correction = f"{lei}:L"
                record.correction_field = self.correction_field_template
                record.error = "Y"
            else:
                record.error = "Y"
        else:
            record.error = "TBC - Investigate branch code"
    
    def _handle_same_value(self, record: DecisionMakerRecord,
                          branch_exists: bool, lei: str, 
                          current_dm: str) -> None:
        """Handle case where DM code equals Buyer code"""
        if branch_exists:
            if lei and lei != current_dm:
                record.correction = f"{lei}:L"
                record.correction_field = self.correction_field_template
                record.error = "Y"
            else:
                record.error = "TBC - Investigate LEI"
        else:
            record.error = "TBC - Investigate branch code"
    
    def validate_batch(self, records: List[DecisionMakerRecord]) -> Dict[str, int]:
        """
        Validate batch of records
        
        Returns:
            Statistics dictionary
        """
        stats = {'total': len(records), 'no_error': 0, 'error': 0, 'tbc': 0}
        
        for record in records:
            self.validate_record(record)
            
            if record.error == "N":
                stats['no_error'] += 1
            elif record.error == "Y":
                stats['error'] += 1
            else:
                stats['tbc'] += 1
        
        return stats
```

```python
# src/main.py
from pathlib import Path
import pandas as pd
from typing import Dict, List
import logging

from .models.decision_maker_record import DecisionMakerRecord
from .validation.dm_validator import DecisionMakerValidator
from .validation.id_format_validator import IDFormatValidator
from .validation.product_determiner import determine_product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FundTradeDMValidationPipeline:
    """Complete validation pipeline for Fund Trade Decision Maker"""
    
    def __init__(self, 
                 validation_workbook: Path,
                 party_type: str = "Buyer"):
        """
        Initialize pipeline
        
        Args:
            validation_workbook: Path to Excel workbook
            party_type: "Buyer" or "Seller"
        """
        self.workbook_path = validation_workbook
        self.party_type = party_type
        self.id_validator = IDFormatValidator()
        self.lei_lookup: Dict[str, str] = {}
        self.records: List[DecisionMakerRecord] = []
    
    def load_data(self) -> None:
        """Load data from Excel workbook"""
        logger.info(f"Loading data from {self.workbook_path}")
        
        # Load client data
        client_df = pd.read_excel(
            self.workbook_path, 
            sheet_name="Client Data",
            dtype=str
        ).fillna('')
        
        # Load LEI reference data
        lei_df = pd.read_excel(
            self.workbook_path,
            sheet_name="LEI Data",
            dtype=str
        ).fillna('')
        
        # Build LEI lookup
        for _, row in lei_df.iterrows():
            branch = str(row.iloc[0]).strip()
            lei = str(row.iloc[1]).strip()
            if branch:
                self.lei_lookup[branch] = lei
        
        # Convert to records
        self.records = []
        for _, row in client_df.iterrows():
            record = DecisionMakerRecord.from_row(row.to_dict())
            self.records.append(record)
        
        logger.info(f"Loaded {len(self.records)} records, {len(self.lei_lookup)} LEI mappings")
    
    def process(self) -> Dict[str, int]:
        """Run validation pipeline"""
        logger.info("Starting validation process")
        
        # Initialize validator
        dm_validator = DecisionMakerValidator(
            lei_lookup=self.lei_lookup,
            party_type=self.party_type
        )
        
        # Process each record
        for record in self.records:
            # Determine product
            record.product = determine_product(record.account_id)
            
            # Validate ID formats
            record.buyer_code_type = self.id_validator.validate(record.buyer_code) or ""
            record.buyer_dm_code_type = self.id_validator.validate(record.buyer_dm_code) or ""
            
            # Validate decision maker
            dm_validator.validate_record(record)
        
        # Get stats
        stats = {'total': len(self.records), 'no_error': 0, 'error': 0, 'tbc': 0}
        for record in self.records:
            if record.error == "N":
                stats['no_error'] += 1
            elif record.error == "Y":
                stats['error'] += 1
            else:
                stats['tbc'] += 1
        
        logger.info(f"Validation complete: {stats}")
        return stats
    
    def save_results(self, output_path: Path = None) -> None:
        """Save results back to Excel"""
        if output_path is None:
            output_path = self.workbook_path
        
        # Convert to DataFrame
        data = [record.to_dict() for record in self.records]
        df = pd.DataFrame(data)
        
        # Write to Excel (preserve other sheets)
        with pd.ExcelWriter(output_path, mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name='Client Data', index=False)
        
        logger.info(f"Results saved to {output_path}")

def main():
    """Main entry point"""
    # Buyer validation
    pipeline = FundTradeDMValidationPipeline(
        validation_workbook=Path("FTBDM Validation.xlsm"),
        party_type="Buyer"
    )
    
    pipeline.load_data()
    stats = pipeline.process()
    pipeline.save_results()
    
    print(f"\nValidation Complete!")
    print(f"Total: {stats['total']}")
    print(f"No Error: {stats['no_error']}")
    print(f"Error: {stats['error']}")
    print(f"TBC: {stats['tbc']}")

if __name__ == "__main__":
    main()
```

### Testing Strategy

```python
# tests/test_dm_validation.py
import pytest
from src.models.decision_maker_record import DecisionMakerRecord
from src.validation.dm_validator import DecisionMakerValidator

class TestDecisionMakerValidation:
    """Test Decision Maker validation logic"""
    
    @pytest.fixture
    def lei_lookup(self):
        return {
            "ABC001": "549300FUNDMANAGER0001",
            "XYZ002": "549300FUNDMANAGER0002",
            "EMPTY": ""  # Branch with empty LEI
        }
    
    @pytest.fixture
    def validator(self, lei_lookup):
        return DecisionMakerValidator(lei_lookup, party_type="Buyer")
    
    def test_sipp_account_no_error(self, validator):
        """SIPP accounts should always pass"""
        record = DecisionMakerRecord(
            transaction_ref="TEST001",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="549300CLIENT00000001",  # Same value
            account_type="SIPP",
            service_level="D",  # Discretionary
            branch_code="ABC001"
        )
        
        validator.validate_record(record)
        
        assert record.error == "N"
        assert record.correction == ""
    
    def test_non_discretionary_no_error(self, validator):
        """Non-discretionary accounts should always pass"""
        record = DecisionMakerRecord(
            transaction_ref="TEST002",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="",  # Empty
            account_type="ISA",
            service_level="E",  # Execution only
            branch_code="ABC001"
        )
        
        validator.validate_record(record)
        
        assert record.error == "N"
    
    def test_discretionary_empty_dm_with_valid_lei(self, validator):
        """Empty DM code with valid LEI lookup"""
        record = DecisionMakerRecord(
            transaction_ref="TEST003",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="",
            account_type="General",
            service_level="D",
            branch_code="ABC001"
        )
        
        validator.validate_record(record)
        
        assert record.error == "Y"
        assert record.correction == "549300FUNDMANAGER0001:L"
        assert "decision maker code" in record.correction_field
    
    def test_discretionary_same_value_with_different_lei(self, validator):
        """DM code same as buyer with different LEI available"""
        record = DecisionMakerRecord(
            transaction_ref="TEST004",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="549300CLIENT00000001",  # Same!
            account_type="General",
            service_level="D",
            branch_code="ABC001"
        )
        
        validator.validate_record(record)
        
        assert record.error == "Y"
        assert record.correction == "549300FUNDMANAGER0001:L"
    
    def test_discretionary_different_values_no_error(self, validator):
        """Different DM code should be valid"""
        record = DecisionMakerRecord(
            transaction_ref="TEST005",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="549300MANAGER0000001",  # Different
            account_type="General",
            service_level="D",
            branch_code="ABC001"
        )
        
        validator.validate_record(record)
        
        assert record.error == "N"
        assert record.correction == ""
    
    def test_unknown_branch_tbc(self, validator):
        """Unknown branch should result in TBC"""
        record = DecisionMakerRecord(
            transaction_ref="TEST006",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="",
            account_type="General",
            service_level="D",
            branch_code="UNKNOWN"
        )
        
        validator.validate_record(record)
        
        assert "TBC" in record.error
        assert "branch" in record.error.lower()
    
    def test_empty_lei_in_lookup_error(self, validator):
        """Branch with empty LEI should be error"""
        record = DecisionMakerRecord(
            transaction_ref="TEST007",
            account_id="A12345",
            buyer_code="549300CLIENT00000001",
            buyer_dm_code="",
            account_type="General",
            service_level="D",
            branch_code="EMPTY"  # Has empty LEI
        )
        
        validator.validate_record(record)
        
        assert record.error == "Y"
        assert record.correction == ""  # No correction possible
```

---

## Error Handling

### Error Categories

| Error Type | Value | Description |
|------------|-------|-------------|
| No Error | "N" | Record passes validation |
| Error with Correction | "Y" | Error found, correction provided |
| Needs Investigation | "TBC - Investigate branch code" | Branch not in LEI lookup |
| Needs Investigation | "TBC - Investigate LEI" | Branch found but LEI issue |

### VBA Error Handling

```vba
Sub ValidateDecisionMaker3_0()
    On Error GoTo ErrorHandler
    
    ' ... validation logic ...
    
    Exit Sub
    
ErrorHandler:
    Application.ScreenUpdating = True
    MsgBox "Error occurred: " & Err.Description & " (Error " & Err.Number & ")"
End Sub
```

### Python Error Handling

```python
class ValidationError(Exception):
    """Base validation error"""
    pass

class LEILookupError(ValidationError):
    """Error looking up LEI"""
    pass

class DataLoadError(ValidationError):
    """Error loading data"""
    pass

def safe_validate(record: DecisionMakerRecord, 
                 validator: DecisionMakerValidator) -> None:
    """Validate with error handling"""
    try:
        validator.validate_record(record)
    except Exception as e:
        logger.error(f"Validation error for {record.transaction_ref}: {e}")
        record.error = f"ERROR: {str(e)}"
```

---

## Appendices

### Appendix A: Complete Column Reference

| Col | Buyer Name | Seller Name | Type | Direction |
|-----|------------|-------------|------|-----------|
| 1 | Transaction Reference | Transaction Reference | String | Static |
| 2 | Account ID | Account ID | String | Input |
| 3 | Buyer Code | Seller Code | String | Input |
| 4 | Type of Buyer ID | Type of Seller ID | String | Output |
| 5 | Buyer DM Code | Seller DM Code | String | Input |
| 6 | Type of Buyer DM ID | Type of Seller DM ID | String | Output |
| 7 | Product | Product | String | Output |
| 8 | Account Type | Account Type | String | Input |
| 9 | Service Level | Service Level | String | Input |
| 10 | Branch Code | Branch Code | String | Input |
| 11 | Error | Error | String | Output |
| 12 | Correction | Correction | String | Output |
| 13 | Correction Field | Correction Field | String | Output |

### Appendix B: Service Level Codes

| Code | Name | Validation Required |
|------|------|---------------------|
| D | Discretionary | Yes |
| A | Advisory | No |
| E | Execution Only | No |

### Appendix C: Account Types

| Account Type | Validation Required |
|--------------|---------------------|
| SIPP | No (exempt) |
| Custody Solutions | If Discretionary |
| ISA | If Discretionary |
| General Investment | If Discretionary |
| Trading | If Discretionary |

### Appendix D: Correction Format

Corrections are formatted as:
```
<LEI>:L
```

Where:
- `<LEI>` = 20-character Legal Entity Identifier
- `:L` = Type indicator for LEI

Example:
```
549300FUNDMANAGER0001:L
```

### Appendix E: Glossary

| Term | Definition |
|------|------------|
| **LEI** | Legal Entity Identifier - 20-char unique identifier |
| **Decision Maker** | Entity/individual making trading decisions |
| **Discretionary** | Account where manager makes investment decisions |
| **SIPP** | Self-Invested Personal Pension |
| **TBC** | To Be Confirmed - requires manual investigation |
| **Branch Code** | Internal branch/partner identifier |
| **BGETTER** | Business getter - branch or partner code |

---

## Document Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 27, 2026 | Initial documentation |

---

**End of Technical Documentation**

For questions or clarifications, contact the Transaction Reporting team.
