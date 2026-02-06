"""
Decision Maker Validation Record Model
======================================

Data structure for Fund Trade Decision Maker validation.

Incident Codes:
    - 12_17: Buyer Decision Maker validation
    - 21_17: Seller Decision Maker validation

Business Rule:
    For discretionary accounts (Service Level = "D"):
    - Decision Maker Code MUST be populated
    - Decision Maker Code MUST be different from Buyer/Seller Code
    - If either condition fails, provide the correct LEI as correction

Version: 1.0
Migrated from: ValidateFTBDM3_0.vb, ValidateFTSDM3_0.vb
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class Product(Enum):
    """Product type derived from Account ID prefix."""
    AJB = "AJB"
    AJBIC = "AJBIC"
    DODL = "DODL"
    CUSTODY_SOLUTIONS = "Custody Solutions"


class ServiceLevel(Enum):
    """Service level classification for accounts."""
    DISCRETIONARY = "D"
    ADVISORY = "A"
    EXECUTION_ONLY = "E"


@dataclass
class DecisionMakerRecord:
    """
    Decision Maker validation record for fund trades.

    This record validates that discretionary trading accounts have the correct
    decision maker code populated. When a trade is executed on a discretionary
    basis, the decision maker (typically a fund manager or investment advisor)
    must be identified separately from the account holder.

    Attributes:
        transaction_ref: Unique transaction identifier (Column 1)
        account_id: Client account identifier (Column 2)
        party_code: Buyer/Seller identification code (Column 3)
        party_code_type: Type of party ID - LEI, NIDN, etc. (Column 4, Output)
        dm_code: Decision maker code (Column 5)
        dm_code_type: Type of DM ID (Column 6, Output)
        product: Product type derived from account ID (Column 7, Output)
        account_type: Account category - SIPP, Custody Solutions, etc. (Column 8)
        service_level: D=Discretionary, A=Advisory, E=Execution (Column 9)
        branch_code: Branch/Partner code for LEI lookup (Column 10)
        error: Validation error flag - N/Y/TBC (Column 11, Output)
        correction: Suggested correction value (Column 12, Output)
        correction_field: Field name(s) being corrected (Column 13, Output)

    Party Type:
        The 'party_type' field determines whether this is for buyer or seller:
        - "Buyer": Uses buyer-specific field names in corrections
        - "Seller": Uses seller-specific field names in corrections
    """

    # Primary identifier
    transaction_ref: str

    # Input fields
    account_id: str
    party_code: str  # Buyer Code or Seller Code
    dm_code: str  # Buyer DM Code or Seller DM Code
    account_type: str
    service_level: str
    branch_code: str

    # Party type for field naming
    party_type: str = "Buyer"  # "Buyer" or "Seller"

    # Output fields (calculated)
    party_code_type: str = ""
    dm_code_type: str = ""
    product: str = ""
    error: str = "N"
    correction: str = ""
    correction_field: str = ""

    # Row tracking (optional, for debugging)
    row_index: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], party_type: str = "Buyer") -> "DecisionMakerRecord":
        """
        Create DecisionMakerRecord from dictionary.

        Args:
            data: Dictionary with column values
            party_type: "Buyer" or "Seller"

        Returns:
            DecisionMakerRecord instance

        Column Mapping:
            For Buyer: party_code = Buyer Code, dm_code = Buyer DM Code
            For Seller: party_code = Seller Code, dm_code = Seller DM Code
        """
        # Determine field names based on party type
        if party_type.lower() == "seller":
            code_field = "Seller Code"
            dm_field = "Seller DM Code"
        else:
            code_field = "Buyer Code"
            dm_field = "Buyer DM Code"

        return cls(
            transaction_ref=str(data.get("Transaction Reference", "")).strip(),
            account_id=str(data.get("Account ID", "")).strip(),
            party_code=str(data.get(code_field, "")).strip(),
            dm_code=str(data.get(dm_field, "")).strip(),
            account_type=str(data.get("Account Type", "")).strip(),
            service_level=str(data.get("Service Level", "")).strip(),
            branch_code=str(data.get("Branch Code", "")).strip(),
            party_type=party_type,
            row_index=data.get("row_index", 0),
        )

    @classmethod
    def from_row(
        cls,
        row: list,
        party_type: str = "Buyer",
        row_index: int = 0
    ) -> "DecisionMakerRecord":
        """
        Create DecisionMakerRecord from CSV row list.

        Args:
            row: List of column values (minimum 10 columns required)
            party_type: "Buyer" or "Seller"
            row_index: Row number for tracking

        Returns:
            DecisionMakerRecord instance

        Input Column Indices (0-based, 10 columns minimum):
            0: Transaction Reference
            1: Account ID
            2: Party Code (Buyer/Seller)
            3: Type of Buyer/Seller ID (output column)
            4: DM Code (Buyer/Seller Decision Maker)
            5: Type of Buyer/Seller DM ID (output column)
            6: Product (output column)
            7: Account Type
            8: Service Level
            9: Branch Code

        Output columns (already included in input for validation):
            - Type of Buyer/Seller ID (column 3)
            - Type of Buyer/Seller DM ID (column 5)
            - Product (column 6)
            - Error, Correction, Correction Field (added after validation)
        """
        if len(row) < 10:
            raise ValueError(f"Row must have at least 10 columns, got {len(row)}")

        return cls(
            transaction_ref=str(row[0]).strip() if row[0] else "",
            account_id=str(row[1]).strip() if row[1] else "",
            party_code=str(row[2]).strip() if row[2] else "",
            dm_code=str(row[4]).strip() if len(row) > 4 and row[4] else "",
            account_type=str(row[7]).strip() if len(row) > 7 and row[7] else "",
            service_level=str(row[8]).strip() if len(row) > 8 and row[8] else "",
            branch_code=str(row[9]).strip() if len(row) > 9 and row[9] else "",
            party_type=party_type,
            row_index=row_index,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert record to dictionary for output.

        Returns:
            Dictionary with all field values using appropriate column names.
        """
        # Use party-specific field names
        if self.party_type.lower() == "seller":
            code_name = "Seller Code"
            code_type_name = "Type of Seller ID"
            dm_code_name = "Seller DM Code"
            dm_code_type_name = "Type of Seller DM ID"
        else:
            code_name = "Buyer Code"
            code_type_name = "Type of Buyer ID"
            dm_code_name = "Buyer DM Code"
            dm_code_type_name = "Type of Buyer DM ID"

        return {
            "Transaction Reference": self.transaction_ref,
            "Account ID": self.account_id,
            code_name: self.party_code,
            code_type_name: self.party_code_type,
            dm_code_name: self.dm_code,
            dm_code_type_name: self.dm_code_type,
            "Product": self.product,
            "Account Type": self.account_type,
            "Service Level": self.service_level,
            "Branch Code": self.branch_code,
            "Error": self.error,
            "Correction": self.correction,
            "Correction Field": self.correction_field,
        }

    def to_output_row(self) -> list:
        """
        Convert record to output row list (13 columns).

        Returns:
            List of column values in order.
        """
        return [
            self.transaction_ref,       # Column 1
            self.account_id,            # Column 2
            self.party_code,            # Column 3
            self.party_code_type,       # Column 4
            self.dm_code,               # Column 5
            self.dm_code_type,          # Column 6
            self.product,               # Column 7
            self.account_type,          # Column 8
            self.service_level,         # Column 9
            self.branch_code,           # Column 10
            self.error,                 # Column 11
            self.correction,            # Column 12
            self.correction_field,      # Column 13
        ]

    def get_output_headers(self) -> list:
        """
        Get output column headers based on party type.

        Returns:
            List of column header names.
        """
        if self.party_type.lower() == "seller":
            return [
                "Transaction Reference",
                "Account ID",
                "Seller Code",
                "Type of Seller ID",
                "Seller DM Code",
                "Type of Seller DM ID",
                "Product",
                "Account Type",
                "Service Level",
                "Branch Code",
                "Error",
                "Correction",
                "Correction Field",
            ]
        else:
            return [
                "Transaction Reference",
                "Account ID",
                "Buyer Code",
                "Type of Buyer ID",
                "Buyer DM Code",
                "Type of Buyer DM ID",
                "Product",
                "Account Type",
                "Service Level",
                "Branch Code",
                "Error",
                "Correction",
                "Correction Field",
            ]

    @property
    def is_sipp(self) -> bool:
        """Check if account is a SIPP (exempt from validation)."""
        return self.account_type.upper() == "SIPP"

    @property
    def is_discretionary(self) -> bool:
        """Check if account is discretionary (requires validation)."""
        return self.service_level.upper() == "D"

    @property
    def is_custody_solutions(self) -> bool:
        """Check if account is Custody Solutions type."""
        return self.account_type.upper() == "CUSTODY SOLUTIONS"

    @property
    def dm_is_empty(self) -> bool:
        """Check if Decision Maker code is empty."""
        return not self.dm_code.strip()

    @property
    def dm_equals_party_code(self) -> bool:
        """Check if Decision Maker code equals Party (Buyer/Seller) code."""
        return self.dm_code.strip() == self.party_code.strip() and self.dm_code.strip() != ""

    @property
    def correction_field_template(self) -> str:
        """Get the correction field string template for this party type."""
        if self.party_type.lower() == "seller":
            return "Seller decision maker code:Type of seller decision maker code"
        else:
            return "Buyer decision maker code:Type of buyer decision maker code"


def determine_product(account_id: str) -> str:
    """
    Determine product type from account ID prefix.

    Args:
        account_id: Client account identifier

    Returns:
        Product name string

    Mapping:
        A -> AJB (AJ Bell Youinvest)
        B -> AJBIC (AJ Bell Investment Centre)
        X -> DODL (DODL Platform)
        Other -> Custody Solutions
    """
    if not account_id:
        return "Custody Solutions"

    prefix = account_id[0].upper()

    product_map = {
        "A": "AJB",
        "B": "AJBIC",
        "X": "DODL",
    }

    return product_map.get(prefix, "Custody Solutions")
