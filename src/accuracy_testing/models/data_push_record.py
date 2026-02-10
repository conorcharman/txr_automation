"""
Data Push Record Model
======================

Data structure for pushing validation results to master tracking files.

This module handles the consolidation of accuracy testing results back
to centralised tracking files after validation is complete.

Business Logic:
    - ALL records are pushed to templates for QA purposes
    - Records are matched by Transaction Reference
    - All validation columns are copied (Error, Correction, etc.)
    - Both validation outputs and templates use "Error" column name

Version: 1.1 (Updated to push all records)
Migrated from: DataPush1_0.vb
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from pathlib import Path


class PushAction(Enum):
    """Action to take for a record during push."""
    UPDATE_ALL = "update_all"      # Push all data columns (Error = Y)
    UPDATE_ERROR_ONLY = "error"    # Only update error flag (Error = N)
    SKIP = "skip"                  # Skip this record (no match or invalid)
    NOT_FOUND = "not_found"        # Transaction not found in target


@dataclass
class ColumnMapping:
    """
    Defines mapping between source and target columns.
    
    Attributes:
        source_col: Column name or index in source file
        target_col: Column name or index in target file
        description: Human-readable description of the column
    """
    source_col: str
    target_col: str
    description: str = ""
    
    def __post_init__(self):
        """Validate column mapping."""
        if not self.source_col or not self.target_col:
            raise ValueError("Both source_col and target_col must be specified")


@dataclass
class DataPushRecord:
    """
    Record representing a single row to push from source to target.
    
    Attributes:
        transaction_ref: Unique transaction identifier (match key)
        error_flag: Validation error flag (Y/N/TBC)
        source_data: Dictionary of source column values to push
        target_row_index: Row index in target file (set after matching)
        action: Push action determined during processing
        push_result: Result of the push operation
    """
    
    # Match key
    transaction_ref: str
    
    # Error status from validation
    error_flag: str = ""
    
    # Source data to push (column_name -> value)
    source_data: Dict[str, Any] = field(default_factory=dict)
    
    # Target matching
    target_row_index: int = -1
    
    # Processing state
    action: PushAction = PushAction.SKIP
    push_result: str = ""
    
    # Row tracking
    source_row_index: int = 0
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        error_column: str = "Error",
        transaction_ref_column: str = "Transaction Reference",
        row_index: int = 0
    ) -> "DataPushRecord":
        """
        Create DataPushRecord from dictionary.
        
        Args:
            data: Dictionary with column values
            error_column: Name of the error flag column
            transaction_ref_column: Name of the transaction reference column
            row_index: Source row index for tracking
            
        Returns:
            DataPushRecord instance
        """
        transaction_ref = str(data.get(transaction_ref_column, "")).strip()
        error_flag = str(data.get(error_column, "")).strip()
        
        # Push ALL records for QA purposes
        # Default to UPDATE_ALL to push all columns regardless of error status
        # This allows QA to see all records in the template
        action = PushAction.UPDATE_ALL
        
        return cls(
            transaction_ref=transaction_ref,
            error_flag=error_flag,
            source_data=dict(data),
            action=action,
            source_row_index=row_index,
        )
    
    @property
    def is_valid(self) -> bool:
        """Check if record has valid transaction reference."""
        return bool(self.transaction_ref.strip())
    
    @property
    def should_push(self) -> bool:
        """Check if record should be pushed to target."""
        return self.action in (PushAction.UPDATE_ALL, PushAction.UPDATE_ERROR_ONLY)
    
    @property
    def was_matched(self) -> bool:
        """Check if record was matched to target row."""
        return self.target_row_index >= 0
    
    def get_push_values(
        self,
        column_mappings: List[ColumnMapping]
    ) -> Dict[str, Any]:
        """
        Get values to push based on action and column mappings.
        
        Args:
            column_mappings: List of column mappings to apply
            
        Returns:
            Dictionary of target_column -> value to push
        """
        result = {}
        
        if self.action == PushAction.UPDATE_ALL:
            # Push all mapped columns (including empty values for QA)
            for mapping in column_mappings:
                if mapping.source_col in self.source_data:
                    value = self.source_data[mapping.source_col]
                    # Push all values including empty ones for QA purposes
                    result[mapping.target_col] = value if value is not None else ""
                        
        elif self.action == PushAction.UPDATE_ERROR_ONLY:
            # Only push error flag column
            for mapping in column_mappings:
                if mapping.source_col == "Error":
                    result[mapping.target_col] = "N"
                    break
        
        return result


@dataclass
class PushStats:
    """Statistics from a data push operation."""
    
    total_source: int = 0
    matched: int = 0
    not_found: int = 0
    updated_all: int = 0
    updated_error_only: int = 0
    skipped: int = 0
    errors: int = 0
    
    def as_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "total_source": self.total_source,
            "matched": self.matched,
            "not_found": self.not_found,
            "updated_all": self.updated_all,
            "updated_error_only": self.updated_error_only,
            "skipped": self.skipped,
            "errors": self.errors,
        }
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_source == 0:
            return 0.0
        return (self.matched / self.total_source) * 100


@dataclass 
class DataPushConfig:
    """
    Configuration for data push operations.
    
    Attributes:
        fiscal_year: Fiscal year (e.g., FY25, FY26)
        quarter: Quarter (e.g., Q1, Q2, Q3, Q4)
        incident_code: Incident code (e.g., 7_37, 12_17)
        source_file: Path to source CSV (validation output)
        target_file: Path to target CSV (master tracking file)
        column_mappings: List of column mappings
        error_column: Name of error column in source
        transaction_ref_column: Name of transaction reference column
        dry_run: If True, don't write changes
        backup: If True, create backup of target before modifying
    """
    
    fiscal_year: str = ""
    quarter: str = ""
    incident_code: str = ""
    source_file: Path = field(default_factory=Path)
    target_file: Path = field(default_factory=Path)
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    error_column: str = "Error"
    transaction_ref_column: str = "Transaction Reference"
    dry_run: bool = False
    backup: bool = True
    backup_dir: Optional[Path] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPushConfig":
        """
        Create configuration from dictionary.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            DataPushConfig instance
        """
        # Parse column mappings
        mappings = []
        if "column_mappings" in data:
            for mapping_data in data["column_mappings"]:
                mappings.append(ColumnMapping(
                    source_col=mapping_data.get("source", ""),
                    target_col=mapping_data.get("target", ""),
                    description=mapping_data.get("description", ""),
                ))
        
        # Get paths
        paths = data.get("paths", {})
        source_file = Path(paths.get("source_file", ""))
        target_file = Path(paths.get("target_file", ""))
        backup_dir_str = paths.get("backup_dir")
        backup_dir = Path(backup_dir_str) if backup_dir_str else None
        
        # Get testing period
        period = data.get("testing_period", {})
        
        return cls(
            fiscal_year=period.get("fiscal_year", ""),
            quarter=period.get("quarter", ""),
            incident_code=data.get("incident", {}).get("code", ""),
            source_file=source_file,
            target_file=target_file,
            column_mappings=mappings,
            error_column=data.get("columns", {}).get("error", "Error"),
            transaction_ref_column=data.get("columns", {}).get(
                "transaction_ref", "Transaction Reference"
            ),
            dry_run=data.get("options", {}).get("dry_run", False),
            backup=data.get("options", {}).get("backup", True),
            backup_dir=backup_dir,
        )


# Default column mappings for Buyer/Seller ID validation outputs
# These match the output columns from buyer_id_validation.py and seller_id_validation.py
DEFAULT_COLUMN_MAPPINGS = [
    # Identity columns
    ColumnMapping("Account ID", "Account ID", "Client account identifier"),
    ColumnMapping("Person Code", "Person Code", "Person code identifier"),
    ColumnMapping("Account Type", "Account Type", "Account type classification"),
    # ID columns (Buyer variant - replace with Seller for seller validation)
    ColumnMapping("Buyer ID Code", "Buyer ID Code", "Buyer identification code"),
    ColumnMapping("Type of Buyer ID Code", "Type of Buyer ID Code", "Type of buyer ID"),
    # Personal details
    ColumnMapping("First Name", "First Name", "Client first name"),
    ColumnMapping("Surname", "Surname", "Client surname"),
    ColumnMapping("Date of Birth", "Date of Birth", "Client date of birth"),
    ColumnMapping("Gender", "Gender", "Client gender"),
    ColumnMapping("Primary Nationality", "Primary Nationality", "Primary nationality code"),
    ColumnMapping("Secondary Nationality", "Secondary Nationality", "Secondary nationality code"),
    # Correction columns (same column names in validation output and template)
    ColumnMapping("Error", "Error", "Validation error flag (Y/N)"),
    ColumnMapping("Correction", "Correction", "Suggested correction (ID:TYPE format)"),
    ColumnMapping("Correction Field", "Correction Field", "Fields being corrected (ID:IDT format)"),
    ColumnMapping("Agree With Correction", "Agree With Correction", "Analyst agreement with correction"),
    ColumnMapping("Suggested Correction", "Suggested Correction", "Analyst suggested alternative correction"),
    ColumnMapping("Suggested Correction Field", "Suggested Correction Field", "Fields for analyst correction"),
    # Status columns
    ColumnMapping("Tracker Status", "Tracker Status", "Status from tracker system"),
    ColumnMapping("Pass/Fail", "Pass/Fail", "Format and logic validation result"),
    ColumnMapping("Failure Reason", "Failure Reason", "Specific reason for validation failure"),
    ColumnMapping("Actions Taken", "Actions Taken", "Actions taken on this record"),
    # Match columns
    ColumnMapping("Kaizen Error", "Kaizen Error", "Template lookup result (ID:TYPE)"),
    ColumnMapping("Match", "Match", "Match result (TRUE/FALSE)"),
]
