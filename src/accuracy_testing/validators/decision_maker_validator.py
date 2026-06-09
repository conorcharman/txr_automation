"""
Decision Maker Validator
========================

Validation logic for Fund Trade Decision Maker records.

Incident Codes:
    - 12_17: Buyer Decision Maker validation
    - 21_17: Seller Decision Maker validation

Business Rules:
    1. SIPP accounts: Always no error (exempt from validation)
    2. Non-discretionary accounts: Always no error
    3. Discretionary accounts (Service Level = "D"):
       - If DM Code is empty → Error, provide LEI correction
       - If DM Code equals Party Code → Error, provide correct LEI
       - If DM Code is different from Party Code → No error

Version: 1.1
Migrated from: ValidateFTBDM3_0.vb, ValidateFTSDM3_0.vb
"""

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models.decision_maker_record import DecisionMakerRecord, determine_product

# Import shared core library for ID format validation
try:
    from src.core.data.id_formats import id_format_manager

    _CORE_FORMAT_MANAGER_AVAILABLE = True
except ImportError:
    try:
        from core.data.id_formats import id_format_manager

        _CORE_FORMAT_MANAGER_AVAILABLE = True
    except ImportError:
        _CORE_FORMAT_MANAGER_AVAILABLE = False
        id_format_manager = None


# LEI format pattern (ISO 17442): 18 alphanumeric + 2 digit checksum
LEI_PATTERN = re.compile(r"^[A-Z0-9]{18}\d{2}$")


@dataclass
class ValidationStats:
    """Statistics from Decision Maker validation run."""

    total: int = 0
    no_error: int = 0
    error: int = 0
    tbc: int = 0
    skipped_sipp: int = 0
    skipped_non_discretionary: int = 0

    def as_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "no_error": self.no_error,
            "error": self.error,
            "tbc": self.tbc,
            "skipped_sipp": self.skipped_sipp,
            "skipped_non_discretionary": self.skipped_non_discretionary,
        }


class LEILookupManager:
    """
    Manages LEI reference data lookup.

    The LEI lookup maps Branch Codes to Legal Entity Identifiers.
    Used to find the correct decision maker LEI when validation fails.
    """

    def __init__(self, lei_data: Optional[Dict[str, str]] = None):
        """
        Initialize LEI lookup manager.

        Args:
            lei_data: Dictionary mapping branch_code -> LEI
        """
        self._lookup: Dict[str, str] = lei_data or {}

    @classmethod
    def from_csv(cls, csv_path: Path) -> "LEILookupManager":
        """
        Load LEI lookup data from CSV file.

        Args:
            csv_path: Path to CSV file with columns: Branch Code, LEI

        Returns:
            LEILookupManager instance

        CSV Format:
            Branch Code,LEI
            ABC001,549300FUNDMANAGER0001
            XYZ002,549300FUNDMANAGER0002
        """
        lookup: Dict[str, str] = {}

        if not csv_path.exists():
            logging.warning(f"LEI data file not found: {csv_path}")
            return cls(lookup)

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # Skip header

            for row in reader:
                if len(row) >= 2:
                    branch = str(row[0]).strip()
                    lei = str(row[1]).strip()
                    if branch:
                        lookup[branch] = lei

        logging.info(f"Loaded {len(lookup)} LEI mappings from {csv_path}")
        return cls(lookup)

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "LEILookupManager":
        """
        Create from dictionary.

        Args:
            data: Dictionary mapping branch_code -> LEI

        Returns:
            LEILookupManager instance
        """
        return cls(data)

    def lookup(self, branch_code: str) -> Tuple[bool, str]:
        """
        Look up LEI for a branch code.

        Args:
            branch_code: Branch/Partner code

        Returns:
            Tuple of (branch_exists, lei_value)
        """
        branch_code = branch_code.strip()
        if branch_code in self._lookup:
            return True, self._lookup[branch_code]
        return False, ""

    def __len__(self) -> int:
        """Return number of LEI mappings."""
        return len(self._lookup)


class IDFormatValidator:
    """
    Validate and classify identification codes.

    Delegates to the shared core library ``id_format_manager`` so that all
    validators use the same canonical regex patterns.  LEI is checked first
    (as before) because it is the most common type for decision-maker codes.
    """

    def validate(self, id_code: str) -> str:
        """
        Validate an ID code and return its type.

        Args:
            id_code: The identification code to validate

        Returns:
            ID type string ("LEI", "NIDN", "CONCAT", "CCPT") if matched,
            empty string if no match.
        """
        if not id_code or not id_code.strip():
            return ""

        id_code = id_code.strip().upper()

        # Check LEI first (most common for decision maker codes)
        if LEI_PATTERN.match(id_code):
            return "LEI"

        # Delegate remaining type detection to the core library
        if _CORE_FORMAT_MANAGER_AVAILABLE and id_format_manager is not None:
            detected = id_format_manager.validate_any_type("", id_code)
            if detected:
                return detected
            # If no country-specific match, try common cross-country types
            for id_type in ("NIDN", "CONCAT", "CCPT"):
                patterns = id_format_manager.get_patterns_for_type(id_type)
                if any(p.matches(id_code) for p in patterns):
                    return id_type

        return ""


class DecisionMakerValidator:
    """
    Validate Decision Maker codes for fund trades.

    This validator ensures discretionary accounts have the correct
    decision maker code populated and different from the party code.
    """

    def __init__(
        self,
        lei_lookup: LEILookupManager,
        id_validator: Optional[IDFormatValidator] = None,
        party_type: str = "Buyer",
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize validator.

        Args:
            lei_lookup: LEI lookup manager for branch → LEI mapping
            id_validator: Optional ID format validator
            party_type: "Buyer" or "Seller" for correction field names
            logger: Optional logger instance
        """
        self.lei_lookup = lei_lookup
        self.id_validator = id_validator or IDFormatValidator()
        self.party_type = party_type
        self.logger = logger or logging.getLogger(__name__)

    def validate_record(self, record: DecisionMakerRecord) -> None:
        """
        Validate a single Decision Maker record.

        Args:
            record: DecisionMakerRecord to validate (modified in place)

        The record is updated with:
            - party_code_type: Validated ID type of party code
            - dm_code_type: Validated ID type of DM code
            - product: Derived product type
            - error: N/Y/TBC status
            - correction: LEI correction if error
            - correction_field: Field being corrected
        """
        # Initialize defaults
        record.error = "N"
        record.correction = ""
        record.correction_field = ""

        # Validate ID formats
        record.party_code_type = self.id_validator.validate(record.party_code)
        record.dm_code_type = self.id_validator.validate(record.dm_code)

        # Determine product from account ID
        record.product = determine_product(record.account_id)

        # Step 1: SIPP accounts - no validation needed
        if record.is_sipp:
            self.logger.debug(f"{record.transaction_ref}: SIPP account, skipping")
            return

        # Step 2: Check if discretionary
        if not record.is_discretionary:
            self.logger.debug(f"{record.transaction_ref}: Non-discretionary, skipping")
            return

        # Step 3: Discretionary validation
        self._validate_discretionary(record)

    def _validate_discretionary(self, record: DecisionMakerRecord) -> None:
        """
        Validate discretionary account decision maker.

        Three scenarios:
        1. DM Code empty → Error, provide LEI
        2. DM Code = Party Code → Error, provide correct LEI
        3. DM Code different → No error
        """
        branch_code = record.branch_code.strip()
        dm_code = record.dm_code.strip()
        party_code = record.party_code.strip()

        branch_exists, decision_maker_lei = self.lei_lookup.lookup(branch_code)

        if record.dm_is_empty:
            # Scenario 1: DM Code is empty
            self._handle_empty_dm(record, branch_exists, decision_maker_lei)

        elif record.dm_equals_party_code:
            # Scenario 2: DM Code equals Party Code
            self._handle_same_value(record, branch_exists, decision_maker_lei, dm_code)

        else:
            # Scenario 3: Different values - no error
            self.logger.debug(
                f"{record.transaction_ref}: DM code differs from party code, valid"
            )
            record.error = "N"

    def _handle_empty_dm(
        self, record: DecisionMakerRecord, branch_exists: bool, lei: str
    ) -> None:
        """Handle case where DM code is empty."""
        if branch_exists:
            if lei:
                record.correction = f"{lei}:L"
                record.correction_field = record.correction_field_template
                record.error = "Y"
                self.logger.info(
                    f"{record.transaction_ref}: Empty DM, correction: {lei}"
                )
            else:
                # Branch found but LEI is empty
                record.error = "Y"
                self.logger.warning(
                    f"{record.transaction_ref}: Empty DM, branch found but LEI empty"
                )
        else:
            record.error = "TBC - Investigate branch code"
            self.logger.warning(
                f"{record.transaction_ref}: Empty DM, branch not found: {record.branch_code}"
            )

    def _handle_same_value(
        self,
        record: DecisionMakerRecord,
        branch_exists: bool,
        lei: str,
        current_dm: str,
    ) -> None:
        """Handle case where DM code equals Party code."""
        if branch_exists:
            if lei and lei != current_dm:
                record.correction = f"{lei}:L"
                record.correction_field = record.correction_field_template
                record.error = "Y"
                self.logger.info(
                    f"{record.transaction_ref}: DM equals party code, correction: {lei}"
                )
            else:
                record.error = "TBC - Investigate LEI"
                self.logger.warning(
                    f"{record.transaction_ref}: DM equals party code, cannot determine LEI"
                )
        else:
            record.error = "TBC - Investigate branch code"
            self.logger.warning(
                f"{record.transaction_ref}: DM equals party code, branch not found"
            )

    def validate_batch(self, records: List[DecisionMakerRecord]) -> ValidationStats:
        """
        Validate a batch of records.

        Args:
            records: List of DecisionMakerRecord to validate

        Returns:
            ValidationStats with counts
        """
        stats = ValidationStats(total=len(records))

        for record in records:
            # Track before validation
            was_sipp = record.is_sipp
            was_discretionary = record.is_discretionary

            # Validate
            self.validate_record(record)

            # Update stats
            if was_sipp:
                stats.skipped_sipp += 1
            elif not was_discretionary:
                stats.skipped_non_discretionary += 1

            if record.error == "N":
                stats.no_error += 1
            elif record.error == "Y":
                stats.error += 1
            else:
                stats.tbc += 1

        return stats


class DecisionMakerProcessor:
    """
    Complete processing pipeline for Decision Maker validation.

    Handles:
    - Loading input data from CSV
    - Loading LEI reference data
    - Validating all records
    - Writing output with results
    """

    def __init__(
        self,
        party_type: str = "Buyer",
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize processor.

        Args:
            party_type: "Buyer" or "Seller"
            logger: Optional logger instance
        """
        self.party_type = party_type
        self.logger = logger or logging.getLogger(__name__)
        self.lei_lookup: Optional[LEILookupManager] = None
        self.validator: Optional[DecisionMakerValidator] = None
        self.records: List[DecisionMakerRecord] = []

    def load_lei_data(self, lei_path: Path) -> None:
        """
        Load LEI reference data.

        Args:
            lei_path: Path to LEI CSV file
        """
        self.lei_lookup = LEILookupManager.from_csv(lei_path)
        self.logger.info(f"Loaded {len(self.lei_lookup)} LEI mappings")

    def load_input_csv(self, input_path: Path) -> int:
        """
        Load input data from CSV.

        Args:
            input_path: Path to input CSV file

        Returns:
            Number of records loaded
        """
        self.records = []

        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            for row_idx, row in enumerate(reader, start=2):
                if len(row) < 7:
                    self.logger.warning(
                        f"Row {row_idx}: insufficient columns (need 7, got {len(row)}), skipping"
                    )
                    continue

                try:
                    record = DecisionMakerRecord.from_row(
                        row, party_type=self.party_type, row_index=row_idx
                    )
                    self.records.append(record)
                except Exception as e:
                    self.logger.error(f"Row {row_idx}: parse error - {e}")

        self.logger.info(f"Loaded {len(self.records)} records from {input_path}")
        return len(self.records)

    def process(self) -> ValidationStats:
        """
        Run validation on all loaded records.

        Returns:
            ValidationStats with results
        """
        if not self.lei_lookup:
            raise ValueError("LEI data not loaded. Call load_lei_data() first.")

        # Initialize validator (IDFormatValidator uses core library)
        self.validator = DecisionMakerValidator(
            lei_lookup=self.lei_lookup,
            id_validator=IDFormatValidator(),
            party_type=self.party_type,
            logger=self.logger,
        )

        # Validate all records
        stats = self.validator.validate_batch(self.records)

        self.logger.info(
            f"Validation complete: {stats.total} total, "
            f"{stats.no_error} no error, {stats.error} errors, {stats.tbc} TBC"
        )

        return stats

    def write_output_csv(self, output_path: Path) -> None:
        """
        Write results to CSV file.

        Args:
            output_path: Path to output CSV file
        """
        if not self.records:
            self.logger.warning("No records to write")
            return

        # Get headers from first record
        headers = self.records[0].get_output_headers()

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for record in self.records:
                writer.writerow(record.to_output_row())

        self.logger.info(f"Wrote {len(self.records)} records to {output_path}")
