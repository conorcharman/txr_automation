"""
SQL Extract Generator
=====================

Unified generator for creating SQL extract files from CSV transaction references.
Replaces multiple VBA scripts (ExtractBuyerID, ExtractInconsistentBuyerID, SCR_extract_generator).

This module provides:
- Template-based SQL generation
- Flexible placeholder detection and replacement
- Batch splitting (configurable, default 900 records)
- Multiple output file generation
- Support for various incident types via templates

Author: Transaction Reporting Team
Date: January 22, 2026
Version: 1.0
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

REF_LENGTH = 12


@dataclass
class ExtractBatch:
    """Represents a batch of transaction references for SQL generation."""
    batch_number: int
    transaction_refs: List[str]
    
    def __len__(self) -> int:
        return len(self.transaction_refs)


class SQLExtractGenerator:
    """
    Generates SQL extract files from templates and transaction reference CSV files.
    
    Features:
    - Loads SQL templates from files
    - Detects placeholder patterns automatically
    - Splits large transaction lists into batches
    - Generates multiple SQL files (one per batch)
    - Supports custom placeholder formats
    """
    
    # Common placeholder patterns (in order of preference for auto-detection)
    PLACEHOLDER_PATTERNS = [
        r'-- TRANSACTION REFERENCES --',
        r'--<<TRANSACTION REFERENCES>>',
        r'--<TRADE REFERENCES>--',
        r'--\{TRANSACTION_REFS\}--',
        r'--\[TRANSACTION REFERENCES\]--',
        r'{VALUES}',
    ]

    # Incidents that use a VALUES block instead of an IN-clause
    VALUES_MODE_INCIDENTS = {'7_6', '7_42'}
    
    def __init__(
        self,
        template_path: str,
        batch_size: int = 900,
        placeholder: Optional[str] = None,
        output_format: str = 'both',
        dtf_template_path: Optional[str] = None,
        values_mode: bool = False
    ):
        """
        Initialize SQL extract generator.
        
        Args:
            template_path: Path to SQL template file
            batch_size: Number of transaction refs per SQL file (default 900)
            placeholder: Custom placeholder pattern (auto-detects if None)
            output_format: Output format - 'sql', 'dtf', or 'both' (default: 'both')
            dtf_template_path: Path to DTF template file (optional, uses default if None)
            values_mode: If True, format refs as a DB2 VALUES block instead of an IN-clause.
                         Each 12-character reference is split into its five component fields
                         and references beginning with 'CA' are excluded.
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If placeholder not found in template or invalid output_format
        """
        self.template_path = Path(template_path)
        self.batch_size = batch_size
        self.values_mode = values_mode
        self.custom_placeholder = placeholder
        
        # Validate output format
        valid_formats = ['sql', 'dtf', 'both']
        if output_format not in valid_formats:
            raise ValueError(f"Invalid output_format: {output_format}. Must be one of: {', '.join(valid_formats)}")
        self.output_format = output_format
        
        # Load SQL template
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        with open(self.template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()
        
        # Detect or validate placeholder
        self.placeholder = self._detect_placeholder()
        
        if not self.placeholder:
            raise ValueError(
                f"No placeholder found in template. Expected one of: {', '.join(self.PLACEHOLDER_PATTERNS)}"
            )

        # Auto-derive values_mode when the template uses a {VALUES} block.
        # This means callers do not need to know the template style in advance.
        if not self.values_mode and self.placeholder == '{VALUES}':
            self.values_mode = True
        
        # Load DTF template if DTF output is requested
        if self.output_format in ['dtf', 'both']:
            if dtf_template_path:
                self.dtf_template_path = Path(dtf_template_path)
            else:
                # Use default DTF template in same directory as SQL templates
                self.dtf_template_path = self.template_path.parent / 'AS400_DataTransfer_template.dtf'
            
            if not self.dtf_template_path.exists():
                raise FileNotFoundError(f"DTF template file not found: {self.dtf_template_path}")
            
            # DTF files from AS/400 use Windows-1252 (CP1252) encoding
            with open(self.dtf_template_path, 'r', encoding='cp1252') as f:
                self.dtf_template = f.read()
    
    def _detect_placeholder(self) -> Optional[str]:
        """
        Detect placeholder pattern in template.
        
        Returns:
            Detected placeholder pattern or None if not found
        """
        # If custom placeholder provided, validate it exists
        if self.custom_placeholder:
            if self.custom_placeholder in self.template:
                return self.custom_placeholder
            else:
                raise ValueError(
                    f"Custom placeholder '{self.custom_placeholder}' not found in template"
                )
        
        # Auto-detect from common patterns
        for pattern in self.PLACEHOLDER_PATTERNS:
            # Use regex search to handle special characters
            if re.search(re.escape(pattern), self.template):
                return pattern
        
        return None
    
    def create_batches(self, transaction_refs: List[str]) -> List[ExtractBatch]:
        """
        Split transaction references into batches.
        
        Args:
            transaction_refs: List of transaction reference strings
            
        Returns:
            List of ExtractBatch objects
        """
        batches = []
        batch_number = 1
        
        for i in range(0, len(transaction_refs), self.batch_size):
            batch_refs = transaction_refs[i:i + self.batch_size]
            batches.append(ExtractBatch(
                batch_number=batch_number,
                transaction_refs=batch_refs
            ))
            batch_number += 1
        
        return batches
    
    def format_transaction_refs(self, refs: List[str]) -> str:
        """
        Format transaction references for SQL IN clause.
        
        Args:
            refs: List of transaction references
            
        Returns:
            Formatted SQL string (e.g., "'REF1',\n'REF2',\n'REF3'")
        """
        # Quote each reference and join with comma + newline
        formatted = []
        for ref in refs:
            # Strip whitespace and add quotes
            clean_ref = ref.strip()
            if clean_ref:  # Skip empty refs
                formatted.append(f"'{clean_ref}'")
        
        return ',\n'.join(formatted)

    @staticmethod
    def split_transaction_ref(ref: str) -> Tuple[str, str, str, str, str]:
        """
        Split a 12-character transaction reference into its five DB2 component fields.

        Field layout (1-based):
            k_firm: chars 1–3   (firm code)
            k_year: chars 4–5   (year)
            k_accl: char  6     (account letter)
            k_cont: chars 7–11  (contract number)
            k_suff: char  12    (suffix)

        Args:
            ref: Exactly 12-character transaction reference (e.g. '44625CMGKHP1')

        Returns:
            Tuple of (k_firm, k_year, k_accl, k_cont, k_suff)

        Raises:
            ValueError: If ref is not exactly 12 characters

        Example:
            >>> SQLExtractGenerator.split_transaction_ref('44625CMGKHP1')
            ('446', '25', 'C', 'MGKHP', '1')
        """
        if len(ref) != REF_LENGTH:
            raise ValueError(
                f"Transaction reference must be exactly {REF_LENGTH} characters: '{ref}' "
                f"(got {len(ref)})"
            )
        return ref[0:3], ref[3:5], ref[5], ref[6:11], ref[11]

    @staticmethod
    def filter_ca_refs(refs: List[str]) -> Tuple[List[str], int]:
        """
        Filter out transaction references beginning with 'CA'.

        References starting with 'CA' use a different field schema and are not
        compatible with the CRSNET VALUES-block template.

        Args:
            refs: List of transaction reference strings

        Returns:
            Tuple of (filtered_refs, skipped_count) where filtered_refs excludes
            any references whose first two characters are 'CA' (case-insensitive)
            and skipped_count is the number of excluded references.
        """
        filtered = [r for r in refs if not r.strip().upper().startswith('CA')]
        return filtered, len(refs) - len(filtered)

    def format_values_block(self, refs: List[str]) -> str:
        """
        Format transaction references as a DB2 VALUES block for use in a CTE.

        Each reference is split into its five component fields and rendered as a
        tuple row.  References beginning with 'CA' are silently excluded.

        Args:
            refs: List of transaction reference strings

        Returns:
            Multi-line string of comma-separated tuple rows, e.g.::

                        ('446','25','C','MGKHP','1'),
                        ('446','25','C','MGKFD','1'),
                        ('446','25','C','MGKF9','1')

        Raises:
            ValueError: If any (non-CA) reference is not exactly 12 characters
        """
        indent = '        '  # 8 spaces — matches the template indentation
        rows = []
        for ref in refs:
            clean_ref = ref.strip()
            if not clean_ref:
                continue
            if clean_ref.upper().startswith('CA'):
                continue
            k_firm, k_year, k_accl, k_cont, k_suff = self.split_transaction_ref(clean_ref)
            rows.append(
                f"{indent}('{k_firm}','{k_year}','{k_accl}','{k_cont}','{k_suff}')"
            )
        return ',\n'.join(rows)

    def generate_sql(self, batch: ExtractBatch) -> str:
        """
        Generate SQL for a single batch.
        
        Args:
            batch: ExtractBatch containing transaction references
            
        Returns:
            Complete SQL string with refs inserted.
            In values_mode, refs are formatted as a DB2 VALUES block and CA
            references are excluded automatically.
        """
        if self.values_mode:
            refs_sql = self.format_values_block(batch.transaction_refs)
            if not refs_sql.strip():
                raise ValueError(
                    f"Batch {batch.batch_number}: VALUES mode produced an empty block. "
                    f"All {len(batch.transaction_refs)} reference(s) were CA-prefix and were "
                    f"excluded. This template requires non-CA contract keys as input."
                )
        else:
            # Format transaction refs
            refs_sql = self.format_transaction_refs(batch.transaction_refs)
        
        # Replace placeholder with formatted refs
        sql = self.template.replace(self.placeholder, refs_sql)
        
        return sql
    
    def format_sql_for_dtf(self, sql: str) -> str:
        """
        Format SQL for DTF file (single line, no newlines).
        
        Args:
            sql: Multi-line SQL string
            
        Returns:
            Single-line SQL string suitable for DTF format
        """
        # Replace all newlines and multiple spaces with single space
        formatted = ' '.join(sql.split())
        return formatted
    
    def write_dtf_file(
        self,
        output_dir: Path,
        base_filename: str,
        batch: ExtractBatch,
        sql: str,
        incident_code: str,
        total_batches: int = 1
    ) -> Path:
        """
        Write DTF (AS/400 Data Transfer) file.
        
        Args:
            output_dir: Output directory path
            base_filename: Base name for output file (without extension)
            batch: Batch information (for numbering)
            sql: SQL content to embed
            incident_code: Incident code for CSV output path
            total_batches: Total number of batches (for filename formatting)
            
        Returns:
            Path to written DTF file
        """
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: {base}_Extract{batch_number}.dtf
        if total_batches == 1:
            filename = f"{base_filename}.dtf"
            csv_filename = f"{incident_code}.csv"
        else:
            filename = f"{base_filename}_Extract{batch.batch_number}.dtf"
            csv_filename = f"{incident_code}_Extract{batch.batch_number}.csv"
        
        output_path = output_dir / filename
        
        # Format SQL for DTF (single line)
        sql_formatted = self.format_sql_for_dtf(sql)
        
        # Get parent directory for CSV path (output_dir should be parent/dtf)
        parent_dir = output_dir.parent
        csv_path = parent_dir / "csv" / csv_filename
        
        # Replace placeholders in DTF template
        dtf_content = self.dtf_template.replace('{SQL_QUERY}', sql_formatted)
        dtf_content = dtf_content.replace('{OUTPUT_PATH}', str(csv_path))
        
        # Write DTF file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dtf_content)
        
        return output_path
    
    def write_sql_file(
        self,
        output_dir: Path,
        base_filename: str,
        batch: ExtractBatch,
        sql: str,
        total_batches: int = 1
    ) -> Path:
        """
        Write SQL to file.
        
        Args:
            output_dir: Output directory path
            base_filename: Base name for output file (without extension)
            batch: Batch information (for numbering)
            sql: SQL content to write
            total_batches: Total number of batches (for filename formatting)
            
        Returns:
            Path to written file
        """
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename: {base}_Extract{batch_number}.sql
        if total_batches == 1:
            # Single batch - no number suffix
            filename = f"{base_filename}.sql"
        else:
            # Multiple batches - add number suffix
            filename = f"{base_filename}_Extract{batch.batch_number}.sql"
        
        output_path = output_dir / filename
        
        # Write SQL file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sql)
        
        return output_path
    
    def generate_extracts(
        self,
        transaction_refs: List[str],
        output_dir: str,
        base_filename: str,
        incident_code: Optional[str] = None
    ) -> dict:
        """
        Generate all extract files (SQL and/or DTF).
        
        Args:
            transaction_refs: List of transaction references
            output_dir: Parent directory for output files (will create /csv and /dtf subdirs)
            base_filename: Base name for output files
            incident_code: Incident code for CSV naming (defaults to base_filename if None)
            
        Returns:
            Dictionary with 'sql_files' and 'dtf_files' lists of generated file paths
        """
        if incident_code is None:
            incident_code = base_filename
        
        parent_dir = Path(output_dir)
        
        # Create output subdirectories based on format
        # SQL files always go to /sql directory (for both 'sql' and 'both' formats)
        sql_dir = parent_dir / 'sql'
        dtf_dir = parent_dir / 'dtf'
        
        # Create batches
        batches = self.create_batches(transaction_refs)
        total_batches = len(batches)
        
        # Generate files for each batch
        generated_files = {'sql_files': [], 'dtf_files': []}
        
        for batch in batches:
            sql = self.generate_sql(batch)
            
            # Write SQL file if requested
            if self.output_format in ['sql', 'both']:
                sql_path = self.write_sql_file(
                    sql_dir,
                    base_filename,
                    batch,
                    sql,
                    total_batches=total_batches
                )
                generated_files['sql_files'].append(sql_path)
            
            # Write DTF file if requested
            if self.output_format in ['dtf', 'both']:
                dtf_path = self.write_dtf_file(
                    dtf_dir,
                    base_filename,
                    batch,
                    sql,
                    incident_code,
                    total_batches=total_batches
                )
                generated_files['dtf_files'].append(dtf_path)
        
        return generated_files
    
    def get_summary(self, transaction_refs: List[str]) -> dict:
        """
        Get generation summary statistics.
        
        Args:
            transaction_refs: List of transaction references
            
        Returns:
            Dictionary with summary statistics
        """
        batches = self.create_batches(transaction_refs)
        
        return {
            'total_transactions': len(transaction_refs),
            'batch_size': self.batch_size,
            'num_batches': len(batches),
            'template': str(self.template_path),
            'placeholder': self.placeholder,
            'values_mode': self.values_mode,
        }
