# DTF File Generation Guide

## Overview

The SQL Extract Generator now supports generating **DTF (Data Transfer) files** in addition to SQL files. DTF files are configuration files for the AS/400 Data Transfer tool that contain:
- Embedded SQL queries
- Pre-configured output paths for CSV files
- All AS/400 connection and formatting settings

This eliminates the manual step of copying SQL into the AS/400 Data Transfer tool.

## Key Features

- **Automated DTF Generation**: Generate ready-to-import AS/400 Data Transfer files
- **Multiple Output Formats**: Choose `sql`, `dtf`, or `both` (default)
- **Structured Output**: Organized directory structure with `/csv` and `/dtf` subdirectories
- **Single-Line SQL**: SQL queries automatically formatted for DTF compatibility
- **Batch Processing**: Generate DTF files for multiple incidents simultaneously

## Directory Structure

When using the extract generator, the following structure is created:

```
output_directory/
├── csv/              # SQL files (or CSV destination for AS/400 extracts)
│   ├── 7_37_FY26_Q1.sql
│   └── 16_21_FY26_Q1.sql
└── dtf/              # DTF files (for AS/400 Data Transfer tool)
    ├── 7_37_FY26_Q1.dtf
    └── 16_21_FY26_Q1.dtf
```

**Note**: When `output_format: 'sql'`, a `/sql` subdirectory is used instead of `/csv`.

## Configuration

### Template Configuration

Edit `config/templates/accuracy_testing/sql_extract_generator_template.yaml`:

```yaml
# Output options
output_options:
  # Output format: 'sql', 'dtf', or 'both' (default: 'both')
  format: "both"  # Generate both SQL and DTF files
  
  # Optional: Override incident code for CSV naming
  # incident_code: "7_37"

# Paths
paths:
  # DTF template file (uses default if not specified)
  dtf_template_file: "src/accuracy_testing/sql_templates/AS400_DataTransfer_template.dtf"
  
  # Parent output directory (creates /csv and /dtf subdirectories)
  output_directory: "data/sql_extracts"
```

### Output Format Options

1. **`both` (Default)**: Generate both SQL and DTF files
   - SQL files → `output_directory/csv/`
   - DTF files → `output_directory/dtf/`

2. **`sql`**: Generate only SQL files
   - SQL files → `output_directory/sql/`

3. **`dtf`**: Generate only DTF files
   - DTF files → `output_directory/dtf/`
   - CSV output paths embedded in DTF files

## Usage

### Command Line

```bash
# Generate both SQL and DTF files (default)
python -m src.accuracy_testing.scripts.sql_extract_generator \
    --config config/local/accuracy_testing/sql_extract_generator.yaml

# Generate only DTF files
python -m src.accuracy_testing.scripts.sql_extract_generator \
    --config config/local/accuracy_testing/sql_extract_generator.yaml \
    --output-format dtf

# Generate only SQL files
python -m src.accuracy_testing.scripts.sql_extract_generator \
    --config config/local/accuracy_testing/sql_extract_generator.yaml \
    --output-format sql

# Single incident with custom incident code
python -m src.accuracy_testing.scripts.sql_extract_generator \
    --template src/accuracy_testing/sql_templates/BuyerID.sql \
    --input data/templates/FY26_Q1_7_37.csv \
    --output data/extracts \
    --incident-code 7_37 \
    --output-format both
```

### Python API

```python
from src.accuracy_testing.sql_extract_generator import SQLExtractGenerator

# Initialize generator with DTF support
generator = SQLExtractGenerator(
    template_path='src/accuracy_testing/sql_templates/BuyerID.sql',
    batch_size=900,
    output_format='both',  # 'sql', 'dtf', or 'both'
    dtf_template_path='src/accuracy_testing/sql_templates/AS400_DataTransfer_template.dtf'
)

# Generate extracts
transaction_refs = ['TXN001', 'TXN002', 'TXN003']
result = generator.generate_extracts(
    transaction_refs=transaction_refs,
    output_dir='data/extracts',
    base_filename='7_37_FY26_Q1',
    incident_code='7_37'
)

# Check results
print(f"SQL files generated: {len(result['sql_files'])}")
print(f"DTF files generated: {len(result['dtf_files'])}")
```

## DTF File Format

### Template Structure

The DTF template (`AS400_DataTransfer_template.dtf`) contains placeholders:

```ini
[ClientInfo]
PCFile={OUTPUT_PATH}    # Replaced with: output_directory/csv/incident_code.csv

[SQL]
SQLSelect={SQL_QUERY}   # Replaced with single-line SQL query

[Properties]
AutoClose=1             # Automatically close after export
AutoRun=1              # Automatically run on import
```

### Generated DTF Example

```ini
[ClientInfo]
PCFile=data/extracts/csv/7_37.csv

[SQL]
SQLSelect=SELECT t1.REPORTREF, t2.CLINUM FROM GLDATA/TXNREPESMA t1 WHERE t1.REPORTREF IN ('TXN001', 'TXN002')

[Properties]
AutoClose=1
AutoRun=1
```

## Workflow Integration

### Complete AS/400 Extraction Workflow

1. **Generate Templates**: Create accuracy testing templates
   ```bash
   python -m src.accuracy_testing.scripts.accuracy_template_generator \
       --config config/local/accuracy_testing/buyer_validation.yaml
   ```

2. **Generate SQL/DTF Files**: Create extraction files
   ```bash
   python -m src.accuracy_testing.scripts.sql_extract_generator \
       --config config/local/accuracy_testing/sql_extract_generator.yaml
   ```

3. **Import DTF to AS/400 Tool**: 
   - Open AS/400 Data Transfer tool
   - File → Import → Select DTF file
   - Tool automatically:
     - Loads SQL query
     - Sets output path
     - Configures all settings
     - Runs extraction (if AutoRun=1)

4. **Run Validation**: Validate extracted data
   ```bash
   python -m src.accuracy_testing.scripts.buyer_id_validation \
       --config config/local/accuracy_testing/buyer_validation.yaml
   ```

## Batch Processing

The batch mode automatically generates DTF files for multiple incidents:

```yaml
# config/local/accuracy_testing/sql_extract_generator.yaml
testing_period:
  fiscal_year: "FY26"
  quarter: "Q1"

incidents:
  - "7_35"
  - "7_37"
  - "7_39"
  - "16_19"
  - "16_21"
  - "16_23"

output_options:
  format: "both"  # Generates both SQL and DTF for all incidents
```

Run batch generation:
```bash
python -m src.accuracy_testing.scripts.sql_extract_generator \
    --config config/local/accuracy_testing/sql_extract_generator.yaml
```

Output:
```
data/sql_extracts/
├── csv/
│   ├── 7_35_FY26_Q1.sql
│   ├── 7_37_FY26_Q1.sql
│   ├── 7_39_FY26_Q1.sql
│   ├── 16_19_FY26_Q1.sql
│   ├── 16_21_FY26_Q1.sql
│   └── 16_23_FY26_Q1.sql
└── dtf/
    ├── 7_35_FY26_Q1.dtf
    ├── 7_37_FY26_Q1.dtf
    ├── 7_39_FY26_Q1.dtf
    ├── 16_19_FY26_Q1.dtf
    ├── 16_21_FY26_Q1.dtf
    └── 16_23_FY26_Q1.dtf
```

## Technical Details

### SQL Formatting for DTF

DTF files require SQL queries on a single line without newlines. The generator automatically:

1. **Removes newlines**: Multi-line SQL → single line
2. **Collapses whitespace**: Multiple spaces → single space
3. **Preserves syntax**: Maintains valid SQL structure

Example transformation:
```sql
-- Original multi-line SQL
SELECT 
    t1.REPORTREF,
    t2.CLINUM
FROM GLDATA/TXNREPESMA t1
WHERE t1.REPORTREF IN (
    'TXN001',
    'TXN002'
)

-- DTF single-line format
SELECT t1.REPORTREF, t2.CLINUM FROM GLDATA/TXNREPESMA t1 WHERE t1.REPORTREF IN ('TXN001', 'TXN002')
```

### Batch Splitting

When transaction counts exceed `batch_size` (default 900), multiple files are generated:

```
csv/
├── 7_37_FY26_Q1_Extract1.sql
├── 7_37_FY26_Q1_Extract2.sql
└── 7_37_FY26_Q1_Extract3.sql

dtf/
├── 7_37_FY26_Q1_Extract1.dtf  → Points to csv/7_37_Extract1.csv
├── 7_37_FY26_Q1_Extract2.dtf  → Points to csv/7_37_Extract2.csv
└── 7_37_FY26_Q1_Extract3.dtf  → Points to csv/7_37_Extract3.csv
```

Each DTF file:
- Contains its batch's SQL query
- Points to its corresponding CSV output file
- Is independently importable into AS/400 tool

## Troubleshooting

### DTF Template Not Found

**Error**: `FileNotFoundError: DTF template file not found`

**Solution**: Verify DTF template exists:
```bash
ls src/accuracy_testing/sql_templates/AS400_DataTransfer_template.dtf
```

If missing, the template should contain:
- `{SQL_QUERY}` placeholder for SQL
- `{OUTPUT_PATH}` placeholder for CSV output
- Valid AS/400 configuration settings

### Placeholder Not Replaced

**Error**: DTF file contains `{SQL_QUERY}` or `{OUTPUT_PATH}`

**Solution**: Check template format:
```ini
# Correct placeholders (exact match required)
SQLSelect={SQL_QUERY}
PCFile={OUTPUT_PATH}
```

### Invalid Output Format

**Error**: `ValueError: Invalid output_format`

**Solution**: Use valid format options:
- `'sql'` - SQL files only
- `'dtf'` - DTF files only  
- `'both'` - Both formats (default)

### Missing CSV Output Path

**Issue**: DTF file points to incorrect CSV location

**Solution**: Ensure `incident_code` parameter matches expected naming:
```python
generator.generate_extracts(
    transaction_refs=refs,
    output_dir='data/extracts',
    base_filename='7_37_FY26_Q1',
    incident_code='7_37'  # Used for CSV naming in DTF
)
```

## Best Practices

1. **Use Default DTF Template**: Unless custom AS/400 settings required
2. **Set AutoRun=1**: Automatically extract on DTF import
3. **Verify Output Paths**: Check DTF files point to correct CSV locations
4. **Batch Processing**: Generate all incidents at once for consistency
5. **Test DTF Import**: Verify DTF files import correctly before production use
6. **Document Custom Settings**: If modifying DTF template, document changes

## Migration from Manual Process

### Old Workflow (Manual)
1. Generate SQL files
2. Open AS/400 Data Transfer tool
3. **Manual**: Copy/paste SQL query
4. **Manual**: Set output CSV path
5. **Manual**: Configure settings (AutoClose, AutoRun, etc.)
6. Run extraction
7. **Manual**: Repeat for each incident

### New Workflow (Automated)
1. Generate SQL + DTF files (`output_format: 'both'`)
2. Import DTF file into AS/400 tool
3. Tool automatically runs extraction
4. **Done** - No manual configuration needed

**Time Savings**: ~5 minutes per incident → 30 seconds (90% reduction)

## Related Documentation

- [SQL Extract Generator Guide](../guides/Quick_Start_Guide.md#sql-extract-generator)
- [AS/400 Data Transfer Tool Documentation](https://example.com/as400-docs)
- [Accuracy Testing Workflow](../guides/Quick_Start_Guide.md#accuracy-testing-workflow)
- [Configuration Templates](../../config/templates/accuracy_testing/)

## Version History

- **v1.1** (2026-01-23): Added DTF file generation support
  - New `output_format` parameter ('sql', 'dtf', 'both')
  - Structured output directories (/csv, /dtf, /sql)
  - Single-line SQL formatting for DTF compatibility
  - Batch processing support for DTF generation
  - AS400_DataTransfer_template.dtf template

- **v1.0** (2026-01-22): Initial SQL extract generator
  - SQL file generation only
  - Batch splitting
  - Template-based generation
