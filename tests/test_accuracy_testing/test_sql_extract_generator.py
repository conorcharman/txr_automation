"""
Tests for SQL Extract Generator
================================

Tests cover:
- Template loading and validation
- Placeholder detection (multiple formats)
- Batch splitting logic
- Transaction reference formatting
- SQL generation
- File output
- CLI interface
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from src.accuracy_testing.sql_extract_generator import (
    SQLExtractGenerator,
    ExtractBatch
)


# Test data
SAMPLE_TEMPLATE = """SELECT * FROM transactions
WHERE trans_ref IN (
--<<TRANSACTION REFERENCES>>
)"""

SAMPLE_REFS = [
    '44625CKTPC31',
    '44625CKT72V1',
    '44625CKVNVJ1',
    '44625CKXGQR1',
    '44625CKYABC1',
]


# Minimal DTF template for testing
SAMPLE_DTF_TEMPLATE = """[DataTransfer]
SourceType=SQL
SQLStatement=<<SQL_CONTENT>>
OutputFormat=CSV
"""


class TestSQLExtractGenerator:
    """Tests for SQLExtractGenerator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_path = self.temp_dir / "template.sql"
        self.template_path.write_text(SAMPLE_TEMPLATE)
        # Create DTF template (required by SQLExtractGenerator when output_format='both')
        self.dtf_template_path = self.temp_dir / "AS400_DataTransfer_template.dtf"
        self.dtf_template_path.write_text(SAMPLE_DTF_TEMPLATE)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_init_loads_template(self):
        """Test that initialization loads template correctly."""
        generator = SQLExtractGenerator(str(self.template_path))
        assert generator.template == SAMPLE_TEMPLATE
        assert generator.batch_size == 900  # default
        assert generator.placeholder is not None
    
    def test_init_template_not_found(self):
        """Test that FileNotFoundError is raised for missing template."""
        with pytest.raises(FileNotFoundError):
            SQLExtractGenerator("nonexistent.sql")
    
    def test_init_custom_batch_size(self):
        """Test custom batch size."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=500)
        assert generator.batch_size == 500
    
    def test_placeholder_detection_default(self):
        """Test automatic placeholder detection."""
        generator = SQLExtractGenerator(str(self.template_path))
        assert generator.placeholder == "--<<TRANSACTION REFERENCES>>"
    
    def test_placeholder_detection_alternative_format(self):
        """Test detection of alternative placeholder format."""
        alt_template = SAMPLE_TEMPLATE.replace(
            "--<<TRANSACTION REFERENCES>>",
            "--<TRADE REFERENCES>--"
        )
        alt_path = self.temp_dir / "alt_template.sql"
        alt_path.write_text(alt_template)
        
        generator = SQLExtractGenerator(str(alt_path))
        assert generator.placeholder == "--<TRADE REFERENCES>--"
    
    def test_placeholder_custom(self):
        """Test custom placeholder specification."""
        custom_template = SAMPLE_TEMPLATE.replace(
            "--<<TRANSACTION REFERENCES>>",
            "--CUSTOM_PLACEHOLDER--"
        )
        custom_path = self.temp_dir / "custom_template.sql"
        custom_path.write_text(custom_template)
        
        generator = SQLExtractGenerator(
            str(custom_path),
            placeholder="--CUSTOM_PLACEHOLDER--"
        )
        assert generator.placeholder == "--CUSTOM_PLACEHOLDER--"
    
    def test_placeholder_not_found(self):
        """Test error when placeholder not found."""
        no_placeholder_template = "SELECT * FROM transactions"
        no_ph_path = self.temp_dir / "no_placeholder.sql"
        no_ph_path.write_text(no_placeholder_template)
        
        with pytest.raises(ValueError, match="No placeholder found"):
            SQLExtractGenerator(str(no_ph_path))
    
    def test_create_batches_single_batch(self):
        """Test batch creation with refs < batch size."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=900)
        batches = generator.create_batches(SAMPLE_REFS)
        
        assert len(batches) == 1
        assert batches[0].batch_number == 1
        assert len(batches[0].transaction_refs) == 5
        assert batches[0].transaction_refs == SAMPLE_REFS
    
    def test_create_batches_multiple_batches(self):
        """Test batch creation with refs > batch size."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=2)
        batches = generator.create_batches(SAMPLE_REFS)
        
        assert len(batches) == 3  # 5 refs / 2 per batch = 3 batches
        assert batches[0].batch_number == 1
        assert len(batches[0].transaction_refs) == 2
        assert batches[1].batch_number == 2
        assert len(batches[1].transaction_refs) == 2
        assert batches[2].batch_number == 3
        assert len(batches[2].transaction_refs) == 1  # remainder
    
    def test_create_batches_exact_multiple(self):
        """Test batch creation when refs exactly divides batch size."""
        refs = ['REF' + str(i) for i in range(6)]
        generator = SQLExtractGenerator(str(self.template_path), batch_size=3)
        batches = generator.create_batches(refs)
        
        assert len(batches) == 2
        assert len(batches[0].transaction_refs) == 3
        assert len(batches[1].transaction_refs) == 3
    
    def test_format_transaction_refs(self):
        """Test transaction reference formatting."""
        generator = SQLExtractGenerator(str(self.template_path))
        formatted = generator.format_transaction_refs(SAMPLE_REFS[:3])
        
        expected = "'44625CKTPC31',\n'44625CKT72V1',\n'44625CKVNVJ1'"
        assert formatted == expected
    
    def test_format_transaction_refs_with_whitespace(self):
        """Test formatting strips whitespace."""
        refs_with_space = ['  REF1  ', ' REF2', 'REF3 ']
        generator = SQLExtractGenerator(str(self.template_path))
        formatted = generator.format_transaction_refs(refs_with_space)
        
        assert "'REF1'" in formatted
        assert "'REF2'" in formatted
        assert "'REF3'" in formatted
        assert "  " not in formatted  # No extra spaces
    
    def test_format_transaction_refs_skips_empty(self):
        """Test formatting skips empty refs."""
        refs_with_empty = ['REF1', '', 'REF2', '  ', 'REF3']
        generator = SQLExtractGenerator(str(self.template_path))
        formatted = generator.format_transaction_refs(refs_with_empty)
        
        assert "'REF1'" in formatted
        assert "'REF2'" in formatted
        assert "'REF3'" in formatted
        assert formatted.count("'") == 6  # 3 refs * 2 quotes each
    
    def test_generate_sql(self):
        """Test SQL generation with placeholder replacement."""
        generator = SQLExtractGenerator(str(self.template_path))
        batch = ExtractBatch(batch_number=1, transaction_refs=SAMPLE_REFS[:2])
        
        sql = generator.generate_sql(batch)
        
        assert "--<<TRANSACTION REFERENCES>>" not in sql  # Placeholder removed
        assert "'44625CKTPC31'" in sql
        assert "'44625CKT72V1'" in sql
        assert "SELECT * FROM transactions" in sql
        assert "WHERE trans_ref IN" in sql
    
    def test_write_sql_file_single_batch(self):
        """Test writing SQL file for single batch."""
        generator = SQLExtractGenerator(str(self.template_path))
        batch = ExtractBatch(batch_number=1, transaction_refs=SAMPLE_REFS[:2])
        sql = generator.generate_sql(batch)
        
        output_dir = self.temp_dir / "output"
        output_path = generator.write_sql_file(
            output_dir,
            "test_extract",
            batch,
            sql,
            total_batches=1
        )
        
        assert output_path.exists()
        assert output_path.name == "test_extract.sql"  # No batch number for single batch
        
        content = output_path.read_text()
        assert "'44625CKTPC31'" in content
    
    def test_write_sql_file_multiple_batches(self):
        """Test writing SQL file with batch number."""
        generator = SQLExtractGenerator(str(self.template_path))
        batch = ExtractBatch(batch_number=2, transaction_refs=SAMPLE_REFS[:2])
        sql = generator.generate_sql(batch)
        
        output_dir = self.temp_dir / "output"
        output_path = generator.write_sql_file(
            output_dir,
            "test_extract",
            batch,
            sql,
            total_batches=3
        )
        
        assert output_path.exists()
        assert output_path.name == "test_extract_Extract2.sql"  # Batch number included
    
    def test_generate_extracts_single_file(self):
        """Test end-to-end generation of single extract file."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=900)
        output_dir = self.temp_dir / "extracts"
        
        result = generator.generate_extracts(
            transaction_refs=SAMPLE_REFS,
            output_dir=str(output_dir),
            base_filename="test_extract"
        )
        
        # Result is a dict with sql_files and dtf_files keys
        assert 'sql_files' in result
        assert 'dtf_files' in result
        assert len(result['sql_files']) == 1
        sql_file = result['sql_files'][0]
        assert sql_file.exists()
        assert sql_file.name == "test_extract.sql"
        
        content = sql_file.read_text()
        for ref in SAMPLE_REFS:
            assert f"'{ref}'" in content
    
    def test_generate_extracts_multiple_files(self):
        """Test end-to-end generation of multiple extract files."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=2)
        output_dir = self.temp_dir / "extracts"
        
        result = generator.generate_extracts(
            transaction_refs=SAMPLE_REFS,
            output_dir=str(output_dir),
            base_filename="test_extract"
        )
        
        # Result is a dict with sql_files and dtf_files keys
        sql_files = result['sql_files']
        assert len(sql_files) == 3  # 5 refs / 2 per batch = 3 files
        assert all(f.exists() for f in sql_files)
        assert sql_files[0].name == "test_extract_Extract1.sql"
        assert sql_files[1].name == "test_extract_Extract2.sql"
        assert sql_files[2].name == "test_extract_Extract3.sql"
    
    def test_get_summary(self):
        """Test generation summary statistics."""
        generator = SQLExtractGenerator(str(self.template_path), batch_size=2)
        summary = generator.get_summary(SAMPLE_REFS)
        
        assert summary['total_transactions'] == 5
        assert summary['batch_size'] == 2
        assert summary['num_batches'] == 3
        assert 'template.sql' in summary['template']
        assert summary['placeholder'] == "--<<TRANSACTION REFERENCES>>"


class TestExtractBatch:
    """Tests for ExtractBatch dataclass."""
    
    def test_extract_batch_creation(self):
        """Test ExtractBatch creation."""
        batch = ExtractBatch(
            batch_number=1,
            transaction_refs=['REF1', 'REF2', 'REF3']
        )
        
        assert batch.batch_number == 1
        assert len(batch) == 3
        assert batch.transaction_refs == ['REF1', 'REF2', 'REF3']
    
    def test_extract_batch_len(self):
        """Test ExtractBatch length."""
        batch = ExtractBatch(batch_number=1, transaction_refs=['A', 'B'])
        assert len(batch) == 2


# ---------------------------------------------------------------------------
# VALUES block mode (incident 7_6 — Non-Zero Net Quantity)
# ---------------------------------------------------------------------------

# Template that mimics NonZeroNetQuantity.sql's CTE structure
VALUES_TEMPLATE = """\
WITH target_keys (k_firm, k_year, k_accl, k_cont, k_suff) AS (
    VALUES
{VALUES}
)
SELECT * FROM target_keys
"""

# Well-known 7_6 sample references (12 chars each)
SAMPLE_REFS_7_6 = [
    '44625CMGKHP1',
    '44625CMGKFD1',
    '44625CMGKF91',
]

# A CA reference that must be excluded
CA_REF = 'CA625CMGKHP1'


class TestValuesMode:
    """Tests for SQLExtractGenerator VALUES block mode (incident 7_6)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_path = self.temp_dir / "values_template.sql"
        self.template_path.write_text(VALUES_TEMPLATE)
        self.dtf_template_path = self.temp_dir / "AS400_DataTransfer_template.dtf"
        self.dtf_template_path.write_text(SAMPLE_DTF_TEMPLATE)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    # --- split_transaction_ref ---

    def test_split_ref_correct_fields(self):
        """split_transaction_ref returns the five correct fields."""
        result = SQLExtractGenerator.split_transaction_ref('44625CMGKHP1')
        assert result == ('446', '25', 'C', 'MGKHP', '1')

    def test_split_ref_all_positions(self):
        """Verify each field occupies the correct character positions."""
        ref = 'ABCDEFGHIJKL'  # 12 chars: ABC|DE|F|GHIJK|L
        k_firm, k_year, k_accl, k_cont, k_suff = SQLExtractGenerator.split_transaction_ref(ref)
        assert k_firm == 'ABC'
        assert k_year == 'DE'
        assert k_accl == 'F'
        assert k_cont == 'GHIJK'
        assert k_suff == 'L'

    def test_split_ref_wrong_length_raises(self):
        """split_transaction_ref raises ValueError for non-12-char input."""
        with pytest.raises(ValueError, match="exactly 12 characters"):
            SQLExtractGenerator.split_transaction_ref('SHORT')

    # --- filter_ca_refs ---

    def test_filter_ca_refs_removes_ca(self):
        """filter_ca_refs excludes references starting with CA."""
        refs = SAMPLE_REFS_7_6 + [CA_REF]
        filtered, skipped = SQLExtractGenerator.filter_ca_refs(refs)
        assert CA_REF not in filtered
        assert skipped == 1
        assert len(filtered) == len(SAMPLE_REFS_7_6)

    def test_filter_ca_refs_case_insensitive(self):
        """filter_ca_refs is case-insensitive."""
        refs = ['ca625X123456', 'CA625X123456', '44625CMGKHP1']
        filtered, skipped = SQLExtractGenerator.filter_ca_refs(refs)
        assert skipped == 2
        assert filtered == ['44625CMGKHP1']

    def test_filter_ca_refs_no_exclusions(self):
        """filter_ca_refs returns all refs when none start with CA."""
        filtered, skipped = SQLExtractGenerator.filter_ca_refs(SAMPLE_REFS_7_6)
        assert filtered == SAMPLE_REFS_7_6
        assert skipped == 0

    # --- format_values_block ---

    def test_format_values_block_structure(self):
        """format_values_block produces correctly formatted tuple rows."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        block = generator.format_values_block(SAMPLE_REFS_7_6)
        rows = block.split(',\n')
        assert len(rows) == 3
        assert rows[0].strip() == "('446','25','C','MGKHP','1')"
        assert rows[1].strip() == "('446','25','C','MGKFD','1')"
        assert rows[2].strip() == "('446','25','C','MGKF9','1')"

    def test_format_values_block_excludes_ca(self):
        """format_values_block silently excludes CA references."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        refs = SAMPLE_REFS_7_6 + [CA_REF]
        block = generator.format_values_block(refs)
        rows = block.split(',\n')
        assert len(rows) == 3  # CA ref excluded
        assert CA_REF not in block

    def test_format_values_block_indentation(self):
        """format_values_block indents each row with 8 spaces."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        block = generator.format_values_block(['44625CMGKHP1'])
        assert block.startswith('        (')

    # --- generate_sql in values_mode ---

    def test_generate_sql_values_mode(self):
        """generate_sql in values_mode replaces {VALUES} placeholder correctly."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        batch = ExtractBatch(batch_number=1, transaction_refs=SAMPLE_REFS_7_6)
        sql = generator.generate_sql(batch)
        assert "('446','25','C','MGKHP','1')" in sql
        assert '{VALUES}' not in sql

    def test_generate_sql_values_mode_excludes_ca(self):
        """generate_sql in values_mode removes CA references from output."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        refs = SAMPLE_REFS_7_6 + [CA_REF]
        batch = ExtractBatch(batch_number=1, transaction_refs=refs)
        sql = generator.generate_sql(batch)
        assert CA_REF not in sql
        assert "('446','25','C','MGKHP','1')" in sql

    def test_get_summary_includes_values_mode(self):
        """get_summary reports values_mode correctly."""
        generator = SQLExtractGenerator(str(self.template_path), values_mode=True)
        summary = generator.get_summary(SAMPLE_REFS_7_6)
        assert summary['values_mode'] is True

    def test_standard_mode_values_mode_false(self):
        """Standard generator reports values_mode as False."""
        std_template = self.temp_dir / "std.sql"
        std_template.write_text(
            "SELECT * FROM t WHERE ref IN (\n-- TRANSACTION REFERENCES --\n)"
        )
        generator = SQLExtractGenerator(str(std_template))
        summary = generator.get_summary(['44625CMGKHP1'])
        assert summary['values_mode'] is False

    def test_values_mode_auto_detected_from_placeholder(self):
        """values_mode is auto-derived from the {VALUES} placeholder without being passed explicitly."""
        generator = SQLExtractGenerator(str(self.template_path))  # no values_mode kwarg
        assert generator.values_mode is True
        assert generator.placeholder == '{VALUES}'

    def test_generate_sql_auto_values_mode(self):
        """generate_sql works correctly when values_mode is auto-detected from the template."""
        generator = SQLExtractGenerator(str(self.template_path))  # no values_mode kwarg
        batch = ExtractBatch(batch_number=1, transaction_refs=SAMPLE_REFS_7_6)
        sql = generator.generate_sql(batch)
        assert "('446','25','C','MGKHP','1')" in sql
        assert '{VALUES}' not in sql


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
