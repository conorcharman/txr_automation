#!/usr/bin/env python3
"""Test backup directory configuration."""

from pathlib import Path

from src.accuracy_testing.models.data_push_record import DataPushConfig
from src.accuracy_testing.validators.data_push_processor import DataPushProcessor

# Create config with backup_dir
config = DataPushConfig(
    backup_dir=Path(
        r"C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\backups"
    )
)

print(f"Config backup_dir: {config.backup_dir}")

# Create processor
processor = DataPushProcessor(config=config)

# Test create_backup with a known file
test_file = Path(
    r"c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_37.csv"
)

if test_file.exists():
    print(f"\nTest file exists: {test_file}")
    print(f"Creating backup...")

    backup_path = processor.create_backup(test_file)

    if backup_path:
        print(f"✓ Backup created: {backup_path}")
        print(f"  Backup directory: {backup_path.parent}")
        print(f"  Expected directory: {config.backup_dir}")
        print(f"  Match: {backup_path.parent == config.backup_dir}")

        # Clean up test backup
        if backup_path.exists():
            backup_path.unlink()
            print(f"\n  Test backup deleted")
    else:
        print("✗ Backup creation failed")
else:
    print(f"✗ Test file not found: {test_file}")
