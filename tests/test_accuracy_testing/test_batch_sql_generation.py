#!/usr/bin/env python3
"""
Integration tests for batch SQL generation.

Tests the run_batch_sql_generation function and SQL template mapping logic.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from typing import Dict
import sys

# Import the function we're testing
from src.accuracy_testing.scripts.sql_extract_generator import (
    get_sql_template_for_incident,
    run_batch_sql_generation
)


class TestSQLTemplateMapping:
    """Test automatic SQL template selection based on incident codes."""
    
    def setup_method(self):
        """Create temporary SQL template directory."""
        self.test_dir = tempfile.mkdtemp()
        self.sql_dir = Path(self.test_dir) / "sql_templates"
        self.sql_dir.mkdir(parents=True)
        
        # Create mock SQL template files
        templates = [
            "BuyerID.sql",
            "SellerID.sql",
            "SCR_pricing_data_v1.0.sql",
            "InconsistentBuyerID.sql",
            "InconsistentSellerID.sql",
            "FTBDM.sql",
            "FTSDM.sql"
        ]
        
        for template in templates:
            (self.sql_dir / template).write_text("SELECT * FROM table WHERE id IN (\n-- TRANSACTION REFERENCES --\n)")
    
    def teardown_method(self):
        """Clean up temporary files."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_buyer_id_incident_mapping(self):
        """Should map buyer ID incidents to BuyerID.sql."""
        # Only test with implemented standard_id buyer codes
        buyer_incidents = ['7_35', '7_37', '7_39']
        
        for incident in buyer_incidents:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "BuyerID.sql", f"Incident {incident} should map to BuyerID.sql"
    
    def test_seller_id_incident_mapping(self):
        """Should map seller ID incidents to SellerID.sql."""
        # Only test with implemented standard_id seller codes
        seller_incidents = ['16_19', '16_21', '16_23']
        
        for incident in seller_incidents:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "SellerID.sql", f"Incident {incident} should map to SellerID.sql"
    
    def test_pricing_incident_mapping(self):
        """Should map pricing incident to SCR_pricing_data_v1.0.sql."""
        result = get_sql_template_for_incident('35_3', self.sql_dir)
        assert result.name == "SCR_pricing_data_v1.0.sql"
    
    def test_inconsistent_buyer_mapping(self):
        """Should map inconsistent buyer incidents to InconsistentBuyerID.sql."""
        # Only 7_66 is implemented (7_68 was removed)
        inconsistent_buyer = ['7_66']
        
        for incident in inconsistent_buyer:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "InconsistentBuyerID.sql"
    
    def test_inconsistent_seller_mapping(self):
        """Should map inconsistent seller incidents to InconsistentSellerID.sql."""
        # Only 16_20 is implemented (16_64 was removed)
        inconsistent_seller = ['16_20']
        
        for incident in inconsistent_seller:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "InconsistentSellerID.sql"
    
    def test_decision_maker_buyer_mapping(self):
        """Should map decision maker buyer incidents (12_*) to FTBDM.sql."""
        # Only 12_17 is implemented
        dm_buyer = ['12_17']
        
        for incident in dm_buyer:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "FTBDM.sql"
    
    def test_decision_maker_seller_mapping(self):
        """Should map decision maker seller incidents (21_*) to FTSDM.sql."""
        # Only 21_17 is implemented
        dm_seller = ['21_17']
        
        for incident in dm_seller:
            result = get_sql_template_for_incident(incident, self.sql_dir)
            assert result.name == "FTSDM.sql"
    
    def test_unknown_incident_raises_error(self):
        """Should raise ValueError for unknown incident codes."""
        with pytest.raises(ValueError, match="Unknown incident code"):
            get_sql_template_for_incident('99_99', self.sql_dir)
    
    def test_missing_template_raises_error(self):
        """Should raise FileNotFoundError if SQL template doesn't exist."""
        empty_dir = Path(self.test_dir) / "empty"
        empty_dir.mkdir()
        
        with pytest.raises(FileNotFoundError, match="SQL template not found"):
            get_sql_template_for_incident('7_37', empty_dir)


class TestBatchSQLGeneration:
    """Integration tests for batch SQL generation."""
    
    def setup_method(self):
        """Create temporary test directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.test_dir) / "validated"
        self.sql_templates_dir = Path(self.test_dir) / "sql_templates"
        self.output_dir = Path(self.test_dir) / "output"
        
        self.template_dir.mkdir(parents=True)
        self.sql_templates_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
        
        # Create SQL templates
        templates = {
            "BuyerID.sql": "SELECT * FROM buyer WHERE ref IN (\n-- TRANSACTION REFERENCES --\n)",
            "SellerID.sql": "SELECT * FROM seller WHERE ref IN (\n-- TRANSACTION REFERENCES --\n)",
            "SCR_pricing_data_v1.0.sql": "SELECT * FROM pricing WHERE ref IN (\n-- TRANSACTION REFERENCES --\n)"
        }
        
        for name, content in templates.items():
            (self.sql_templates_dir / name).write_text(content)
        
        # Create DTF template (required when output_format='both')
        dtf_template = """[DataTransfer]
SourceType=SQL
SQLStatement=<<SQL_CONTENT>>
OutputFormat=CSV
"""
        (self.sql_templates_dir / "AS400_DataTransfer_template.dtf").write_text(dtf_template)
    
    def teardown_method(self):
        """Clean up temporary test files."""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def create_validated_csv(self, fiscal_year: str, quarter: str, incident: str, num_refs: int = 10):
        """Create a mock validated CSV file with transaction references."""
        filename = f"{fiscal_year} {quarter} {incident}.csv"
        filepath = self.template_dir / filename
        
        content = "Transaction reference number,Other Column\n"
        for i in range(num_refs):
            content += f"TXN{i:05d},Data{i}\n"
        
        filepath.write_text(content)
        return filepath
    
    def test_processes_single_incident(self):
        """Should process a single incident in batch mode."""
        # Create validated CSV
        self.create_validated_csv('FY25', 'Q3', '7_37', num_refs=5)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': ['7_37'],
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number',
                'placeholder_pattern': '-- TRANSACTION REFERENCES --'
            }
        }
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr  # Suppress print output
        
        result = run_batch_sql_generation(config, dry_run=False, verbose=False)
        
        sys.stdout = old_stdout
        
        # Check result
        assert result == 0
        
        # Check output file exists (files go to sql/ subdir when output_format='sql' or 'both')
        output_file = self.output_dir / "sql" / "7_37_FY25_Q3.sql"
        assert output_file.exists()
        
        # Check content contains transaction refs
        content = output_file.read_text()
        assert "TXN00000" in content
        assert "TXN00004" in content
    
    def test_processes_multiple_incidents(self):
        """Should process multiple incidents in batch mode."""
        # Create validated CSVs
        incidents = ['7_37', '16_21', '35_3']
        for incident in incidents:
            self.create_validated_csv('FY25', 'Q3', incident, num_refs=3)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': incidents,
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number',
                'placeholder_pattern': '-- TRANSACTION REFERENCES --'
            }
        }
        
        # Suppress output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        result = run_batch_sql_generation(config, dry_run=False, verbose=False)
        
        sys.stdout = old_stdout
        
        # Check result
        assert result == 0
        
        # Check all output files exist (files go to sql/ subdir when output_format='sql' or 'both')
        for incident in incidents:
            output_file = self.output_dir / "sql" / f"{incident}_FY25_Q3.sql"
            assert output_file.exists(), f"Output file not found: {output_file}"
    
    def test_splits_large_dataset(self):
        """Should split large datasets into multiple extract files."""
        # Create validated CSV with 2000 refs (batch_size = 900)
        self.create_validated_csv('FY25', 'Q3', '7_37', num_refs=2000)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': ['7_37'],
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number',
                'placeholder_pattern': '-- TRANSACTION REFERENCES --'
            }
        }
        
        # Suppress output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        result = run_batch_sql_generation(config, dry_run=False, verbose=False)
        
        sys.stdout = old_stdout
        
        assert result == 0
        
        # Should create 3 files: Extract1 (900), Extract2 (900), Extract3 (200)
        # Files go to sql/ subdir when output_format='sql' or 'both'
        assert (self.output_dir / "sql" / "7_37_FY25_Q3_Extract1.sql").exists()
        assert (self.output_dir / "sql" / "7_37_FY25_Q3_Extract2.sql").exists()
        assert (self.output_dir / "sql" / "7_37_FY25_Q3_Extract3.sql").exists()
    
    def test_handles_missing_validated_csv(self):
        """Should handle missing validated CSV gracefully."""
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': ['7_37', 'MISSING'],
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number',
                'placeholder_pattern': '-- TRANSACTION REFERENCES --'
            }
        }
        
        # Create only one validated CSV
        self.create_validated_csv('FY25', 'Q3', '7_37', num_refs=5)
        
        # Suppress output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        result = run_batch_sql_generation(config, dry_run=False, verbose=False)
        
        sys.stdout = old_stdout
        
        # Should return error code (MISSING incident unknown)
        assert result == 1
        
        # Should still create output for valid CSV (files go to sql/ subdir)
        assert (self.output_dir / "sql" / "7_37_FY25_Q3.sql").exists()
    
    def test_dry_run_mode(self):
        """Should not create files in dry run mode."""
        self.create_validated_csv('FY25', 'Q3', '7_37', num_refs=5)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': ['7_37'],
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number',
                'placeholder_pattern': '-- TRANSACTION REFERENCES --'
            }
        }
        
        # Suppress output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        result = run_batch_sql_generation(config, dry_run=True, verbose=False)
        
        sys.stdout = old_stdout
        
        assert result == 0
        
        # Output file should NOT exist
        output_file = self.output_dir / "7_37_FY25_Q3.sql"
        assert not output_file.exists()
    
    def test_returns_error_when_no_incidents(self):
        """Should return error code when incidents list is empty."""
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': [],
            'paths': {
                'template_dir': str(self.template_dir),
                'sql_template_dir': str(self.sql_templates_dir),
                'output_directory': str(self.output_dir)
            },
            'processing': {
                'batch_size': 900,
                'transaction_column': 'Transaction reference number'
            }
        }
        
        # Suppress output
        old_stdout = sys.stdout
        sys.stdout = sys.stderr
        
        result = run_batch_sql_generation(config, dry_run=False, verbose=False)
        
        sys.stdout = old_stdout
        
        assert result == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
