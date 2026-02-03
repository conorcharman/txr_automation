#!/usr/bin/env python3
"""
Integration tests for batch validation processing.

Tests batch processing functionality across buyer_id_validation, seller_id_validation,
and pricing_validation scripts.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import yaml
from typing import Dict, List
import sys
from io import StringIO

# Import validation scripts
from src.accuracy_testing.scripts import buyer_id_validation, seller_id_validation, pricing_validation


class TestBatchValidationDetection:
    """Test batch mode detection logic."""
    
    def test_detects_batch_mode_with_incidents_and_testing_period(self):
        """Should detect batch mode when config has incidents and testing_period."""
        config = {
            'mode': 'batch',
            'batch': {
                'incidents': ['7_37', '16_21', '35_3'],
                'testing_period': {
                    'fiscal_year': 'FY25',
                    'quarter': 'Q3'
                },
                'paths': {
                'template_dir': 'data/templates',
                'output_dir': 'data/validated'
            }
        }
        
        is_batch = 'incidents' in config and 'testing_period' in config
        assert is_batch is True
    
    def test_detects_single_mode_without_incidents(self):
        """Should detect single mode when config has mode='single'."""
        config = {
            'mode': 'single',
            'single': {
                'incident_code': '7_66',
                'paths': {
                    'input_file': 'data/input.csv',
                    'output_file': 'data/output.csv'
                }
            }
        }
        
        mode = config.get('mode', 'single')
        is_batch = mode == 'batch'
        assert is_batch is False
    
    def test_detects_single_mode_without_testing_period(self):
        """Should detect single mode when mode field is missing (defaults to single)."""
        config = {
            'incidents': ['7_37', '16_21'],
            'paths': {
                'template_dir': 'data/templates',
                'output_dir': 'data/validated'
            }
        }
        
        mode = config.get('mode', 'single')
        is_batch = mode == 'batch'
        assert is_batch is False


class TestBatchFileNaming:
    """Test file naming conventions for batch processing."""
    
    def test_template_filename_construction(self):
        """Should construct template filename as 'FY25 Q3 7_37.csv'."""
        fiscal_year = 'FY25'
        quarter = 'Q3'
        incident = '7_37'
        
        template_filename = f"{fiscal_year} {quarter} {incident}.csv"
        assert template_filename == "FY25 Q3 7_37.csv"
    
    def test_output_filename_construction(self):
        """Should construct output filename as 'validated_FY25_Q3_7_37.csv'."""
        fiscal_year = 'FY25'
        quarter = 'Q3'
        incident = '7_37'
        
        output_filename = f"validated_{fiscal_year}_{quarter}_{incident}.csv"
        assert output_filename == "validated_FY25_Q3_7_37.csv"
    
    def test_multiple_incident_filenames(self):
        """Should construct correct filenames for multiple incidents."""
        fiscal_year = 'FY25'
        quarter = 'Q3'
        incidents = ['7_37', '16_21', '35_3']
        
        expected_templates = [
            "FY25 Q3 7_37.csv",
            "FY25 Q3 16_21.csv",
            "FY25 Q3 35_3.csv"
        ]
        
        expected_outputs = [
            "validated_FY25_Q3_7_37.csv",
            "validated_FY25_Q3_16_21.csv",
            "validated_FY25_Q3_35_3.csv"
        ]
        
        for incident, exp_template, exp_output in zip(incidents, expected_templates, expected_outputs):
            template = f"{fiscal_year} {quarter} {incident}.csv"
            output = f"validated_{fiscal_year}_{quarter}_{incident}.csv"
            
            assert template == exp_template
            assert output == exp_output


class TestBuyerBatchValidation:
    """Integration tests for buyer ID validation batch processing."""
    
    def setup_method(self):
        """Create temporary test directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.test_dir) / "templates"
        self.output_dir = Path(self.test_dir) / "output"
        self.template_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up temporary test files."""
        # Close all logging handlers to release file locks (Windows issue)
        import logging
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if Path(self.test_dir).exists():
            try:
                shutil.rmtree(self.test_dir)
            except PermissionError:
                # On Windows, file locks can persist briefly
                import time
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.test_dir)
                except PermissionError:
                    pass  # Best effort cleanup
    
    def create_buyer_template(self, fiscal_year: str, quarter: str, incident: str) -> Path:
        """Create sample files for buyer ID validation.
        
        Creates both:
        1. Extract file: {incident}_{FY}_{Q}.csv (SQL database export format)
        2. Template file: {FY} {Q} {incident}.csv (Kaizen template format)
        """
        # Create extract file with new naming convention
        extract_filename = f"{incident}_{fiscal_year}_{quarter}.csv"
        extract_filepath = self.template_dir / extract_filename
        
        # Create template file with old naming convention (for Kaizen lookup)
        template_filename = f"{fiscal_year} {quarter} {incident}.csv"
        template_filepath = self.template_dir / template_filename
        
        # Create sample CSV with full column structure matching buyer validation expectations
        # Columns: Transaction Ref, Account ID, Col2-4, Person Code, Account Type, ID Value, ID Type, 
        #          First Name, Surname, DOB, Gender, Primary Nationality, Secondary Nationality
        content = """Transaction Ref,Account ID,Col2,Col3,Col4,Person Code,Account Type,ID Value,ID Type,First Name,Surname,DOB,Gender,Primary Nationality,Secondary Nationality
TXN001,ACC001,,,,,B,12345678,PASSPORT,John,Doe,1990-01-01,M,US,
TXN002,ACC002,,,,,B,87654321,PASSPORT,Jane,Smith,1985-05-15,F,GB,
TXN003,ACC003,,,,,B,11111111,PASSPORT,Bob,Johnson,1992-12-20,M,CA,
"""
        extract_filepath.write_text(content)
        template_filepath.write_text(content)
        return extract_filepath
    
    def test_processes_single_incident(self):
        """Should process a single incident in batch mode."""
        # Create template
        self.create_buyer_template('FY25', 'Q3', '7_37')
        
        # Create config
        config = {
            'mode': 'batch',
            'batch': {
                'incidents': ['7_37'],
                'testing_period': {
                    'fiscal_year': 'FY25',
                    'quarter': 'Q3'
                },
                'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'  # Suppress output
            }
        }
        
        # Run batch validation
        result = buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        # Check result
        assert result == 0
        
        # Check output file exists
        output_file = self.output_dir / "validated_FY25_Q3_7_37.csv"
        assert output_file.exists()
    
    def test_processes_multiple_incidents(self):
        """Should process multiple incidents in batch mode."""
        # Create templates - use only buyer incidents (standard_id type)
        # 7_35, 7_37, 7_39 are valid buyer ID incidents
        incidents = ['7_35', '7_37', '7_39']
        for incident in incidents:
            self.create_buyer_template('FY25', 'Q3', incident)
        
        # Create config
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': incidents,
            'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        # Run batch validation
        result = buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        # Check result
        assert result == 0
        
        # Check all output files exist
        for incident in incidents:
            output_file = self.output_dir / f"validated_FY25_Q3_{incident}.csv"
            assert output_file.exists(), f"Output file not found: {output_file}"
    
    def test_handles_missing_template(self):
        """Should handle missing template gracefully."""
        # Create only one template
        self.create_buyer_template('FY25', 'Q3', '7_37')
        
        # Config references missing template
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': ['7_37', '16_21', 'MISSING'],  # MISSING template doesn't exist
            'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Run batch validation
        result = buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        # Should return error code
        assert result == 1
        
        # Should show warning for missing templates
        assert "Template not found" in output or "Skipping" in output
        
        # Should still create output for valid template
        assert (self.output_dir / "validated_FY25_Q3_7_37.csv").exists()
    
    def test_isolates_output_by_incident(self):
        """Should create separate output files for each incident."""
        incidents = ['7_37', '16_21']
        
        # Create templates with different content
        for i, incident in enumerate(incidents):
            filepath = self.template_dir / f"FY25 Q3 {incident}.csv"
            content = f"""Transaction Ref,Account ID,Col2,Col3,Col4,Person Code,Account Type,ID Value,ID Type,First Name,Surname,DOB,Gender,Primary Nationality,Secondary Nationality
TXN{i:03d},ACC{i:03d},,,,,B,1234567{i},PASSPORT,Person{i},Name{i},1990-01-01,M,US,
"""
            filepath.write_text(content)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': incidents,
            'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        # Run batch validation
        buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        # Check each output is unique
        output_files = []
        for incident in incidents:
            output_file = self.output_dir / f"validated_FY25_Q3_{incident}.csv"
            assert output_file.exists()
            content = output_file.read_text()
            output_files.append(content)
        
        # Verify outputs are different (contain different transaction refs)
        assert output_files[0] != output_files[1]


class TestSellerBatchValidation:
    """Integration tests for seller ID validation batch processing."""
    
    def setup_method(self):
        """Create temporary test directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.test_dir) / "templates"
        self.output_dir = Path(self.test_dir) / "output"
        self.template_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up temporary test files."""
        # Close all logging handlers to release file locks (Windows issue)
        import logging
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if Path(self.test_dir).exists():
            try:
                shutil.rmtree(self.test_dir)
            except PermissionError:
                import time
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.test_dir)
                except PermissionError:
                    pass  # Best effort cleanup
    
    def create_seller_template(self, fiscal_year: str, quarter: str, incident: str) -> Path:
        """Create a sample seller ID validation template CSV."""
        filename = f"{fiscal_year} {quarter} {incident}.csv"
        filepath = self.template_dir / filename
        
        # Match seller validation column structure (same as buyer)
        content = """Transaction Ref,Account ID,Col2,Col3,Col4,Person Code,Account Type,ID Value,ID Type,First Name,Surname,DOB,Gender,Primary Nationality,Secondary Nationality
TXN001,ACC001,,,,,S,98765432,PASSPORT,Alice,Williams,1988-03-10,F,US,
TXN002,ACC002,,,,,S,12345678,PASSPORT,Charlie,Brown,1991-07-22,M,GB,
"""
        filepath.write_text(content)
        return filepath
    
    def test_processes_multiple_incidents(self):
        """Should process multiple seller incidents in batch mode."""
        # Use only seller incidents (16_19, 16_21, 16_23 are standard_id seller)
        incidents = ['16_19', '16_21', '16_23']
        for incident in incidents:
            self.create_seller_template('FY25', 'Q3', incident)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': incidents,
            'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        result = seller_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        assert result == 0
        
        for incident in incidents:
            output_file = self.output_dir / f"validated_FY25_Q3_{incident}.csv"
            assert output_file.exists()


class TestPricingBatchValidation:
    """Integration tests for pricing validation batch processing."""
    
    def setup_method(self):
        """Create temporary test directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.test_dir) / "templates"
        self.output_dir = Path(self.test_dir) / "output"
        self.template_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up temporary test files."""
        # Close all logging handlers to release file locks (Windows issue)
        import logging
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if Path(self.test_dir).exists():
            try:
                shutil.rmtree(self.test_dir)
            except PermissionError:
                import time
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.test_dir)
                except PermissionError:
                    pass  # Best effort cleanup
    
    def create_pricing_template(self, fiscal_year: str, quarter: str, incident: str) -> Path:
        """Create a sample pricing validation template CSV."""
        filename = f"{fiscal_year} {quarter} {incident}.csv"
        filepath = self.template_dir / filename
        
        # Pricing columns: Transaction Ref, Net Amount, Consideration, Interest
        content = """Transaction Ref,Net Amount,Consideration,Interest
TXN001,100.00,95.00,5.00
TXN002,200.00,190.00,10.00
"""
        filepath.write_text(content)
        return filepath
    
    def test_processes_multiple_incidents(self):
        """Should process pricing incident in batch mode."""
        # Only 35_3 is a pricing incident (7_37 is buyer standard_id)
        incidents = ['35_3']
        for incident in incidents:
            self.create_pricing_template('FY25', 'Q3', incident)
        
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': incidents,
            'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        result = pricing_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        assert result == 0
        
        for incident in incidents:
            output_file = self.output_dir / f"validated_FY25_Q3_{incident}.csv"
            assert output_file.exists()


class TestBatchValidationDryRun:
    """Test dry run mode for batch validation."""
    
    def setup_method(self):
        """Create temporary test directories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.test_dir) / "templates"
        self.output_dir = Path(self.test_dir) / "output"
        self.template_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
    
    def teardown_method(self):
        """Clean up temporary test files."""
        # Close all logging handlers to release file locks (Windows issue)
        import logging
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
        
        if Path(self.test_dir).exists():
            try:
                shutil.rmtree(self.test_dir)
            except PermissionError:
                import time
                time.sleep(0.1)
                try:
                    shutil.rmtree(self.test_dir)
                except PermissionError:
                    pass  # Best effort cleanup
    
    def create_buyer_template(self, fiscal_year: str, quarter: str, incident: str) -> Path:
        """Create a sample template."""
        filename = f"{fiscal_year} {quarter} {incident}.csv"
        filepath = self.template_dir / filename
        
        # Match buyer validation column structure
        content = """Transaction Ref,Account ID,Col2,Col3,Col4,Person Code,Account Type,ID Value,ID Type,First Name,Surname,DOB,Gender,Primary Nationality,Secondary Nationality
TXN001,ACC001,,,,,B,12345678,PASSPORT,John,Doe,1990-01-01,M,US,
"""
        filepath.write_text(content)
        return filepath
    
    def test_dry_run_does_not_create_output(self):
        """Should not create output files in dry run mode."""
        self.create_buyer_template('FY25', 'Q3', '7_37')
        
        config = {
            'mode': 'batch',
            'batch': {
                'incidents': ['7_37'],
                'testing_period': {
                    'fiscal_year': 'FY25',
                    'quarter': 'Q3'
                },
                'paths': {
                'template_dir': str(self.template_dir),
                'output_dir': str(self.output_dir),
                'log_output': str(self.output_dir / 'logs')
            },
            'processor': {
                'log_level': 'ERROR'
            }
        }
        
        # Run in dry run mode
        buyer_id_validation.run_batch_validation(config, dry_run=True, show_progress=False)
        
        # Output file should not exist
        output_file = self.output_dir / "validated_FY25_Q3_7_37.csv"
        assert not output_file.exists()


class TestBatchValidationErrorHandling:
    """Test error handling in batch validation."""
    
    def test_returns_error_code_when_no_incidents(self):
        """Should return error code when incidents list is empty."""
        config = {
            'testing_period': {
                'fiscal_year': 'FY25',
                'quarter': 'Q3'
            },
            'incidents': [],  # Empty list
            'paths': {
                'template_dir': 'data/templates',
                'output_dir': 'data/output'
            }
        }
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        result = buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
        
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        assert result == 1
        assert "No incidents" in output
    
    def test_returns_error_code_when_all_templates_missing(self):
        """Should return error code when all templates are missing."""
        test_dir = tempfile.mkdtemp()
        try:
            template_dir = Path(test_dir) / "templates"
            output_dir = Path(test_dir) / "output"
            template_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            
            config = {
            'mode': 'batch',
            'batch': {
                'incidents': ['MISSING1', 'MISSING2'],
                'testing_period': {
                    'fiscal_year': 'FY25',
                    'quarter': 'Q3'
                },
                'paths': {
                    'template_dir': str(template_dir),
                    'output_dir': str(output_dir),
                    'log_output': str(output_dir / 'logs')
                },
                'processor': {
                    'log_level': 'ERROR'
                }
            }
            
            # Capture output
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            result = buyer_id_validation.run_batch_validation(config, dry_run=False, show_progress=False)
            
            sys.stdout = old_stdout
            
            assert result == 1
        finally:
            shutil.rmtree(test_dir)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
