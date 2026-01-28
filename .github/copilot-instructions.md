# AI Agent Custom Instructions: VBA-Python Migration

## Project Overview

This project is migrating VBA macros for transaction reporting automation to Python. The codebase includes both already-migrated Python scripts and remaining VBA code to convert.

**Key Planning Documents:**

- [Python_Migration_Plan.md](../documentation/planning/Python_Migration_Plan.md) - Master migration plan with phases, timelines, and technical approach
- [Phase_8_CLI_Tool_Plan.md](../documentation/planning/Phase_8_CLI_Tool_Plan.md) - Future CLI unification plan

**Current Status (28 January 2026):**

- Phase 0 (Refactoring): ✅ Complete
- Phase 1 (Foundation): ✅ Complete
- Phase 2 (Simple Scripts): ✅ Complete
- Phase 3 (Decision Maker Validation): 🔲 Not started
- Phase 4 (Inconsistent ID): ✅ Complete
- Phase 5 (Data Operations): 🔲 Not started

---

## Terminal Environment

**Important:** When creating a new terminal session, always activate the conda environment first:

```bash
conda activate txr_automation
```

This ensures all Python commands use the correct environment with the required dependencies.

---

## Project Structure

```text
txr_automation/
├── src/
│   ├── accuracy_testing/          # VBA-migrated accuracy testing scripts
│   │   ├── core/                  # Accuracy testing core library
│   │   ├── models/                # Data models (dataclasses)
│   │   ├── scripts/               # CLI scripts (buyer_id_validation.py, etc.)
│   │   ├── validators/            # Validation logic classes
│   │   └── processor.py           # Main processing logic
│   ├── core/                      # Shared core library (txr_core)
│   │   ├── config/                # Configuration management
│   │   ├── data/                  # Reference data, constants, data structures
│   │   ├── logging/               # Structured logging
│   │   ├── utils/                 # Utilities (date parsing, CSV, file discovery)
│   │   └── validation/            # Core validation functions
│   ├── replay/                    # Replay processing scripts
│   └── utils/                     # Shared utilities
├── legacy/vba/                    # Original VBA macros (source for migration)
├── config/                        # YAML configuration files
│   ├── local/                     # Local environment configs
│   └── templates/                 # Configuration templates
├── tests/                         # Test suite
│   ├── test_accuracy_testing/     # Accuracy testing tests
│   ├── test_core/                 # Core library tests
│   └── integration/               # Integration tests
└── documentation/                 # Project documentation
    ├── guides/                    # User guides
    ├── planning/                  # Migration planning docs
    └── reference_data/            # CSV reference data files
```

---

## Coding Standards

### Python Conventions

1. **Python Version:** 3.10+
2. **Style:** PEP 8 compliant
3. **Type Hints:** Required on all functions and methods
4. **Docstrings:** Google-style docstrings on all public functions, classes, and modules

### Module Header Template

```python
#!/usr/bin/env python3
"""
Module Name
===========

Brief description of module purpose.

Version X.Y Changes:
- List significant changes

Usage:
    Example usage if applicable
"""
```

### Function Docstring Template

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of function purpose.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When invalid input provided

    Example:
        >>> function_name("test", 42)
        True
    """
```

### Import Order

1. Standard library imports
2. Third-party imports (pandas, click, etc.)
3. Local imports from `core`
4. Local imports from current package

```python
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict

import pandas as pd
import click

from core import (
    StructuredLogger,
    create_logger,
    country_manager,
    id_format_manager,
)

from .processor import ClientRecord, IDValidationProcessor
```

### Dataclasses for Data Structures

Use `@dataclass` for all data transfer objects:

```python
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class ClientRecord:
    """Represents a client record for ID validation."""

    transaction_ref: str
    account_id: str
    person_code: str
    id_value: str = ""
    id_type: str = ""
    correction: str = ""
    error_flag: str = "N"
```

### Configuration Management

Use the established `AccuracyConfigManager` pattern:

```python
from src.accuracy_testing.processor import (
    AccuracyConfigManager,
    AccuracyPathConfig,
    AccuracyProcessorConfig,
)

# Load from YAML, environment variables, or CLI args
config_manager = AccuracyConfigManager()
path_config = config_manager.load_path_config(config_file)
```

### Error Handling

```python
try:
    result = process_record(record)
except ValueError as e:
    logger.warning(f"Validation failed for {record.transaction_ref}: {e}")
    record.error_flag = "Y"
except Exception as e:
    logger.error(f"Unexpected error processing {record.transaction_ref}: {e}")
    raise
```

### Logging

Use structured logging from core:

```python
from core import create_logger, StructuredLogger

logger = create_logger(__name__)

# Log with context
logger.info("Processing batch", extra={
    "batch_size": len(records),
    "incident_code": "7_39",
})
```

---

## VBA Migration Guidelines

### When Converting VBA to Python

1. **Read the VBA carefully** - Understand all business logic before writing Python
2. **Map VBA functions to Python** - Document which VBA function maps to which Python function
3. **Preserve business logic exactly** - The Python must produce identical results to VBA
4. **Use existing core utilities** - Check `src/core/` and `src/accuracy_testing/core/` for existing implementations before writing new code
5. **Write tests first** - Create test cases from VBA expected outputs before implementing

### VBA to Python Patterns

| VBA Pattern | Python Equivalent |
|-------------|-------------------|
| `Dim x As String` | `x: str = ""` |
| `For i = 1 To n` | `for i in range(1, n + 1):` |
| `Left(str, n)` | `str[:n]` |
| `Right(str, n)` | `str[-n:]` |
| `Mid(str, start, len)` | `str[start-1:start-1+len]` |
| `Len(str)` | `len(str)` |
| `UCase(str)` | `str.upper()` |
| `LCase(str)` | `str.lower()` |
| `Trim(str)` | `str.strip()` |
| `IsNumeric(x)` | `str(x).isdigit()` or use regex |
| `InStr(str, sub)` | `sub in str` or `str.find(sub)` |
| `Split(str, delim)` | `str.split(delim)` |
| `Join(arr, delim)` | `delim.join(arr)` |
| `Range("A1").Value` | Use pandas DataFrame or CSV reader |
| `Cells(row, col).Value` | `df.iloc[row, col]` |

### Reference Data Access

Use the established managers:

```python
from src.accuracy_testing.core import (
    country_manager,      # Country code lookups
    id_format_manager,    # ID format validation
    validate_id,          # ID validation
    validate_id_auto,     # Auto-detect ID type validation
)

# Check country
if country_manager.is_eea_country("GB"):
    # EEA-specific logic

# Validate ID format
is_valid = id_format_manager.validate_format("GB", "NIDN", id_value)
```

### CSV-First Approach

- **No Excel dependencies** - All I/O uses CSV
- Use `pandas` for DataFrame operations
- Use `csv` module for simple read/write
- Always specify `encoding='utf-8'`

```python
import pandas as pd

# Reading
df = pd.read_csv(input_path, encoding='utf-8')

# Writing
df.to_csv(output_path, index=False, encoding='utf-8')
```

---

## Testing Requirements

### Test File Structure

```text
tests/
├── test_accuracy_testing/
│   ├── test_buyer_id_validation.py
│   ├── test_seller_id_validation.py
│   └── fixtures/
│       └── sample_input.csv
└── conftest.py
```

### Test Naming Convention

```python
def test_validate_nidn_valid_uk_nino():
    """Test NIDN validation with valid UK NINO."""
    pass

def test_validate_nidn_invalid_checksum():
    """Test NIDN validation fails with invalid checksum."""
    pass
```

### Required Test Coverage

- All validation functions must have unit tests
- All scripts must have integration tests
- Test edge cases: empty values, special characters, boundary conditions
- Test with sample data from VBA outputs

---

## Documentation Standards

### Language

- **British English** throughout (e.g., "colour" not "color", "organisation" not "organization", "behaviour" not "behavior")
- Use "whilst" appropriately, but "while" is also acceptable
- Use "licence" (noun) and "license" (verb)

### Markdown Standards (markdownlint compliant)

1. **Headings:**
   - Use ATX-style headings (`#`, `##`, etc.)
   - Include blank line before and after headings
   - No trailing punctuation on headings
   - Headings must increment by one level (no skipping)

2. **Lists:**
   - Use `-` for unordered lists (consistent marker)
   - Use `1.` for ordered lists
   - Include blank line before and after lists
   - Indent nested lists with 2 or 4 spaces consistently

3. **Code blocks:**
   - Use fenced code blocks with language identifier
   - Use `python`, `bash`, `yaml`, `csv`, `text` as appropriate

4. **Line length:**
   - Aim for 100 characters maximum per line
   - Break long lines at logical points

5. **Links:**
   - Use relative paths for internal links
   - Ensure all links are valid

6. **Files:**
   - Single trailing newline at end of file
   - No trailing whitespace on lines
   - No multiple consecutive blank lines

### Documentation Template for New Scripts

```markdown
# Script Name

Brief description of what the script does.

## Overview

Detailed explanation of the script's purpose and the business logic it implements.

## Usage

### Command Line

```bash
python -m src.accuracy_testing.scripts.script_name --config config.yaml
```

### Configuration

Describe YAML configuration options.

## Input Format

Describe expected CSV input columns.

## Output Format

Describe CSV output columns added.

## Validation Rules

List business rules implemented.

## Examples

Provide usage examples.

## Migration Notes

Document any differences from original VBA behaviour.
```

---

## CLI Interface Standards

Use `argparse` or `click` consistently:

```python
def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for script."""
    parser = argparse.ArgumentParser(
        description="Buyer ID Validation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser
```

---

## Performance Considerations

1. **Use indexing for lookups** - Create dictionaries/sets for O(1) lookups
2. **Batch processing** - Process records in batches for large datasets
3. **Lazy loading** - Load reference data once at startup
4. **Avoid repeated regex compilation** - Pre-compile patterns

```python
# Good: Pre-compiled regex
import re
PATTERNS = {
    "uk_nino": re.compile(r"^[A-Z]{2}\d{6}[A-Z]$"),
}

# Good: Indexed lookups
records_by_person = defaultdict(list)
for record in records:
    records_by_person[record.person_code].append(record)
```

---

## Git Workflow

- **Branch:** `vba-migration` for all VBA migration work
- **Commits:** Clear, descriptive commit messages
- **Format:** `type(scope): description`
  - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
  - Example: `feat(accuracy): add seller ID validation script`

---

## Checklist for New Script Migration

- [ ] Read and understand VBA source completely
- [ ] Document VBA-to-Python function mapping
- [ ] Create test fixtures from VBA expected outputs
- [ ] Write unit tests for validation logic
- [ ] Implement core validation in appropriate module
- [ ] Create CLI script following established patterns
- [ ] Use existing core utilities (don't reinvent)
- [ ] Add integration tests
- [ ] Verify output matches VBA exactly
- [ ] Update documentation
- [ ] Update `__init__.py` exports if needed
- [ ] Add to console scripts in `setup.py` if needed

---

## Common Pitfalls to Avoid

1. **Don't create new utility functions** if they exist in `src/core/`
2. **Don't use Excel libraries** - CSV only
3. **Don't hardcode paths** - Use configuration
4. **Don't skip type hints** - Required everywhere
5. **Don't write American English** in documentation
6. **Don't skip tests** - Every function needs tests
7. **Don't modify VBA files** - They are read-only reference
8. **Don't create duplicate reference data** - Use existing CSVs in `documentation/reference_data/`

---

## Quick Reference: Existing Utilities

### From `src/core/`

- `StructuredLogger` - Logging
- `DateParser` - Date parsing and formatting
- `FileDiscovery` - File discovery utilities
- `safe_open_csv` - Safe CSV operations
- `country_manager` - Country code lookups
- `id_format_manager` - ID format validation
- `ConfigManager` - Configuration management

### From `src/accuracy_testing/core/`

- `validate_id` - ID validation
- `validate_id_auto` - Auto-detect ID type validation
- `validate_date_format` - Date format validation
- `validate_not_empty` - Empty value validation
- `IDType` - ID type enumeration

### From `src/accuracy_testing/processor.py`

- `ClientRecord` - Client record dataclass
- `IDValidationProcessor` - Main validation processor
- `ProcessingStats` - Processing statistics
- `AccuracyConfigManager` - Accuracy testing config management
