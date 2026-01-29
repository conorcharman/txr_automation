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
    ]
    
    def __init__(
        self,
        template_path: str,
        batch_size: int = 900,
        placeholder: Optional[str] = None,
        output_format: str = 'both',
        dtf_template_path: Optional[str] = None
    ):
        """
        Initialize SQL extract generator.
        
        Args:
            template_path: Path to SQL template file
            batch_size: Number of transaction refs per SQL file (default 900)
            placeholder: Custom placeholder pattern (auto-detects if None)
            output_format: Output format - 'sql', 'dtf', or 'both' (default: 'both')
            dtf_template_path: Path to DTF template file (optional, uses default if None)
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If placeholder not found in template or invalid output_format
        """
        self.template_path = Path(template_path)
        self.batch_size = batch_size
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
        
        # Load DTF template if DTF output is requested
        if self.output_format in ['dtf', 'both']:
            if dtf_template_path:
                self.dtf_template_path = Path(dtf_template_path)
            else:
                # Use default DTF template in same directory as SQL templates
                self.dtf_template_path = self.template_path.parent / 'AS400_DataTransfer_template.dtf'
            
            if not self.dtf_template_path.exists():
                raise FileNotFoundError(f"DTF template file not found: {self.dtf_template_path}")
            
            with open(self.dtf_template_path, 'r', encoding='utf-8') as f:
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
    
    def generate_sql(self, batch: ExtractBatch) -> str:
        """
        Generate SQL for a single batch.
        
        Args:
            batch: ExtractBatch containing transaction references
            
        Returns:
            Complete SQL string with refs inserted
        """
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
        }
