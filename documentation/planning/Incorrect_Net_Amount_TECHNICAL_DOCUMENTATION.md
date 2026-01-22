# Incorrect Net Amount - Technical Documentation

## Document Overview
**Version:** 1.0  
**Date:** January 22, 2026  
**Purpose:** Comprehensive technical documentation for Python refactoring  
**Incident Code:** 35_3

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Data Model](#data-model)
4. [Validation Logic](#validation-logic)
5. [Database Queries](#database-queries)
6. [Extract Generation](#extract-generation)
7. [Data Push Mechanism](#data-push-mechanism)
8. [Python Refactoring Guidelines](#python-refactoring-guidelines)
9. [Error Handling](#error-handling)
10. [Appendices](#appendices)

---

## Executive Summary

### Purpose
This macro validates the pricing of trades in transaction reports by verifying the mathematical relationship between net amount, consideration amount, and interest amount. The validation ensures that the sum of consideration and interest equals the net amount, identifying discrepancies that indicate data quality issues.

### Key Principle
The core validation formula is:

```
Net Amount = Consideration + Interest
```

Any deviation from this equality indicates an incorrect net amount that requires investigation.

### Validation Logic
1. **Calculate Total:** Total = Consideration + Interest
2. **Calculate Expected Interest:** Expected Interest = Consideration - Net Amount
3. **Calculate Net Difference:** Net Difference = Total - Net Amount
4. **Error Determination:**
   - If Net Difference = 0: No error (output "N")
   - If Net Difference ≠ 0: Error detected (output "TBC" - To Be Confirmed)

### Key Features
- **Simple Arithmetic Validation:** Mathematical verification of pricing components
- **Tolerance Handling:** Uses 0.01 tolerance for floating-point comparison
- **Batch Processing:** Handles multiple transaction records efficiently
- **SQL Extract Generation:** Automated SQL query generation for data extraction
- **Data Push Integration:** Pushes results back to Kaizen templates
- **Clear Output:** Calculated fields for analysis (Total, Expected Interest, Net Difference)

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│              Pricing Data Validation System                  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Data Extraction                                   │  │
│  │     - SQL query generation                            │  │
│  │     - Transaction reference batching                  │  │
│  │     - DB2 database extraction                         │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Data Loading                                      │  │
│  │     - Load transaction references                     │  │
│  │     - Load pricing data (Net, Consideration, Interest)│  │
│  │     - Validate numeric fields                         │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Pricing Validation                                │  │
│  │     - Calculate Total Amount                          │  │
│  │     - Calculate Expected Interest                     │  │
│  │     - Calculate Net Difference                        │  │
│  │     - Determine Error Status                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Output & Reporting                                │  │
│  │     - Write calculated fields                         │  │
│  │     - Set error flags                                 │  │
│  │     - Format numeric outputs                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. Data Push (Optional)                              │  │
│  │     - Match by Transaction Reference                  │  │
│  │     - Update Kaizen template                          │  │
│  │     - Save results                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### External Dependencies

#### Database Connection
- **Database:** DB2 (GLDATA schema)
- **Tables:**
  - `GLDATA/TXNREPESMA` - Main transaction table
  - `GLDATA/CONTCT` - Contract/account details

#### File Paths
- **Extract Generator:** `pricing_data_extract_generator.xlsm`
- **Validation Workbook:** `pricing_data_validation.xlsm`
- **SQL Output:** `Extracts/sql/ExtractN.sql` (where N = batch number)
- **Template Files:** `Templates/pricing_data_validation_template.csv`
- **Kaizen Template Path:** `F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\{FinancialYear}\{Quarter}\Incident Code Analysis\{FY} {Q} - 35_3.xlsx`

---

## Data Model

### PricingRecord Structure

```python
@dataclass
class PricingRecord:
    """
    Core data structure representing a single pricing validation record
    """
    # Primary identifier
    transaction_ref: str              # Transaction Reference (Column 1)
    
    # Input fields (from database)
    net_amount: Decimal              # Net Amount (Column 6)
    consideration: Decimal           # Consideration Amount (Column 7)
    interest: Decimal                # Interest Amount (Column 8)
    
    # Calculated output fields
    total: Decimal                   # Total = Consideration + Interest (Column 9)
    expected_interest: Decimal       # Expected = Consideration - Net (Column 10)
    net_difference: Decimal          # Difference = Total - Net (Column 11)
    
    # Validation result
    error: str                       # Error flag: "N" or "TBC" (Column 2)
    
    # Additional fields (static/optional)
    correction: str                  # Correction field (Column 3)
    correction_field: str            # Correction field name (Column 4)
    comments: str                    # Comments (Column 5)
```

### Column Mapping (11 columns)

| Column | Name | Type | Input/Output | Description |
|--------|------|------|--------------|-------------|
| 1 | Transaction Reference | String | Static | Unique transaction ID |
| 2 | Error | String | Output | "N" or "TBC" based on validation |
| 3 | Correction | String | Static | Correction value (if applicable) |
| 4 | Correction Field | String | Static | Field being corrected |
| 5 | Comments | String | Static | Additional notes |
| 6 | Net Amount | Decimal | Input | Net transaction amount |
| 7 | Consideration | Decimal | Input | Consideration amount |
| 8 | Interest | Decimal | Input | Interest amount |
| 9 | Total | Decimal | Output | Consideration + Interest |
| 10 | Expected Interest | Decimal | Output | Consideration - Net Amount |
| 11 | Net Difference | Decimal | Output | Total - Net Amount |

### Database Schema

#### TXNREPESMA Table (Transaction Reports)
```sql
Column: REPORTREF    Type: VARCHAR    Description: Transaction Reference
Column: NETAMT       Type: DECIMAL    Description: Net Amount
```

#### CONTCT Table (Contract Details)
```sql
Column: FRMCOD       Type: VARCHAR    Description: Firm Code
Column: YEAR         Type: VARCHAR    Description: Year
Column: ACCLTR       Type: VARCHAR    Description: Account Letter
Column: CONTNO       Type: VARCHAR    Description: Contract Number
Column: CLICSD       Type: DECIMAL    Description: Consideration Amount
Column: INTRST       Type: DECIMAL    Description: Interest Amount
```

---

## Validation Logic

### Mathematical Formulas

The validation uses three primary calculations:

#### 1. Total Amount Calculation
```python
total = consideration + interest
```

**Purpose:** Calculate the sum of consideration and interest to compare against net amount.

**Example:**
```
Consideration: 1,000.00
Interest:        150.00
Total:         1,150.00
```

#### 2. Expected Interest Calculation
```python
expected_interest = consideration - net_amount
```

**Purpose:** Calculate what the interest should be based on the difference between consideration and net amount.

**Example:**
```
Consideration: 1,000.00
Net Amount:    1,150.00
Expected Int:   -150.00  (negative indicates net includes interest)
```

#### 3. Net Difference Calculation
```python
net_difference = total - net_amount
```

**Purpose:** Calculate the discrepancy between the calculated total and the reported net amount.

**Example:**
```
Total:         1,150.00
Net Amount:    1,150.00
Difference:        0.00  (no error)
```

### Error Determination Logic

```python
def determine_error_status(net_difference: Decimal, 
                          tolerance: Decimal = Decimal('0.01')) -> str:
    """
    Determine error status based on net difference
    
    Args:
        net_difference: Calculated difference between total and net amount
        tolerance: Acceptable tolerance for floating-point comparison (default 0.01)
    
    Returns:
        "N" if no error (difference within tolerance)
        "TBC" if error detected (difference exceeds tolerance)
    
    Business Rules:
    - Use tolerance to handle floating-point rounding issues
    - Any difference outside tolerance indicates data quality issue
    - "TBC" (To Be Confirmed) flags record for manual review
    """
    if abs(net_difference) <= tolerance:
        return "N"  # No error
    else:
        return "TBC"  # To Be Confirmed - requires investigation
```

### Complete Validation Algorithm

```python
def validate_pricing_record(record: PricingRecord, 
                           tolerance: Decimal = Decimal('0.01')) -> None:
    """
    Complete pricing validation for a single record
    
    Args:
        record: PricingRecord to validate
        tolerance: Tolerance for floating-point comparison
    
    Modifies:
        record.total
        record.expected_interest
        record.net_difference
        record.error
    """
    # Step 1: Calculate Total
    record.total = record.consideration + record.interest
    
    # Step 2: Calculate Expected Interest
    record.expected_interest = record.consideration - record.net_amount
    
    # Step 3: Calculate Net Difference
    record.net_difference = record.total - record.net_amount
    
    # Step 4: Determine Error Status
    record.error = determine_error_status(record.net_difference, tolerance)
```

### VBA Implementation

```vba
Sub PricingDataValidation()
    ' Pricing Data Validation Macro v1.0
    ' Validates pricing using net amount, consideration and interest
    
    Dim ws As Worksheet
    Dim lastRow As Long
    Dim currentRow As Long
    
    ' Column constants
    Const COL_TRANSACTION_REF As Integer = 1
    Const COL_ERROR As Integer = 2
    Const COL_NET_AMOUNT As Integer = 6
    Const COL_CONSIDERATION As Integer = 7
    Const COL_INTEREST As Integer = 8
    Const COL_TOTAL As Integer = 9
    Const COL_EXPECTED_INTEREST As Integer = 10
    Const COL_NET_DIFFERENCE As Integer = 11
    
    Set ws = ActiveSheet
    lastRow = ws.Cells(ws.Rows.Count, COL_NET_AMOUNT).End(xlUp).Row
    
    ' Process each row
    For currentRow = 2 To lastRow
        
        ' Validate numeric inputs
        If IsNumeric(ws.Cells(currentRow, COL_NET_AMOUNT).Value) And _
           IsNumeric(ws.Cells(currentRow, COL_CONSIDERATION).Value) And _
           IsNumeric(ws.Cells(currentRow, COL_INTEREST).Value) Then
            
            ' Get input values
            Dim netAmount As Double
            Dim consideration As Double
            Dim interest As Double
            
            netAmount = ws.Cells(currentRow, COL_NET_AMOUNT).Value
            consideration = ws.Cells(currentRow, COL_CONSIDERATION).Value
            interest = ws.Cells(currentRow, COL_INTEREST).Value
            
            ' Calculate outputs
            Dim total As Double
            Dim expectedInterest As Double
            Dim netDifference As Double
            
            total = consideration + interest
            expectedInterest = consideration - netAmount
            netDifference = total - netAmount
            
            ' Write calculated values
            ws.Cells(currentRow, COL_TOTAL).Value = total
            ws.Cells(currentRow, COL_EXPECTED_INTEREST).Value = expectedInterest
            ws.Cells(currentRow, COL_NET_DIFFERENCE).Value = netDifference
            
            ' Determine error status (0.01 tolerance)
            If Abs(netDifference) > 0.01 Then
                ws.Cells(currentRow, COL_ERROR).Value = "TBC"
            Else
                ws.Cells(currentRow, COL_ERROR).Value = "N"
            End If
            
        End If
        
    Next currentRow
    
    ' Format calculated columns
    ws.Range(ws.Cells(2, COL_TOTAL), ws.Cells(lastRow, COL_TOTAL)).NumberFormat = "0.00"
    ws.Range(ws.Cells(2, COL_EXPECTED_INTEREST), ws.Cells(lastRow, COL_EXPECTED_INTEREST)).NumberFormat = "0.00"
    ws.Range(ws.Cells(2, COL_NET_DIFFERENCE), ws.Cells(lastRow, COL_NET_DIFFERENCE)).NumberFormat = "0.00"
    
    MsgBox "Pricing data validation completed successfully!" & vbCrLf & _
           "Processed " & (lastRow - 1) & " rows of data.", vbInformation
    
End Sub
```

### Validation Examples

#### Example 1: No Error (Perfect Match)
```
Input:
  Transaction Reference: 44625CKT72V1
  Net Amount:           1,150.00
  Consideration:        1,000.00
  Interest:               150.00

Calculations:
  Total = 1,000.00 + 150.00 = 1,150.00
  Expected Interest = 1,000.00 - 1,150.00 = -150.00
  Net Difference = 1,150.00 - 1,150.00 = 0.00

Result:
  Error: "N" (No error)
```

#### Example 2: Error Detected (Discrepancy)
```
Input:
  Transaction Reference: 44625CKVNVJ1
  Net Amount:           1,150.00
  Consideration:        1,000.00
  Interest:               145.00  (Incorrect!)

Calculations:
  Total = 1,000.00 + 145.00 = 1,145.00
  Expected Interest = 1,000.00 - 1,150.00 = -150.00
  Net Difference = 1,145.00 - 1,150.00 = -5.00

Result:
  Error: "TBC" (To Be Confirmed - discrepancy of -5.00)
```

#### Example 3: Rounding Tolerance
```
Input:
  Transaction Reference: 44625CKXGQR1
  Net Amount:           1,150.00
  Consideration:        1,000.00
  Interest:               150.005  (Rounding difference)

Calculations:
  Total = 1,000.00 + 150.005 = 1,150.005
  Expected Interest = 1,000.00 - 1,150.00 = -150.00
  Net Difference = 1,150.005 - 1,150.00 = 0.005

Result:
  Error: "N" (Within 0.01 tolerance)
```

---

## Database Queries

### SQL Extract Query

The data is extracted from DB2 database using a simple join query:

```sql
SELECT
    t1.REPORTREF,       -- Transaction Reference
    t1.NETAMT,          -- Net Amount
    t2.CLICSD,          -- Consideration Amount
    t2.INTRST           -- Interest Amount
FROM
    GLDATA/TXNREPESMA t1
JOIN 
    GLDATA/CONTCT t2 
    ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
WHERE
    t1.REPORTREF IN (
        '44625CKTPC31',
        '44625CKT72V1',
        '44625CKVNVJ1',
        -- ... (more transaction references)
    )
```

### Query Components

#### 1. Table Joins

**Primary Table:** `GLDATA/TXNREPESMA` (Transaction Reports)
- Contains: Transaction reference, net amount

**Secondary Table:** `GLDATA/CONTCT` (Contract Details)
- Contains: Consideration amount, interest amount

**Join Logic:**
```sql
t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
```

This concatenates contract components to form the transaction reference:
- FRMCOD: Firm code (e.g., "44625")
- YEAR: Year code (e.g., "CK")
- ACCLTR: Account letter (e.g., "T")
- CONTNO: Contract number (e.g., "PC3")
- Suffix: Always "1"

Example: `44625` + `CK` + `T` + `PC3` + `1` = `44625CKTPC31`

#### 2. Field Descriptions

| Field | Source | Description | Data Type | Example |
|-------|--------|-------------|-----------|---------|
| REPORTREF | t1.REPORTREF | Transaction Reference | VARCHAR(12) | 44625CKTPC31 |
| NETAMT | t1.NETAMT | Net Amount | DECIMAL(15,2) | 1150.00 |
| CLICSD | t2.CLICSD | Consideration | DECIMAL(15,2) | 1000.00 |
| INTRST | t2.INTRST | Interest | DECIMAL(15,2) | 150.00 |

#### 3. IN Clause Batching

Transaction references are batched in groups of up to 900 to avoid SQL query size limits:

```sql
-- Extract 1 (up to 900 transactions)
WHERE t1.REPORTREF IN ('44625CKTPC31', '44625CKT72V1', ...)

-- Extract 2 (next 900 transactions)
WHERE t1.REPORTREF IN ('44625XXXXXX1', '44625YYYYYY1', ...)
```

### Python Query Generation

```python
def generate_sql_query(transaction_refs: List[str]) -> str:
    """
    Generate SQL query for pricing data extraction
    
    Args:
        transaction_refs: List of transaction references to extract
    
    Returns:
        Complete SQL query string
    """
    # Format transaction references for IN clause
    formatted_refs = ",\n".join([f"'{ref}'" for ref in transaction_refs])
    
    query = f"""SELECT
    t1.REPORTREF,
    t1.NETAMT,
    t2.CLICSD,
    t2.INTRST
FROM
    GLDATA/TXNREPESMA t1
JOIN GLDATA/CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
WHERE
    t1.REPORTREF IN (
{formatted_refs}
    )"""
    
    return query

def batch_transaction_refs(all_refs: List[str], 
                          batch_size: int = 900) -> List[List[str]]:
    """
    Batch transaction references to avoid SQL query size limits
    
    Args:
        all_refs: Complete list of transaction references
        batch_size: Maximum number of refs per batch (default 900)
    
    Returns:
        List of batches, each containing up to batch_size references
    """
    batches = []
    for i in range(0, len(all_refs), batch_size):
        batch = all_refs[i:i + batch_size]
        batches.append(batch)
    return batches

# Usage example
transaction_refs = load_transaction_refs_from_excel()
batches = batch_transaction_refs(transaction_refs, batch_size=900)

for batch_num, batch in enumerate(batches, start=1):
    sql_query = generate_sql_query(batch)
    output_file = f"Extract{batch_num}.sql"
    write_sql_to_file(sql_query, output_file)
```

---

## Extract Generation

### Extract Generator Workflow

The extract generator automates the creation of SQL files for batch data extraction:

```
┌─────────────────────────────────────────────────────────┐
│              Extract Generation Process                  │
│                                                           │
│  1. Load Transaction References                          │
│     ↓                                                     │
│  2. Assign Extract Numbers (batch of 900)                │
│     ↓                                                     │
│  3. Generate SQL Query per Batch                         │
│     ↓                                                     │
│  4. Write SQL Files (ExtractN.sql)                       │
└─────────────────────────────────────────────────────────┘
```

### VBA Extract Generator

```vba
Sub extract_buyer_id()
    ' Extract Generator for Pricing Data v1.0
    ' Generates SQL files with batched transaction references
    
    Dim ws As Worksheet
    Dim outputPath As String
    Dim lRow As Long
    Dim extractNumber As Long
    Dim transactionCount As Long
    Dim previousExtract As String
    Dim sqlBody As String
    
    Set ws = ThisWorkbook.Sheets("Extract Generator")
    outputPath = "F:\Transaction Reporting\Kaizen Reporting\Accuracy Testing\" & _
                 "Automated Accuracy Testing\Incorrect Net Amount - 35_3\Extracts\SQL\"
    
    ' ===================================================
    ' STEP 1: Assign Extract Numbers
    ' ===================================================
    lRow = 2
    extractNumber = 1
    transactionCount = 0
    
    Do While ws.Cells(lRow, 1).Value <> ""
        Dim transactionRef As String
        transactionRef = Trim(ws.Cells(lRow, 1).Value)
        
        If transactionRef <> "" Then
            ' Check if we need to start a new batch
            If transactionCount = 900 Then
                extractNumber = extractNumber + 1
                transactionCount = 0
            End If
            
            transactionCount = transactionCount + 1
            ws.Cells(lRow, 2).Value = extractNumber
        End If
        
        lRow = lRow + 1
    Loop
    
    ' ===================================================
    ' STEP 2: Generate SQL Files
    ' ===================================================
    
    ' SQL Template
    Dim sqlTemplate As String
    sqlTemplate = "SELECT" & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.REPORTREF," & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.NETAMT," & vbCrLf
    sqlTemplate = sqlTemplate & "    t2.CLICSD," & vbCrLf
    sqlTemplate = sqlTemplate & "    t2.INTRST" & vbCrLf
    sqlTemplate = sqlTemplate & "FROM" & vbCrLf
    sqlTemplate = sqlTemplate & "    GLDATA/TXNREPESMA t1" & vbCrLf
    sqlTemplate = sqlTemplate & "JOIN GLDATA/CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF" & vbCrLf
    sqlTemplate = sqlTemplate & "WHERE" & vbCrLf
    sqlTemplate = sqlTemplate & "    t1.REPORTREF IN (" & vbCrLf
    sqlTemplate = sqlTemplate & "--<<TRANSACTION REFERENCES>>" & vbCrLf
    sqlTemplate = sqlTemplate & "    )"
    
    ' Process rows and create SQL files
    lRow = 2
    previousExtract = ""
    sqlBody = ""
    
    Do While ws.Cells(lRow, 1).Value <> "" Or ws.Cells(lRow, 2).Value <> ""
        transactionRef = Trim(ws.Cells(lRow, 1).Value)
        Dim currentExtract As String
        currentExtract = Trim(ws.Cells(lRow, 2).Value)
        
        If transactionRef = "" Or currentExtract = "" Then
            lRow = lRow + 1
            GoTo ContinueLoop
        End If
        
        ' Check if we need to write the previous extract
        If currentExtract <> previousExtract And previousExtract <> "" Then
            WriteSQLToFile outputPath, previousExtract, sqlTemplate, sqlBody
            sqlBody = ""
        End If
        
        ' Build SQL body
        If sqlBody = "" Then
            sqlBody = "'" & transactionRef & "'"
        Else
            sqlBody = sqlBody & "," & vbCrLf & "'" & transactionRef & "'"
        End If
        
        previousExtract = currentExtract
        
ContinueLoop:
        lRow = lRow + 1
    Loop
    
    ' Write final extract
    If sqlBody <> "" Then
        WriteSQLToFile outputPath, previousExtract, sqlTemplate, sqlBody
    End If
    
    MsgBox "Extract numbers assigned and SQL files created successfully.", vbInformation
End Sub

Private Sub WriteSQLToFile(strFilePath As String, fileName As String, template As String, refs As String)
    ' Write SQL query to file
    Dim fullPath As String
    Dim iFileNum As Integer
    Dim finalSQL As String
    
    finalSQL = Replace(template, "--<<TRANSACTION REFERENCES>>", refs)
    fullPath = strFilePath & "Extract" & fileName & ".sql"
    
    iFileNum = FreeFile
    Open fullPath For Output As iFileNum
    Print #iFileNum, finalSQL;
    Close iFileNum
End Sub
```

### Python Extract Generator

```python
from pathlib import Path
from typing import List
import pandas as pd

class ExtractGenerator:
    """Generate SQL extract files for pricing data"""
    
    def __init__(self, output_dir: Path, batch_size: int = 900):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.sql_template = """SELECT
    t1.REPORTREF,
    t1.NETAMT,
    t2.CLICSD,
    t2.INTRST
FROM
    GLDATA/TXNREPESMA t1
JOIN GLDATA/CONTCT t2 ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
WHERE
    t1.REPORTREF IN (
{transaction_refs}
    )"""
    
    def load_transaction_refs(self, excel_path: Path, 
                             sheet_name: str = "Extract Generator") -> List[str]:
        """Load transaction references from Excel"""
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        refs = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
        return [ref for ref in refs if ref]
    
    def assign_extract_numbers(self, refs: List[str]) -> List[tuple]:
        """Assign extract batch numbers to transaction references"""
        extract_data = []
        extract_number = 1
        
        for i, ref in enumerate(refs):
            if i > 0 and i % self.batch_size == 0:
                extract_number += 1
            extract_data.append((ref, extract_number))
        
        return extract_data
    
    def generate_extracts(self, excel_path: Path) -> None:
        """Main function to generate all SQL extract files"""
        # Load transaction references
        refs = self.load_transaction_refs(excel_path)
        print(f"Loaded {len(refs)} transaction references")
        
        # Assign extract numbers
        extract_data = self.assign_extract_numbers(refs)
        
        # Group by extract number
        from itertools import groupby
        extract_groups = {}
        for ref, extract_num in extract_data:
            if extract_num not in extract_groups:
                extract_groups[extract_num] = []
            extract_groups[extract_num].append(ref)
        
        # Generate SQL files
        for extract_num, batch_refs in extract_groups.items():
            self.write_sql_file(extract_num, batch_refs)
        
        print(f"Generated {len(extract_groups)} SQL extract files")
    
    def write_sql_file(self, extract_num: int, refs: List[str]) -> None:
        """Write SQL query to file"""
        # Format transaction references
        formatted_refs = ",\n".join([f"'{ref}'" for ref in refs])
        
        # Build complete SQL
        sql = self.sql_template.format(transaction_refs=formatted_refs)
        
        # Write to file
        output_file = self.output_dir / f"Extract{extract_num}.sql"
        output_file.write_text(sql, encoding='utf-8')
        print(f"Created {output_file.name} with {len(refs)} references")

# Usage
generator = ExtractGenerator(
    output_dir=Path("Extracts/sql"),
    batch_size=900
)
generator.generate_extracts(Path("pricing_data_extract_generator.xlsm"))
```

---

## Data Push Mechanism

### Purpose
The Data Push mechanism updates Kaizen template files with validation results without requiring macro-enabled workbooks.

### Process Flow

```
┌─────────────────────────────────────────────────────────┐
│                  Data Push Workflow                      │
│                                                           │
│  1. Open Source Workbook (Validation Results)            │
│     ↓                                                     │
│  2. Open Target Workbook (Kaizen Template)               │
│     ↓                                                     │
│  3. Match Records by Transaction Reference               │
│     ↓                                                     │
│  4. Push Validation Results to Target                    │
│     ↓                                                     │
│  5. Save Target Workbook                                 │
└─────────────────────────────────────────────────────────┘
```

### Column Mapping

**Source Columns (Validation Workbook):**
- Column 2: Error
- Column 6: Net Amount
- Column 25: (Additional field - TBD)
- Columns 21-24: (Additional fields - TBD)

**Target Columns (Kaizen Template):**
- Column 3: Error (from source column 2)
- Column 4: Net Amount (from source column 6)
- Columns 5-9: Additional fields (from source columns 25, 21-24)

### VBA Data Push Implementation

```vba
Private Const SOURCE_DATA_COLS As String = "2,6,25,21,22,23,24"
Private Const TARGET_UPDATE_COLS As String = "3,4,5,6,7,8,9"

Private Function ProcessDataPush(sourceWs As Worksheet, targetWs As Worksheet) As Long
    ' Push validation results from source to target workbook
    
    Dim lastRow As Long
    lastRow = sourceWs.Cells(sourceWs.Rows.Count, 1).End(xlUp).Row
    
    Dim sourceColumns As Variant
    Dim targetColumns As Variant
    sourceColumns = Split(SOURCE_DATA_COLS, ",")
    targetColumns = Split(TARGET_UPDATE_COLS, ",")
    
    Dim updateCount As Long
    updateCount = 0
    
    Dim i As Long
    For i = 2 To lastRow
        Dim transactionRef As String
        transactionRef = Trim(CStr(sourceWs.Cells(i, 1).Value))
        
        If transactionRef <> "" Then
            If ProcessSingleDataPush(sourceWs, targetWs, i, transactionRef, sourceColumns, targetColumns) Then
                updateCount = updateCount + 1
            End If
        End If
        
        If i Mod 50 = 0 Then
            Application.StatusBar = "Processing record " & (i - 1) & " of " & (lastRow - 1)
        End If
    Next i
    
    Application.StatusBar = False
    ProcessDataPush = updateCount
End Function

Private Function FindTransactionRow(targetWs As Worksheet, transactionRef As String) As Long
    ' Find row in target worksheet by transaction reference
    On Error Resume Next
    
    Dim lastRow As Long
    lastRow = targetWs.Cells(targetWs.Rows.Count, 1).End(xlUp).Row
    
    Dim result As Variant
    result = Application.Match(transactionRef, targetWs.Range("A2:A" & lastRow), 0)
    
    If IsError(result) Then
        FindTransactionRow = 0
    Else
        FindTransactionRow = result + 1  ' +1 because Match is relative to A2
    End If
End Function
```

### Python Data Push Implementation

```python
from pathlib import Path
from typing import List, Dict
import pandas as pd
from openpyxl import load_workbook

class DataPusher:
    """Push validation results to Kaizen template"""
    
    def __init__(self, 
                 source_columns: List[int] = [2, 6, 25, 21, 22, 23, 24],
                 target_columns: List[int] = [3, 4, 5, 6, 7, 8, 9]):
        """
        Initialize data pusher
        
        Args:
            source_columns: Column indices in source workbook (1-based)
            target_columns: Column indices in target workbook (1-based)
        """
        self.source_columns = source_columns
        self.target_columns = target_columns
    
    def push_data(self, 
                  source_path: Path, 
                  target_path: Path,
                  source_sheet: str = "Client Data - 35_3",
                  target_sheet: str = "Template") -> int:
        """
        Push validation results from source to target
        
        Args:
            source_path: Path to validation results workbook
            target_path: Path to Kaizen template workbook
            source_sheet: Sheet name in source workbook
            target_sheet: Sheet name in target workbook
        
        Returns:
            Number of records updated
        """
        # Load source data
        source_df = pd.read_excel(
            source_path,
            sheet_name=source_sheet,
            header=0
        )
        
        # Load target workbook (use openpyxl to preserve formatting)
        target_wb = load_workbook(target_path)
        target_ws = target_wb[target_sheet]
        
        # Create transaction reference lookup
        target_refs = {}
        for row_idx in range(2, target_ws.max_row + 1):
            trans_ref = target_ws.cell(row_idx, 1).value
            if trans_ref:
                target_refs[str(trans_ref).strip()] = row_idx
        
        # Process each source row
        update_count = 0
        
        for source_idx, source_row in source_df.iterrows():
            trans_ref = str(source_row.iloc[0]).strip()
            
            if trans_ref in target_refs:
                target_row_idx = target_refs[trans_ref]
                
                # Copy data from source columns to target columns
                for src_col, tgt_col in zip(self.source_columns, self.target_columns):
                    value = source_row.iloc[src_col - 1]  # Convert to 0-based
                    target_ws.cell(target_row_idx, tgt_col, value)
                
                update_count += 1
            
            # Progress update
            if (source_idx + 1) % 50 == 0:
                print(f"Processing record {source_idx + 1} of {len(source_df)}")
        
        # Save target workbook
        target_wb.save(target_path)
        print(f"Updated {update_count} records in target workbook")
        
        return update_count

# Usage
pusher = DataPusher()
updated = pusher.push_data(
    source_path=Path("pricing_data_validation.xlsm"),
    target_path=Path("FY25/Q3/Incident Code Analysis/FY25 Q3 - 35_3.xlsx")
)
print(f"Successfully updated {updated} records")
```

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
│   │   └── pricing_record.py        # PricingRecord dataclass
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py                # Data loading from Excel/CSV
│   │   ├── database.py              # Database connection and queries
│   │   └── sql_generator.py         # SQL query generation
│   ├── validation/
│   │   ├── __init__.py
│   │   └── pricing_validator.py    # Pricing validation logic
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── extract_generator.py    # Extract file generation
│   │   ├── batch_processor.py      # Batch processing
│   │   └── data_pusher.py          # Data push to templates
│   ├── output/
│   │   ├── __init__.py
│   │   └── writer.py               # Write results to Excel
│   └── utils/
│       ├── __init__.py
│       ├── decimal_utils.py        # Decimal arithmetic utilities
│       └── error_handler.py        # Error handling
├── tests/
│   ├── __init__.py
│   ├── test_validation.py
│   ├── test_sql_generation.py
│   └── test_integration.py
├── config/
│   └── paths.yaml                  # File paths configuration
├── requirements.txt
└── README.md
```

### Key Python Libraries

```python
# requirements.txt
pandas>=2.0.0          # Data manipulation
openpyxl>=3.1.0        # Excel file handling
pyyaml>=6.0            # Configuration files
pyodbc>=4.0.0          # Database connectivity (for DB2)
pytest>=7.0.0          # Testing
pytest-cov>=4.0.0      # Test coverage
black>=23.0.0          # Code formatting
flake8>=6.0.0          # Linting
mypy>=1.0.0            # Type checking
```

### Core Implementation

#### 1. PricingRecord Model

```python
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

@dataclass
class PricingRecord:
    """Pricing validation record"""
    
    # Input fields
    transaction_ref: str
    net_amount: Decimal
    consideration: Decimal
    interest: Decimal
    
    # Output fields (calculated)
    total: Decimal = field(default=Decimal('0'))
    expected_interest: Decimal = field(default=Decimal('0'))
    net_difference: Decimal = field(default=Decimal('0'))
    error: str = field(default="N")
    
    # Optional fields
    correction: Optional[str] = None
    correction_field: Optional[str] = None
    comments: Optional[str] = None
    
    def calculate_fields(self, tolerance: Decimal = Decimal('0.01')) -> None:
        """Calculate all derived fields and set error status"""
        self.total = self.consideration + self.interest
        self.expected_interest = self.consideration - self.net_amount
        self.net_difference = self.total - self.net_amount
        
        # Determine error status
        if abs(self.net_difference) <= tolerance:
            self.error = "N"
        else:
            self.error = "TBC"
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PricingRecord':
        """Create PricingRecord from dictionary"""
        return cls(
            transaction_ref=str(data.get('REPORTREF', '')),
            net_amount=Decimal(str(data.get('NETAMT', 0))),
            consideration=Decimal(str(data.get('CLICSD', 0))),
            interest=Decimal(str(data.get('INTRST', 0)))
        )
```

#### 2. Pricing Validator

```python
from typing import List
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class PricingValidator:
    """Validate pricing data for transactions"""
    
    def __init__(self, tolerance: Decimal = Decimal('0.01')):
        """
        Initialize validator
        
        Args:
            tolerance: Tolerance for floating-point comparison
        """
        self.tolerance = tolerance
    
    def validate_record(self, record: PricingRecord) -> None:
        """
        Validate a single pricing record
        
        Args:
            record: PricingRecord to validate
        
        Modifies:
            record.total, record.expected_interest, record.net_difference, record.error
        """
        try:
            record.calculate_fields(self.tolerance)
            
            if record.error == "TBC":
                logger.warning(
                    f"Pricing discrepancy for {record.transaction_ref}: "
                    f"Net Difference = {record.net_difference}"
                )
        except Exception as e:
            logger.error(f"Error validating record {record.transaction_ref}: {e}")
            record.error = "ERROR"
    
    def validate_batch(self, records: List[PricingRecord]) -> Dict[str, int]:
        """
        Validate a batch of pricing records
        
        Args:
            records: List of PricingRecords to validate
        
        Returns:
            Dictionary with validation statistics
        """
        stats = {
            'total': len(records),
            'valid': 0,
            'invalid': 0,
            'errors': 0
        }
        
        for record in records:
            self.validate_record(record)
            
            if record.error == "N":
                stats['valid'] += 1
            elif record.error == "TBC":
                stats['invalid'] += 1
            else:
                stats['errors'] += 1
        
        return stats
```

#### 3. Database Connection

```python
import pyodbc
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class DB2Connection:
    """Handle DB2 database connections"""
    
    def __init__(self, dsn: str, username: str, password: str):
        self.dsn = dsn
        self.username = username
        self.password = password
        self.connection = None
    
    def connect(self) -> None:
        """Establish database connection"""
        try:
            connection_string = (
                f"DSN={self.dsn};"
                f"UID={self.username};"
                f"PWD={self.password};"
            )
            self.connection = pyodbc.connect(connection_string)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def execute_query(self, sql: str) -> List[Dict]:
        """
        Execute SQL query and return results
        
        Args:
            sql: SQL query string
        
        Returns:
            List of dictionaries, one per row
        """
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        
        try:
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            logger.info(f"Query returned {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            cursor.close()
    
    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
```

#### 4. Main Processing Pipeline

```python
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)

class PricingValidationPipeline:
    """Complete pricing validation pipeline"""
    
    def __init__(self, 
                 db_connection: DB2Connection,
                 validator: PricingValidator):
        self.db = db_connection
        self.validator = validator
    
    def load_data_from_database(self, sql_file: Path) -> List[PricingRecord]:
        """Load pricing data from database using SQL file"""
        # Read SQL query
        sql = sql_file.read_text()
        
        # Execute query
        results = self.db.execute_query(sql)
        
        # Convert to PricingRecords
        records = [PricingRecord.from_dict(row) for row in results]
        
        logger.info(f"Loaded {len(records)} records from database")
        return records
    
    def process_extract(self, extract_file: Path) -> List[PricingRecord]:
        """Process a single extract file"""
        logger.info(f"Processing {extract_file.name}")
        
        # Load data
        records = self.load_data_from_database(extract_file)
        
        # Validate
        stats = self.validator.validate_batch(records)
        
        logger.info(
            f"Validation complete: {stats['valid']} valid, "
            f"{stats['invalid']} invalid, {stats['errors']} errors"
        )
        
        return records
    
    def process_all_extracts(self, extract_dir: Path) -> List[PricingRecord]:
        """Process all extract files in directory"""
        all_records = []
        
        extract_files = sorted(extract_dir.glob("Extract*.sql"))
        logger.info(f"Found {len(extract_files)} extract files")
        
        for extract_file in extract_files:
            records = self.process_extract(extract_file)
            all_records.extend(records)
        
        return all_records
    
    def write_results(self, records: List[PricingRecord], output_file: Path) -> None:
        """Write validation results to Excel"""
        import pandas as pd
        
        # Convert to DataFrame
        data = {
            'Transaction Reference': [r.transaction_ref for r in records],
            'Error': [r.error for r in records],
            'Correction': [r.correction or '' for r in records],
            'Correction Field': [r.correction_field or '' for r in records],
            'Comments': [r.comments or '' for r in records],
            'Net Amount': [float(r.net_amount) for r in records],
            'Consideration': [float(r.consideration) for r in records],
            'Interest': [float(r.interest) for r in records],
            'Total': [float(r.total) for r in records],
            'Expected Interest': [float(r.expected_interest) for r in records],
            'Net Difference': [float(r.net_difference) for r in records]
        }
        
        df = pd.DataFrame(data)
        
        # Write to Excel
        df.to_excel(output_file, index=False, sheet_name='Validation Results')
        
        logger.info(f"Results written to {output_file}")

# Usage
def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize components
    db = DB2Connection(
        dsn="YOUR_DSN",
        username="YOUR_USERNAME",
        password="YOUR_PASSWORD"
    )
    
    validator = PricingValidator(tolerance=Decimal('0.01'))
    
    pipeline = PricingValidationPipeline(db, validator)
    
    # Process all extracts
    extract_dir = Path("Extracts/sql")
    records = pipeline.process_all_extracts(extract_dir)
    
    # Write results
    output_file = Path("Outputs/pricing_validation_results.xlsx")
    pipeline.write_results(records, output_file)
    
    # Close database
    db.close()
    
    logger.info("Pipeline complete")

if __name__ == "__main__":
    main()
```

### Testing Strategy

```python
import pytest
from decimal import Decimal
from src.models.pricing_record import PricingRecord
from src.validation.pricing_validator import PricingValidator

class TestPricingValidation:
    """Test pricing validation logic"""
    
    def test_no_error_perfect_match(self):
        """Test case where pricing is perfect"""
        record = PricingRecord(
            transaction_ref="TEST001",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.00')
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('1150.00')
        assert record.expected_interest == Decimal('-150.00')
        assert record.net_difference == Decimal('0.00')
        assert record.error == "N"
    
    def test_error_detected(self):
        """Test case where pricing has discrepancy"""
        record = PricingRecord(
            transaction_ref="TEST002",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('145.00')  # Wrong!
        )
        
        record.calculate_fields()
        
        assert record.total == Decimal('1145.00')
        assert record.net_difference == Decimal('-5.00')
        assert record.error == "TBC"
    
    def test_tolerance_handling(self):
        """Test tolerance for floating-point rounding"""
        record = PricingRecord(
            transaction_ref="TEST003",
            net_amount=Decimal('1150.00'),
            consideration=Decimal('1000.00'),
            interest=Decimal('150.005')  # Rounding difference
        )
        
        record.calculate_fields(tolerance=Decimal('0.01'))
        
        assert record.net_difference == Decimal('0.005')
        assert record.error == "N"  # Within tolerance
    
    def test_batch_validation(self):
        """Test batch validation statistics"""
        records = [
            PricingRecord("TEST001", Decimal('1150'), Decimal('1000'), Decimal('150')),
            PricingRecord("TEST002", Decimal('1150'), Decimal('1000'), Decimal('145')),
            PricingRecord("TEST003", Decimal('2000'), Decimal('1800'), Decimal('200'))
        ]
        
        validator = PricingValidator()
        stats = validator.validate_batch(records)
        
        assert stats['total'] == 3
        assert stats['valid'] == 2
        assert stats['invalid'] == 1
```

---

## Error Handling

### Error Categories

1. **Data Loading Errors**
   - Missing transaction references
   - Invalid numeric values
   - Database connection failures

2. **Validation Errors**
   - Null or empty values
   - Non-numeric data
   - Calculation overflow

3. **File I/O Errors**
   - Missing files
   - Permission issues
   - Corrupted Excel files

### Error Handling Strategy

```python
class PricingValidationError(Exception):
    """Base exception for pricing validation"""
    pass

class DataLoadingError(PricingValidationError):
    """Error loading data"""
    pass

class ValidationError(PricingValidationError):
    """Error during validation"""
    pass

def safe_validate_record(record: PricingRecord, 
                        validator: PricingValidator) -> None:
    """Validate record with error handling"""
    try:
        validator.validate_record(record)
    except Exception as e:
        logger.error(f"Validation failed for {record.transaction_ref}: {e}")
        record.error = "ERROR"
        record.comments = f"Validation Error: {str(e)}"

def main_with_error_handling():
    """Main function with comprehensive error handling"""
    try:
        # Initialize
        db = DB2Connection(dsn, username, password)
        validator = PricingValidator()
        pipeline = PricingValidationPipeline(db, validator)
        
        # Process
        try:
            records = pipeline.process_all_extracts(extract_dir)
        except DataLoadingError as e:
            logger.error(f"Failed to load data: {e}")
            return
        
        # Write results
        try:
            pipeline.write_results(records, output_file)
        except Exception as e:
            logger.error(f"Failed to write results: {e}")
            # Try backup location
            backup_file = Path(f"backup_results_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
            pipeline.write_results(records, backup_file)
            logger.info(f"Results saved to backup: {backup_file}")
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        raise
    finally:
        if db:
            db.close()
```

---

## Appendices

### Appendix A: Complete Column Reference

| Column | Name | Type | Direction | Description | Example |
|--------|------|------|-----------|-------------|---------|
| 1 | Transaction Reference | String | Static | Unique transaction ID | 44625CKTPC31 |
| 2 | Error | String | Output | Error flag (N/TBC) | N |
| 3 | Correction | String | Static | Correction value | |
| 4 | Correction Field | String | Static | Field being corrected | |
| 5 | Comments | String | Static | Additional notes | |
| 6 | Net Amount | Decimal(15,2) | Input | Net transaction amount | 1150.00 |
| 7 | Consideration | Decimal(15,2) | Input | Consideration amount | 1000.00 |
| 8 | Interest | Decimal(15,2) | Input | Interest amount | 150.00 |
| 9 | Total | Decimal(15,2) | Output | Sum of consideration + interest | 1150.00 |
| 10 | Expected Interest | Decimal(15,2) | Output | Consideration - Net Amount | -150.00 |
| 11 | Net Difference | Decimal(15,2) | Output | Total - Net Amount | 0.00 |

### Appendix B: Database Tables

#### GLDATA/TXNREPESMA
Main transaction reporting table containing net amounts and transaction references.

| Column | Type | Description |
|--------|------|-------------|
| REPORTREF | VARCHAR(12) | Transaction Reference |
| NETAMT | DECIMAL(15,2) | Net Amount |
| TRDDATTIM | TIMESTAMP | Trade Date/Time |
| ... | ... | (Other fields) |

#### GLDATA/CONTCT
Contract details table containing consideration and interest amounts.

| Column | Type | Description |
|--------|------|-------------|
| FRMCOD | VARCHAR(5) | Firm Code |
| YEAR | VARCHAR(2) | Year Code |
| ACCLTR | VARCHAR(1) | Account Letter |
| CONTNO | VARCHAR(4) | Contract Number |
| CLICSD | DECIMAL(15,2) | Consideration Amount |
| INTRST | DECIMAL(15,2) | Interest Amount |
| ... | ... | (Other fields) |

### Appendix C: Error Flag Definitions

| Flag | Meaning | Action |
|------|---------|--------|
| N | No Error | Net Amount matches Total (within tolerance) |
| TBC | To Be Confirmed | Discrepancy detected, requires investigation |
| ERROR | Processing Error | Validation failed due to technical issue |

### Appendix D: Calculation Examples

#### Example 1: Buy Transaction
```
Input:
  Consideration: 10,000.00 (cost of securities)
  Interest:         250.00 (accrued interest)
  Net Amount:    10,250.00 (total payment)

Calculations:
  Total = 10,000.00 + 250.00 = 10,250.00
  Expected Interest = 10,000.00 - 10,250.00 = -250.00
  Net Difference = 10,250.00 - 10,250.00 = 0.00

Result: No Error (N)
```

#### Example 2: Sell Transaction
```
Input:
  Consideration: 15,000.00 (proceeds from sale)
  Interest:        -300.00 (accrued interest paid)
  Net Amount:    14,700.00 (net proceeds)

Calculations:
  Total = 15,000.00 + (-300.00) = 14,700.00
  Expected Interest = 15,000.00 - 14,700.00 = 300.00
  Net Difference = 14,700.00 - 14,700.00 = 0.00

Result: No Error (N)
```

#### Example 3: Error Case
```
Input:
  Consideration: 8,500.00
  Interest:        200.00 (should be 180.00)
  Net Amount:    8,680.00

Calculations:
  Total = 8,500.00 + 200.00 = 8,700.00
  Expected Interest = 8,500.00 - 8,680.00 = -180.00
  Net Difference = 8,700.00 - 8,680.00 = 20.00

Result: Error (TBC) - Discrepancy of 20.00
```

### Appendix E: Glossary

| Term | Definition |
|------|------------|
| **Net Amount** | Total amount paid/received in transaction including all costs |
| **Consideration** | Base price of securities traded |
| **Interest** | Accrued interest component (positive for buy, negative for sell) |
| **Total** | Calculated sum of consideration and interest |
| **Expected Interest** | What interest should be based on net vs consideration |
| **Net Difference** | Discrepancy between calculated total and reported net |
| **TBC** | To Be Confirmed - flag indicating discrepancy requiring review |
| **Transaction Reference** | Unique 12-character identifier for each transaction |
| **Extract** | Batch of up to 900 transaction references for SQL query |
| **Tolerance** | Acceptable rounding difference (0.01) for floating-point comparison |

---

## Document Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 22, 2026 | Initial documentation creation |

---

**End of Technical Documentation**

For questions or clarifications, contact the Transaction Reporting team.
