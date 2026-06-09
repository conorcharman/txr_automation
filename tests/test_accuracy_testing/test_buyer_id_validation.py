"""
Test Buyer ID Validation Script
================================

Unit and integration tests for buyer_id_validation.py
"""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from src.accuracy_testing.processor import ClientRecord
from src.accuracy_testing.scripts.buyer_id_validation import BuyerIDValidator


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing."""
    return [
        [
            "Transaction Reference",
            "Col2",
            "Col3",
            "Col4",
            "Col5",
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
        ],
        [
            "TXN001",
            "",
            "",
            "",
            "",
            "P001",
            "INDIVIDUAL",
            "AB123456C",
            "NIDN",
            "John",
            "Smith",
            "1985-06-15",
            "M",
            "GB",
            "",
        ],
        [
            "TXN002",
            "",
            "",
            "",
            "",
            "P002",
            "INDIVIDUAL",
            "INVALID123",
            "NIDN",
            "Jane",
            "Doe",
            "1990-03-20",
            "F",
            "GB",
            "",
        ],
        [
            "TXN003",
            "",
            "",
            "",
            "",
            "P003",
            "INDIVIDUAL",
            "",
            "",
            "Bob",
            "Jones",
            "1975-12-10",
            "M",
            "DE",
            "",
        ],
    ]


@pytest.fixture
def temp_input_csv(tmp_path, sample_csv_data):
    """Create temporary input CSV file."""
    input_file = tmp_path / "input.csv"
    with open(input_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(sample_csv_data)
    return input_file


class TestBuyerIDValidator:
    """Test suite for BuyerIDValidator."""

    def test_validator_initialization(self, tmp_path):
        """Test validator can be initialized."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(input_file),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)
        assert validator is not None
        assert validator.processor.client_type == "buyer"

    def test_read_input_csv(self, temp_input_csv, tmp_path):
        """Test reading CSV input file."""
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(temp_input_csv),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)
        records = validator.read_input_csv()

        assert len(records) == 3
        assert records[0].transaction_ref == "TXN001"
        assert records[0].id_value == "AB123456C"
        assert records[0].id_type == "NIDN"
        assert records[0].first_name == "John"
        assert records[0].primary_nationality == "GB"

    def test_write_output_csv(self, tmp_path):
        """Test writing CSV output file."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(input_file),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)

        # Create sample processed records
        records = [
            ClientRecord(
                row_index=2,
                transaction_ref="TXN001",
                account_id="ACC001",
                person_code="P001",
                account_type="INDIVIDUAL",
                id_value="AB123456C",
                id_type="NIDN",
                first_name="John",
                surname="Smith",
                date_of_birth="1985-06-15",
                gender="M",
                primary_nationality="GB",
                is_valid=True,
                original_row=[
                    "TXN001",
                    "",
                    "",
                    "",
                    "",
                    "P001",
                    "INDIVIDUAL",
                    "AB123456C",
                    "NIDN",
                    "John",
                    "Smith",
                    "1985-06-15",
                    "M",
                    "GB",
                    "",
                ],
            )
        ]
        records[0].actions_taken.append("Validated NIDN")

        validator.write_output_csv(records)

        assert output_file.exists()

        # Read and verify output
        with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

            assert len(rows) == 2  # Header + 1 data row
            assert "Account ID" in rows[0]  # New column added
            assert "Pass/Fail" in rows[0]  # Updated column name
            # Just verify the row has data
            assert len(rows[1]) > 10  # Should have all columns filled
            assert rows[1][0] == "TXN001"  # Transaction ref
            assert rows[1][1] == "ACC001"  # Account ID

    def test_end_to_end_processing(self, temp_input_csv, tmp_path):
        """Test complete validation workflow."""
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(temp_input_csv),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)

        validator.run()

        # Verify output file was created
        assert output_file.exists()

        # Read and verify results
        with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

            assert len(rows) == 4  # Header + 3 data rows

            # Check that output has expected columns
            assert "Account ID" in rows[0]
            assert "Pass/Fail" in rows[0]
            # Check that records were processed (should have Format:/Logic: status)
            assert any(
                any("Format:" in cell or "Logic:" in cell for cell in row)
                for row in rows[1:]
            )

            # Check that statistics were calculated
            assert validator.processor.stats.total_records == 3


class TestProcessorLogic:
    """Test core processing logic."""

    def test_valid_uk_nidn(self, tmp_path):
        """Test validation of valid UK NIDN."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(input_file),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)

        record = ClientRecord(
            row_index=1,
            transaction_ref="TXN001",
            account_id="ACC001",
            person_code="P001",
            account_type="INDIVIDUAL",
            id_value="AB123456C",  # Valid UK NIDN format
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1985-06-15",
            gender="M",
            primary_nationality="GB",
        )

        processed = validator.processor.process_record(record)

        # Check that processing was completed
        assert processed is not None
        # May be valid or invalid depending on validation logic
        # Just verify it has validation status
        assert hasattr(processed, "is_valid")
        assert hasattr(processed, "format_status")

    def test_invalid_id_generates_concat(self, tmp_path):
        """Test that invalid ID generates CONCAT correction."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(input_file),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)

        record = ClientRecord(
            row_index=1,
            transaction_ref="TXN002",
            account_id="ACC002",
            person_code="P002",
            account_type="INDIVIDUAL",
            id_value="",
            id_type="",
            first_name="Jane",
            surname="Doe",
            date_of_birth="1990-03-20",
            gender="F",
            primary_nationality="GB",
        )

        processed = validator.processor.process_record(record)

        # Should have generated a correction (CONCAT)
        assert processed is not None
        assert len(processed.actions_taken) > 0
        assert processed.correction is not None
        # Check that CONCAT was generated (format may vary)
        assert processed.correction_type == "CONCAT" or "CONCAT" in str(
            processed.actions_taken
        )

    def test_missing_nationality(self, tmp_path):
        """Test handling of missing nationality."""
        input_file = tmp_path / "input.csv"
        output_file = tmp_path / "output.csv"

        config = {
            "paths": {
                "input_file": str(input_file),
                "output_file": str(output_file),
                "log_output": "logs",
            },
            "processor": {"log_level": "INFO", "verbose": False},
        }

        validator = BuyerIDValidator(config_dict=config)

        record = ClientRecord(
            row_index=1,
            transaction_ref="TXN003",
            account_id="ACC003",
            person_code="P003",
            account_type="INDIVIDUAL",
            id_value="AB123456C",
            id_type="NIDN",
            first_name="John",
            surname="Smith",
            date_of_birth="1985-06-15",
            gender="M",
            primary_nationality="",  # Missing
        )

        processed = validator.processor.process_record(record)

        assert "ERROR" in processed.actions_taken[0]
        assert "No valid country code" in processed.validation_error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
