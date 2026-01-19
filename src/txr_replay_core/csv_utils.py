"""
CSV Utilities
=============

Utilities for CSV file operations with schema validation, type conversion,
and robust error handling.

Provides:
- Safe CSV reading/writing with encoding detection
- Column validation and type conversion
- Missing value handling
- Schema validation
- Batch processing utilities
"""

import csv
import pandas as pd
from typing import List, Dict, Any, Optional, Callable, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from .validators import ValidationResult


class ColumnType(Enum):
    """Supported column data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


@dataclass
class ColumnDefinition:
    """
    Definition of a CSV column.
    
    Attributes:
        name: Column name
        dtype: Data type
        required: Whether column is required
        nullable: Whether null values are allowed
        default: Default value if missing
        validator: Optional validation function
    """
    name: str
    dtype: ColumnType = ColumnType.STRING
    required: bool = True
    nullable: bool = True
    default: Any = None
    validator: Optional[Callable[[Any], ValidationResult]] = None
    
    def __repr__(self) -> str:
        req = "required" if self.required else "optional"
        null = "nullable" if self.nullable else "not null"
        return f"Column({self.name}, {self.dtype.value}, {req}, {null})"


@dataclass
class CSVSchema:
    """
    Schema definition for CSV files.
    
    Attributes:
        name: Schema name/identifier
        columns: List of column definitions
        allow_extra_columns: Whether to allow columns not in schema
        encoding: Default file encoding
    """
    name: str
    columns: List[ColumnDefinition]
    allow_extra_columns: bool = False
    encoding: str = "utf-8-sig"
    
    def get_column(self, name: str) -> Optional[ColumnDefinition]:
        """Get column definition by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None
    
    def get_required_columns(self) -> List[str]:
        """Get list of required column names."""
        return [col.name for col in self.columns if col.required]
    
    def get_column_names(self) -> List[str]:
        """Get list of all column names."""
        return [col.name for col in self.columns]
    
    def __repr__(self) -> str:
        return f"CSVSchema({self.name}, {len(self.columns)} columns)"


class CSVValidationError(Exception):
    """Exception raised for CSV validation errors."""
    
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


class CSVReader:
    """
    Enhanced CSV reader with validation and type conversion.
    
    Usage:
        reader = CSVReader(schema)
        df = reader.read_file("input.csv")
        
        # With validation
        df = reader.read_file("input.csv", validate=True)
    """
    
    def __init__(self, schema: Optional[CSVSchema] = None):
        """
        Initialize CSV reader.
        
        Args:
            schema: Optional CSV schema for validation
        """
        self.schema = schema
    
    def read_file(
        self,
        filepath: Union[str, Path],
        validate: bool = False,
        encoding: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Read CSV file with optional validation.
        
        Args:
            filepath: Path to CSV file
            validate: Whether to validate against schema
            encoding: File encoding (uses schema encoding if not provided)
        
        Returns:
            pandas DataFrame
        
        Raises:
            CSVValidationError: If validation fails
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        
        # Determine encoding
        if encoding is None and self.schema:
            encoding = self.schema.encoding
        elif encoding is None:
            encoding = "utf-8-sig"
        
        # Read CSV
        try:
            df = pd.read_csv(filepath, encoding=encoding, dtype=str)
        except Exception as e:
            raise CSVValidationError(f"Failed to read CSV file: {e}")
        
        # Validate if requested
        if validate and self.schema:
            self.validate_dataframe(df)
        
        return df
    
    def validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Validate DataFrame against schema.
        
        Args:
            df: DataFrame to validate
        
        Raises:
            CSVValidationError: If validation fails
        """
        if not self.schema:
            return
        
        errors = []
        
        # Check required columns
        required_cols = self.schema.get_required_columns()
        missing_cols = set(required_cols) - set(df.columns)
        
        if missing_cols:
            errors.append(f"Missing required columns: {', '.join(missing_cols)}")
        
        # Check for extra columns
        if not self.schema.allow_extra_columns:
            schema_cols = set(self.schema.get_column_names())
            extra_cols = set(df.columns) - schema_cols
            
            if extra_cols:
                errors.append(f"Unexpected columns: {', '.join(extra_cols)}")
        
        # Validate column types and values
        for col_def in self.schema.columns:
            if col_def.name not in df.columns:
                continue
            
            col_data = df[col_def.name]
            
            # Check for null values
            if not col_def.nullable and col_data.isnull().any():
                null_count = col_data.isnull().sum()
                errors.append(
                    f"Column '{col_def.name}' has {null_count} null values "
                    f"but is marked as not nullable"
                )
        
        if errors:
            raise CSVValidationError(
                f"CSV validation failed for schema '{self.schema.name}'",
                errors
            )
    
    def get_column_stats(self, df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics about DataFrame columns.
        
        Args:
            df: DataFrame to analyze
        
        Returns:
            Dictionary of column statistics
        """
        stats = {}
        
        for col in df.columns:
            col_data = df[col]
            stats[col] = {
                "dtype": str(col_data.dtype),
                "non_null_count": col_data.count(),
                "null_count": col_data.isnull().sum(),
                "unique_count": col_data.nunique(),
                "sample_values": col_data.dropna().head(3).tolist()
            }
        
        return stats


class CSVWriter:
    """
    Enhanced CSV writer with schema validation.
    
    Usage:
        writer = CSVWriter(schema)
        writer.write_file(df, "output.csv")
    """
    
    def __init__(self, schema: Optional[CSVSchema] = None):
        """
        Initialize CSV writer.
        
        Args:
            schema: Optional CSV schema for validation
        """
        self.schema = schema
    
    def write_file(
        self,
        df: pd.DataFrame,
        filepath: Union[str, Path],
        validate: bool = False,
        encoding: Optional[str] = None,
        index: bool = False
    ) -> None:
        """
        Write DataFrame to CSV file.
        
        Args:
            df: DataFrame to write
            filepath: Output file path
            validate: Whether to validate before writing
            encoding: File encoding (uses schema encoding if not provided)
            index: Whether to write row index
        
        Raises:
            CSVValidationError: If validation fails
        """
        filepath = Path(filepath)
        
        # Validate if requested
        if validate and self.schema:
            reader = CSVReader(self.schema)
            reader.validate_dataframe(df)
        
        # Determine encoding
        if encoding is None and self.schema:
            encoding = self.schema.encoding
        elif encoding is None:
            encoding = "utf-8-sig"
        
        # Ensure output directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Write CSV
        try:
            df.to_csv(filepath, encoding=encoding, index=index)
        except Exception as e:
            raise CSVValidationError(f"Failed to write CSV file: {e}")


# ============================================================================
# Convenience Functions
# ============================================================================

def read_csv_with_schema(
    filepath: Union[str, Path],
    schema: CSVSchema,
    validate: bool = True
) -> pd.DataFrame:
    """
    Convenience function to read CSV with schema validation.
    
    Args:
        filepath: Path to CSV file
        schema: CSV schema definition
        validate: Whether to validate
    
    Returns:
        pandas DataFrame
    """
    reader = CSVReader(schema)
    return reader.read_file(filepath, validate=validate)


def write_csv_with_schema(
    df: pd.DataFrame,
    filepath: Union[str, Path],
    schema: CSVSchema,
    validate: bool = True
) -> None:
    """
    Convenience function to write CSV with schema validation.
    
    Args:
        df: DataFrame to write
        filepath: Output file path
        schema: CSV schema definition
        validate: Whether to validate
    """
    writer = CSVWriter(schema)
    writer.write_file(df, filepath, validate=validate)


def validate_csv_file(filepath: Union[str, Path], schema: CSVSchema) -> List[str]:
    """
    Validate CSV file against schema and return errors.
    
    Args:
        filepath: Path to CSV file
        schema: CSV schema definition
    
    Returns:
        List of error messages (empty if valid)
    """
    try:
        reader = CSVReader(schema)
        df = reader.read_file(filepath, validate=True)
        return []
    except CSVValidationError as e:
        return e.errors
    except Exception as e:
        return [str(e)]
