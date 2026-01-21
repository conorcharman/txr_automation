# Quick Start Guide: Using txr_replay_core and Accuracy Testing

This guide shows how to use the `txr_replay_core` library in your scripts and run accuracy testing tools.

## Prerequisites

**Ensure Conda environment is activated:**

```bash
conda activate txr_automation
```

If you haven't set up the environment yet, see [Conda_Setup_Guide.md](Conda_Setup_Guide.md).

## Running Processors

### Console Scripts (Recommended)

The package installs console scripts for easy command-line access:

```bash
# Activate environment first
conda activate txr_automation

# Accuracy Testing
validate-buyer          # Buyer ID validation
validate-seller         # Seller ID validation

# Replay Processors
replay-phase2           # Phase 2 processor
replay-phase3           # Phase 3 processor
replay-phase3-final     # Phase 3 final lookup

# Utilities
replay-xlsx-converter   # XLSX to CSV converter (single directory)
replay-xlsx-converter-v2  # XLSX to CSV converter v2 (recursive with filters)
```

These commands automatically use your local configuration files from `config/local/`.

**Override with custom config:**

```bash
validate-buyer --config config/custom/buyer_validation.yaml
replay-phase2 --config config/custom/phase2.yaml
replay-phase3 --log-level DEBUG
```

### Accuracy Testing Commands

**Buyer ID Validation:**

```bash
# Basic validation
validate-buyer --config config/buyer_validation.yaml

# Preview changes without writing output
validate-buyer --config config/buyer_validation.yaml --dry-run

# Show progress bar during processing (requires tqdm)
validate-buyer --config config/buyer_validation.yaml --progress

# Combine flags
validate-buyer --config config/buyer_validation.yaml --progress --dry-run
```

**Seller ID Validation:**

```bash
# Basic validation
validate-seller --config config/seller_validation.yaml

# With progress bar
validate-seller --config config/seller_validation.yaml --progress
```

**Output Files:**

- Main output: `{output_file}.csv` - All records with validation results
- Errors only: `{output_file}_errors_only.csv` - Only invalid records for easy review

**XLSX Converter v2 - Enhanced Features:**

```bash
# Convert all FY25 Q3 data across all phases
replay-xlsx-converter-v2 --parent-dir C:/Data/txr_replay_automation \
                         --filter-year FY25 --filter-quarter Q3

# Preview what would be converted (dry run)
replay-xlsx-converter-v2 --parent-dir C:/Data/txr_replay_automation --dry-run

# Convert specific phases only
replay-xlsx-converter-v2 --parent-dir C:/Data/txr_replay_automation \
                         --filter-phase phase_ii phase_iii

# Force overwrite existing CSV files
replay-xlsx-converter-v2 --parent-dir C:/Data/txr_replay_automation --force
```

### Alternative: Run as Module

You can also run scripts directly as Python modules:

```bash
# Accuracy Testing
python -m src.accuracy_testing.scripts.buyer_id_validation
python -m src.accuracy_testing.scripts.seller_id_validation

# Replay
python -m src.replay.phase_2_processor
python -m src.replay.phase_3_processor
python -m src.replay.phase_3_final_lookup

# Utilities
python -m src.utils.xlsx_csv_converter
```

## Basic Usage

### 1. Import the Library

```python
from txr_replay_core import (
    ReplayRecord,
    LookupResult,
    UnaVistaTransaction,
    ProcessingStats,
    DateParser,
    CharacterReplacement,
    FileDiscovery,
)
from txr_replay_core.config import ConfigManager
from txr_replay_core.logger import create_logger
```

### 2. Set Up Configuration

#### YAML File

```python
# Load configuration from YAML
config = ConfigManager.load_from_yaml("config/phase2.yaml")

# Create typed configurations
path_config = ConfigManager.get_path_config(config)
proc_config = ConfigManager.get_processor_config(config)

print(path_config.replay_input)  # /path/to/replay/input
print(proc_config.batch_size)     # 50
```

#### Option B: Using Environment Variables

```python
# Load from environment (TXR_* variables)
env_config = ConfigManager.load_from_env("TXR_")

# Create typed configurations
path_config = ConfigManager.get_path_config(env_config)
proc_config = ConfigManager.get_processor_config(env_config)
```

#### Option C: Hybrid Approach (Recommended)

```python
# Load both and merge (env overrides YAML)
yaml_config = ConfigManager.load_from_yaml("config/phase2.yaml")
env_config = ConfigManager.load_from_env("TXR_")
merged = ConfigManager.merge_configs(yaml_config, env_config)

# Create typed configurations
path_config = ConfigManager.get_path_config(merged)
proc_config = ConfigManager.get_processor_config(merged)
```

### 3. Set Up Logging

```python
# Create logger
logger = create_logger(
    name="phase2_processor",
    log_dir=path_config.log_output,
    log_level=proc_config.log_level
)

# Log messages
logger.info("Processing started")
logger.debug("Debug information", extra={"row": 42})

# Log section headers
logger.log_header("Phase 2 Processing")
logger.log_section("Loading incident files")
```

### 4. Parse Dates

```python
# DateParser handles multiple formats automatically
dob = DateParser.parse_date("01/12/1984")  # Returns: '1984-12-01'
dob = DateParser.parse_date("1984-12-01")  # Returns: '1984-12-01'
dob = DateParser.parse_date("01/12/1984 00:00:00")  # Returns: '1984-12-01'

# Check cache performance
print(f"Cache size: {DateParser.cache_size()}")
```

### 5. Track Statistics

```python
# Create stats tracker
stats = ProcessingStats()

# Increment standard statistics
stats.increment('processed_records')
stats.increment('successful_matches')
stats.increment('not_found')

# Increment custom statistics
stats.increment('joint_accounts', 5)
stats.increment('swedish_ids', 3)

# Log statistics
logger.log_stats(stats)

# Convert to dictionary
stats_dict = stats.to_dict()
print(stats_dict)
```

### 6. Use Data Structures

```python
# Create a replay record
record = ReplayRecord(
    record_type='phase2',
    transaction_reference='ABC123456',
    incident_codes=['7_35', '7_37'],
    original_row=['ABC123456', 'Field1', 'Field2'],
    row_index=42,
    source_file='replay_file.csv'
)

# Create a lookup result
result = LookupResult(
    found=True,
    correction="New Value",
    correction_field="Field Name",
    match_type="id_buyer"
)

# Create UnaVista transaction
txn = UnaVistaTransaction(
    transaction_ref='ABC123456',
    row_data=['ABC123456', 'Data1', 'Data2'],
    row_index=100
)

# Safely get field
value = txn.get_field(1, default="N/A")  # Returns 'Data1'
```

### 7. Character Replacement

```python
# Phase 2 processing: Replace colons with NOT SIGN
correction = "Field:Value:123"
safe_correction = CharacterReplacement.colon_to_not_sign(correction)
# Result: "Field¬Value¬123"

# Reverse when needed
original = CharacterReplacement.not_sign_to_colon(safe_correction)
# Result: "Field:Value:123"

# Special markers are preserved
result = CharacterReplacement.colon_to_not_sign("No Change")
# Result: "No Change" (unchanged)
```

### 8. File Discovery

```python
# Find most recent file matching pattern
latest_unavista = FileDiscovery.find_latest_file(
    directory="/path/to/files",
    pattern="UnaVista_*.csv"
)

# Find all matching files
all_replay_files = FileDiscovery.find_all_files(
    directory="/path/to/replay",
    pattern="*_Phase2_*.csv"
)

# Ensure output directory exists
FileDiscovery.ensure_directory_exists("/path/to/output")
```

## Complete Example Script

```python
#!/usr/bin/env python3
"""
Example: Phase 2 Processor using txr_replay_core
"""

import csv
from txr_replay_core import (
    ReplayRecord,
    ProcessingStats,
    DateParser,
)
from txr_replay_core.config import ConfigManager
from txr_replay_core.logger import create_logger


def main():
    # Load configuration
    config = ConfigManager.load_from_yaml("config/phase2.yaml")
    path_config = ConfigManager.get_path_config(config)
    proc_config = ConfigManager.get_processor_config(config)
    
    # Set up logging
    logger = create_logger(
        name="phase2_example",
        log_dir=path_config.log_output,
        log_level=proc_config.log_level
    )
    
    logger.log_header("Phase 2 Processing Example")
    logger.info(f"Input directory: {path_config.replay_input}")
    logger.info(f"Output directory: {path_config.replay_output}")
    
    # Initialize statistics
    stats = ProcessingStats()
    
    # Process replay files
    logger.log_section("Processing Replay Files")
    
    # Example: Read a CSV file
    replay_file = f"{path_config.replay_input}/example_replay.csv"
    
    try:
        with open(replay_file, 'r', encoding=proc_config.encoding) as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header
            
            for idx, row in enumerate(reader, start=1):
                # Create replay record
                record = ReplayRecord(
                    record_type='phase2',
                    transaction_reference=row[0],
                    original_row=row,
                    row_index=idx,
                    source_file=replay_file
                )
                
                # Parse date if present
                if len(row) > 5 and row[5]:
                    parsed_dob = DateParser.parse_date(row[5])
                    logger.debug(f"Parsed DOB: {row[5]} -> {parsed_dob}")
                
                # Process record (your logic here)
                # ...
                
                stats.increment('processed_records')
                
                # Progress reporting
                if idx % proc_config.batch_size == 0:
                    logger.info(f"Processed {idx} records...")
        
        stats.processed_files = 1
        logger.log_section("Processing Complete")
        logger.log_stats(stats)
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        stats.increment('errors')
    
    return stats


if __name__ == "__main__":
    main()
```

## CLI Interface Pattern

Here's how to add a CLI interface to your script:

```python
#!/usr/bin/env python3
import argparse
from txr_replay_core.config import ConfigManager


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Phase 2 Replay Processor',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='Override replay input directory'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Override replay output directory'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def main():
    # Parse arguments
    args = parse_arguments()
    
    # Load configuration
    if args.config:
        config = ConfigManager.load_from_yaml(args.config)
    else:
        # Use defaults or environment variables
        config = ConfigManager.load_from_env("TXR_")
    
    # Override with CLI arguments
    if args.input:
        config['paths']['replay_input'] = args.input
    if args.output:
        config['paths']['replay_output'] = args.output
    if args.log_level:
        config['processing']['log_level'] = args.log_level
    
    # Get typed configurations
    path_config = ConfigManager.get_path_config(config)
    proc_config = ConfigManager.get_processor_config(config)
    
    # Your processing logic here
    # ...


if __name__ == "__main__":
    main()
```

## Testing Your Script

```python
# tests/test_integration/test_phase2_example.py

import pytest
from txr_replay_core import ProcessingStats
from your_script import main  # Import your main function


def test_phase2_processing(tmp_path):
    """Test Phase 2 processing with sample data"""
    # Create test configuration
    config = {
        'paths': {
            'replay_input': str(tmp_path / 'input'),
            'incident_files': str(tmp_path / 'incident'),
            'replay_output': str(tmp_path / 'output'),
            'log_output': str(tmp_path / 'logs'),
        },
        'processing': {
            'batch_size': 10,
            'log_level': 'DEBUG',
        }
    }
    
    # Create test files
    # ... create sample CSV files ...
    
    # Run processing
    stats = main(config)
    
    # Assert results
    assert stats.processed_records > 0
    assert stats.errors == 0
```

## Tips and Best Practices

1. **Always use ConfigManager**: Never hardcode paths
2. **Use structured logging**: Helps with debugging and monitoring
3. **Track statistics**: Makes it easy to report progress
4. **Cache date parsing**: DateParser caching improves performance significantly
5. **Validate configurations**: ProcessorConfig validates on creation
6. **Use type hints**: Makes code more maintainable
7. **Write tests**: Use pytest fixtures and the test utilities

## Next Steps

- Read [txr_replay_core/README.md](../txr_replay_core/README.md) for detailed API documentation
- See [Phase_0_Progress.md](Phase_0_Progress.md) for refactoring progress
- Check existing tests in `tests/test_core/` for more examples
