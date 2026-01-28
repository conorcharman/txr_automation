#!/usr/bin/env python3
"""
End-to-End Accuracy Testing Workflow Tests
===========================================

Tests the complete accuracy testing pipeline:
1. Template generation (consolidated data → templates)
2. Validation (templates → validated output)
3. Data push (validated output → master tracking)

These tests use synthetic data to verify the full workflow without
requiring actual production files.
"""

import csv
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

# Import processors
from accuracy_testing.accuracy_template_generator import (
    AccuracyTemplateGenerator,
    TemplateFormat,
)
from accuracy_testing.scripts.buyer_id_validation import BuyerIDValidator
from accuracy_testing.validators.data_push_processor import DataPushProcessor
from accuracy_testing.models.data_push_record import (
    DataPushConfig,
    ColumnMapping,
)


class TestAccuracyWorkflowEndToEnd:
    """End-to-end tests for the accuracy testing workflow."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_consolidated_data(self, temp_dir: Path) -> Path:
        """Create sample consolidated errors/queries CSV."""
        csv_path = temp_dir / "consolidated_errors.csv"
        
        # Columns expected by AccuracyTemplateGenerator
        header = [
            "Transaction reference number",
            "Account ID",
            "Person Code",
            "Incident Code",
            "Error Description",
            "Query Status",
        ]
        
        rows = [
            ["TXN001", "A12345678", "PC001", "7_37", "Invalid buyer ID", "Open"],
            ["TXN002", "B98765432", "PC002", "7_37", "Missing ID type", "Open"],
            ["TXN003", "C11111111", "PC003", "7_35", "Format error", "Open"],
            ["TXN004", "D22222222", "PC004", "16_19", "Seller ID issue", "Open"],
        ]
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        
        return csv_path

    @pytest.fixture
    def sample_template_file(self, temp_dir: Path) -> Path:
        """Create a sample template file for validation."""
        csv_path = temp_dir / "FY26 Q1 - 7_37.csv"
        
        # Template format columns (buyer validation)
        header = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Buyer ID Code",
            "Type of Buyer ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",
            "Correction Fields",
            "Tracker Status",
        ]
        
        rows = [
            ["TXN001", "A12345678", "PC001", "549300VALIDLEI0001", "LEI",
             "John", "Smith", "1990-01-15", "M", "GB", "", "", "", ""],
            ["TXN002", "B98765432", "PC002", "AB123456C", "NIDN",
             "Jane", "Doe", "1985-06-20", "F", "GB", "", "", "", ""],
            ["TXN003", "C11111111", "PC003", "", "",
             "Bob", "Wilson", "1975-03-10", "M", "DE", "GB", "", "", ""],
        ]
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        
        return csv_path

    @pytest.fixture
    def sample_validation_output(self, temp_dir: Path) -> Path:
        """Create sample validation output for data push testing."""
        csv_path = temp_dir / "validated_output.csv"
        
        header = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Account Type",
            "Buyer ID Code",
            "Type of Buyer ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",
            "Correction Fields",
            "Tracker Status",
            "Pass/Fail",
            "Failure Reason",
            "Actions Taken",
            "Error",
            "Kaizen Error",
            "Match",
        ]
        
        rows = [
            ["TXN001", "A12345678", "PC001", "APTS", "549300VALIDLEI0001", "LEI",
             "John", "Smith", "1990-01-15", "M", "GB", "",
             "", "", "Resolved", "PASS", "", "", "N", "", "TRUE"],
            ["TXN002", "B98765432", "PC002", "AETS", "AB123456C", "NIDN",
             "Jane", "Doe", "1985-06-20", "F", "GB", "",
             "549300CORRECTED01:LEI", "ID:IDT", "", "FAIL", "Invalid checksum", "",
             "Y", "549300CORRECTED01:LEI", "FALSE"],
            ["TXN003", "C11111111", "PC003", "APTS", "", "",
             "Bob", "Wilson", "1975-03-10", "M", "DE", "GB",
             "549300MANAGER0001:LEI", "ID:IDT", "", "FAIL", "Missing ID", "",
             "Y", "549300MANAGER0001:LEI", "FALSE"],
        ]
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        
        return csv_path

    @pytest.fixture
    def sample_master_tracking(self, temp_dir: Path) -> Path:
        """Create sample master tracking file for data push testing."""
        csv_path = temp_dir / "master_tracking.csv"
        
        header = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Error",
            "Correction Output",
            "Correction Fields",
            "Extra Column",
        ]
        
        rows = [
            ["TXN001", "", "", "", "", "", "extra1"],
            ["TXN002", "", "", "", "", "", "extra2"],
            ["TXN003", "", "", "", "", "", "extra3"],
            ["TXN999", "OLD", "OLD_PC", "Y", "", "", "extra999"],
        ]
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
        
        return csv_path

    def test_template_format_classification(self):
        """Test incident code to template type classification."""
        assert TemplateFormat.get_template_type("7_37") == "buyer"
        assert TemplateFormat.get_template_type("7_35") == "buyer"
        assert TemplateFormat.get_template_type("16_19") == "seller"
        assert TemplateFormat.get_template_type("35_3") == "pricing"
        assert TemplateFormat.get_template_type("99_99") == "default"

    def test_template_columns_differ_by_type(self):
        """Test that different template types have different columns."""
        buyer_cols = TemplateFormat.get_validation_columns("buyer")
        seller_cols = TemplateFormat.get_validation_columns("seller")
        pricing_cols = TemplateFormat.get_validation_columns("pricing")
        
        # Buyer and seller should have ID-specific columns
        assert "Buyer ID Code" in buyer_cols
        assert "Seller ID Code" in seller_cols
        assert "Buyer ID Code" not in seller_cols
        assert "Seller ID Code" not in buyer_cols
        
        # Pricing has different structure
        assert "Net Amount" in pricing_cols
        assert "Buyer ID Code" not in pricing_cols

    def test_data_push_workflow(
        self,
        temp_dir: Path,
        sample_validation_output: Path,
        sample_master_tracking: Path,
    ):
        """Test the complete data push workflow."""
        # Set up column mappings for this test
        column_mappings = [
            ColumnMapping("Account ID", "Account ID", ""),
            ColumnMapping("Person Code", "Person Code", ""),
            ColumnMapping("Error", "Error", ""),
            ColumnMapping("Correction Output", "Correction Output", ""),
            ColumnMapping("Correction Fields", "Correction Fields", ""),
        ]
        
        config = DataPushConfig(
            fiscal_year="FY26",
            quarter="Q1",
            incident_code="7_37",
            source_file=sample_validation_output,
            target_file=sample_master_tracking,
            column_mappings=column_mappings,
            dry_run=False,
            backup=True,
        )
        
        processor = DataPushProcessor(config)
        
        # Load files
        source_count = processor.load_source(sample_validation_output)
        target_count = processor.load_target(sample_master_tracking)
        
        assert source_count == 3
        assert target_count == 4
        
        # Match records
        matched, not_found = processor.match_records()
        assert matched == 3  # TXN001, TXN002, TXN003
        assert not_found == 0
        
        # Push data
        processor.push_data()
        
        # Write results
        processor.write_target(sample_master_tracking)
        
        # Verify the output
        with open(sample_master_tracking, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Find TXN001 - Error=N, should only have error pushed
        txn001 = next(r for r in rows if r["Transaction Reference"] == "TXN001")
        assert txn001["Error"] == "N"
        assert txn001["Extra Column"] == "extra1"  # Preserved
        
        # Find TXN002 - Error=Y, should have all columns pushed
        txn002 = next(r for r in rows if r["Transaction Reference"] == "TXN002")
        assert txn002["Error"] == "Y"
        assert txn002["Account ID"] == "B98765432"
        assert txn002["Person Code"] == "PC002"
        assert txn002["Correction Output"] == "549300CORRECTED01:LEI"
        assert txn002["Extra Column"] == "extra2"  # Preserved
        
        # Find TXN003 - Error=Y, should have all columns pushed
        txn003 = next(r for r in rows if r["Transaction Reference"] == "TXN003")
        assert txn003["Error"] == "Y"
        assert txn003["Account ID"] == "C11111111"
        assert txn003["Correction Output"] == "549300MANAGER0001:LEI"
        
        # Find TXN999 - Not in source, should be unchanged
        txn999 = next(r for r in rows if r["Transaction Reference"] == "TXN999")
        assert txn999["Account ID"] == "OLD"
        assert txn999["Error"] == "Y"

    def test_data_push_creates_backup(
        self,
        temp_dir: Path,
        sample_validation_output: Path,
        sample_master_tracking: Path,
    ):
        """Test that data push creates backup before modifying target."""
        config = DataPushConfig(
            source_file=sample_validation_output,
            target_file=sample_master_tracking,
            backup=True,
        )
        
        processor = DataPushProcessor(config)
        processor.load_source(sample_validation_output)
        processor.load_target(sample_master_tracking)
        processor.match_records()
        processor.push_data()
        
        # Create backup
        backup_path = processor.create_backup(sample_master_tracking)
        
        assert backup_path is not None
        assert backup_path.exists()
        assert "backup" in backup_path.name

    def test_data_push_dry_run(
        self,
        temp_dir: Path,
        sample_validation_output: Path,
        sample_master_tracking: Path,
    ):
        """Test that dry run doesn't modify files."""
        # Get original content
        with open(sample_master_tracking, "r", encoding="utf-8") as f:
            original_content = f.read()
        
        # Configure with minimal mappings to match target columns
        column_mappings = [
            ColumnMapping("Account ID", "Account ID", ""),
            ColumnMapping("Person Code", "Person Code", ""),
            ColumnMapping("Error", "Error", ""),
            ColumnMapping("Correction Output", "Correction Output", ""),
            ColumnMapping("Correction Fields", "Correction Fields", ""),
        ]
        
        config = DataPushConfig(
            source_file=sample_validation_output,
            target_file=sample_master_tracking,
            column_mappings=column_mappings,
            dry_run=True,
        )
        
        processor = DataPushProcessor(config)
        stats = processor.process(
            sample_validation_output,
            sample_master_tracking,
            sample_master_tracking,
            dry_run=True,  # Explicitly pass dry_run to process()
        )
        
        # Verify file unchanged
        with open(sample_master_tracking, "r", encoding="utf-8") as f:
            new_content = f.read()
        
        assert original_content == new_content
        assert stats.matched == 3

    def test_workflow_statistics(
        self,
        temp_dir: Path,
        sample_validation_output: Path,
        sample_master_tracking: Path,
    ):
        """Test that workflow produces accurate statistics."""
        # Configure with minimal mappings to match target columns
        column_mappings = [
            ColumnMapping("Account ID", "Account ID", ""),
            ColumnMapping("Person Code", "Person Code", ""),
            ColumnMapping("Error", "Error", ""),
            ColumnMapping("Correction Output", "Correction Output", ""),
            ColumnMapping("Correction Fields", "Correction Fields", ""),
        ]
        
        config = DataPushConfig(
            source_file=sample_validation_output,
            target_file=sample_master_tracking,
            column_mappings=column_mappings,
            dry_run=True,
        )
        
        processor = DataPushProcessor(config)
        stats = processor.process(
            sample_validation_output,
            sample_master_tracking,
            sample_master_tracking,
            dry_run=True,
        )
        
        assert stats.total_source == 3
        assert stats.matched == 3
        assert stats.not_found == 0
        # TXN001 has Error=N (error only), TXN002 and TXN003 have Error=Y (update all)
        assert stats.updated_error_only == 1
        assert stats.updated_all == 2
        assert stats.skipped == 0


class TestTemplateColumnIntegrity:
    """Tests to verify template and validation column consistency."""

    def test_buyer_template_has_required_columns(self):
        """Verify buyer template has all required validation columns."""
        cols = TemplateFormat.BUYER_VALIDATION_COLS
        
        required = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Buyer ID Code",
            "Type of Buyer ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
            "Correction Output",
            "Correction Fields",
            "Tracker Status",
        ]
        
        for col in required:
            assert col in cols, f"Missing required column: {col}"

    def test_seller_template_has_required_columns(self):
        """Verify seller template has all required validation columns."""
        cols = TemplateFormat.SELLER_VALIDATION_COLS
        
        required = [
            "Transaction Reference",
            "Account ID",
            "Person Code",
            "Seller ID Code",
            "Type of Seller ID Code",
        ]
        
        for col in required:
            assert col in cols, f"Missing required column: {col}"

    def test_pricing_template_has_required_columns(self):
        """Verify pricing template has all required validation columns."""
        cols = TemplateFormat.PRICING_VALIDATION_COLS
        
        required = [
            "Transaction Reference",
            "Error",
            "Net Amount",
            "Consideration",
            "Interest",
        ]
        
        for col in required:
            assert col in cols, f"Missing required column: {col}"


class TestDataPushEdgeCases:
    """Edge case tests for the data push workflow."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_tbc_error_flag_skipped(self, temp_dir: Path):
        """Test that TBC error flag causes record to be skipped."""
        source_path = temp_dir / "source.csv"
        target_path = temp_dir / "target.csv"
        
        # Source with TBC
        with open(source_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Account ID", "Error"])
            writer.writerow(["TXN001", "A123", "TBC"])
        
        # Target
        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Account ID", "Error"])
            writer.writerow(["TXN001", "", ""])
        
        config = DataPushConfig(
            source_file=source_path,
            target_file=target_path,
            column_mappings=[
                ColumnMapping("Account ID", "Account ID", ""),
                ColumnMapping("Error", "Error", ""),
            ],
        )
        
        processor = DataPushProcessor(config)
        stats = processor.process(source_path, target_path, target_path)
        
        assert stats.skipped == 1
        assert stats.updated_all == 0
        assert stats.updated_error_only == 0

    def test_unmatched_source_records(self, temp_dir: Path):
        """Test handling of source records not found in target."""
        source_path = temp_dir / "source.csv"
        target_path = temp_dir / "target.csv"
        
        # Source with transaction not in target
        with open(source_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Error"])
            writer.writerow(["TXN_NOT_FOUND", "Y"])
        
        # Empty target
        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Error"])
        
        config = DataPushConfig(
            source_file=source_path,
            target_file=target_path,
        )
        
        processor = DataPushProcessor(config)
        stats = processor.process(source_path, target_path, target_path)
        
        assert stats.not_found == 1
        assert stats.matched == 0

    def test_case_sensitivity_in_transaction_ref(self, temp_dir: Path):
        """Test that transaction reference matching is case-sensitive."""
        source_path = temp_dir / "source.csv"
        target_path = temp_dir / "target.csv"
        
        with open(source_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Error"])
            writer.writerow(["txn001", "Y"])  # lowercase
        
        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Transaction Reference", "Error"])
            writer.writerow(["TXN001", ""])  # uppercase
        
        config = DataPushConfig(
            source_file=source_path,
            target_file=target_path,
        )
        
        processor = DataPushProcessor(config)
        stats = processor.process(source_path, target_path, target_path)
        
        # Should not match due to case difference
        assert stats.not_found == 1
        assert stats.matched == 0
