"""
Pricing Validation Record Model
================================

Data structure for pricing validation (Incident Code 35_3).

Validates the relationship: Net Amount = Consideration + Interest
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass
class PricingRecord:
    """
    Pricing validation record representing a single transaction.
    
    Validates pricing using the formula:
        Net Amount = Consideration + Interest
    
    Input Fields (from database/CSV):
        - transaction_ref: Unique transaction identifier
        - net_amount: Net transaction amount
        - consideration: Consideration amount (base price)
        - interest: Interest amount (accrued interest)
    
    Output Fields (calculated):
        - total: Consideration + Interest
        - expected_interest: Consideration - Net Amount
        - net_difference: Total - Net Amount
        - error: "N" (no error) or "TBC" (to be confirmed)
    
    Static Fields (optional):
        - correction: Correction value (if applicable)
        - correction_field: Field being corrected
        - comments: Additional notes
    """
    
    # Primary identifier
    transaction_ref: str
    
    # Input fields (from database/CSV)
    net_amount: Decimal
    consideration: Decimal
    interest: Decimal
    
    # Output fields (calculated - initialized to 0)
    total: Decimal = field(default_factory=lambda: Decimal('0'))
    expected_interest: Decimal = field(default_factory=lambda: Decimal('0'))
    net_difference: Decimal = field(default_factory=lambda: Decimal('0'))
    error: str = field(default="N")
    
    # Static/optional fields
    correction: Optional[str] = None
    correction_field: Optional[str] = None
    comments: Optional[str] = None
    
    def calculate_fields(self, tolerance: Decimal = Decimal('0.01')) -> None:
        """
        Calculate all derived fields and determine error status.
        
        Calculations:
            1. Total = Consideration + Interest
            2. Expected Interest = Consideration - Net Amount
            3. Net Difference = Total - Net Amount
            4. Error = "TBC" if |Net Difference| > tolerance else "N"
        
        Args:
            tolerance: Acceptable tolerance for floating-point comparison (default 0.01)
        
        Modifies:
            self.total
            self.expected_interest
            self.net_difference
            self.error
        """
        # Step 1: Calculate Total
        self.total = self.consideration + self.interest
        
        # Step 2: Calculate Expected Interest
        self.expected_interest = self.consideration - self.net_amount
        
        # Step 3: Calculate Net Difference
        self.net_difference = self.total - self.net_amount
        
        # Step 4: Determine Error Status
        if abs(self.net_difference) <= tolerance:
            self.error = "N"  # No error
        else:
            self.error = "TBC"  # To Be Confirmed - requires investigation
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PricingRecord':
        """
        Create PricingRecord from dictionary (e.g., database row or CSV row).
        
        Args:
            data: Dictionary with keys matching expected field names:
                - REPORTREF or transaction_ref: Transaction reference
                - NETAMT or net_amount: Net amount
                - CLICSD or consideration: Consideration amount
                - INTRST or interest: Interest amount
        
        Returns:
            PricingRecord instance
        
        Example:
            >>> data = {
            ...     'REPORTREF': '44625CKTPC31',
            ...     'NETAMT': '1150.00',
            ...     'CLICSD': '1000.00',
            ...     'INTRST': '150.00'
            ... }
            >>> record = PricingRecord.from_dict(data)
        """
        # Support both database column names and Python field names
        transaction_ref = str(data.get('REPORTREF') or data.get('transaction_ref', ''))
        net_amount = Decimal(str(data.get('NETAMT') or data.get('net_amount', 0)))
        consideration = Decimal(str(data.get('CLICSD') or data.get('consideration', 0)))
        interest = Decimal(str(data.get('INTRST') or data.get('interest', 0)))
        
        return cls(
            transaction_ref=transaction_ref,
            net_amount=net_amount,
            consideration=consideration,
            interest=interest
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PricingRecord to dictionary for CSV output.
        
        Returns:
            Dictionary with all fields suitable for CSV writing
        
        Example:
            >>> record.to_dict()
            {
                'Transaction Reference': '44625CKTPC31',
                'Error': 'N',
                'Net Amount': '1150.00',
                ...
            }
        """
        return {
            'Transaction Reference': self.transaction_ref,
            'Error': self.error,
            'Correction': self.correction or '',
            'Correction Field': self.correction_field or '',
            'Comments': self.comments or '',
            'Net Amount': float(self.net_amount),
            'Consideration': float(self.consideration),
            'Interest': float(self.interest),
            'Total': float(self.total),
            'Expected Interest': float(self.expected_interest),
            'Net Difference': float(self.net_difference)
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"PricingRecord(ref={self.transaction_ref}, "
                f"error={self.error}, diff={self.net_difference})")
