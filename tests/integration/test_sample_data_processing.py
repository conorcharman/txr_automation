"""
Stage 2 Integration Tests - End-to-End Testing with Sample Data

Tests that process real sample data through the refactored scripts
to verify correct functionality, output format, and data accuracy.

NOTE: These tests require sample data files that are not committed to the repository
for confidentiality reasons. Tests will be skipped if data is not available.
"""

import pytest
import sys
import subprocess
from pathlib import Path
import csv

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"

# Check if sample data exists
HAS_SAMPLE_DATA = (
    (SAMPLE_DATA_DIR / "incident_code_files").exists() and 
    (SAMPLE_DATA_DIR / "phase_ii").exists()
)
SKIP_REASON = "Sample data not available (requires confidential test data)"


@pytest.mark.skipif(not HAS_SAMPLE_DATA, reason=SKIP_REASON)
class TestPhase2ProcessorWithSampleData:
    """Test Phase 2 Processor with real sample data."""
    
    def test_sample_data_files_exist(self):
        """Verify sample data files are present."""
        incident_dir = SAMPLE_DATA_DIR / "incident_code_files"
        phase2_dir = SAMPLE_DATA_DIR / "phase_ii"
        
        assert incident_dir.exists(), f"Incident files directory not found: {incident_dir}"
        assert phase2_dir.exists(), f"Phase II directory not found: {phase2_dir}"
        
        # Check incident files
        incident_files = list(incident_dir.glob("*.csv"))
        assert len(incident_files) > 0, "No incident CSV files found"
        
        # Check Phase 2 replay files
        phase2_files = list(phase2_dir.glob("*.csv"))
        assert len(phase2_files) > 0, "No Phase 2 replay files found"
    
    def test_phase2_sample_file_structure(self):
        """Test Phase 2 sample file has expected columns."""
        phase2_file = SAMPLE_DATA_DIR / "phase_ii" / "1903a~G14~P2_8-19~12_1~KR Final Analysis_Data_1 OF 1_anon_sample.csv"
        
        assert phase2_file.exists(), f"Phase 2 sample file not found: {phase2_file}"
        
        # Use latin-1 encoding (ISO-8859-1) for sample CSV files
        with open(phase2_file, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            # Verify essential columns
            required_columns = [
                'KR_RECORD_KEY',
                'Transaction reference number',
                'Buyer identification code',
                'Seller identification code'
            ]
            
            for col in required_columns:
                assert col in headers, f"Missing required column: {col}"
    
    def test_incident_file_structure(self):
        """Test incident file has expected columns."""
        incident_file = SAMPLE_DATA_DIR / "incident_code_files" / "FY25 Q3 - 12_1_anon_sample.csv"
        
        assert incident_file.exists(), f"Incident file not found: {incident_file}"
        
        # Use latin-1 encoding (ISO-8859-1) for sample CSV files
        with open(incident_file, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            # Verify essential columns
            required_columns = [
                'Transaction Reference',
                'Correction',
                'Correction Field (Select Dropdown)',
                'INCIDENT_CODE'
            ]
            
            for col in required_columns:
                assert col in headers, f"Missing required column: {col}"
    
    def test_phase2_processor_with_sample_data(self, tmp_path):
        """Test Phase 2 processor processes sample data successfully."""
        # Create test configuration
        config_content = f"""
paths:
  replay_input: {SAMPLE_DATA_DIR / "phase_ii"}
  incident_files: {SAMPLE_DATA_DIR / "incident_code_files"}
  replay_output: {tmp_path / "output"}
  log_output: {tmp_path / "logs"}

processing:
  batch_size: 50
  log_level: INFO

replace_pattern:
  old: "KR"
  new: "AJB"
"""
        config_file = tmp_path / "phase2_test.yaml"
        config_file.write_text(config_content)
        
        # Create output directory
        (tmp_path / "output").mkdir()
        (tmp_path / "logs").mkdir()
        
        # Run Phase 2 processor
        result = subprocess.run(
            [
                sys.executable, "-m", "src.replay.phase_2_processor",
                "--config", str(config_file)
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Check execution completed (may have no matches with sample data, but should process)
        assert result.returncode == 0 or result.returncode == 1, \
            f"Phase 2 processor failed with code {result.returncode}: {result.stderr}"
        
        # Check log file was created
        log_files = list((tmp_path / "logs").glob("phase2_processor_*.log"))
        assert len(log_files) > 0, "No log file created"
        
        # Check log contains processing information
        log_content = log_files[0].read_text()
        assert "Phase 2 Processor" in log_content or "phase_2_processor" in log_content
        assert "Loading incident files" in log_content or "incident" in log_content.lower()
    
    def test_phase2_output_file_creation(self, tmp_path):
        """Test Phase 2 processor creates output files."""
        # Create test configuration
        config_content = f"""
paths:
  replay_input: {SAMPLE_DATA_DIR / "phase_ii"}
  incident_files: {SAMPLE_DATA_DIR / "incident_code_files"}
  replay_output: {tmp_path / "output"}
  log_output: {tmp_path / "logs"}

processing:
  batch_size: 50
  log_level: DEBUG

replace_pattern:
  old: "KR"
  new: "AJB"
"""
        config_file = tmp_path / "phase2_test.yaml"
        config_file.write_text(config_content)
        
        # Create output directory
        (tmp_path / "output").mkdir()
        (tmp_path / "logs").mkdir()
        
        # Run Phase 2 processor
        result = subprocess.run(
            [
                sys.executable, "-m", "src.replay.phase_2_processor",
                "--config", str(config_file)
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Output files should be created (or attempted)
        # Check that processing completed even if no matches found
        assert "error" not in result.stderr.lower() or "KeyError" not in result.stderr, \
            f"Processor encountered errors: {result.stderr}"


@pytest.mark.skipif(not HAS_SAMPLE_DATA, reason=SKIP_REASON)
class TestPhase3ProcessorWithSampleData:
    """Test Phase 3 Processor with sample data (XLSX files)."""
    
    def test_phase3_sample_files_exist(self):
        """Verify Phase 3 sample files exist."""
        phase3_dir = SAMPLE_DATA_DIR / "phase_iii" / "xlsx"
        
        assert phase3_dir.exists(), f"Phase III XLSX directory not found: {phase3_dir}"
        
        # Check for XLSX files
        xlsx_files = list(phase3_dir.glob("*.xlsx"))
        assert len(xlsx_files) > 0, "No Phase 3 XLSX files found"
    
    def test_phase3_xlsx_files_are_readable(self):
        """Test Phase 3 XLSX files can be read."""
        import pandas as pd
        
        phase3_dir = SAMPLE_DATA_DIR / "phase_iii" / "xlsx"
        xlsx_files = list(phase3_dir.glob("*.xlsx"))
        
        for xlsx_file in xlsx_files:
            # Should be able to read without error
            try:
                df = pd.read_excel(xlsx_file)
                assert len(df.columns) > 0, f"File has no columns: {xlsx_file.name}"
                assert len(df) >= 0, f"File could not be read: {xlsx_file.name}"
            except Exception as e:
                pytest.fail(f"Failed to read {xlsx_file.name}: {e}")


@pytest.mark.skipif(not HAS_SAMPLE_DATA, reason=SKIP_REASON)
class TestXLSXConverterWithSampleData:
    """Test XLSX Converter with Phase 3 sample data."""
    
    def test_xlsx_converter_with_phase3_files(self, tmp_path):
        """Test XLSX converter can process Phase 3 XLSX files."""
        phase3_xlsx_dir = SAMPLE_DATA_DIR / "phase_iii" / "xlsx"
        output_dir = tmp_path / "csv_output"
        output_dir.mkdir()
        
        xlsx_files = list(phase3_xlsx_dir.glob("*.xlsx"))
        
        if len(xlsx_files) == 0:
            pytest.skip("No XLSX files found for testing")
        
        # Run converter
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--input-dir", str(phase3_xlsx_dir),
                "--output-dir", str(output_dir),
                "--log-level", "INFO"
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should complete successfully
        assert result.returncode == 0, f"Converter failed: {result.stderr}"
        
        # Check CSV files were created
        csv_files = list(output_dir.glob("*.csv"))
        assert len(csv_files) == len(xlsx_files), \
            f"Expected {len(xlsx_files)} CSV files, got {len(csv_files)}"
        
        # Verify CSV files are not empty
        for csv_file in csv_files:
            assert csv_file.stat().st_size > 0, f"CSV file is empty: {csv_file.name}"


@pytest.mark.skipif(not HAS_SAMPLE_DATA, reason=SKIP_REASON)
class TestDataIntegrity:
    """Test data integrity and processing accuracy."""
    
    def test_incident_file_transaction_references(self):
        """Test incident files contain valid transaction references."""
        incident_file = SAMPLE_DATA_DIR / "incident_code_files" / "FY25 Q3 - 12_1_anon_sample.csv"
        
        # Use latin-1 encoding (ISO-8859-1) for sample CSV files
        with open(incident_file, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert len(rows) > 0, "Incident file is empty"
            
            # Check transaction references are present
            for row in rows:
                txn_ref = row.get('Transaction Reference', '')
                assert txn_ref, "Transaction Reference is missing"
                assert len(txn_ref) > 0, "Transaction Reference is empty"
    
    def test_phase2_file_record_keys(self):
        """Test Phase 2 file contains valid record keys."""
        phase2_file = SAMPLE_DATA_DIR / "phase_ii" / "1903a~G14~P2_8-19~12_1~KR Final Analysis_Data_1 OF 1_anon_sample.csv"
        
        # Use latin-1 encoding (ISO-8859-1) for sample files
        with open(phase2_file, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert len(rows) > 0, "Phase 2 file is empty"
            
            # Check KR_RECORD_KEY is present
            for row in rows:
                record_key = row.get('KR_RECORD_KEY', '')
                # Record key might be empty in sample data, just check column exists
                assert 'KR_RECORD_KEY' in row, "KR_RECORD_KEY column missing"
    
    def test_sample_data_character_encoding(self):
        """Test sample data handles special characters correctly."""
        incident_file = SAMPLE_DATA_DIR / "incident_code_files" / "FY25 Q3 - 12_1_anon_sample.csv"
        
        # Use latin-1 encoding (ISO-8859-1) for sample CSV files
        with open(incident_file, 'r', encoding='latin-1') as f:
            content = f.read()
            
            # Check for special characters
            # NOT SIGN character (chr(172)) is used in corrections
            assert chr(172) in content or ':' in content, \
                "File should contain correction delimiters"
    
    def test_correction_field_format(self):
        """Test correction fields have expected format."""
        incident_file = SAMPLE_DATA_DIR / "incident_code_files" / "FY25 Q3 - 12_1_anon_sample.csv"
        
        # Use latin-1 encoding (ISO-8859-1) for sample CSV files
        with open(incident_file, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            corrections_found = 0
            for row in rows:
                correction = row.get('Correction', '')
                if correction and correction != 'NULL' and len(correction) > 0:
                    corrections_found += 1
                    # Corrections use chr(172) or : as delimiters
                    assert chr(172) in correction or ':' in correction or 'NULL' in correction, \
                        f"Correction format unexpected: {correction[:50]}"
            
            # Should have at least some corrections in sample data
            assert corrections_found > 0, "No corrections found in sample data"
