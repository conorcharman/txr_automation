"""
Tests for Accuracy Template Generator
======================================

Tests cover:
- Consolidated data loading (errors and queries)
- Incident code parsing (including pipe-delimited codes)
- Template format selection (buyer/seller/pricing/default)
- Template header generation
- Template data row generation (transaction ref in column 1)
- File generation and output
- Summary statistics
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import csv

from src.accuracy_testing.accuracy_template_generator import (
    AccuracyTemplateGenerator,
    TemplateFormat,
    IncidentRecord
)


# Test data
SAMPLE_CONSOLIDATED_HEADER = [
    'INCIDENT_CODE',
    'INCIDENT_DESCRIPTION',
    'KR_RECORD_KEY',
    'Transaction reference number',
    'Buyer identification code'
]

SAMPLE_CONSOLIDATED_DATA = [
    ['7_37', 'Buyer ID missing', 'REC001', 'TXN001', ''],
    ['7_37|16_21', 'Multiple issues', 'REC002', 'TXN002', 'BUY123'],
    ['16_21', 'Seller ID missing', 'REC003', 'TXN003', 'BUY456'],
    ['35_3', 'Price missing', 'REC004', 'TXN004', 'BUY789'],
    ['99_1', 'Other error', 'REC005', 'TXN005', 'BUY000'],
]


class TestTemplateFormat:
    """Tests for TemplateFormat class."""
    
    def test_buyer_incidents(self):
        """Test buyer incident code set."""
        assert '7_35' in TemplateFormat.BUYER_INCIDENTS
        assert '7_37' in TemplateFormat.BUYER_INCIDENTS
        assert '7_39' in TemplateFormat.BUYER_INCIDENTS
        assert '7_66' in TemplateFormat.BUYER_INCIDENTS
    
    def test_seller_incidents(self):
        """Test seller incident code set."""
        assert '16_19' in TemplateFormat.SELLER_INCIDENTS
        assert '16_21' in TemplateFormat.SELLER_INCIDENTS
        assert '16_23' in TemplateFormat.SELLER_INCIDENTS
        assert '16_20' in TemplateFormat.SELLER_INCIDENTS
    
    def test_incorrect_net_amount_incidents(self):
        """Test incorrect net amount incident code set."""
        assert '35_3' in TemplateFormat.INCORRECT_NET_AMOUNT_INCIDENTS
    
    def test_get_template_type_buyer(self):
        """Test template type detection for buyer incidents."""
        assert TemplateFormat.get_template_type('7_37') == 'buyer'
        assert TemplateFormat.get_template_type('7_35') == 'buyer'
    
    def test_get_template_type_seller(self):
        """Test template type detection for seller incidents."""
        assert TemplateFormat.get_template_type('16_21') == 'seller'
        assert TemplateFormat.get_template_type('16_19') == 'seller'
    
    def test_get_template_type_incorrect_net_amount(self):
        """Test template type detection for incorrect net amount incidents."""
        assert TemplateFormat.get_template_type('35_3') == 'incorrect_net_amount'
    
    def test_get_template_type_default(self):
        """Test template type detection for unknown incidents."""
        assert TemplateFormat.get_template_type('99_1') == 'default'
        assert TemplateFormat.get_template_type('unknown') == 'default'
    
    def test_get_validation_columns_buyer(self):
        """Test buyer validation columns."""
        cols = TemplateFormat.get_validation_columns('buyer')
        assert len(cols) == 17
        assert cols[0] == 'Transaction Reference'
        assert 'Account ID' in cols
        assert 'Buyer ID Code' in cols
    
    def test_get_validation_columns_seller(self):
        """Test seller validation columns."""
        cols = TemplateFormat.get_validation_columns('seller')
        assert len(cols) == 17
        assert cols[0] == 'Transaction Reference'
        assert 'Account ID' in cols
        assert 'Seller ID Code' in cols
    
    def test_get_validation_columns_incorrect_net_amount(self):
        """Test incorrect net amount validation columns."""
        cols = TemplateFormat.get_validation_columns('incorrect_net_amount')
        assert len(cols) == 13
        assert cols[0] == 'Transaction Reference'
        assert 'SEDOL' in cols
        assert 'Instrument Classification' in cols
        assert 'Instrument Type' in cols
        assert 'Net Amount' in cols
        assert 'Error' in cols
    
    def test_get_validation_columns_default(self):
        """Test default validation columns."""
        cols = TemplateFormat.get_validation_columns('default')
        assert len(cols) == 6
        assert cols[0] == 'Transaction Reference'
    
    def test_comparison_columns(self):
        """Test comparison columns."""
        assert len(TemplateFormat.COMPARISON_COLS) == 3
        assert 'Agree With Correction' in TemplateFormat.COMPARISON_COLS


class TestIncidentRecord:
    """Tests for IncidentRecord dataclass."""
    
    def test_incident_record_creation(self):
        """Test creating incident record."""
        record = IncidentRecord(
            incident_codes=['7_37'],
            incident_descriptions=['Buyer ID missing'],
            data_row=['7_37', 'Test', 'REC001', 'TXN001', 'BUY123']
        )
        assert record.incident_codes == ['7_37']
        assert len(record.data_row) == 5
        assert record.data_row[3] == 'TXN001'


class TestAccuracyTemplateGenerator:
    """Tests for AccuracyTemplateGenerator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create test consolidated errors file
        self.errors_file = self.temp_dir / "consolidated_errors.csv"
        with open(self.errors_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(SAMPLE_CONSOLIDATED_HEADER)
            writer.writerows(SAMPLE_CONSOLIDATED_DATA)
        
        # Create test consolidated queries file
        self.queries_file = self.temp_dir / "consolidated_queries.csv"
        queries_data = [
            ['35_3', 'Price query', 'REC006', 'TXN006', 'BUY111'],
        ]
        with open(self.queries_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(SAMPLE_CONSOLIDATED_HEADER)
            writer.writerows(queries_data)
        
        self.output_dir = self.temp_dir / "templates"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_init_with_errors_only(self):
        """Test initialization with errors file only."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        assert str(generator.consolidated_errors) == str(self.errors_file)
        assert generator.consolidated_queries is None
    
    def test_init_with_both_files(self):
        """Test initialization with both errors and queries."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file),
            consolidated_queries=str(self.queries_file)
        )
        assert str(generator.consolidated_errors) == str(self.errors_file)
        assert str(generator.consolidated_queries) == str(self.queries_file)
    
    def test_init_with_neither_file(self):
        """Test initialization requires at least one file."""
        generator = AccuracyTemplateGenerator()
        assert generator.consolidated_errors is None
        assert generator.consolidated_queries is None
    
    def test_read_consolidated_file(self):
        """Test reading consolidated file."""
        generator = AccuracyTemplateGenerator()
        records = generator.read_consolidated_file(str(self.errors_file))
        
        assert len(records) == 5
        assert records[0].incident_codes == ['7_37']
        assert records[1].incident_codes == ['7_37', '16_21']
        assert records[2].incident_codes == ['16_21']
    
    def test_read_consolidated_file_not_found(self):
        """Test reading nonexistent file."""
        generator = AccuracyTemplateGenerator()
        with pytest.raises(FileNotFoundError):
            generator.read_consolidated_file("nonexistent.csv")
    
    def test_load_consolidated_data_errors_only(self):
        """Test loading errors data only."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        # Check that data was loaded
        assert len(generator.incident_records) > 0
        assert generator.consolidated_header is not None
        assert 'INCIDENT_CODE' in generator.consolidated_header
    
    def test_load_consolidated_data_both_files(self):
        """Test loading both errors and queries."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file),
            consolidated_queries=str(self.queries_file)
        )
        generator.load_consolidated_data()
        
        # Should have records from both files
        # pricing incident (35_3) should have 2 records (1 from errors, 1 from queries)
        assert '35_3' in generator.incident_records
        assert len(generator.incident_records['35_3']) == 2
    
    def test_incident_code_parsing_with_pipe_delimiter(self):
        """Test parsing pipe-delimited incident codes."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        # Record with '7_37|16_21' should appear in both incident lists
        assert '7_37' in generator.incident_records
        assert '16_21' in generator.incident_records
        
        # Both should have at least one record with 'TXN002'
        buyer_txns = [r.data_row[3] for r in generator.incident_records['7_37']]
        seller_txns = [r.data_row[3] for r in generator.incident_records['16_21']]
        
        assert 'TXN002' in buyer_txns
        assert 'TXN002' in seller_txns
    
    def test_create_template_header_buyer(self):
        """Test buyer template header generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        header = generator.create_template_header('7_37')
        
        # Should have validation cols + comparison cols + consolidated cols
        assert len(header) == 17 + 3 + len(SAMPLE_CONSOLIDATED_HEADER)
        assert header[0] == 'Transaction Reference'
        assert header[17] == 'Agree With Correction'  # First comparison col
        assert 'INCIDENT_CODE' in header
    
    def test_create_template_header_seller(self):
        """Test seller template header generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        header = generator.create_template_header('16_21')
        
        assert len(header) == 17 + 3 + len(SAMPLE_CONSOLIDATED_HEADER)
        assert header[0] == 'Transaction Reference'
    
    def test_create_template_header_pricing(self):
        """Test pricing template header generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        header = generator.create_template_header('35_3')
        
        assert len(header) == 13 + 3 + len(SAMPLE_CONSOLIDATED_HEADER)
        assert header[0] == 'Transaction Reference'
    
    def test_create_template_header_default(self):
        """Test default template header generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        header = generator.create_template_header('99_1')
        
        assert len(header) == 6 + 3 + len(SAMPLE_CONSOLIDATED_HEADER)
        assert header[0] == 'Transaction Reference'
    
    def test_create_template_data_rows(self):
        """Test template data row generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        rows = generator.create_template_data_rows('7_37')
        
        # Should have 2 rows (REC001 and REC002)
        assert len(rows) == 2
        
        # First row should have transaction reference in column 0
        assert rows[0][0] == 'TXN001'
        assert rows[1][0] == 'TXN002'
        
        # Validation columns should be empty (except column 0)
        for i in range(1, 14):
            assert rows[0][i] == ''
        
        # Comparison columns should be empty
        for i in range(14, 17):
            assert rows[0][i] == ''
    
    def test_transaction_reference_copied_to_column_one(self):
        """Test that transaction reference is copied to first validation column."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        rows = generator.create_template_data_rows('35_3')
        
        # Should have transaction reference from consolidated data in column 0
        assert rows[0][0] == 'TXN004'
        
        # Verify it matches the transaction reference in consolidated data
        # Header has 'Transaction reference number' at index 3
        # 13 validation + 3 comparison + index 3
        txn_ref_col = 13 + 3 + 3
        assert len(rows[0]) > txn_ref_col
        assert rows[0][txn_ref_col] == 'TXN004'
    
    def test_generate_template(self):
        """Test single template file generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        output_path = generator.generate_template('7_37', self.output_dir)
        
        assert output_path.exists()
        assert output_path.name == 'template_7_37.csv'
        
        # Verify file contents
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            first_row = next(reader)
            
            # Check header
            assert header[0] == 'Transaction Reference'
            assert 'INCIDENT_CODE' in header
            
            # Check first data row has transaction reference
            assert first_row[0] == 'TXN001'
    
    def test_generate_templates_all(self):
        """Test generating all template files."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        generated = generator.generate_templates(str(self.output_dir))
        
        # Should generate 4 templates (7_37, 16_21, 35_3, 99_1)
        assert len(generated) == 4
        assert '7_37' in generated
        assert '16_21' in generated
        assert '35_3' in generated
        assert '99_1' in generated
        
        # Verify all files exist
        for incident_code, path in generated.items():
            assert path.exists()
            assert path.name == f'template_{incident_code}.csv'
    
    def test_get_summary(self):
        """Test summary statistics generation."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        summary = generator.get_summary()
        
        assert summary['total_incidents'] == 4
        assert summary['total_records'] == 6  # 5 original + 1 duplicated from pipe-delimiter
        assert summary['buyer_records'] == 2  # REC001, REC002
        assert summary['seller_records'] == 2  # REC002, REC003
        assert summary['incorrect_net_amount_records'] == 1  # REC004
        assert summary['default_records'] == 1  # REC005
    
    def test_empty_consolidated_data(self):
        """Test handling empty consolidated data."""
        empty_file = self.temp_dir / "empty.csv"
        with open(empty_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(SAMPLE_CONSOLIDATED_HEADER)
            # No data rows
        
        generator = AccuracyTemplateGenerator(consolidated_errors=str(empty_file))
        generator.load_consolidated_data()
        
        assert len(generator.incident_records) == 0
        
        summary = generator.get_summary()
        assert summary['total_incidents'] == 0
        assert summary['total_records'] == 0
    
    def test_missing_incident_code_column(self):
        """Test handling file without INCIDENT_CODE column."""
        bad_file = self.temp_dir / "bad.csv"
        with open(bad_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['COL1', 'COL2', 'COL3'])
            writer.writerow(['A', 'B', 'C'])
        
        generator = AccuracyTemplateGenerator(consolidated_errors=str(bad_file))
        
        with pytest.raises(ValueError, match="Required column not found"):
            generator.load_consolidated_data()
    
    def test_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist."""
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        generator.load_consolidated_data()
        
        new_output_dir = self.temp_dir / "nested" / "output" / "dir"
        assert not new_output_dir.exists()
        
        generator.generate_template('7_37', new_output_dir)
        
        assert new_output_dir.exists()
        assert (new_output_dir / 'template_7_37.csv').exists()


class TestTemplateGeneratorIntegration:
    """Integration tests for complete workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create realistic test data
        self.errors_file = self.temp_dir / "consolidated_errors.csv"
        with open(self.errors_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(SAMPLE_CONSOLIDATED_HEADER)
            writer.writerows(SAMPLE_CONSOLIDATED_DATA)
        
        self.output_dir = self.temp_dir / "templates"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_template_generation(self):
        """Test complete template generation workflow."""
        # Initialize generator
        generator = AccuracyTemplateGenerator(
            consolidated_errors=str(self.errors_file)
        )
        
        # Load data
        generator.load_consolidated_data()
        
        # Generate all templates
        generated = generator.generate_templates(str(self.output_dir))
        
        # Verify all templates
        assert len(generated) == 4
        
        # Test buyer template (7_37)
        buyer_template = generated['7_37']
        with open(buyer_template, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            row1 = next(reader)
            row2 = next(reader)
            
            # Verify structure
            assert len(header) == 17 + 3 + 5  # validation + comparison + consolidated
            
            # Verify transaction references are populated
            assert row1[0] == 'TXN001'
            assert row2[0] == 'TXN002'
            
            # Verify other validation columns are empty
            assert all(row1[i] == '' for i in range(1, 17))
            
            # Verify consolidated data is appended
            assert row1[20] == '7_37'  # INCIDENT_CODE
            assert row1[23] == 'TXN001'  # Transaction reference number
        
        # Test that pipe-delimited record appears in both templates
        seller_template = generated['16_21']
        with open(seller_template, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row1 = next(reader)
            
            # Should have TXN002 from the pipe-delimited record
            assert row1[0] == 'TXN002'
