#!/usr/bin/env python3
"""
Unit tests for the new correction decision logic in Phase 2 and Phase 3 processors.

Tests the decision flow:
1. If Correction has value:
   - If Agree is Y/P/empty: Apply Correction
   - If Agree is N/F: Apply Suggested (if exists), else No Change
2. If Correction is empty: Apply Suggested (if exists), else No Change
"""

import os
import sys
from pathlib import Path
from typing import Dict, List

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core import LookupResult
from replay.phase_2_processor import IncidentColumnMapper, Phase2Processor
from replay.phase_3_processor import Phase3Processor


class TestIncidentColumnMapper:
    """Test the IncidentColumnMapper used by both processors"""

    def test_column_mapping(self):
        """Test basic column mapping functionality"""
        header = [
            "Transaction Reference",
            "Error",
            "Correction",
            "Correction Field",
            "Agree With Correction",
            "Suggested Correction",
            "Suggested Correction Field",
        ]
        config = {
            "transaction_ref": "Transaction Reference",
            "error_flag": "Error",
            "correction": "Correction",
            "correction_field": "Correction Field",
            "agree_with_correction": "Agree With Correction",
            "suggested_correction": "Suggested Correction",
            "suggested_correction_field": "Suggested Correction Field",
        }

        mapper = IncidentColumnMapper(header, config)

        assert mapper.get("transaction_ref") == 0
        assert mapper.get("error_flag") == 1
        assert mapper.get("correction") == 2
        assert mapper.get("correction_field") == 3
        assert mapper.get("agree_with_correction") == 4
        assert mapper.get("suggested_correction") == 5
        assert mapper.get("suggested_correction_field") == 6

    def test_missing_column(self):
        """Test handling of missing columns"""
        header = ["Transaction Reference", "Correction"]
        config = {
            "transaction_ref": "Transaction Reference",
            "correction": "Correction",
            "non_existent": "Does Not Exist",
        }

        mapper = IncidentColumnMapper(header, config)

        assert mapper.get("transaction_ref") == 0
        assert mapper.get("correction") == 1
        assert mapper.get("non_existent") is None
        assert mapper.has_column("transaction_ref") is True
        assert mapper.has_column("non_existent") is False


class TestCorrectionDecisionLogic:
    """Test the new correction decision logic"""

    @pytest.fixture
    def sample_column_config(self):
        """Sample column configuration"""
        return {
            "transaction_ref": "Transaction Reference",
            "error_flag": "Error",
            "correction": "Correction",
            "correction_field": "Correction Field",
            "agree_with_correction": "Agree With Correction",
            "suggested_correction": "Suggested Correction",
            "suggested_correction_field": "Suggested Correction Field",
        }

    @pytest.fixture
    def sample_header(self):
        """Sample CSV header"""
        return [
            "Transaction Reference",
            "Error",
            "Correction",
            "Correction Field",
            "Agree With Correction",
            "Suggested Correction",
            "Suggested Correction Field",
        ]

    def create_test_row(
        self,
        txn_ref: str,
        correction: str,
        correction_field: str,
        agree: str,
        suggested: str,
        suggested_field: str,
    ) -> List[str]:
        """Helper to create a test row"""
        return [
            txn_ref,
            "Y",
            correction,
            correction_field,
            agree,
            suggested,
            suggested_field,
        ]

    def test_correction_with_agree_y(self, sample_header, sample_column_config):
        """Test: Correction exists + Agree = 'Y' → Apply Correction"""
        row = self.create_test_row("TXN001", "NewValue", "Field1", "Y", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        # Create minimal processor instance to call the method
        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }

        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.found is True
        assert result.correction == "NewValue"
        assert result.correction_field == "Field1"

    def test_correction_with_agree_p(self, sample_header, sample_column_config):
        """Test: Correction exists + Agree = 'P' → Apply Correction"""
        row = self.create_test_row("TXN002", "NewValue", "Field2", "P", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "NewValue"
        assert result.correction_field == "Field2"

    def test_correction_with_agree_empty(self, sample_header, sample_column_config):
        """Test: Correction exists + Agree = empty → Apply Correction"""
        row = self.create_test_row("TXN003", "NewValue", "Field3", "", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "NewValue"
        assert result.correction_field == "Field3"

    def test_correction_with_agree_n_and_suggested(
        self, sample_header, sample_column_config
    ):
        """Test: Correction exists + Agree = 'N' + Suggested exists → Apply Suggested"""
        row = self.create_test_row(
            "TXN004", "OrigValue", "Field4", "N", "SuggestedValue", "SuggestedField"
        )
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "SuggestedValue"
        assert result.correction_field == "SuggestedField"

    def test_correction_with_agree_f_and_suggested(
        self, sample_header, sample_column_config
    ):
        """Test: Correction exists + Agree = 'F' + Suggested exists → Apply Suggested"""
        row = self.create_test_row(
            "TXN005", "OrigValue", "Field5", "F", "SuggestedValue", "SuggestedField"
        )
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "SuggestedValue"
        assert result.correction_field == "SuggestedField"

    def test_correction_with_agree_n_no_suggested(
        self, sample_header, sample_column_config
    ):
        """Test: Correction exists + Agree = 'N' + No Suggested → No Change"""
        row = self.create_test_row("TXN006", "OrigValue", "Field6", "N", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "No Change"
        assert result.correction_field == "No Change"

    def test_correction_with_agree_f_no_suggested(
        self, sample_header, sample_column_config
    ):
        """Test: Correction exists + Agree = 'F' + No Suggested → No Change"""
        row = self.create_test_row("TXN007", "OrigValue", "Field7", "F", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "No Change"
        assert result.correction_field == "No Change"

    def test_no_correction_with_suggested(self, sample_header, sample_column_config):
        """Test: No Correction + Suggested exists → Apply Suggested"""
        row = self.create_test_row(
            "TXN008", "", "", "", "SuggestedValue", "SuggestedField"
        )
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "SuggestedValue"
        assert result.correction_field == "SuggestedField"

    def test_no_correction_no_suggested(self, sample_header, sample_column_config):
        """Test: No Correction + No Suggested → No Change"""
        row = self.create_test_row("TXN009", "", "", "", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        assert result.correction == "No Change"
        assert result.correction_field == "No Change"

    def test_correction_with_unknown_agree_value(
        self, sample_header, sample_column_config
    ):
        """Test: Correction exists + Unknown Agree value → Apply Correction with warning"""
        row = self.create_test_row("TXN010", "NewValue", "Field10", "INVALID", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row, mapper)

        # Should default to applying Correction
        assert result.correction == "NewValue"
        assert result.correction_field == "Field10"

    def test_case_insensitive_agree_values(self, sample_header, sample_column_config):
        """Test: Agree values are case-insensitive"""
        # Test lowercase 'y'
        row_y = self.create_test_row("TXN011", "NewValue", "Field11", "y", "", "")
        mapper = IncidentColumnMapper(sample_header, sample_column_config)

        config = {
            "paths": {
                "replay_input": "dummy",
                "incident_files": "dummy",
                "replay_output": "dummy",
                "log_output": "dummy",
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": sample_column_config,
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }
        processor = Phase2Processor(config_dict=config)
        result = processor._create_lookup_result(row_y, mapper)

        assert result.correction == "NewValue"
        assert result.correction_field == "Field11"

        # Test lowercase 'n'
        row_n = self.create_test_row(
            "TXN012", "OldValue", "Field12", "n", "SuggestedValue", "SuggestedField"
        )
        result = processor._create_lookup_result(row_n, mapper)

        assert result.correction == "SuggestedValue"
        assert result.correction_field == "SuggestedField"


class TestPhase3CorrectionLogic:
    """Test Phase 3 processor correction logic"""

    @pytest.fixture
    def temp_replay_dir(self):
        """Create temporary directory with dummy replay file for Phase 3"""
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        replay_dir = os.path.join(temp_dir, "replay")
        os.makedirs(replay_dir, exist_ok=True)

        # Create dummy replay file so Phase3Processor doesn't fail during init
        dummy_file = os.path.join(replay_dir, "dummy.csv")
        with open(dummy_file, "w") as f:
            f.write("header\n")

        yield replay_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def phase3_config(self, temp_replay_dir):
        """Phase 3 configuration with valid replay directory"""
        return {
            "paths": {
                "replay_input": temp_replay_dir,
                "incident_files": temp_replay_dir,  # Use same dir (not actually used in test)
                "replay_output": temp_replay_dir,
                "log_output": temp_replay_dir,
            },
            "files": {
                "replay_patterns": ["*.csv"],
                "incident_pattern": "FY25 Q4 *.csv",
            },
            "incident_columns": {
                "transaction_ref": "Transaction Reference",
                "error_flag": "Error",
                "correction": "Correction",
                "correction_field": "Correction Field",
                "agree_with_correction": "Agree With Correction",
                "suggested_correction": "Suggested Correction",
                "suggested_correction_field": "Suggested Correction Field",
                "buyer_id": "Buyer ID",
                "seller_id": "Seller ID",
                "buyer_first_name": "Buyer First Name",
                "buyer_last_name": "Buyer Last Name",
                "seller_first_name": "Seller First Name",
                "seller_last_name": "Seller Last Name",
            },
            "processor": {"batch_size": 50, "log_level": "DEBUG"},
        }

    @pytest.fixture
    def sample_header(self):
        """Sample CSV header for Phase 3"""
        return [
            "Transaction Reference",
            "Error",
            "Correction",
            "Correction Field",
            "Agree With Correction",
            "Suggested Correction",
            "Suggested Correction Field",
            "Buyer ID",
            "Seller ID",
            "Buyer First Name",
            "Buyer Last Name",
            "Seller First Name",
            "Seller Last Name",
        ]

    def test_phase3_correction_with_match_type(self, phase3_config, sample_header):
        """Test Phase 3 includes match_type in result"""
        row = [
            "TXN001",
            "Y",
            "NewValue",
            "Field1",
            "Y",
            "",
            "",
            "BUY123",
            "SEL456",
            "John",
            "Doe",
            "Jane",
            "Smith",
        ]

        mapper = IncidentColumnMapper(sample_header, phase3_config["incident_columns"])
        processor = Phase3Processor(config_dict=phase3_config)
        result = processor._create_lookup_result(row, mapper, "id_buyer")

        assert result.found is True
        assert result.correction == "NewValue"
        assert result.correction_field == "Field1"
        assert result.match_type == "id_buyer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
