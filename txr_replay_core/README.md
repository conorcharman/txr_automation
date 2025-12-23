# TXR Replay Core Library

Shared utilities and core functionality for transaction replay processing scripts.

## Overview

The `txr_replay_core` package provides common functionality used across all replay processing scripts, eliminating code duplication and ensuring consistency.

## Installation

```bash
# From the project root directory
pip install -e .
```

## Modules

### `data_structures.py`

Common dataclasses for replay processing:

- **`ReplayRecord`**: Universal replay record structure
- **`LookupResult`**: Result of transaction/client lookups
- **`UnaVistaTransaction`**: UnaVista transaction record
- **`ProcessingStats`**: Standardized statistics tracking

### `utils.py`

Utility functions:

- **`DateParser`**: Date parsing with caching (supports multiple formats)
- **`CharacterReplacement`**: Special character replacements (colon ↔ NOT SIGN)
- **`FileDiscovery`**: File discovery with glob patterns

### `config.py`

Configuration management:

- **`PathConfig`**: File path configuration
- **`ProcessorConfig`**: Processor behavior configuration
- **`ConfigManager`**: Load from YAML files and environment variables

### `logger.py`

Logging infrastructure:

- **`StructuredLogger`**: Unified logging with file and console output
- **`create_logger()`**: Factory function for creating loggers

## Usage Examples

### Date Parsing

```python
from txr_replay_core import DateParser

# Parse various date formats
date1 = DateParser.parse_date("01/12/2023")  # Returns: '2023-12-01'
date2 = DateParser.parse_date("2023-12-01")  # Returns: '2023-12-01'
date3 = DateParser.parse_date("01/12/2023 14:30:00")  # Returns: '2023-12-01'

# Cache is used automatically for performance
print(DateParser.cache_size())  # Number of cached dates
```

### Configuration Management

```python
from txr_replay_core.config import ConfigManager

# Load from YAML file
config = ConfigManager.load_from_yaml("config/phase2.yaml")

# Load from environment variables
env_config = ConfigManager.load_from_env("TXR_")

# Merge configurations (env overrides YAML)
merged = ConfigManager.merge_configs(config, env_config)

# Create path configuration
path_config = ConfigManager.get_path_config(merged)
print(path_config.replay_input)
```

### Logging

```python
from txr_replay_core.logger import create_logger
from txr_replay_core.data_structures import ProcessingStats

# Create logger
logger = create_logger("my_processor", "./logs", "INFO")

# Log messages
logger.info("Processing started")
logger.debug("Debug information", extra={"row": 42})

# Log statistics
stats = ProcessingStats()
stats.processed_records = 100
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
