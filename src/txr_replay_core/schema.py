"""
CSV Schema Definitions
======================

Predefined CSV schemas for transaction reporting automation.
Defines the structure, column types, and validation rules for different
file formats used across the VBA migration scripts.

Schemas are organized by:
- Input schemas (source data files)
- Output schemas (results and corrections)
- Reference schemas (lookup tables)
"""

from .csv_utils import CSVSchema, ColumnDefinition, ColumnType


# ============================================================================
# ID Validation Schemas
# ============================================================================

BUYER_ID_VALIDATION_SCHEMA = CSVSchema(
    name="BuyerIDValidation",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Buyer DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Buyer DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Product", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Service Level", ColumnType.STRING, nullable=True),
        ColumnDefinition("Branch Code", ColumnType.STRING, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


SELLER_ID_VALIDATION_SCHEMA = CSVSchema(
    name="SellerIDValidation",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Seller DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Seller DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Product", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Service Level", ColumnType.STRING, nullable=True),
        ColumnDefinition("Branch Code", ColumnType.STRING, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


# ============================================================================
# Identification Code Schemas
# ============================================================================

BUYER_IDENTIFICATION_CODE_SCHEMA = CSVSchema(
    name="BuyerIdentificationCode",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("BEN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("OWN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("TPA Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("Person Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Buyer - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer - DOB", ColumnType.DATE, nullable=True),
        ColumnDefinition("Buyer - Gender", ColumnType.STRING, nullable=True),
        ColumnDefinition("Nationality", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of DM ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - DOB", ColumnType.DATE, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


SELLER_IDENTIFICATION_CODE_SCHEMA = CSVSchema(
    name="SellerIdentificationCode",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("BEN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("OWN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("TPA Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("Person Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Seller - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller - DOB", ColumnType.DATE, nullable=True),
        ColumnDefinition("Seller - Gender", ColumnType.STRING, nullable=True),
        ColumnDefinition("Nationality", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of DM ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("DM - DOB", ColumnType.DATE, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


# ============================================================================
# Inconsistent ID Schemas
# ============================================================================

INCONSISTENT_BUYER_ID_SCHEMA = CSVSchema(
    name="InconsistentBuyerID",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("BEN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("OWN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("Person Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Buyer ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Buyer - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer - DOB", ColumnType.DATE, nullable=True),
        ColumnDefinition("Buyer - Gender", ColumnType.STRING, nullable=True),
        ColumnDefinition("Nationality", ColumnType.STRING, nullable=True),
        ColumnDefinition("Trade_Date_Time", ColumnType.DATETIME, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


INCONSISTENT_SELLER_ID_SCHEMA = CSVSchema(
    name="InconsistentSellerID",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("BEN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("OWN Link", ColumnType.STRING, nullable=True),
        ColumnDefinition("Person Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Type of Seller ID Code", ColumnType.STRING, required=True),
        ColumnDefinition("Seller - First Name(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller - Surname(s)", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller - DOB", ColumnType.DATE, nullable=True),
        ColumnDefinition("Seller - Gender", ColumnType.STRING, nullable=True),
        ColumnDefinition("Nationality", ColumnType.STRING, nullable=True),
        ColumnDefinition("Trade_Date_Time", ColumnType.DATETIME, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


# ============================================================================
# Pricing/Net Amount Schemas
# ============================================================================

PRICING_DATA_VALIDATION_SCHEMA = CSVSchema(
    name="PricingDataValidation",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Net amount", ColumnType.FLOAT, required=True),
        ColumnDefinition("Consideration", ColumnType.FLOAT, required=True),
        ColumnDefinition("Interest", ColumnType.FLOAT, required=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


NET_AMOUNT_CORRECTION_SCHEMA = CSVSchema(
    name="NetAmountCorrection",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Error", ColumnType.STRING, nullable=True),
        ColumnDefinition("Correction", ColumnType.STRING, nullable=True),
        ColumnDefinition("Correction Field", ColumnType.STRING, nullable=True),
        ColumnDefinition("Comments", ColumnType.STRING, nullable=True),
        ColumnDefinition("Net amount", ColumnType.FLOAT, nullable=True),
        ColumnDefinition("Consideration", ColumnType.FLOAT, nullable=True),
        ColumnDefinition("Interest", ColumnType.FLOAT, nullable=True),
        ColumnDefinition("Total", ColumnType.FLOAT, nullable=True),
        ColumnDefinition("Expected Interest", ColumnType.FLOAT, nullable=True),
        ColumnDefinition("Net Amount difference", ColumnType.FLOAT, nullable=True),
    ],
    allow_extra_columns=False,
    encoding="utf-8-sig"
)


# ============================================================================
# Decision Maker Schemas
# ============================================================================

FUND_TRADE_DM_BUYER_SCHEMA = CSVSchema(
    name="FundTradeDMBuyer",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("Buyer ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Buyer ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Buyer DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Buyer DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Product", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Service Level", ColumnType.STRING, nullable=True),
        ColumnDefinition("Branch Code", ColumnType.STRING, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


FUND_TRADE_DM_SELLER_SCHEMA = CSVSchema(
    name="FundTradeDMSeller",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Account ID", ColumnType.STRING, required=True),
        ColumnDefinition("Seller ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Seller ID Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Seller DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Type of Seller DM Code", ColumnType.STRING, nullable=True),
        ColumnDefinition("Product", ColumnType.STRING, nullable=True),
        ColumnDefinition("Account Type", ColumnType.STRING, nullable=True),
        ColumnDefinition("Service Level", ColumnType.STRING, nullable=True),
        ColumnDefinition("Branch Code", ColumnType.STRING, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


# ============================================================================
# Generic Output Schema
# ============================================================================

VALIDATION_OUTPUT_SCHEMA = CSVSchema(
    name="ValidationOutput",
    columns=[
        ColumnDefinition("Transaction Reference", ColumnType.STRING, required=True),
        ColumnDefinition("Error", ColumnType.STRING, nullable=True),
        ColumnDefinition("Correction", ColumnType.STRING, nullable=True),
        ColumnDefinition("Correction Field", ColumnType.STRING, nullable=True),
        ColumnDefinition("Tracker Status", ColumnType.STRING, nullable=True),
        ColumnDefinition("Actions", ColumnType.STRING, nullable=True),
    ],
    allow_extra_columns=True,
    encoding="utf-8-sig"
)


# ============================================================================
# Schema Registry
# ============================================================================

SCHEMA_REGISTRY = {
    # ID Validation
    "buyer_id_validation": BUYER_ID_VALIDATION_SCHEMA,
    "seller_id_validation": SELLER_ID_VALIDATION_SCHEMA,
    
    # Identification Code
    "buyer_identification_code": BUYER_IDENTIFICATION_CODE_SCHEMA,
    "seller_identification_code": SELLER_IDENTIFICATION_CODE_SCHEMA,
    
    # Inconsistent ID
    "inconsistent_buyer_id": INCONSISTENT_BUYER_ID_SCHEMA,
    "inconsistent_seller_id": INCONSISTENT_SELLER_ID_SCHEMA,
    
    # Pricing
    "pricing_data_validation": PRICING_DATA_VALIDATION_SCHEMA,
    "net_amount_correction": NET_AMOUNT_CORRECTION_SCHEMA,
    
    # Decision Maker
    "fund_trade_dm_buyer": FUND_TRADE_DM_BUYER_SCHEMA,
    "fund_trade_dm_seller": FUND_TRADE_DM_SELLER_SCHEMA,
    
    # Generic
    "validation_output": VALIDATION_OUTPUT_SCHEMA,
}


def get_schema(name: str) -> CSVSchema:
    """
    Get schema by name from registry.
    
    Args:
        name: Schema name (e.g., "buyer_id_validation")
    
    Returns:
        CSVSchema object
    
    Raises:
        KeyError: If schema name not found
    """
    if name not in SCHEMA_REGISTRY:
        available = ", ".join(SCHEMA_REGISTRY.keys())
        raise KeyError(
            f"Schema '{name}' not found. Available schemas: {available}"
        )
    return SCHEMA_REGISTRY[name]


def list_schemas() -> list:
    """
    Get list of all available schema names.
    
    Returns:
        List of schema names
    """
    return list(SCHEMA_REGISTRY.keys())
