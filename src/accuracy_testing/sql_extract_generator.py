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
        placeholder: Optional[str] = None
    ):
        """
        Initialize SQL extract generator.
        
        Args:
            template_path: Path to SQL template file
            batch_size: Number of transaction refs per SQL file (default 900)
            placeholder: Custom placeholder pattern (auto-detects if None)
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If placeholder not found in template
        """
        self.template_path = Path(template_path)
        self.batch_size = batch_size
        self.custom_placeholder = placeholder
        
        # Load template
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
        base_filename: str
    ) -> List[Path]:
        """
        Generate all SQL extract files.
        
        Args:
            transaction_refs: List of transaction references
            output_dir: Directory for output SQL files
            base_filename: Base name for output files
            
        Returns:
            List of paths to generated SQL files
        """
        output_dir_path = Path(output_dir)
        
        # Create batches
        batches = self.create_batches(transaction_refs)
        total_batches = len(batches)
        
        # Generate SQL for each batch
        generated_files = []
        for batch in batches:
            sql = self.generate_sql(batch)
            output_path = self.write_sql_file(
                output_dir_path,
                base_filename,
                batch,
                sql,
                total_batches=total_batches
            )
            generated_files.append(output_path)
        
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
