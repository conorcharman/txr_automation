"""
Pricing Validation Logic
=========================

Core validation logic for pricing data (Incident Code 35_3).

Validates the mathematical relationship:
    Net Amount = Consideration + Interest
"""

from typing import List, Dict
from decimal import Decimal
import logging

from ..models.pricing_record import PricingRecord

logger = logging.getLogger(__name__)


class PricingValidator:
    """
    Validates pricing data for transactions.
    
    Validates that Net Amount equals the sum of Consideration and Interest,
    within a specified tolerance for floating-point comparison.
    
    Usage:
        validator = PricingValidator(tolerance=Decimal('0.01'))
        validator.validate_record(record)
        # record.error will be "N" or "TBC"
        # record.total, expected_interest, net_difference will be calculated
    """
    
    def __init__(self, tolerance: Decimal = Decimal('0.01'), verbose: bool = False):
        """
        Initialize validator.
        
        Args:
            tolerance: Tolerance for floating-point comparison (default 0.01)
            verbose: Enable verbose logging (default False)
        """
        self.tolerance = tolerance
        self.verbose = verbose
        
        if self.verbose:
            logger.info(f"PricingValidator initialized with tolerance={self.tolerance}")
    
    def validate_record(self, record: PricingRecord) -> None:
        """
        Validate a single pricing record.
        
        Calculates derived fields and sets error status based on net difference.
        
        Args:
            record: PricingRecord to validate
        
        Modifies:
            record.total
            record.expected_interest
            record.net_difference
            record.error
        
        Raises:
            ValueError: If record has invalid numeric values
        
        Example:
            >>> record = PricingRecord(
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
            # Perform calculations
            record.calculate_fields(self.tolerance)
            
            # Log discrepancies
            if record.error == "TBC" and self.verbose:
                logger.warning(
                    f"Pricing discrepancy for {record.transaction_ref}: "
                    f"Net Difference = {record.net_difference}"
                )
            elif self.verbose:
                logger.debug(f"Record {record.transaction_ref} validated successfully")
                
        except Exception as e:
            logger.error(f"Error validating record {record.transaction_ref}: {e}")
            record.error = "ERROR"
            record.comments = f"Validation Error: {str(e)}"
            raise
    
    def validate_batch(self, records: List[PricingRecord]) -> Dict[str, int]:
        """
        Validate a batch of pricing records.
        
        Args:
            records: List of PricingRecords to validate
        
        Returns:
            Dictionary with validation statistics:
                - total: Total number of records processed
                - valid: Records with no error (error = "N")
                - invalid: Records with discrepancy (error = "TBC")
                - errors: Records that failed validation (error = "ERROR")
        
        Example:
            >>> records = [record1, record2, record3]
            >>> stats = validator.validate_batch(records)
            >>> print(f"Processed {stats['total']}, {stats['invalid']} invalid")
        """
        stats = {
            'total': len(records),
            'valid': 0,
            'invalid': 0,
            'errors': 0
        }
        
        for record in records:
            try:
                self.validate_record(record)
                
                if record.error == "N":
                    stats['valid'] += 1
                elif record.error == "TBC":
                    stats['invalid'] += 1
                else:
                    stats['errors'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to validate {record.transaction_ref}: {e}")
                record.error = "ERROR"
                stats['errors'] += 1
        
        if self.verbose:
            logger.info(
                f"Batch validation complete: {stats['valid']} valid, "
                f"{stats['invalid']} invalid, {stats['errors']} errors"
            )
        
        return stats
    
    def validate_record_safe(self, record: PricingRecord) -> None:
        """
        Validate record with error handling (does not raise exceptions).
        
        Args:
            record: PricingRecord to validate
        
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
