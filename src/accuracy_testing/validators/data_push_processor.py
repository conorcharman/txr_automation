"""
Data Push Processor
===================

Core logic for pushing validation results to master tracking files.

This processor consolidates accuracy testing results back to centralised
tracking files after validation is complete. It matches records by
transaction reference and updates target columns with validation results.

Business Logic (Updated v1.2):
    1. Load source CSV (validation output with "Error" column)
    2. Load target CSV (master tracking file/template with "Error" column)
    3. For each source record:
       a. Find matching row in target by Transaction Reference
       b. Push ALL validation columns (Error, Correction, etc.)
       c. Exception: If Error="N" and Correction has a value, do not push
          Correction or Correction Field columns (not relevant for passing records)
       d. This allows QA to see all records regardless of error status
    4. Write updated target file

Version: 1.2 (Conditional correction push based on Error flag)
Migrated from: DataPush1_0.vb
"""

import csv
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

from ..models.data_push_record import (
    DataPushRecord,
    DataPushConfig,
    PushStats,
    PushAction,
    DEFAULT_COLUMN_MAPPINGS,
)


class DataPushProcessor:
    """
    Processor for pushing validation results to master tracking files.
    
    This processor handles:
    - Loading source and target CSV files
    - Matching records by transaction reference
    - Updating target with validation results
    - Creating backups before modification
    - Writing updated target file
    """
    
    def __init__(
        self,
        config: Optional[DataPushConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize processor.
        
        Args:
            config: Data push configuration
            logger: Optional logger instance
        """
        self.config = config or DataPushConfig()
        self.logger = logger or logging.getLogger(__name__)
        
        # Data storage
        self.source_records: List[DataPushRecord] = []
        self.target_df: Optional[pd.DataFrame] = None
        self.target_index: Dict[str, int] = {}  # transaction_ref -> row index
        
        # Statistics
        self.stats = PushStats()
        
        # Use default mappings if none provided
        if not self.config.column_mappings:
            self.config.column_mappings = DEFAULT_COLUMN_MAPPINGS.copy()
    
    def load_source(self, source_path: Path) -> int:
        """
        Load source CSV file (validation output).
        
        Args:
            source_path: Path to source CSV file
            
        Returns:
            Number of records loaded
            
        Raises:
            FileNotFoundError: If source file doesn't exist
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        self.source_records = []
        
        with open(source_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            
            # Resolve the source column to use as the transaction reference.
            # Normally this is transaction_ref_column ("Transaction Reference")
            # directly in the source.  For incidents like 7_6 the source has a
            # differently-named column (e.g. "child_ref") that is mapped *to*
            # "Transaction Reference" in column_mappings.  When the standard
            # name is absent, fall back to the first mapping whose target_col
            # matches transaction_ref_column so the match key is still correct.
            ref_col = self.config.transaction_ref_column
            if ref_col not in fieldnames:
                for mapping in self.config.column_mappings:
                    if (
                        mapping.target_col == ref_col
                        and mapping.source_col in fieldnames
                    ):
                        ref_col = mapping.source_col
                        self.logger.info(
                            f"Transaction reference column '{self.config.transaction_ref_column}' "
                            f"not found in source — using mapped column '{ref_col}' instead"
                        )
                        break
            
            for row_idx, row in enumerate(reader, start=2):
                record = DataPushRecord.from_dict(
                    data=row,
                    error_column=self.config.error_column,
                    transaction_ref_column=ref_col,
                    row_index=row_idx,
                )
                
                if record.is_valid:
                    self.source_records.append(record)
                else:
                    self.logger.warning(
                        f"Row {row_idx}: Invalid record (empty transaction ref)"
                    )
        
        self.stats.total_source = len(self.source_records)
        self.logger.info(f"Loaded {len(self.source_records)} source records")
        
        return len(self.source_records)
    
    def load_target(self, target_path: Path) -> int:
        """
        Load target CSV file and build transaction reference index.
        
        Args:
            target_path: Path to target CSV file
            
        Returns:
            Number of rows in target
            
        Raises:
            FileNotFoundError: If target file doesn't exist
        """
        if not target_path.exists():
            raise FileNotFoundError(f"Target file not found: {target_path}")
        
        self.target_df = pd.read_csv(target_path, encoding="utf-8", dtype=str)
        
        # Build index for fast lookup
        self.target_index = {}
        ref_col = self.config.transaction_ref_column
        
        if ref_col not in self.target_df.columns:
            raise ValueError(
                f"Transaction reference column '{ref_col}' not found in target. "
                f"Available columns: {list(self.target_df.columns)}"
            )
        
        for idx, row in self.target_df.iterrows():
            trans_ref = str(row[ref_col]).strip()
            if trans_ref:
                self.target_index[trans_ref] = idx
        
        self.logger.info(
            f"Loaded target file with {len(self.target_df)} rows, "
            f"{len(self.target_index)} indexed"
        )
        
        return len(self.target_df)
    
    def match_records(self) -> Tuple[int, int]:
        """
        Match source records to target rows by transaction reference.
        
        Returns:
            Tuple of (matched_count, not_found_count)
        """
        matched = 0
        not_found = 0
        
        for record in self.source_records:
            if record.transaction_ref in self.target_index:
                record.target_row_index = self.target_index[record.transaction_ref]
                matched += 1
            else:
                record.action = PushAction.NOT_FOUND
                record.push_result = "Transaction reference not found in target"
                not_found += 1
                self.logger.debug(
                    f"Not found: {record.transaction_ref}"
                )
        
        self.stats.matched = matched
        self.stats.not_found = not_found
        
        self.logger.info(f"Matched {matched} records, {not_found} not found")
        
        return matched, not_found
    
    def push_data(self) -> PushStats:
        """
        Push matched source data to target DataFrame.
        
        Returns:
            PushStats with operation results
        """
        if self.target_df is None:
            raise ValueError("Target not loaded. Call load_target() first.")
        
        for record in self.source_records:
            if not record.was_matched:
                continue
            
            try:
                self._push_single_record(record)
            except Exception as e:
                record.push_result = f"Error: {str(e)}"
                self.stats.errors += 1
                self.logger.error(
                    f"Error pushing {record.transaction_ref}: {e}"
                )
        
        self.logger.info(
            f"Push complete: {self.stats.updated_all} full updates, "
            f"{self.stats.updated_error_only} error-only updates, "
            f"{self.stats.skipped} skipped"
        )
        
        return self.stats
    
    def _push_single_record(self, record: DataPushRecord) -> None:
        """
        Push a single record's data to target.
        
        Args:
            record: DataPushRecord to push
        """
        if record.action == PushAction.UPDATE_ALL:
            # Push all mapped columns
            push_values = record.get_push_values(self.config.column_mappings)
            
            # Debug logging for Error column
            if "Error" in record.source_data:
                self.logger.debug(
                    f"Transaction {record.transaction_ref}: "
                    f"Error value in source = '{record.source_data.get('Error')}', "
                    f"pushing {len(push_values)} columns"
                )
            
            for target_col, value in push_values.items():
                if target_col in self.target_df.columns:
                    self.target_df.at[record.target_row_index, target_col] = value
                else:
                    # Create column if configured to do so
                    if self.config.create_missing_columns:
                        self.logger.info(
                            f"Creating missing target column: '{target_col}'"
                        )
                        # Initialize column with empty strings
                        self.target_df[target_col] = ""
                        # Now set the value
                        self.target_df.at[record.target_row_index, target_col] = value
                    else:
                        self.logger.warning(
                            f"Target column '{target_col}' not found, skipping"
                        )
            
            record.push_result = f"Updated {len(push_values)} columns"
            self.stats.updated_all += 1
            
        elif record.action == PushAction.UPDATE_ERROR_ONLY:
            # Only update error column to "N"
            error_target_col = None
            for mapping in self.config.column_mappings:
                if mapping.source_col == self.config.error_column:
                    error_target_col = mapping.target_col
                    break
            
            if error_target_col and error_target_col in self.target_df.columns:
                self.target_df.at[record.target_row_index, error_target_col] = "N"
                record.push_result = "Updated error flag to N"
            else:
                # Fallback: use same column name as source
                if self.config.error_column in self.target_df.columns:
                    self.target_df.at[
                        record.target_row_index, 
                        self.config.error_column
                    ] = "N"
                    record.push_result = "Updated error flag to N"
            
            self.stats.updated_error_only += 1
            
        else:
            record.push_result = "Skipped"
            self.stats.skipped += 1
    
    def create_backup(self, target_path: Path) -> Optional[Path]:
        """
        Create a timestamped backup of the target file.
        
        Args:
            target_path: Path to target file
            
        Returns:
            Path to backup file, or None if backup failed
        """
        if not target_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine backup location
        if self.config.backup_dir:
            # Use configured backup directory
            backup_dir = Path(self.config.backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_filename = f"{target_path.stem}.backup_{timestamp}.csv"
            backup_path = backup_dir / backup_filename
        else:
            # Default: same directory as target file
            backup_path = target_path.with_suffix(f".backup_{timestamp}.csv")
        
        try:
            shutil.copy2(target_path, backup_path)
            self.logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return None
    
    def write_target(self, output_path: Path) -> None:
        """
        Write updated target DataFrame to CSV.
        
        Args:
            output_path: Path to write output file
        """
        if self.target_df is None:
            raise ValueError("No target data to write")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.target_df.to_csv(output_path, index=False, encoding="utf-8")
        
        self.logger.info(f"Wrote {len(self.target_df)} rows to {output_path}")
    
    def process(
        self,
        source_path: Path,
        target_path: Path,
        output_path: Optional[Path] = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> PushStats:
        """
        Run the complete data push pipeline.
        
        Args:
            source_path: Path to source CSV (validation output)
            target_path: Path to target CSV (master tracking file)
            output_path: Path for output (defaults to target_path)
            dry_run: If True, don't write changes
            backup: If True, create backup before modifying
            
        Returns:
            PushStats with operation results
        """
        # Reset stats
        self.stats = PushStats()
        
        # Set output path
        if output_path is None:
            output_path = target_path
        
        self.logger.info(f"Starting data push: {source_path} -> {target_path}")
        
        # Load files
        self.load_source(source_path)
        self.load_target(target_path)
        
        # Match records
        self.match_records()
        
        # Push data
        self.push_data()
        
        # Write output
        if not dry_run:
            if backup and output_path == target_path:
                self.create_backup(target_path)
            
            self.write_target(output_path)
        else:
            self.logger.info("Dry run - no changes written")
        
        return self.stats
    
    def get_unmatched_records(self) -> List[DataPushRecord]:
        """
        Get list of source records that weren't found in target.
        
        Returns:
            List of unmatched DataPushRecord instances
        """
        return [
            r for r in self.source_records 
            if r.action == PushAction.NOT_FOUND
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of push operation.
        
        Returns:
            Dictionary with operation summary
        """
        return {
            "config": {
                "fiscal_year": self.config.fiscal_year,
                "quarter": self.config.quarter,
                "incident_code": self.config.incident_code,
            },
            "stats": self.stats.as_dict(),
            "success_rate": f"{self.stats.success_rate:.1f}%",
            "column_mappings": [
                {"source": m.source_col, "target": m.target_col}
                for m in self.config.column_mappings
            ],
        }


class BatchDataPushProcessor:
    """
    Processor for batch data push operations across multiple incidents.
    
    Handles pushing validation results for multiple incident codes
    in a single run.
    """
    
    def __init__(
        self,
        base_source_dir: Path,
        base_target_dir: Path,
        fiscal_year: str,
        quarter: str,
        column_mappings: Optional[List] = None,
        backup_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize batch processor.
        
        Args:
            base_source_dir: Base directory for source files
            base_target_dir: Base directory for target files
            fiscal_year: Fiscal year (e.g., FY26)
            quarter: Quarter (e.g., Q1)
            column_mappings: Optional list of column mappings to use
            backup_dir: Optional directory for backup files
            logger: Optional logger instance
        """
        self.base_source_dir = Path(base_source_dir)
        self.base_target_dir = Path(base_target_dir)
        self.fiscal_year = fiscal_year
        self.quarter = quarter
        self.column_mappings = column_mappings
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self.logger = logger or logging.getLogger(__name__)
        
        # Results storage
        self.results: Dict[str, PushStats] = {}
    
    def discover_incidents(self) -> List[str]:
        """
        Discover available incident codes from source directory.
        
        Returns:
            List of incident codes found
        """
        incidents = set()
        
        # Try multiple naming patterns to discover incidents
        patterns = [
            f"validated_{self.fiscal_year}_{self.quarter}_*.csv",  # New validation output format
            f"{self.fiscal_year} {self.quarter} - *.csv",          # Legacy/template format
            f"*_validated.csv",                                     # Generic fallback
        ]
        
        for pattern in patterns:
            for file in self.base_source_dir.glob(pattern):
                name = file.stem
                
                # Extract incident code based on pattern
                if name.startswith(f"validated_{self.fiscal_year}_{self.quarter}_"):
                    # Pattern: validated_FY25_Q4_7_37.csv or validated_FY25_Q4_7_37_errors_only.csv
                    suffix = name.replace(f"validated_{self.fiscal_year}_{self.quarter}_", "")
                    # Remove _errors_only suffix if present
                    incident = suffix.replace("_errors_only", "")
                    incidents.add(incident)
                elif " - " in name:
                    # Pattern: FY25 Q4 - 7_37.csv
                    incident = name.split(" - ")[-1]
                    incidents.add(incident)
                elif name.endswith("_validated"):
                    # Pattern: 7_37_validated.csv
                    incident = name.replace("_validated", "")
                    incidents.add(incident)
        
        incidents = sorted(list(incidents))
        self.logger.info(f"Discovered {len(incidents)} incidents: {incidents}")
        return incidents
    
    def process_batch(
        self,
        incidents: Optional[List[str]] = None,
        dry_run: bool = False,
        backup: bool = True,
    ) -> Dict[str, PushStats]:
        """
        Process multiple incidents in batch.
        
        Args:
            incidents: List of incident codes (or None to auto-discover)
            dry_run: If True, don't write changes
            backup: If True, create backups
            
        Returns:
            Dictionary of incident_code -> PushStats
        """
        if incidents is None:
            incidents = self.discover_incidents()
        
        self.results = {}
        
        for incident in incidents:
            try:
                stats = self._process_incident(incident, dry_run, backup)
                self.results[incident] = stats
            except Exception as e:
                self.logger.error(f"Failed to process {incident}: {e}")
                self.results[incident] = PushStats(errors=1)
        
        return self.results
    
    def _process_incident(
        self,
        incident: str,
        dry_run: bool,
        backup: bool,
    ) -> PushStats:
        """
        Process a single incident.
        
        Args:
            incident: Incident code
            dry_run: If True, don't write changes
            backup: If True, create backup
            
        Returns:
            PushStats for this incident
        """
        # Try multiple naming patterns for target file (master tracking files)
        target_patterns = [
            f"{incident}_{self.fiscal_year}_{self.quarter}.csv",      # Standard format: 7_42_FY25_Q4.csv
            f"{self.fiscal_year} {self.quarter} {incident}.csv",      # Legacy: FY25 Q4 7_42.csv
            f"{self.fiscal_year} {self.quarter} - {incident}.csv",    # Legacy with dash
            f"{incident}.csv",                                         # Generic fallback
        ]
        
        target_path = None
        for pattern in target_patterns:
            candidate = self.base_target_dir / pattern
            if candidate.exists():
                target_path = candidate
                self.logger.debug(f"Found target file: {pattern}")
                break
        
        if target_path is None:
            raise FileNotFoundError(
                f"Target file not found for {incident}. Tried patterns: {target_patterns}"
            )
        
        # Try multiple naming patterns for source file (validation outputs)
        source_patterns = [
            f"validated_{self.fiscal_year}_{self.quarter}_{incident}.csv",  # New validation output format
            f"{self.fiscal_year} {self.quarter} - {incident}.csv",          # Legacy/template format
            f"{incident}_validated.csv",                                     # Generic fallback
        ]
        
        source_path = None
        for pattern in source_patterns:
            candidate = self.base_source_dir / pattern
            if candidate.exists():
                source_path = candidate
                self.logger.debug(f"Found source file: {pattern}")
                break
        
        if source_path is None:
            raise FileNotFoundError(
                f"Source file not found for {incident}. Tried patterns: {source_patterns}"
            )
        
        # Create processor and run
        config = DataPushConfig(
            fiscal_year=self.fiscal_year,
            quarter=self.quarter,
            incident_code=incident,
            column_mappings=self.column_mappings or [],
            backup_dir=self.backup_dir,
        )
        
        processor = DataPushProcessor(config=config, logger=self.logger)
        
        return processor.process(
            source_path=source_path,
            target_path=target_path,
            dry_run=dry_run,
            backup=backup,
        )
    
    def get_batch_summary(self) -> Dict[str, Any]:
        """
        Get summary of batch operation.
        
        Returns:
            Dictionary with batch summary
        """
        total_source = sum(s.total_source for s in self.results.values())
        total_matched = sum(s.matched for s in self.results.values())
        total_updated = sum(
            s.updated_all + s.updated_error_only 
            for s in self.results.values()
        )
        
        return {
            "incidents_processed": len(self.results),
            "total_source_records": total_source,
            "total_matched": total_matched,
            "total_updated": total_updated,
            "by_incident": {
                code: stats.as_dict() 
                for code, stats in self.results.items()
            },
        }
