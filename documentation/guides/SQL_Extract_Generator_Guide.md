# SQL Extract Generator Guide

## Overview

The SQL Extract Generator is a unified Python tool that replaces three legacy VBA scripts:
- `ExtractBuyerID4_1.vb`
- `ExtractInconsistentBuyerID1_0.vb`
- `SCR_extract_generator_v1_0.vb`

It generates SQL extract files by inserting transaction references into SQL templates with placeholder markers.

## Features

- **Template-driven**: Works with any SQL template containing a transaction reference placeholder
- **Batch processing**: Automatically splits large transaction lists into manageable batches
- **Multiple placeholder formats**: Supports various placeholder patterns for compatibility
- **Dry-run mode**: Preview generation without creating files
- **Flexible batch sizes**: Configure transactions per extract (default: 900)
- **Smart filename handling**: Single extracts use template name, multiple extracts are numbered

## Installation

The tool is installed as part of the `txr-automation` package:

```bash
pip install -e .
```

This registers the `generate-sql-extract` console command.

## Usage

### Basic Usage

```bash
generate-sql-extract \
  --template path/to/template.sql \
  --input path/to/transactions.csv \
  --output path/to/output
```

### Command-Line Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `--template` | Path to SQL template file | - | Yes |
| `--input` | Path to CSV file with transaction references | - | Yes |
| `--output` | Output directory for generated SQL files | - | Yes |
| `--batch-size` | Number of transactions per extract file | 900 | No |
| `--dry-run` | Preview generation without creating files | False | No |

### Examples

#### 1. Generate Single Extract File

```bash
generate-sql-extract \
  --template legacy/sql/buyer_id_extract.sql \
  --input data/output/transactions_35_3.csv \
  --output data/output/sql
```

**Output**: `data/output/sql/buyer_id_extract.sql`

#### 2. Generate Multiple Batch Files

```bash
generate-sql-extract \
  --template legacy/sql/pricing_extract.sql \
  --input data/output/transactions_35_3.csv \
  --output data/output/sql \
  --batch-size 500
```

**Output** (if 1,200 transactions):
- `data/output/sql/pricing_extract_Extract1.sql` (500 transactions)
- `data/output/sql/pricing_extract_Extract2.sql` (500 transactions)
- `data/output/sql/pricing_extract_Extract3.sql` (200 transactions)

#### 3. Preview Without Generating Files

```bash
generate-sql-extract \
  --template legacy/sql/seller_id_extract.sql \
  --input data/output/transactions_35_4.csv \
  --output data/output/sql \
  --dry-run
```

This displays a summary without creating any files.

## SQL Templates

### Template Requirements

SQL templates must contain exactly one placeholder for transaction references. The tool automatically detects the placeholder format.

### Supported Placeholder Formats

1. **Standard format**: `--<<TRANSACTION REFERENCES>>`
2. **Alternative format**: `--<TRADE REFERENCES>--`
3. **Custom format**: Can be specified programmatically (future CLI enhancement)

### Template Example

```sql
-- Buyer ID Extract Template
SELECT
    t1.REPORTREF,
    t1.BUYID,
    t2.FRNAME,
    t2.CLICSD
FROM
    GLDATA/TXNREPESMA t1
LEFT JOIN GLDATA/CONTCT t2 
    ON t2.FRMCOD || t2.YEAR || t2.ACCLTR || t2.CONTNO || '1' = t1.REPORTREF
WHERE
    t1.REPORTREF IN (
    --<<TRANSACTION REFERENCES>>
    )
ORDER BY t1.REPORTREF
```

### Placeholder Replacement

The placeholder is replaced with formatted transaction references:

```sql
WHERE
    t1.REPORTREF IN (
    '44625CKTPC31',
    '44625CKT72V1',
    '44625CKVNVJ1'
    )
```

## Input CSV Format

### Requirements

- **Header row**: Must have a header row (first row)
- **Transaction references**: First column contains transaction references
- **Additional columns**: Ignored (can include incident codes, dates, etc.)

### Example CSV

```csv
TRANSACTION_REFERENCE,INCIDENT_CODE,DATE
44625CKTPC31,35_3,2024-01-15
44625CKT72V1,35_3,2024-01-15
44625CKVNVJ1,35_3,2024-01-16
```

### Data Handling

- **Whitespace**: Automatically stripped from references
- **Empty rows**: Skipped automatically
- **Encoding**: UTF-8 (default)

## Output Files

### Filename Conventions

- **Single batch**: Uses template filename
  - Example: `buyer_id_extract.sql`
  
- **Multiple batches**: Adds batch number suffix
  - Example: `buyer_id_extract_Extract1.sql`, `buyer_id_extract_Extract2.sql`

### Output Format

- **Encoding**: UTF-8
- **Line endings**: Platform-specific (LF on Unix, CRLF on Windows)
- **Overwrite behavior**: Existing files are overwritten without warning

## Batch Processing

### Batch Size Selection

The default batch size is 900 transactions (matching VBA logic), but can be adjusted based on:

1. **Database query limits**: Some databases have IN clause size limits
2. **Performance**: Smaller batches process faster but create more files
3. **Manageability**: Larger batches mean fewer files to handle

### Batch Size Guidelines

| Scenario | Recommended Batch Size |
|----------|------------------------|
| Standard processing | 900 (default) |
| Large datasets (10,000+ transactions) | 500-700 |
| Database with IN clause limits | 500 or less |
| Quick testing | 50-100 |

## Error Handling

### Common Errors

1. **Template not found**
   ```
   FileNotFoundError: Template file not found: path/to/template.sql
   ```
   **Solution**: Verify the template path is correct

2. **No placeholder found**
   ```
   ValueError: No placeholder found in template
   ```
   **Solution**: Ensure template contains a valid placeholder

3. **Input CSV not found**
   ```
   FileNotFoundError: Input CSV not found: path/to/input.csv
   ```
   **Solution**: Verify the input CSV path is correct

4. **Empty input CSV**
   ```
   Warning: No transaction references found in CSV
   ```
   **Solution**: Verify CSV contains data in first column

## Migration from VBA

### ExtractBuyerID4_1.vb → SQL Extract Generator

**VBA:**
```vb
' Hard-coded template path
' Hard-coded batch size (900)
' Manual file numbering
```

**Python:**
```bash
generate-sql-extract \
  --template legacy/sql/buyer_id_extract.sql \
  --input data/output/transactions.csv \
  --output data/output/sql \
  --batch-size 900
```

### Advantages Over VBA

1. **Flexibility**: Any template, any placeholder format
2. **No hard-coding**: All paths configurable via CLI
3. **Better error messages**: Clear error reporting
4. **Testability**: Comprehensive unit test coverage (21 tests)
5. **Dry-run mode**: Preview without generating files
6. **Platform-independent**: Works on Windows, macOS, Linux

## Testing

### Running Unit Tests

```bash
pytest tests/test_accuracy_testing/test_sql_extract_generator.py -v
```

### Test Coverage

The test suite includes:
- Template loading and validation
- Placeholder detection (multiple formats)
- Batch splitting logic
- Transaction reference formatting
- SQL generation
- File output
- CLI interface

**Current coverage**: 21 tests, all passing

### Manual Testing

```bash
# Test with sample data
generate-sql-extract \
  --template data/test/test_template.sql \
  --input data/test/sql_extract_sample.csv \
  --output data/test/output
```

## API Usage

For programmatic use:

```python
from src.accuracy_testing.sql_extract_generator import SQLExtractGenerator

# Initialize generator
generator = SQLExtractGenerator(
    template_path="path/to/template.sql",
    batch_size=900
)

# Generate extracts
transaction_refs = ['44625CKTPC31', '44625CKT72V1', '44625CKVNVJ1']
generated_files = generator.generate_extracts(
    transaction_refs=transaction_refs,
    output_dir="data/output/sql",
    base_filename="extract"
)

# Get summary
summary = generator.get_summary(transaction_refs)
print(f"Generated {summary['num_batches']} batch(es)")
```

## Configuration

### YAML Configuration (Future Enhancement)

While not yet implemented, a YAML-based configuration file is planned:

```yaml
# config/sql_extract_config.yaml
sql_extract:
  batch_size: 900
  template_dir: "legacy/sql"
  output_dir: "data/output/sql"
```

### Environment Variables (Future Enhancement)

Planned support for environment variables:
- `SQL_EXTRACT_TEMPLATE_DIR`: Default template directory
- `SQL_EXTRACT_OUTPUT_DIR`: Default output directory
- `SQL_EXTRACT_BATCH_SIZE`: Default batch size

## Troubleshooting

### Issue: "No placeholder found in template"

**Cause**: Template doesn't contain a recognized placeholder pattern

**Solution**:
1. Check template contains `--<<TRANSACTION REFERENCES>>` or `--<TRADE REFERENCES>--`
2. Verify placeholder is on its own line
3. Check for typos in placeholder syntax

### Issue: Generated SQL has formatting issues

**Cause**: Transaction references contain unexpected characters

**Solution**:
1. Verify CSV data is clean (no special characters)
2. Check encoding is UTF-8
3. Review generated SQL file manually

### Issue: Wrong number of batches generated

**Cause**: Incorrect batch size calculation

**Solution**:
1. Verify `--batch-size` parameter
2. Check number of transaction references in input CSV
3. Use `--dry-run` to preview batch count

## Performance

### Benchmarks

Tested on MacBook Pro M1:
- 1,000 transactions: <0.1 seconds
- 10,000 transactions: ~0.5 seconds
- 100,000 transactions: ~4 seconds

### Optimization Tips

1. **Use appropriate batch sizes**: Don't make batches too small
2. **Pre-filter input CSV**: Remove unnecessary rows before processing
3. **Use SSD storage**: I/O-bound operations benefit from fast storage

## Future Enhancements

1. **YAML configuration**: Support for configuration files
2. **Custom placeholders**: Specify placeholder pattern via CLI
3. **Multiple placeholders**: Support templates with multiple insertion points
4. **Output validation**: Verify generated SQL syntax
5. **Progress reporting**: Progress bars for large datasets
6. **Parallel processing**: Generate multiple batches concurrently

## Support

For issues or questions:
1. Check this documentation
2. Review test cases in `tests/test_accuracy_testing/test_sql_extract_generator.py`
3. Examine sample files in `data/test/`
4. Contact the Transaction Reporting Team

## Related Documentation

- [Python Migration Plan](../planning/Python_Migration_Plan.md)
- [Quick Start Guide](Quick_Start_Guide.md)
- [Phase 2 Scripts Overview](../planning/Existing_Python_Scripts_Refactoring_Plan.md)
