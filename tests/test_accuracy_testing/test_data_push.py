"""
Data Push Tests
===============

Comprehensive test suite for Data Push functionality.

Tests cover:
    - DataPushRecord model
    - Column mapping
    - DataPushProcessor matching and push logic
    - Backup and write operations
    - Batch processing

Migrated from: DataPush1_0.vb
"""

import pytest
import csv
from pathlib import Path
from typing import Dict
import tempfile
import shutil

from src.accuracy_testing.models.data_push_record import (
    DataPushRecord,
    DataPushConfig,
    PushStats,
    PushAction,
    ColumnMapping,
    DEFAULT_COLUMN_MAPPINGS,
)
from src.accuracy_testing.validators.data_push_processor import (
    DataPushProcessor,
    BatchDataPushProcessor,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_source_data() -> list:
    """Sample source data rows."""
    return [
        {
            "Transaction Reference": "TXN001",
            "Account ID": "A12345678",
            "ID Value": "549300CLIENT00000001",
            "Error": "Y",
            "Correction": "549300CORRECT0000001",
            "Correction Field": "ID Value",
            "ID Type": "LEI",
            "Notes": "Corrected from invalid format",
        },
        {
            "Transaction Reference": "TXN002",
            "Account ID": "B98765432",
            "ID Value": "AB123456C",
            "Error": "N",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "NIDN",
            "Notes": "",
        },
        {
            "Transaction Reference": "TXN003",
            "Account ID": "X11111111",
            "ID Value": "",
            "Error": "Y",
            "Correction": "549300MANAGER0000001",
            "Correction Field": "ID Value",
            "ID Type": "LEI",
            "Notes": "Missing ID",
        },
        {
            "Transaction Reference": "TXN004",
            "Account ID": "C22222222",
            "ID Value": "TEST123",
            "Error": "TBC",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "",
            "Notes": "Needs investigation",
        },
    ]


@pytest.fixture
def sample_target_data() -> list:
    """Sample target data rows."""
    return [
        {
            "Transaction Reference": "TXN001",
            "Account ID": "",
            "ID Value": "",
            "Error": "",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "",
            "Notes": "",
            "Extra Column": "extra1",
        },
        {
            "Transaction Reference": "TXN002",
            "Account ID": "",
            "ID Value": "",
            "Error": "",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "",
            "Notes": "",
            "Extra Column": "extra2",
        },
        {
            "Transaction Reference": "TXN003",
            "Account ID": "",
            "ID Value": "",
            "Error": "",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "",
            "Notes": "",
            "Extra Column": "extra3",
        },
        {
            "Transaction Reference": "TXN999",
            "Account ID": "OLD",
            "ID Value": "OLD_VALUE",
            "Error": "Y",
            "Correction": "",
            "Correction Field": "",
            "ID Type": "",
            "Notes": "",
            "Extra Column": "extra999",
        },
    ]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def source_csv_file(temp_dir, sample_source_data) -> Path:
    """Create a temporary source CSV file."""
    path = temp_dir / "source.csv"
    
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sample_source_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_source_data)
    
    return path


@pytest.fixture
def target_csv_file(temp_dir, sample_target_data) -> Path:
    """Create a temporary target CSV file."""
    path = temp_dir / "target.csv"
    
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sample_target_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_target_data)
    
    return path


@pytest.fixture
def column_mappings() -> list:
    """Simple column mappings for testing."""
    return [
        ColumnMapping("Account ID", "Account ID", "Account"),
        ColumnMapping("ID Value", "ID Value", "ID"),
        ColumnMapping("Error", "Error", "Error flag"),
        ColumnMapping("Correction", "Correction", "Correction value"),
        ColumnMapping("Correction Field", "Correction Field", "Field"),
        ColumnMapping("ID Type", "ID Type", "Type"),
        ColumnMapping("Notes", "Notes", "Notes"),
    ]


# =============================================================================
# Test: DataPushRecord Model
# =============================================================================

class TestDataPushRecord:
    """Tests for DataPushRecord dataclass."""
    
    def test_from_dict_error_y(self, sample_source_data):
        """Test creating record with Error = Y."""
        record = DataPushRecord.from_dict(sample_source_data[0])
        
        assert record.transaction_ref == "TXN001"
        assert record.error_flag == "Y"
        assert record.action == PushAction.UPDATE_ALL
        assert record.is_valid is True
        assert record.should_push is True
    
    def test_from_dict_error_n(self, sample_source_data):
        """Test creating record with Error = N - should push all fields."""
        record = DataPushRecord.from_dict(sample_source_data[1])
        
        assert record.transaction_ref == "TXN002"
        assert record.error_flag == "N"
        # Changed: Now all records are pushed (UPDATE_ALL for QA purposes)
        assert record.action == PushAction.UPDATE_ALL
        assert record.should_push is True
    
    def test_from_dict_error_tbc(self, sample_source_data):
        """Test creating record with Error = TBC - should push all fields."""
        record = DataPushRecord.from_dict(sample_source_data[3])
        
        assert record.transaction_ref == "TXN004"
        assert record.error_flag == "TBC"
        # Changed: Now all records are pushed (UPDATE_ALL for QA purposes)
        assert record.action == PushAction.UPDATE_ALL
        assert record.should_push is True
    
    def test_from_dict_empty_transaction_ref(self):
        """Test record with empty transaction reference is invalid."""
        data = {"Transaction Reference": "", "Error": "Y"}
        record = DataPushRecord.from_dict(data)
        
        assert record.is_valid is False
    
    def test_get_push_values_update_all(self, sample_source_data, column_mappings):
        """Test getting push values for UPDATE_ALL action."""
        record = DataPushRecord.from_dict(sample_source_data[0])
        
        values = record.get_push_values(column_mappings)
        
        assert "Account ID" in values
        assert values["Account ID"] == "A12345678"
        assert values["ID Value"] == "549300CLIENT00000001"
        assert values["Correction"] == "549300CORRECT0000001"
    
    def test_get_push_values_error_n_without_correction_value(self, sample_source_data, column_mappings):
        """Test that all fields including empty Correction are pushed when Error=N and no correction value."""
        # TXN002 has Error="N" and empty Correction
        record = DataPushRecord.from_dict(sample_source_data[1])
        
        values = record.get_push_values(column_mappings)
        
        # Should push all fields including empty Correction fields
        assert "Account ID" in values
        assert "Error" in values
        assert values["Error"] == "N"
        assert "Correction" in values  # Empty correction should be pushed
        assert values["Correction"] == ""
        assert "Correction Field" in values
        assert values["Correction Field"] == ""
    
    def test_get_push_values_error_n_with_correction(self, column_mappings):
        """Test that Correction fields are NOT pushed when Error=N and correction exists."""
        # Create a record with Error="N" but has a correction value
        data = {
            "Transaction Reference": "TXN005",
            "Account ID": "C33333333",
            "ID Value": "AB123456C",
            "Error": "N",
            "Correction": "AB123456D",  # Has correction but Error is N
            "Correction Field": "ID Value",
            "ID Type": "NIDN",
        }
        record = DataPushRecord.from_dict(data)
        
        values = record.get_push_values(column_mappings)
        
        # Should push all fields EXCEPT Correction and Correction Field
        assert "Account ID" in values
        assert values["Account ID"] == "C33333333"
        assert "ID Value" in values
        assert values["ID Value"] == "AB123456C"
        assert "ID Type" in values
        assert values["ID Type"] == "NIDN"
        assert "Error" in values
        assert values["Error"] == "N"
        
        # These should NOT be in the pushed values
        assert "Correction" not in values
        assert "Correction Field" not in values
    
    def test_get_push_values_error_y_with_correction(self, sample_source_data, column_mappings):
        """Test that Correction fields ARE pushed when Error=Y."""
        record = DataPushRecord.from_dict(sample_source_data[0])  # Error="Y" with correction
        
        values = record.get_push_values(column_mappings)
        
        # Should push ALL fields including Correction
        assert "Correction" in values
        assert values["Correction"] == "549300CORRECT0000001"
        assert "Correction Field" in values
        assert values["Correction Field"] == "ID Value"
    
    def test_get_push_values_error_n_no_correction(self, column_mappings):
        """Test that empty Correction fields ARE pushed when Error=N and no correction."""
        data = {
            "Transaction Reference": "TXN006",
            "Account ID": "D44444444",
            "ID Value": "VALID123",
            "Error": "N",
            "Correction": "",  # No correction
            "Correction Field": "",
            "ID Type": "CONCAT",
        }
        record = DataPushRecord.from_dict(data)
        
        values = record.get_push_values(column_mappings)
        
        # Should push all fields including empty Correction fields (no correction exists)
        assert "Correction" in values
        assert values["Correction"] == ""
        assert "Correction Field" in values
        assert values["Correction Field"] == ""
    
    def test_was_matched_property(self):
        """Test was_matched property."""
        record = DataPushRecord(
            transaction_ref="TEST",
            error_flag="Y",
            target_row_index=-1,
        )
        assert record.was_matched is False
        
        record.target_row_index = 5
        assert record.was_matched is True


# =============================================================================
# Test: ColumnMapping
# =============================================================================

class TestColumnMapping:
    """Tests for ColumnMapping dataclass."""
    
    def test_create_mapping(self):
        """Test creating a column mapping."""
        mapping = ColumnMapping(
            source_col="Source Column",
            target_col="Target Column",
            description="Test mapping",
        )
        
        assert mapping.source_col == "Source Column"
        assert mapping.target_col == "Target Column"
        assert mapping.description == "Test mapping"
    
    def test_mapping_validation_empty_source(self):
        """Test that empty source column raises error."""
        with pytest.raises(ValueError, match="source_col"):
            ColumnMapping(source_col="", target_col="Target")
    
    def test_mapping_validation_empty_target(self):
        """Test that empty target column raises error."""
        with pytest.raises(ValueError, match="target_col"):
            ColumnMapping(source_col="Source", target_col="")


# =============================================================================
# Test: PushStats
# =============================================================================

class TestPushStats:
    """Tests for PushStats dataclass."""
    
    def test_default_values(self):
        """Test default stat values."""
        stats = PushStats()
        
        assert stats.total_source == 0
        assert stats.matched == 0
        assert stats.not_found == 0
        assert stats.updated_all == 0
        assert stats.updated_error_only == 0
        assert stats.skipped == 0
        assert stats.errors == 0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = PushStats(total_source=100, matched=75)
        
        assert stats.success_rate == 75.0
    
    def test_success_rate_zero_total(self):
        """Test success rate with zero total."""
        stats = PushStats(total_source=0, matched=0)
        
        assert stats.success_rate == 0.0
    
    def test_as_dict(self):
        """Test conversion to dictionary."""
        stats = PushStats(
            total_source=100,
            matched=80,
            not_found=20,
            updated_all=50,
            updated_error_only=30,
            skipped=0,
            errors=0,
        )
        
        d = stats.as_dict()
        
        assert d["total_source"] == 100
        assert d["matched"] == 80
        assert d["updated_all"] == 50


# =============================================================================
# Test: DataPushConfig
# =============================================================================

class TestDataPushConfig:
    """Tests for DataPushConfig dataclass."""
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "testing_period": {
                "fiscal_year": "FY26",
                "quarter": "Q1",
            },
            "incident": {
                "code": "7_37",
            },
            "paths": {
                "source_file": "source.csv",
                "target_file": "target.csv",
            },
            "column_mappings": [
                {"source": "Error", "target": "Error", "description": "Error flag"},
            ],
            "options": {
                "dry_run": True,
                "backup": False,
            },
        }
        
        config = DataPushConfig.from_dict(config_dict)
        
        assert config.fiscal_year == "FY26"
        assert config.quarter == "Q1"
        assert config.incident_code == "7_37"
        assert config.dry_run is True
        assert config.backup is False
        assert len(config.column_mappings) == 1


# =============================================================================
# Test: DataPushProcessor
# =============================================================================

class TestDataPushProcessor:
    """Tests for DataPushProcessor."""
    
    def test_load_source(self, source_csv_file, column_mappings):
        """Test loading source CSV file."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        count = processor.load_source(source_csv_file)
        
        assert count == 4
        assert processor.stats.total_source == 4
    
    def test_load_target(self, target_csv_file, column_mappings):
        """Test loading target CSV file."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        count = processor.load_target(target_csv_file)
        
        assert count == 4
        assert len(processor.target_index) == 4
        assert "TXN001" in processor.target_index
        assert "TXN999" in processor.target_index
    
    def test_match_records(self, source_csv_file, target_csv_file, column_mappings):
        """Test matching source records to target rows."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_csv_file)
        processor.load_target(target_csv_file)
        matched, not_found = processor.match_records()
        
        assert matched == 3  # TXN001, TXN002, TXN003
        assert not_found == 1  # TXN004
    
    def test_push_data(self, source_csv_file, target_csv_file, column_mappings):
        """Test pushing data from source to target."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_csv_file)
        processor.load_target(target_csv_file)
        processor.match_records()
        stats = processor.push_data()
        
        # Changed: All matched records now push all fields (UPDATE_ALL)
        # TXN001: Error=Y -> update all
        # TXN002: Error=N -> update all (but skip corrections if present)
        # TXN003: Error=Y -> update all
        # TXN004: not matched
        assert stats.updated_all == 3
        assert stats.updated_error_only == 0
    
    def test_full_process(
        self, 
        source_csv_file, 
        target_csv_file, 
        temp_dir,
        column_mappings
    ):
        """Test full processing pipeline."""
        output_file = temp_dir / "output.csv"
        
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        stats = processor.process(
            source_path=source_csv_file,
            target_path=target_csv_file,
            output_path=output_file,
            dry_run=False,
            backup=False,
        )
        
        assert stats.total_source == 4
        assert stats.matched == 3
        assert output_file.exists()
        
        # Verify output content
        import pandas as pd
        output_df = pd.read_csv(output_file)
        
        # TXN001 should have updated values
        txn001 = output_df[output_df["Transaction Reference"] == "TXN001"].iloc[0]
        assert txn001["Account ID"] == "A12345678"
        assert txn001["Error"] == "Y"
        
        # TXN002 should only have Error updated to N
        txn002 = output_df[output_df["Transaction Reference"] == "TXN002"].iloc[0]
        assert txn002["Error"] == "N"
        
        # TXN999 should be unchanged (not in source)
        txn999 = output_df[output_df["Transaction Reference"] == "TXN999"].iloc[0]
        assert txn999["Account ID"] == "OLD"
    
    def test_dry_run(self, source_csv_file, target_csv_file, column_mappings):
        """Test dry run doesn't modify files."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        # Get original target content
        original_content = target_csv_file.read_text()
        
        stats = processor.process(
            source_path=source_csv_file,
            target_path=target_csv_file,
            dry_run=True,
            backup=False,
        )
        
        # File should be unchanged
        assert target_csv_file.read_text() == original_content
        
        # Stats should still be populated
        assert stats.matched == 3
    
    def test_backup_creation(
        self, 
        source_csv_file, 
        target_csv_file, 
        temp_dir,
        column_mappings
    ):
        """Test backup file creation."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_csv_file)
        processor.load_target(target_csv_file)
        
        backup_path = processor.create_backup(target_csv_file)
        
        assert backup_path is not None
        assert backup_path.exists()
        assert ".backup_" in backup_path.name
    
    def test_get_unmatched_records(
        self, 
        source_csv_file, 
        target_csv_file, 
        column_mappings
    ):
        """Test getting unmatched records."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_csv_file)
        processor.load_target(target_csv_file)
        processor.match_records()
        
        unmatched = processor.get_unmatched_records()
        
        assert len(unmatched) == 1
        assert unmatched[0].transaction_ref == "TXN004"
    
    def test_missing_source_file(self, column_mappings):
        """Test error handling for missing source file."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        with pytest.raises(FileNotFoundError):
            processor.load_source(Path("/nonexistent/source.csv"))
    
    def test_missing_target_file(self, column_mappings):
        """Test error handling for missing target file."""
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        with pytest.raises(FileNotFoundError):
            processor.load_target(Path("/nonexistent/target.csv"))


# =============================================================================
# Test: BatchDataPushProcessor
# =============================================================================

class TestBatchDataPushProcessor:
    """Tests for BatchDataPushProcessor."""

    def test_process_batch_resolves_incident_first_validated_pattern(self, temp_dir):
        """Should resolve source files named incident_FY_Q_validated.csv in batch mode."""
        source_dir = temp_dir / "output"
        target_dir = temp_dir / "templates"
        source_dir.mkdir()
        target_dir.mkdir()

        source_path = source_dir / "7_37_FY26_Q1_validated.csv"
        target_path = target_dir / "FY26 Q1 7_37.csv"

        with open(source_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
            f.write("TXN001,Y\n")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
            f.write("TXN001,\n")

        processor = BatchDataPushProcessor(
            base_source_dir=source_dir,
            base_target_dir=target_dir,
            fiscal_year="FY26",
            quarter="Q1",
        )

        results = processor.process_batch(
            incidents=["7_37"],
            dry_run=True,
            backup=False,
        )

        assert "7_37" in results
        assert results["7_37"].errors == 0
        assert results["7_37"].total_source == 1
        assert results["7_37"].matched == 1


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_source_file(self, temp_dir, column_mappings):
        """Test handling empty source file."""
        # Create empty CSV with just headers
        source_path = temp_dir / "empty_source.csv"
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
        
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        count = processor.load_source(source_path)
        
        assert count == 0
    
    def test_missing_transaction_ref_column(self, temp_dir, column_mappings):
        """Test error when transaction reference column missing."""
        target_path = temp_dir / "no_ref.csv"
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("Other Column,Error\n")
            f.write("value1,Y\n")
        
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        with pytest.raises(ValueError, match="Transaction reference column"):
            processor.load_target(target_path)
    
    def test_whitespace_in_transaction_ref(self, temp_dir, column_mappings):
        """Test that whitespace is stripped from transaction references."""
        source_path = temp_dir / "whitespace_source.csv"
        target_path = temp_dir / "whitespace_target.csv"
        
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
            f.write("  TXN001  ,Y\n")
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
            f.write("TXN001,\n")
        
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_path)
        processor.load_target(target_path)
        matched, _ = processor.match_records()
        
        assert matched == 1
    
    def test_case_sensitive_error_flag(self, temp_dir, column_mappings):
        """Test that error flag is case-insensitive."""
        source_path = temp_dir / "case_source.csv"
        
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("Transaction Reference,Error\n")
            f.write("TXN001,y\n")
            f.write("TXN002,n\n")
            f.write("TXN003,Y\n")
            f.write("TXN004,N\n")
        
        config = DataPushConfig(column_mappings=column_mappings)
        processor = DataPushProcessor(config=config)
        
        processor.load_source(source_path)
        
        # Changed: All records now use UPDATE_ALL action
        # Check actions are correctly determined regardless of case
        actions = [r.action for r in processor.source_records]
        assert actions[0] == PushAction.UPDATE_ALL  # y -> Y
        assert actions[1] == PushAction.UPDATE_ALL  # n -> N (now pushes all)
        assert actions[2] == PushAction.UPDATE_ALL  # Y
        assert actions[3] == PushAction.UPDATE_ALL  # N (now pushes all)


# =============================================================================
# Test: Default Column Mappings
# =============================================================================

class TestDefaultColumnMappings:
    """Tests for default column mappings."""
    
    def test_default_mappings_exist(self):
        """Test that default mappings are defined."""
        assert len(DEFAULT_COLUMN_MAPPINGS) > 0
    
    def test_default_mappings_have_error(self):
        """Test that default mappings include Error column."""
        error_mappings = [
            m for m in DEFAULT_COLUMN_MAPPINGS 
            if m.source_col == "Error"
        ]
        assert len(error_mappings) == 1
    
    def test_processor_uses_defaults(self):
        """Test processor uses default mappings when none provided."""
        config = DataPushConfig()  # No mappings
        processor = DataPushProcessor(config=config)
        
        assert len(processor.config.column_mappings) == len(DEFAULT_COLUMN_MAPPINGS)
