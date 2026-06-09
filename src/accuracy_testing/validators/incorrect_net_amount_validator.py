"""
Incorrect Net Amount Validation Logic
======================================

Core validation logic for incorrect net amount data (Incident Code 35_3).

Validates the mathematical relationship:
    Net Amount = Consideration + Interest
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from ..models.incorrect_net_amount_record import IncorrectNetAmountRecord

logger = logging.getLogger(__name__)


# Instrument classification code → instrument type mapping.
# 3-character codes take priority over 2-character codes during lookup.
INSTRUMENT_TYPE_MAP: dict[str, str] = {
    # 3-character codes (checked first)
    "DAF": "Debt",
    # 2-character codes (fallback)
    "DB": "Debt",
    "DC": "Debt",
    "DW": "Debt",
    "DT": "Debt",
    "DG": "Debt",
    "DN": "Debt",
    "DD": "Debt",
    "DY": "Debt",
    "DA": "Equity",
    "DE": "Equity",
    "DS": "Equity",
    "DM": "Equity",
}


class IncorrectNetAmountValidator:
    """
    Validates pricing data for transactions.

    Validates that Net Amount equals the sum of Consideration and Interest,
    within a specified tolerance for floating-point comparison.

    Usage:
        validator = IncorrectNetAmountValidator(tolerance=Decimal('0.01'))
        validator.validate_record(record)
        # record.error will be "N" or "TBC"
        # record.total, expected_interest, net_difference will be calculated
    """

    def __init__(self, tolerance: Decimal = Decimal("0.01"), verbose: bool = False):
        """
        Initialize validator.

        Args:
            tolerance: Tolerance for floating-point comparison (default 0.01)
            verbose: Enable verbose logging (default False)
        """
        self.tolerance = tolerance
        self.verbose = verbose

        if self.verbose:
            logger.info(
                f"IncorrectNetAmountValidator initialized with tolerance={self.tolerance}"
            )

    def validate_record(self, record: IncorrectNetAmountRecord) -> None:
        """
        Validate a single pricing record.

        First applies instrument pre-validation to classify the record as Debt
        or Equity. Equity records with a net amount are flagged with Error="Y"
        and bypass the net-amount arithmetic. All other records proceed to the
        standard 35_3 calculation.

        Args:
            record: IncorrectNetAmountRecord to validate

        Modifies:
            record.instrument_type
            record.total
            record.expected_interest
            record.net_difference
            record.error

        Raises:
            ValueError: If record has invalid numeric values

        Example:
            >>> record = IncorrectNetAmountRecord(
            ...     transaction_ref='TEST001',
            ...     net_amount=Decimal('1150.00'),
            ...     consideration=Decimal('1000.00'),
            ...     interest=Decimal('150.00')
            ... )
            >>> validator.validate_record(record)
            >>> print(record.error)  # "N"
            >>> print(record.net_difference)  # Decimal('0.00')
        """
        try:
            # Stage 1: Instrument pre-validation
            self.apply_pre_validation(record)

            # Stage 2: Net-amount arithmetic (35_3 logic) — Debt and unclassified only
            if record.error == "N":
                record.calculate_fields(self.tolerance)

            if record.error == "Y" and self.verbose:
                logger.info(
                    f"Pre-validation: {record.transaction_ref} classified as Equity "
                    "— net amount error flagged (Y)"
                )
            elif record.error == "TBC" and self.verbose:
                logger.warning(
                    f"Incorrect net amount discrepancy for {record.transaction_ref}: "
                    f"Net Difference = {record.net_difference}"
                )
            elif self.verbose:
                logger.debug(f"Record {record.transaction_ref} validated successfully")

        except Exception as e:
            logger.error(f"Error validating record {record.transaction_ref}: {e}")
            record.error = "ERROR"
            record.comments = f"Validation Error: {str(e)}"
            raise

    def validate_batch(self, records: List[IncorrectNetAmountRecord]) -> Dict[str, int]:
        """
        Validate a batch of incorrect net amount records.

        Args:
            records: List of IncorrectNetAmountRecords to validate

        Returns:
            Dictionary with validation statistics:
                - total: Total number of records processed
                - valid: Records with no error (error = "N")
                - invalid: Records with discrepancy (error = "TBC" or "Y")
                - errors: Records that failed validation (error = "ERROR")

        Example:
            >>> records = [record1, record2, record3]
            >>> stats = validator.validate_batch(records)
            >>> print(f"Processed {stats['total']}, {stats['invalid']} invalid")
        """
        stats = {"total": len(records), "valid": 0, "invalid": 0, "errors": 0}

        for record in records:
            try:
                self.validate_record(record)

                if record.error == "N":
                    stats["valid"] += 1
                elif record.error in ("TBC", "Y"):
                    stats["invalid"] += 1
                else:
                    stats["errors"] += 1

            except Exception as e:
                logger.error(f"Failed to validate {record.transaction_ref}: {e}")
                record.error = "ERROR"
                stats["errors"] += 1

        if self.verbose:
            logger.info(
                f"Batch validation complete: {stats['valid']} valid, "
                f"{stats['invalid']} invalid, {stats['errors']} errors"
            )

        return stats

    @staticmethod
    def classify_instrument(classification_code: Optional[str]) -> Optional[str]:
        """
        Derive instrument type from a classification code.

        Tries the first 3 characters of the code first, then falls back to the
        first 2 characters.  Returns ``None`` when the code is absent or does
        not match any known prefix.

        Args:
            classification_code: Raw instrument classification string (e.g. ``"DAFEQ"``).

        Returns:
            ``"Debt"``, ``"Equity"``, or ``None``.

        Examples:
            >>> IncorrectNetAmountValidator.classify_instrument("DAF")
            'Debt'
            >>> IncorrectNetAmountValidator.classify_instrument("DA123")
            'Equity'
            >>> IncorrectNetAmountValidator.classify_instrument("XYZ")
            None
            >>> IncorrectNetAmountValidator.classify_instrument(None)
            None
        """
        if not classification_code:
            return None
        code = classification_code.strip().upper()
        if code[:3] in INSTRUMENT_TYPE_MAP:
            return INSTRUMENT_TYPE_MAP[code[:3]]
        if code[:2] in INSTRUMENT_TYPE_MAP:
            return INSTRUMENT_TYPE_MAP[code[:2]]
        return None

    def apply_pre_validation(self, record: IncorrectNetAmountRecord) -> None:
        """
        Apply instrument-type pre-validation to a record.

        Sets ``record.instrument_type`` from the classification code and flags
        Equity records with ``Error="Y"``.  Records without a recognised
        instrument type pass through with ``Error="N"`` for subsequent 35_3
        arithmetic.

        Pre-validation rules:
            - Equity instrument type → ``Error = "Y"``
            - All other cases (Debt, unmatched, null) → ``Error = "N"``

        Args:
            record: IncorrectNetAmountRecord to pre-validate (mutated in place).
        """
        record.instrument_type = self.classify_instrument(
            record.instrument_classification
        )
        if record.instrument_type == "Equity":
            record.error = "Y"
        else:
            record.error = "N"

    def validate_record_safe(self, record: IncorrectNetAmountRecord) -> None:
        """
        Validate record with error handling (does not raise exceptions).

        Args:
            record: IncorrectNetAmountRecord to validate

        Modifies:
            record.error (set to "ERROR" if validation fails)
            record.comments (set to error message if validation fails)
        """
        try:
            self.validate_record(record)
        except Exception as e:
            logger.error(f"Validation failed for {record.transaction_ref}: {e}")
            record.error = "ERROR"
            record.comments = f"Validation Error: {str(e)}"
