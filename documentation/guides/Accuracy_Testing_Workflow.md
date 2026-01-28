# Accuracy Testing Workflow Guide

## Overview

This guide documents the complete workflow for accuracy testing of transaction
reporting data using the template-based approach. The workflow automates the
creation of validation templates, SQL extraction, and data validation.

## Workflow Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                     ACCURACY TESTING WORKFLOW                    │
└─────────────────────────────────────────────────────────────────┘

1. CONSOLIDATED DATA INPUT
   ├── Consolidated Errors CSV (from regulatory reporting system)
   └── Consolidated Queries CSV (from regulatory reporting system)
                            ↓
2. TEMPLATE GENERATION
   ├── Tool: generate-accuracy-template
   ├── Splits pipe-delimited incident codes (e.g., "7_37|16_21")
   ├── Applies template format (buyer/seller/pricing/default)
   └── Creates one template CSV per incident code
                            ↓
3. TEMPLATE FILES (Generated)
   ├── template_7_37.csv (buyer validation format)
   ├── template_16_21.csv (seller validation format)
   ├── template_35_3.csv (pricing validation format)
   └── template_*.csv (default format for other incidents)
   
   Structure: [Validation Columns | Comparison Columns | Consolidated Data]
                            ↓
4. SQL EXTRACT GENERATION
   ├── Tool: generate-sql-extract
   ├── Reads transaction references from template files
   ├── Batches references (default 900 per file)
   └── Generates SQL queries with -- TRANSACTION REFERENCES -- placeholder
                            ↓
5. SQL QUERY FILES (Generated)
   ├── ExtractBuyerID.sql
   ├── ExtractSellerID.sql
   └── PricingData.sql
                            ↓
6. DATABASE EXECUTION
   ├── Run SQL queries against production database
   └── Export results to CSV files
                            ↓
7. VALIDATION SCRIPTS
   ├── Tool: buyer-id-validation, seller-id-validation, pricing-validation
   ├── Reads database extract CSV
   ├── Reads template file with transaction references
   ├── Performs validation logic
   └── Fills validation columns in template with results
                            ↓
8. FILLED TEMPLATE FILES
   ├── Validation columns populated with script output
   ├── Comparison columns remain empty for manual QA
   └── Consolidated data unchanged
                            ↓
9. MANUAL QA REVIEW
   ├── Review validation results
   ├── Fill comparison columns (Agree With Correction, etc.)
   └── Document findings
                            ↓
10. FINAL REPORTING
    └── Submit completed templates to regulatory authority
```

## Detailed Step-by-Step Guide

### Step 1: Prepare Consolidated Data

**Input Files:**

- `consolidated_errors.csv` - Errors from regulatory reporting system
- `consolidated_queries.csv` - Queries from regulatory reporting system

**Required Columns:**

- `INCIDENT_CODE` - Must contain incident code (e.g., "7_37" or "7_37|16_21" for multiple)
- `Transaction reference number` - Transaction identifier
- Additional columns vary by incident type

**Example Data:**

```csv
INCIDENT_CODE,INCIDENT_DESCRIPTION,KR_RECORD_KEY,Transaction reference number,Buyer identification code
7_37,Buyer ID missing,REC001,TXN001,
7_37|16_21,Multiple issues,REC002,TXN002,BUY123
16_21,Seller ID missing,REC003,TXN003,BUY456
35_3,Price missing,REC004,TXN004,BUY789
```

**Note on Pipe-Delimited Codes:**

Records with multiple incident codes (e.g., "7_37|16_21") will be duplicated
across multiple template files - one for each incident code.

---

### Step 2: Generate Template Files

**Tool:** `generate-accuracy-template`

**Configuration:**

Create or edit `config/environments/local.yaml`:

```yaml
paths:
  input:
    errors_file: "data/input/consolidated_errors.csv"
    queries_file: "data/input/consolidated_queries.csv"
  output:
    directory: "data/output/accuracy_testing/templates"
```

**Command:**

```bash
# Using config file
generate-accuracy-template --config config/environments/local.yaml

# Or with CLI arguments
generate-accuracy-template \
  --errors data/input/consolidated_errors.csv \
  --queries data/input/consolidated_queries.csv \
  --output data/output/templates

# Preview without generating files
generate-accuracy-template --config config/environments/local.yaml --dry-run
```

**Output:**

- One CSV file per unique incident code: `template_7_37.csv`, `template_16_21.csv`, etc.
- Files include:
  - **Validation columns** (empty, to be filled by validation scripts)
  - **Comparison columns** (empty, for manual QA)
  - **Consolidated data columns** (all original data)

**Template Formats:**

| Incident Codes | Format | Validation Columns |
| ---------------- | -------- | ------------------- |
| 7_35, 7_37, 7_39, 7_66 | Buyer | 14 columns |
| 16_19, 16_21, 16_23, 16_20 | Seller | 14 columns |
| 35_3 | Pricing | 10 columns |
| All others | Default | 6 columns |

**Key Feature:**

The first validation column (Transaction Reference) is automatically
populated from the consolidated data for easy reference.

---

### Step 3: Generate SQL Extract Queries

**Tool:** `generate-sql-extract`

**SQL Template Requirements:**

Your SQL template file must contain the placeholder `-- TRANSACTION REFERENCES --`
where transaction references should be inserted.

**Example Template:** `sql/ExtractBuyerID.sql`

```sql
SELECT
    t1.REPORTREF,
    t1.BUYER_ID,
    t1.BUYER_FIRST_NAME,
    t1.BUYER_SURNAME
FROM
    GLDATA/TXNREPESMA t1
WHERE
    t1.REPORTREF IN (
    -- TRANSACTION REFERENCES --
    )
```

**Configuration:**

```yaml
# In config/environments/local.yaml
paths:
  templates:
    buyer_extract: "sql/ExtractBuyerID.sql"
    seller_extract: "sql/ExtractSellerID.sql"
    pricing_extract: "sql/PricingData.sql"
  output:
    sql_directory: "data/output/sql"
```

**Command:**

```bash
# Generate SQL for buyer validation (incident 7_37)
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql

# With batch size control (default 900)
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql \
  --batch-size 500

# Preview without generating
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql \
  --dry-run
```

**Output:**

- `ExtractBuyerID.sql` - Single file if ≤900 transactions
- `ExtractBuyerID_Extract1.sql`, `ExtractBuyerID_Extract2.sql`, etc.
  - Multiple files if >900 transactions

**Generated SQL Example:**

```sql
SELECT
    t1.REPORTREF,
    t1.BUYER_ID,
    t1.BUYER_FIRST_NAME,
    t1.BUYER_SURNAME
FROM
    GLDATA/TXNREPESMA t1
WHERE
    t1.REPORTREF IN (
    'TXN001',
    'TXN002',
    'TXN003'
    )
```

---

### Step 4: Execute SQL Queries

**Process:**

1. Copy generated SQL files to database query tool
2. Execute queries against production database
3. Export results to CSV files

**Naming Convention:**

- Use incident-specific names: `buyer_id_data_7_37.csv`, `seller_id_data_16_21.csv`
- Include date for tracking: `buyer_id_data_7_37_2026-01-23.csv`

---

### Step 5: Run Validation Scripts

**Tools:**

- `buyer-id-validation` - For buyer ID incidents (7_35, 7_37, 7_39, 7_66)
- `seller-id-validation` - For seller ID incidents (16_19, 16_21, 16_23, 16_20)
- `pricing-validation` - For pricing incidents (35_3)

**Buyer Validation Example:**

```bash
buyer-id-validation \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_id_data_7_37.csv \
  --output data/output/validated
```

**Seller Validation Example:**

```bash
seller-id-validation \
  --reference data/output/templates/template_16_21.csv \
  --extract data/database/seller_id_data_16_21.csv \
  --output data/output/validated
```

**Pricing Validation Example:**

```bash
pricing-validation \
  --reference data/output/templates/template_35_3.csv \
  --extract data/database/pricing_data_35_3.csv \
  --output data/output/validated
```

**Validation Logic:**

**Buyer ID Validation:**

- Extracts Account ID from Transaction Reference
- Determines account type (NIDN, CONCAT, CCPT)
- Validates Buyer ID format matches account type
- Populates validation columns with results

**Seller ID Validation:**

- Similar logic to buyer validation
- Validates Seller ID instead of Buyer ID

**Pricing Validation:**

- Validates Price field presence and format
- Checks Price Currency
- Validates Net Amount calculations

**Output:**

- Updated template files with validation columns filled
- Summary statistics printed to console
- Log files in `data/output/logs/`

---

### Step 6: Manual QA Review

**Process:**

1. Open filled template files in spreadsheet software
2. Review validation results in validation columns
3. For each record, fill comparison columns:
   - **Agree With Correction** - Do you agree with the validation result? (Yes/No)
   - **Suggested Correction** - If no, what should the correction be?
   - **Suggested Correction Field** - Which field needs correction?

**Comparison Columns:**

- Column 15: `Agree With Correction`
- Column 16: `Suggested Correction`
- Column 17: `Suggested Correction Field`

**Tips:**

- Use filters to focus on specific validation outcomes
- Cross-reference with consolidated data columns
- Document patterns or systemic issues
- Save completed files with QA suffix: `template_7_37_QA_complete.csv`

---

### Step 7: Final Reporting

**Deliverables:**

1. Completed template files with all columns filled
2. Summary report with:
   - Total records processed
   - Validation success/failure counts
   - Common error patterns identified
   - Recommendations for data quality improvements

**Archive:**

- Store all files (templates, SQL, extracts, logs) in dated folder
- Document any manual adjustments or exceptions
- Track for audit trail

---

## Template File Structure

### Column Layout

```text
┌───────────────────────────────────────────────────────────────────┐
│                        TEMPLATE FILE STRUCTURE                     │
└───────────────────────────────────────────────────────────────────┘

VALIDATION COLUMNS (filled by scripts)
├── Column 0: Transaction Reference [auto-populated during generation]
├── Column 1: Account ID [filled by validation script]
├── Column 2: Person Code [filled by validation script]
├── Column 3-13: Additional validation fields [varies by template type]

COMPARISON COLUMNS (filled manually during QA)
├── Column 14: Agree With Correction
├── Column 15: Suggested Correction
└── Column 16: Suggested Correction Field

CONSOLIDATED DATA COLUMNS (read-only, from original data)
└── Column 17+: All original columns from consolidated errors/queries
```

### Buyer Template (14 validation columns)

```text
Transaction Reference | Account ID | Person Code | Buyer ID Code | 
Type of Buyer ID Code | First Name | Surname | Date of Birth | Gender |
Primary Nationality | Secondary Nationality | Correction Output | 
Correction Fields | Tracker Status | [Comparison Cols] | [Consolidated Data]
```

### Seller Template (14 validation columns)

```text
Transaction Reference | Account ID | Person Code | Seller ID Code | 
Type of Seller ID Code | First Name | Surname | Date of Birth | Gender |
Primary Nationality | Secondary Nationality | Correction Output | 
Correction Fields | Tracker Status | [Comparison Cols] | [Consolidated Data]
```

### Pricing Template (10 validation columns)

```text
Transaction Reference | Account ID | Person Code | Price | Price Currency |
Type of Price | Net Amount | Correction Output | Correction Fields | 
Tracker Status | [Comparison Cols] | [Consolidated Data]
```

### Default Template (6 validation columns)

```text
Transaction Reference | Record Key | Description | Correction Output |
Correction Fields | Tracker Status | [Comparison Cols] | [Consolidated Data]
```

---

## Configuration Files

### Accuracy Template Generator Config

**Location:** `config/environments/local.yaml` or custom config

```yaml
paths:
  input:
    errors_file: "data/input/consolidated_errors.csv"
    queries_file: "data/input/consolidated_queries.csv"
  output:
    directory: "data/output/accuracy_testing/templates"

processing:
  include_queries: true
  validate_incident_codes: true
```

### SQL Extract Generator Config

The SQL extract generator primarily uses CLI arguments but can reference config for paths.

**Command-line Options:**

- `--template PATH` - SQL template file
- `--input PATH` - Template CSV file
- `--output PATH` - Output directory for SQL files
- `--batch-size N` - Transactions per file (default 900)
- `--dry-run` - Preview without generating files

---

## Troubleshooting

### Issue: "INCIDENT_CODE column not found"

**Solution:** Ensure consolidated CSV has `INCIDENT_CODE` header (case-sensitive)

### Issue: "Template placeholder not found"

**Solution:** Ensure SQL template contains `-- TRANSACTION REFERENCES --` (spaces around text)

### Issue: No transaction references extracted

**Solution:**

- Check that template file has data rows (not just header)
- Verify "Transaction reference number" column exists in consolidated data
- Check for empty transaction reference values

### Issue: Validation script can't find transaction

**Solution:**

- Ensure database extract includes all transactions from template
- Check that transaction reference format matches between files
- Verify JOIN conditions in SQL query are correct

### Issue: Wrong template format applied

**Solution:**

- Check incident code matches expected format
- Review TemplateFormat class mappings in `accuracy_template_generator.py`
- Verify incident code doesn't have extra whitespace

---

## Best Practices

1. **Version Control**
   - Commit template files to git for audit trail
   - Use dated branches for each accuracy testing cycle
   - Tag releases with regulatory submission dates

2. **File Organization**

   ```text
   data/
   ├── input/
   │   ├── consolidated_errors_2026-01-23.csv
   │   └── consolidated_queries_2026-01-23.csv
   ├── output/
   │   ├── templates/
   │   ├── sql/
   │   ├── validated/
   │   └── logs/
   └── archive/
       └── 2026-01-23/
   ```

3. **Testing**
   - Always use `--dry-run` first to preview results
   - Test with small subset before processing full dataset
   - Validate one template completely before batch processing

4. **Documentation**
   - Log all commands executed
   - Document any manual adjustments
   - Note database connection details used
   - Track processing timestamps

5. **Quality Assurance**
   - Cross-check record counts at each step
   - Verify no transactions are lost during batching
   - Sample-check validation results before QA review
   - Double-check comparison column entries

---

## Quick Reference Commands

```bash
# Complete workflow example for buyer validation (incident 7_37)

# 1. Generate templates
generate-accuracy-template \
  --errors data/input/consolidated_errors.csv \
  --output data/output/templates

# 2. Generate SQL extract
generate-sql-extract \
  --template sql/ExtractBuyerID.sql \
  --input data/output/templates/template_7_37.csv \
  --output data/output/sql

# 3. (Execute SQL in database tool and export to CSV)

# 4. Run validation
buyer-id-validation \
  --reference data/output/templates/template_7_37.csv \
  --extract data/database/buyer_id_extract.csv \
  --output data/output/validated

# 5. (Manual QA review in spreadsheet)

# 6. Archive
mkdir data/archive/$(date +%Y-%m-%d)
cp -r data/output/* data/archive/$(date +%Y-%m-%d)/
```

---

## Related Documentation

- [Quick Start Guide](Quick_Start_Guide.md) - General project setup
- [Git Workflow Summary](Git_Workflow_Summary.md) - Version control practices
- [Conda Setup Guide](Conda_Setup_Guide.md) - Python environment setup
- Phase-specific documentation in `documentation/planning/`

---

## Support

For issues or questions:

1. Check logs in `data/output/logs/`
2. Review test cases in `tests/test_accuracy_testing/`
3. Consult source code documentation in module docstrings
4. Contact Transaction Reporting Team

---

**Last Updated:** January 23, 2026  
**Version:** 1.0
