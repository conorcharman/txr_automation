# TXR Replay Core Library

Shared utilities and core functionality for transaction replay processing and VBA migration scripts.

## Overview

The `txr_replay_core` package provides common functionality used across all processing scripts, eliminating code duplication and ensuring consistency. It includes embedded reference data (country codes, ID formats) removing CSV file dependencies.

**Version:** 1.1.0  
**Last Updated:** January 2026

## Installation

```bash
# From the project root directory
pip install -e .
```

## Modules

### Core Data Structures

#### `data_structures.py`

Common dataclasses for replay processing:

- **`ReplayRecord`**: Universal replay record structure
- **`LookupResult`**: Result of transaction/client lookups
- **`UnaVistaTransaction`**: UnaVista transaction record
- **`ProcessingStats`**: Standardized statistics tracking

### Reference Data (Embedded - No CSV Dependencies)

#### `country_codes.py`

ISO 3166-1 country codes with EEA status:

- **249 countries** with Alpha-2, Alpha-3 codes and EEA flag
- **`Country`**: Immutable country data structure
- **`CountryDataManager`**: Singleton manager with O(1) lookups
- **`country_manager`**: Pre-instantiated singleton

```python
from txr_replay_core import country_manager

# Lookup by Alpha-2 code
uk = country_manager.get_by_alpha2("GB")
print(uk.name)  # "United Kingdom..."
print(uk.is_eea)  # True

# Check EEA membership
is_eea = country_manager.is_eea("DE")  # True

# Convert codes
alpha3 = country_manager.get_alpha3_from_alpha2("GB")  # "GBR"

# Get all EEA countries
eea_countries = country_manager.get_eea_countries()
```

#### `id_formats.py`

ID format validation patterns (NIDN, CONCAT, CCPT, LEI):

- **67 regex patterns** for validating ID codes across countries
- **`IDPattern`**: Immutable pattern with compiled regex
- **`IDFormatManager`**: Singleton manager for pattern matching
- **`id_format_manager`**: Pre-instantiated singleton

```python
from txr_replay_core import id_format_manager

# Validate ID against country and type
is_valid = id_format_manager.validate("GB", "NIDN", "AB123456C")

# Auto-detect ID type
detected_type = id_format_manager.validate_any_type("GB", "AB123456C")
print(detected_type)  # "NIDN"

# Get supported types for country
types = id_format_manager.get_id_types_for_country("GB")
print(types)  # ["NIDN", "CONCAT"]

# Validate LEI (country-independent)
is_valid_lei = id_format_manager.validate_lei("ABCDEFGHIJKLMNOPQR12")
```

### Validation

#### `validators.py`

Core validation functions:

- **`ValidationResult`**: Result object with success/failure and corrected value
- Date validators: `validate_date_format`, `validate_date_range`, `validate_date_not_future`
- String validators: `validate_not_empty`, `validate_length`, `validate_pattern`, `validate_alphanumeric`
- Numeric validators: `validate_numeric_range`, `validate_positive`, `validate_non_negative`
- Choice validators: `validate_in_list`
- Combined validators: `validate_all`, `validate_any`
- Special field validators: `validate_gender`, `validate_email`, `validate_phone`

```python
from txr_replay_core.validators import validate_date_format, validate_not_empty, validate_in_list

# Date validation
result = validate_date_format("2024-01-15")
if result.is_valid:
    print(result.corrected_value)  # date(2024, 1, 15)

# String validation
result = validate_not_empty("  Hello  ")
print(result.corrected_value)  # "Hello" (trimmed)

# Choice validation
result = validate_in_list("red", ["RED", "GREEN", "BLUE"], case_sensitive=False)
print(result.corrected_value)  # "RED" (normalized)
```

#### `id_validation.py`

High-level ID validation combining country codes, formats, and validators:

- **`IDType`**: Enum for ID types (NIDN, CONCAT, CCPT, LEI)
- **`IDValidationResult`**: Comprehensive validation result
- **`IDValidator`**: High-level validator
- **`id_validator`**: Pre-instantiated singleton
- Convenience functions: `validate_id`, `validate_id_auto`, `validate_lei`

```python
from txr_replay_core import validate_id, validate_id_auto, validate_lei

# Validate with known type
result = validate_id("GB", "NIDN", "AB123456C")
if result.is_valid:
    print("Valid ID")
else:
    print(result.primary_error)

# Auto-detect type
result = validate_id_auto("GB", "AB123456C")
print(result.detected_type)  # "NIDN"

# Validate LEI
result = validate_lei("ABCDEFGHIJKLMNOPQR12")
```

### CSV Utilities

#### `csv_utils.py`

CSV file operations with schema validation:

- **`ColumnType`**: Enum for column data types
- **`ColumnDefinition`**: Column schema definition
- **`CSVSchema`**: Complete CSV schema
- **`CSVReader`**: Enhanced CSV reader with validation
- **`CSVWriter`**: Enhanced CSV writer
- **`CSVValidationError`**: Validation exception

```python
from txr_replay_core.csv_utils import CSVSchema, ColumnDefinition, ColumnType, CSVReader

# Define schema
schema = CSVSchema(
    name="MyData",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Amount", ColumnType.FLOAT, required=True),
        ColumnDefinition("Date", ColumnType.DATE, nullable=True),
    ]
)

# Read with validation
reader = CSVReader(schema)
df = reader.read_file("input.csv", validate=True)
```

#### `schema.py`

Predefined CSV schemas for transaction reporting:

- **11+ predefined schemas** for common file formats
- **`SCHEMA_REGISTRY`**: Central registry of all schemas
- Functions: `get_schema()`, `list_schemas()`

```python
from txr_replay_core.schema import get_schema, list_schemas

# Get predefined schema
schema = get_schema("buyer_id_validation")

# List all available schemas
all_schemas = list_schemas()
print(all_schemas)  # ["buyer_id_validation", "seller_id_validation", ...]
```

### Configuration & Logging

#### `config.py`

Configuration management:

- **`PathConfig`**: File path configuration
- **`ProcessorConfig`**: Processor behavior configuration
- **`ConfigManager`**: Load from YAML files and environment variables

```python
from txr_replay_core.config import ConfigManager

# Load from YAML file
config = ConfigManager.load_from_yaml("config/phase2.yaml")

# Create path configuration
path_config = ConfigManager.get_path_config(config)
print(path_config.replay_input)
```

#### `logger.py`

Logging infrastructure:

- **`StructuredLogger`**: Unified logging with file and console output
- **`create_logger()`**: Factory function for creating loggers

```python
from txr_replay_core.logger import create_logger

# Create logger
logger = create_logger("my_processor", "./logs", "INFO")

# Log messages
logger.info("Processing started")
logger.debug("Debug information", extra={"row": 42})
```

### Utilities

#### `utils.py`

Utility functions:

- **`DateParser`**: Date parsing with caching (supports multiple formats)
- **`CharacterReplacement`**: Special character replacements (colon ↔ NOT SIGN)
- **`FileDiscovery`**: File discovery with glob patterns
- **`safe_open_csv`**: Safe CSV file opening with encoding handling

```python
from txr_replay_core import DateParser

# Parse various date formats
date1 = DateParser.parse_date("01/12/2023")  # Returns: '2023-12-01'
date2 = DateParser.parse_date("2023-12-01")  # Returns: '2023-12-01'

# Cache is used automatically for performance
print(DateParser.cache_size())  # Number of cached dates
```

#### `incident_codes.py`

Incident code matrix and utilities:

- **`INCIDENT_CODE_MATRIX`**: Complete incident code definitions
- Functions: `get_client_types()`, `is_buyer_incident()`, `is_seller_incident()`

```python
from txr_replay_core import is_buyer_incident, get_all_incident_codes

# Check if incident code is buyer-related
if is_buyer_incident("7_35"):
    print("This is a buyer incident")

# Get all incident codes
all_codes = get_all_incident_codes()
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/test_core/

# Run specific test file
pytest tests/test_core/test_country_codes.py

# Run with coverage
pytest tests/test_core/ --cov=src/txr_replay_core --cov-report=html
```

## Key Features

### ✅ **No External CSV Dependencies**
- Country codes and ID formats are embedded as Python data
- Eliminates file path issues and simplifies deployment
- Data versioned with code

### ✅ **Singleton Managers with O(1) Lookups**
- `CountryDataManager` and `IDFormatManager` use singleton pattern
- Pre-compiled regex patterns cached in memory
- Hash-based lookups for instant access

### ✅ **Comprehensive Validation Framework**
- Composable validators with consistent API
- Type-safe with full type hints
- Detailed error messages and correction suggestions

### ✅ **CSV Schema Validation**
- Define schemas once, reuse across scripts
- Automatic column validation and type checking
- Registry of predefined schemas for common formats

### ✅ **Production-Ready**
- Fully tested with pytest (90%+ coverage)
- Comprehensive error handling
- Structured logging throughout
stats.successful_matches = 95
logger.log_stats(stats)

# Log structured data
logger.log_dict({"input_files": 5, "output_files": 5}, "File Summary")
```

### Data Structures

```python
from txr_replay_core import ReplayRecord, LookupResult, ProcessingStats

# Create replay record
record = ReplayRecord(
    record_type='phase2',
    transaction_reference='ABC123',
    incident_codes=['7_35', '7_37']
)

# Create lookup result
result = LookupResult(
    found=True,
    correction="New Value",
    correction_field="Field Name",
    match_type="id_buyer"
)

# Track statistics
stats = ProcessingStats()
stats.increment('processed_records')
stats.increment('successful_matches')
print(stats.to_dict())
```

## Configuration File Format

### YAML Configuration Example

```yaml
# config/phase2.yaml
paths:
  replay_input: /path/to/replay/input
  incident_files: /path/to/incident/files
  replay_output: /path/to/output
  log_output: /path/to/logs

processing:
  batch_size: 50
  log_level: INFO
  enable_progress_reporting: true
  encoding: utf-8
```

### Environment Variables

Set environment variables with `TXR_` prefix:

```bash
export TXR_REPLAY_INPUT=/path/to/input
export TXR_INCIDENT_FILES=/path/to/incident
export TXR_REPLAY_OUTPUT=/path/to/output
export TXR_LOG_OUTPUT=/path/to/logs
export TXR_LOG_LEVEL=DEBUG
export TXR_BATCH_SIZE=100
```

## Testing

```bash
# Run tests
pytest tests/test_core/

# Run specific test file
pytest tests/test_core/test_date_parser.py

# Run with coverage
pytest tests/test_core/ --cov=txr_replay_core --cov-report=html
```

## Development

### Adding New Utilities

1. Add the utility function/class to the appropriate module
2. Update `__init__.py` to export it
3. Add unit tests in `tests/test_core/`
4. Update this README with usage examples

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Write docstrings for all public functions/classes
- Add examples in docstrings where helpful

## Version History

- **1.0.0** (2025-12-22): Initial release
  - DateParser with caching
  - Configuration management
  - Structured logging
  - Common data structures
  - Character replacement utilities
  - File discovery utilities
