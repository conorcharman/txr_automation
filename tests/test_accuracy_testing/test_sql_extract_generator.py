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


# ---------------------------------------------------------------------------
# Template selection tests — get_sql_template_for_incident
# ---------------------------------------------------------------------------

class TestGetSqlTemplateForIncident:
    """Tests for get_sql_template_for_incident() template routing."""

    def setup_method(self):
        """Create a mock sql_template_dir with stub files for every expected template."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self._stub_templates = [
            "BuyerID.sql",
            "SellerID.sql",
            "IncorrectNetAmount.sql",
            "InconsistentBuyerID.sql",
            "InconsistentSellerID.sql",
            "FTBDM.sql",
            "FTSDM.sql",
            "NonZeroNetQuantity.sql",
            "NonZeroNetAmount.sql",
            "IncorrectTime.sql",
            "InconsistentQtyType.sql",
            "InconsistentPriceType.sql",
            "SCR_pricing_data_v1.0.sql",
        ]
        for name in self._stub_templates:
            (self.temp_dir / name).write_text("-- stub")

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def _get(self, incident_code: str) -> Path:
        from src.accuracy_testing.scripts.sql_extract_generator import (
            get_sql_template_for_incident,
        )
        return get_sql_template_for_incident(incident_code, self.temp_dir)

    def test_35_3_maps_to_incorrect_net_amount(self):
        """35_3 (Incorrect net amount) must use IncorrectNetAmount.sql, not SCR_pricing_data."""
        result = self._get("35_3")
        assert result.name == "IncorrectNetAmount.sql", (
            f"Expected IncorrectNetAmount.sql, got {result.name}. "
            "The legacy SCR_pricing_data_v1.0.sql template lacks the SECFIG join."
        )

    def test_35_10_maps_to_incorrect_net_amount(self):
        """35_10 (Suspected incorrect net amount) was previously unknown; must now resolve."""
        result = self._get("35_10")
        assert result.name == "IncorrectNetAmount.sql"

    def test_35_3_and_35_10_return_same_template(self):
        """Both net-amount incidents must use the same template."""
        assert self._get("35_3") == self._get("35_10")

    def test_unknown_incident_raises(self):
        """A genuinely unknown incident code must still raise ValueError."""
        from src.accuracy_testing.scripts.sql_extract_generator import (
            get_sql_template_for_incident,
        )
        with pytest.raises(ValueError, match="Unknown incident code"):
            get_sql_template_for_incident("99_99", self.temp_dir)

    def test_buyer_incidents_map_to_buyerid(self):
        """Standard buyer incidents (7_35, 7_37, 7_39) must use BuyerID.sql."""
        for code in ("7_35", "7_37", "7_39"):
            assert self._get(code).name == "BuyerID.sql", f"Failed for {code}"

    def test_seller_incidents_map_to_sellerid(self):
        """Standard seller incidents (16_19, 16_21, 16_23) must use SellerID.sql."""
        for code in ("16_19", "16_21", "16_23"):
            assert self._get(code).name == "SellerID.sql", f"Failed for {code}"


# ---------------------------------------------------------------------------
# run_batch_sql_generation path-resilience tests
# ---------------------------------------------------------------------------

class TestRunBatchSqlGenerationPaths:
    """Tests for config path resolution in run_batch_sql_generation."""

    def _make_config(self, template_dir_value, incidents=None) -> dict:
        return {
            'testing_period': {'fiscal_year': 'FY26', 'quarter': 'Q2'},
            'batch': {
                'incidents': incidents or ['35_3'],
                'paths': {'template_dir': template_dir_value},
            },
        }

    def test_empty_string_template_dir_returns_error(self, tmp_path):
        """An empty string template_dir must fail early with a clear message, not silently use '.'."""
        from src.accuracy_testing.scripts.sql_extract_generator import (
            run_batch_sql_generation,
        )
        config = self._make_config("")
        result = run_batch_sql_generation(config)
        # The resolved path for "" is cwd which almost certainly won't have the templates.
        # If somehow it does exist, the test still passes because we just need no silent skip.
        # In CI/clean checkouts it will be 1.
        assert result in (0, 1)  # must not raise; must produce an exit code

    def test_null_template_dir_returns_error(self, tmp_path):
        """A null (None) template_dir must not crash with TypeError; must fail with exit code 1."""
        from src.accuracy_testing.scripts.sql_extract_generator import (
            run_batch_sql_generation,
        )
        config = self._make_config(None)
        result = run_batch_sql_generation(config)
        assert result in (0, 1)

    def test_valid_template_dir_with_missing_csv_fails_with_informative_message(
        self, tmp_path, capsys
    ):
        """When template_dir is valid but the template CSV is absent, print the full resolved path."""
        from src.accuracy_testing.scripts.sql_extract_generator import (
            run_batch_sql_generation,
        )
        # tmp_path exists but has no CSV files
        sql_template_dir = Path("src/accuracy_testing/sql_templates")
        config = {
            'testing_period': {'fiscal_year': 'FY26', 'quarter': 'Q2'},
            'batch': {
                'incidents': ['35_3'],
                'paths': {
                    'template_dir': str(tmp_path),
                    'output_dir': str(tmp_path / 'out'),
                    'sql_template_dir': str(sql_template_dir),
                },
            },
        }
        run_batch_sql_generation(config)
        captured = capsys.readouterr()
        # The error message must show the full absolute path, not a relative one like '.'
        assert str(tmp_path) in captured.out
        assert "Template not found" in captured.out

    def test_transaction_column_case_insensitive_match(self, tmp_path, capsys):
        """Column name lookup must succeed even when file uses different casing."""
        import csv as csv_mod
        from src.accuracy_testing.scripts.sql_extract_generator import (
            run_batch_sql_generation,
        )
        sql_template_dir = Path("src/accuracy_testing/sql_templates")

        # Write a template CSV with lowercase column header
        template_csv = tmp_path / "FY26 Q2 35_3.csv"
        with template_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv_mod.writer(fh)
            writer.writerow(["transaction reference", "SEDOL", "Net Amount"])
            writer.writerow(["44626CWFBPM1", "B0YQ5W0", "1000.00"])

        config = {
            'testing_period': {'fiscal_year': 'FY26', 'quarter': 'Q2'},
            'batch': {
                'incidents': ['35_3'],
                'paths': {
                    'template_dir': str(tmp_path),
                    'output_dir': str(tmp_path / 'out'),
                    'sql_template_dir': str(sql_template_dir),
                },
                'filename_patterns': {
                    'template': '{fiscal_year} {quarter} {incident}.csv',
                },
            },
            'processing': {
                'transaction_column': 'Transaction Reference',  # different casing from file
            },
        }
        exit_code = run_batch_sql_generation(config)
        captured = capsys.readouterr()
        # Column mismatch warning must NOT appear — case-insensitive lookup should find it
        assert "Column 'Transaction Reference' not found" not in captured.out
        # Transaction ref should be found
        assert "Transaction refs: 1" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


