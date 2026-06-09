"""
Incident Code Matrix Module
============================

Comprehensive incident code mappings with validation type routing.
This serves as the single source of truth for all incident metadata.

This is the canonical location for incident codes.
For backward compatibility, this is also re-exported from:
- txr_replay_core.incident_codes

Data source: Internal incident code specifications
Last updated: March 2026

Validation Types:
- 'standard_id': Standard identification validation (buyer or seller determined by 'sides')
- 'decision_maker': Decision maker validation for fund trades
- 'inconsistent_id': Inconsistent identification code across suspected same individual
- 'standard_name': Name field validation (buyer or seller)
- 'non_zero_net_qty': INTC ISIN net quantity validation
- 'non_zero_net_amt': INTC ISIN net amount validation
- 'pricing': Pricing and net amount data validation
- 'pending': Trade-level, venue, or structural validation not actioned in replay processing

The 'sides' parameter determines whether validation is buyer/seller focused.
Codes with sides=set() are trade-level and do not route to buyer or seller processing.
"""

from typing import Dict, Optional, Set, TypedDict


class IncidentMetadata(TypedDict):
    """Metadata for an incident code."""

    sides: Set[str]  # {'buyer', 'seller', or both}
    validation_type: str  # Type of validation required
    description: str  # Human-readable description


# Incident code mappings with full metadata
# Format: incident_code -> IncidentMetadata
INCIDENT_CODE_MATRIX: Dict[str, IncidentMetadata] = {
    # ── Submission / Trade Reference ──────────────────────────────────────────
    "0_5": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Over-reported instrument",
    },
    "0_7": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Late submission",
    },
    "1_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Updating new trade that does not have the original execution timestamp",
    },
    "3_3": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading venue transaction identification code is missing on a venue with market membership",
    },
    "3_18": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading venue transaction identification code is missing on a venue with no market membership",
    },
    "3_70": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading venue transaction identification code populated on a suspected RSP venue trade",
    },
    # ── Buyer Identification Code (Field 7) ───────────────────────────────────
    "7_3": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "AOTC trade where trading capacity or buyer code is incorrect",
    },
    "7_6": {
        "sides": {"buyer", "seller"},
        "validation_type": "non_zero_net_qty",
        "description": "INTC ISIN trade where quantity does not net to zero",
    },
    "7_11": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "Incorrect buyer or seller code as both populated with the same value",
    },
    "7_27": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Single INTC ISIN trade",
    },
    "7_28": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Block or allocation ISIN trade that does not correctly pair",
    },
    "7_29": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "INTC ISIN trade where part of one to one block and allocation pair",
    },
    "7_30": {
        "sides": {"buyer"},
        "validation_type": "incorrect_time",
        "description": "Block or allocation ISIN trade with incorrect time",
    },
    "7_38": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "INTC ISIN trade with inconsistent quantity types across block and allocations",
    },
    "7_35": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Incorrect CONCAT value within Buyer identification code field",
    },
    "7_36": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Non-preferred value type within Buyer identification code field",
    },
    "7_37": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Incorrect NIDN value within Buyer identification code field",
    },
    "7_39": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Incorrect CCPT value within Buyer identification code field",
    },
    "7_42": {
        "sides": {"buyer", "seller"},
        "validation_type": "non_zero_net_amt",
        "description": "INTC ISIN trade where net amount does not net to zero",
    },
    "7_43": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Non-applicable value type within Buyer identification code field",
    },
    "7_45": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Duplicate values within Buyer identification code field",
    },
    "7_50": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "INTC ISIN trade with inconsistent price types across block and allocations",
    },
    "7_51": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "On venue trade reported without venue CCP",
    },
    "7_55": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Venue found in buyer code field unexpectedly",
    },
    "7_66": {
        "sides": {"buyer"},
        "validation_type": "inconsistent_id",
        "description": "Inconsistent Buyer identification code reported across suspected same individual",
    },
    "7_68": {
        "sides": {"buyer"},
        "validation_type": "inconsistent_id",
        "description": "Inconsistent individual reported across Buyer identification code",
    },
    "7_74": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Suspected SIPP found in buyer code field",
    },
    # ── Country of Branch – Buyer (Field 8) ──────────────────────────────────
    "8_2": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Trade executed on national holiday of country of the branch for the buyer",
    },
    "8_3": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer is populated where buyer is executing entity",
    },
    "8_6": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "Trading venue trade where country of the branch for the buyer and seller both populated",
    },
    "8_17": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer and seller both populated unexpectedly",
    },
    "8_19": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer and seller both null unexpectedly",
    },
    "8_61": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer is null where buyer decision maker code is populated",
    },
    "8_1": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer is not recognised as an active trading branch",
    },
    "8_4": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer populated inconsistently across buyer identification code",
    },
    "8_7": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Country of the branch for the buyer is populated where buyer is a broker",
    },
    # ── Buyer Name (Fields 9–10) ──────────────────────────────────────────────
    "9_1": {
        "sides": {"buyer"},
        "validation_type": "standard_name",
        "description": "Invalid Buyer - First name(s)",
    },
    "10_1": {
        "sides": {"buyer"},
        "validation_type": "standard_name",
        "description": "Invalid Buyer - Surname(s)",
    },
    # ── Buyer Date of Birth (Field 11) ────────────────────────────────────────
    "11_2": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Person below expected minimum age within Buyer - Date of birth field",
    },
    "11_4": {
        "sides": {"buyer"},
        "validation_type": "standard_id",
        "description": "Person above expected maximum age within Buyer - Date of birth field",
    },
    # ── Buyer Decision Maker Code (Field 12) ─────────────────────────────────
    "12_1": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Incorrect buyer code or buyer decision maker code as both populated with the same value",
    },
    "12_2": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Incorrect buyer decision maker code or seller code as both populated with the same value",
    },
    "12_11": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Buyer decision maker field populated with fund",
    },
    "12_17": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Incorrect buyer decision maker or buyer populated for fund trade",
    },
    "12_18": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Non-preferred value type within Buyer decision maker code field",
    },
    "12_22": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Inconsistent Buyer decision maker code reported across suspected same individual",
    },
    "12_24": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Inconsistent individual reported across Buyer decision maker code",
    },
    "12_27": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Incorrect CONCAT value within Buyer decision maker code field",
    },
    "12_29": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Incorrect NIDN value within Buyer decision maker code field",
    },
    "12_31": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Incorrect CCPT value within Buyer decision maker code field",
    },
    "12_35": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Non-applicable value type within Buyer decision maker code field",
    },
    "12_43": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Buyer decision maker code is populated where buyer is a broker",
    },
    "12_55": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Buyer decision maker code is populated where buyer is INTC",
    },
    "12_75": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Buyer decision maker code is null where buyer is below expected minimum age for trading",
    },
    # ── Buyer Decision Maker Name (Fields 13–14) ─────────────────────────────
    "13_1": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Invalid Buy decision maker - First name(s)",
    },
    "14_1": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Invalid Buy decision maker - Surname(s)",
    },
    # ── Buyer Decision Maker Date of Birth (Field 15) ────────────────────────
    "15_2": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Person below expected minimum age within Buy decision maker - Date of birth field",
    },
    "15_4": {
        "sides": {"buyer"},
        "validation_type": "decision_maker",
        "description": "Person above expected maximum age within Buy decision maker - Date of birth field",
    },
    # ── Seller Identification Code (Field 16) ────────────────────────────────
    "16_3": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "AOTC trade where trading capacity or seller code is incorrect",
    },
    "16_18": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Non-preferred value type within Seller identification code field",
    },
    "16_19": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Incorrect CONCAT value within Seller identification code field",
    },
    "16_20": {
        "sides": {"seller"},
        "validation_type": "inconsistent_id",
        "description": "Inconsistent Seller identification code reported across suspected same individual",
    },
    "16_21": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Incorrect NIDN value within Seller identification code field",
    },
    "16_22": {
        "sides": {"seller"},
        "validation_type": "inconsistent_id",
        "description": "Inconsistent individual reported across Seller identification code",
    },
    "16_23": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Incorrect CCPT value within Seller identification code field",
    },
    "16_27": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Non-applicable value type within Seller identification code field",
    },
    "16_29": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Duplicate values within Seller identification code field",
    },
    "16_37": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Venue found in seller code field unexpectedly",
    },
    "16_58": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Suspected RSP venue trade reported without RSP market maker",
    },
    "16_64": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Suspected SIPP found in seller code field",
    },
    "16_24": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Unexpected buy sell ratio across equity deal trading",
    },
    # ── Country of Branch – Seller (Field 17) ────────────────────────────────
    "17_2": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Trade executed on national holiday of country of the branch for the seller",
    },
    "17_3": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the seller is populated where seller is executing entity",
    },
    "17_7": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the seller is populated where seller is a broker",
    },
    "17_11": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the seller is populated where seller is INTC",
    },
    "17_59": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Country of the branch for the seller is null where seller decision maker code is populated",
    },
    # ── Seller Name (Fields 18–19) ────────────────────────────────────────────
    "18_1": {
        "sides": {"seller"},
        "validation_type": "standard_name",
        "description": "Invalid Seller - First name(s)",
    },
    "19_1": {
        "sides": {"seller"},
        "validation_type": "standard_name",
        "description": "Invalid Seller - Surname(s)",
    },
    # ── Seller Date of Birth (Field 20) ──────────────────────────────────────
    "20_2": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Person below expected minimum age within Seller - Date of birth field",
    },
    "20_4": {
        "sides": {"seller"},
        "validation_type": "standard_id",
        "description": "Person above expected maximum age within Seller - Date of birth field",
    },
    # ── Seller Decision Maker Code (Field 21) ────────────────────────────────
    "21_1": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Incorrect seller code or seller decision maker code as both populated with the same value",
    },
    "21_2": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Incorrect seller decision maker code or buyer code as both populated with the same value",
    },
    "21_11": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Seller decision maker field populated with fund",
    },
    "21_16": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Non-preferred value type within Seller decision maker code field",
    },
    "21_17": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Incorrect seller decision maker or seller populated for fund trade",
    },
    "21_20": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Inconsistent Seller decision maker code reported across suspected same individual",
    },
    "21_22": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Inconsistent individual reported across Seller decision maker code",
    },
    "21_29": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Incorrect NIDN value within Seller decision maker code field",
    },
    "21_31": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Incorrect CCPT value within Seller decision maker code field",
    },
    "21_35": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Non-applicable value type within Seller decision maker code field",
    },
    "21_43": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Seller decision maker code is populated where seller is a broker",
    },
    "21_55": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Seller decision maker code is populated where seller is INTC",
    },
    "21_75": {
        "sides": {"seller"},
        "validation_type": "pending",
        "description": "Seller decision maker code is null where seller is below expected minimum age for trading",
    },
    # ── Seller Decision Maker Name (Fields 22–23) ────────────────────────────
    "22_1": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Invalid Sell decision maker - First name(s)",
    },
    "23_1": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Invalid Sell decision maker - Surname(s)",
    },
    # ── Seller Decision Maker Date of Birth (Field 24) ───────────────────────
    "24_2": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Person below expected minimum age within Sell decision maker - Date of birth field",
    },
    "24_4": {
        "sides": {"seller"},
        "validation_type": "decision_maker",
        "description": "Person above expected maximum age within Sell decision maker - Date of birth field",
    },
    # ── Transmission of Order (Field 25) ─────────────────────────────────────
    "25_11": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "AOTC trade where trading capacity or transmission of order indicator is incorrect",
    },
    "25_17": {
        "sides": {"buyer", "seller"},
        "validation_type": "pending",
        "description": "INTC ISIN trade with incorrect transmission of order indicator across block and allocations",
    },
    # ── Trading Date / Time (Field 28) ────────────────────────────────────────
    "28_2": {
        "sides": {"buyer"},
        "validation_type": "pending",
        "description": "Trade executed on national holiday of country of the branch for the buyer",
    },
    "28_4": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading date time on day when venue was closed",
    },
    "28_6": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading date time with potential legacy default trade time",
    },
    "28_8": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading date time with potential incorrect legacy default trade time",
    },
    "28_12": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trade executed on national holiday of venue's country",
    },
    "28_13": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading venue trade where trading timestamp reported with insufficient granularity",
    },
    "28_24": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading venue trade reported with sufficient granularity but trading timestamp has unexpectedly high frequency",
    },
    "28_42": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Non-in-scope trading venue trade reported with sufficient granularity but trading timestamp has unexpectedly high frequency to the second",
    },
    "28_16": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trade failing post clock change testing by venue (End of day)",
    },
    # ── Trading Capacity (Field 29) ───────────────────────────────────────────
    "29_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trading capacity is not AOTC as expected for HKG trade",
    },
    # ── Quantity (Field 30) ───────────────────────────────────────────────────
    "30_1": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Incorrect quantity value reported for bond",
    },
    "30_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Potential incorrect quantity value reported for bond",
    },
    "30_3": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Quantity reported with unexpected quantity type",
    },
    "30_4": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Multiple quantity types reported on this instrument",
    },
    # ── Price (Field 33) ──────────────────────────────────────────────────────
    "33_1": {"sides": set(), "validation_type": "pricing", "description": "Price is 0"},
    "33_2": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Equity with suspected incorrect price (Band A)",
    },
    "33_3": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Equity with incorrect price (Band A)",
    },
    "33_6": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Debt with suspected incorrect price (Band A)",
    },
    "33_7": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Debt with incorrect price (Band A)",
    },
    "33_30": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Equity with suspected incorrect price (Band B)",
    },
    "33_31": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Equity with incorrect price (Band B)",
    },
    "33_33": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Collective investment vehicle with incorrect price (Band B)",
    },
    "33_35": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Debt with incorrect price (Band B)",
    },
    "33_58": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Inconsistent price reported on this single instrument or single underlier",
    },
    "33_59": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Price reported with unexpected price type",
    },
    "33_72": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Debt with suspected incorrect price (Band C)",
    },
    "33_96": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Equity with suspected incorrect price (Band D)",
    },
    "33_124": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Multiple price types reported on this instrument",
    },
    # ── Net Amount (Field 35) ─────────────────────────────────────────────────
    "35_3": {
        "sides": {"seller"},
        "validation_type": "pricing",
        "description": "Incorrect net amount",
    },
    "35_8": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Debt trade with null net amount",
    },
    "35_10": {
        "sides": set(),
        "validation_type": "pricing",
        "description": "Suspected incorrect net amount",
    },
    # ── Venue / SI (Fields 36–37) ─────────────────────────────────────────────
    "36_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Venue not identified as a known execution venue for the client and not an SI broker",
    },
    "36_14": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Non-ETD instrument not listed on reported venue at time of execution as per FIRDS list",
    },
    "36_16": {
        "sides": set(),
        "validation_type": "pending",
        "description": "SI only listed instrument at time of execution as per FIRDS list",
    },
    "36_23": {
        "sides": set(),
        "validation_type": "pending",
        "description": "SI venue reported without the SI in the buyer or seller",
    },
    "36_27": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Non-FIRDS listed instrument with venue reported as XOFF",
    },
    "36_31": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Non-execution venue reported",
    },
    "36_33": {
        "sides": set(),
        "validation_type": "pending",
        "description": "SI only listed instrument at time of execution with venue reported as XOFF",
    },
    "36_53": {
        "sides": set(),
        "validation_type": "pending",
        "description": "INTC trade incorrectly reported with both market and client side trade characteristics",
    },
    "37_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Country of the branch membership populated on a venue with no market membership",
    },
    "37_3": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Country of the branch membership populated on SI venue",
    },
    # ── Miscellaneous ─────────────────────────────────────────────────────────
    "48_41": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trade executed post LIBOR demise date",
    },
    "57_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Investment decision within firm individual not recognised",
    },
    "57_8": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Non-preferred value type within Investment decision within firm field",
    },
    "57_17": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Incorrect NIDN value within Investment decision within firm field",
    },
    "58_1": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Country of the branch responsible for the person making the investment decision is not consistent with client static",
    },
    "58_4": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Country of the branch responsible for the person making the investment decision populated inconsistently across investment decision within firm value",
    },
    "58_5": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Country of the branch responsible for the person making the investment decision is not recognised as an active trading branch",
    },
    "59_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Execution within firm individual not recognised",
    },
    "59_5": {
        "sides": set(),
        "validation_type": "pending",
        "description": "DEAL trade where execution within firm is populated with 'NORE'",
    },
    "59_12": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Execution within firm populated with 'NORE' unexpectedly",
    },
    "59_14": {
        "sides": set(),
        "validation_type": "pending",
        "description": "DEAL trade where execution within firm is populated with 'NORE' potentially in error",
    },
    "59_16": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Execution within firm and investment decision within firm populated with same value unexpectedly",
    },
    "59_18": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Execution within firm algo ID not recognised",
    },
    "59_27": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Execution within firm unexpectedly populated with algo ID",
    },
    "60_2": {
        "sides": set(),
        "validation_type": "pending",
        "description": "Trade executed on national holiday of country of the branch supervising the person responsible for the execution",
    },
}


def get_client_types(incident_codes: list) -> Set[str]:
    """
    Determine client types (buyer/seller) from a list of incident codes.

    Args:
        incident_codes: List of incident code strings (e.g., ['7_3', '16_22'])

    Returns:
        Set of client types: {'buyer'}, {'seller'}, or {'buyer', 'seller'}
        Returns empty set if no codes match.

    Example:
        >>> get_client_types(['7_3', '7_35'])
        {'buyer'}
        >>> get_client_types(['16_22', '21_1'])
        {'seller'}
        >>> get_client_types(['8_6'])
        {'buyer', 'seller'}
    """
    types = set()
    for code in incident_codes:
        if code in INCIDENT_CODE_MATRIX:
            types.update(INCIDENT_CODE_MATRIX[code]["sides"])
    return types


def is_buyer_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with buyers."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return "buyer" in code_data["sides"]
    return False


def is_seller_incident(incident_code: str) -> bool:
    """Check if an incident code is associated with sellers."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return "seller" in code_data["sides"]
    return False


def get_all_incident_codes() -> Set[str]:
    """Get all known incident codes."""
    return set(INCIDENT_CODE_MATRIX.keys())


def get_buyer_incident_codes() -> Set[str]:
    """Get all buyer incident codes."""
    return {
        code for code, data in INCIDENT_CODE_MATRIX.items() if "buyer" in data["sides"]
    }


def get_seller_incident_codes() -> Set[str]:
    """Get all seller incident codes."""
    return {
        code for code, data in INCIDENT_CODE_MATRIX.items() if "seller" in data["sides"]
    }


def get_standard_buyer_incident_codes() -> Set[str]:
    """Get buyer incident codes excluding decision maker incidents."""
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "buyer" in data["sides"] and data["validation_type"] != "decision_maker"
    }


def get_standard_seller_incident_codes() -> Set[str]:
    """Get seller incident codes excluding decision maker incidents."""
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "seller" in data["sides"] and data["validation_type"] != "decision_maker"
    }


def get_decision_maker_buyer_codes() -> Set[str]:
    """Get buyer decision maker incident codes (12_17)."""
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "buyer" in data["sides"] and data["validation_type"] == "decision_maker"
    }


def get_decision_maker_seller_codes() -> Set[str]:
    """Get seller decision maker incident codes (21_17)."""
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "seller" in data["sides"] and data["validation_type"] == "decision_maker"
    }


def is_decision_maker_incident(incident_code: str) -> bool:
    """Check if an incident code is a decision maker incident."""
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["validation_type"] == "decision_maker"
    return False


# Validation type routing functions


def get_validation_type(incident_code: str) -> Optional[str]:
    """
    Get the validation type for an incident code.

    Args:
        incident_code: Incident code string (e.g., '7_37')

    Returns:
        Validation type string ('standard_id', 'decision_maker', 'pricing')
        or None if code not found.

    Example:
        >>> get_validation_type('7_37')
        'standard_id'
        >>> get_validation_type('7_66')
        'inconsistent_id'
        >>> get_validation_type('35_3')
        'pricing'
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["validation_type"]
    return None


def get_incidents_by_validation_type(validation_type: str) -> Set[str]:
    """
    Get all incident codes requiring a specific validation type.

    Args:
        validation_type: Type of validation ('standard_id', 'decision_maker', 'pricing')

    Returns:
        Set of incident codes matching the validation type.

    Example:
        >>> get_incidents_by_validation_type('pricing')
        {'33_1', '33_3', '33_6', ...}  # all pricing-related codes
        >>> get_incidents_by_validation_type('inconsistent_id')
        {'7_66', '7_68', '16_20', '16_22'}
    """
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if data["validation_type"] == validation_type
    }


def get_incident_description(incident_code: str) -> Optional[str]:
    """
    Get the description for an incident code.

    Args:
        incident_code: Incident code string (e.g., '7_37')

    Returns:
        Description string or None if code not found.

    Example:
        >>> get_incident_description('7_37')
        'FTBDM - standard txr'
        >>> get_incident_description('7_66')
        'Inconsistent buyer decision maker ID'
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["description"]
    return None


def get_available_validation_types() -> Set[str]:
    """
    Get all available validation types in the system.

    Returns:
        Set of validation type strings.

    Example:
        >>> sorted(get_available_validation_types())
        ['decision_maker', 'inconsistent_id', 'pricing', 'standard_id']
    """
    return {data["validation_type"] for data in INCIDENT_CODE_MATRIX.values()}


def get_inconsistent_buyer_incident_codes() -> Set[str]:
    """
    Get buyer incident codes requiring inconsistent ID validation.

    Returns:
        Set of incident codes with validation_type='inconsistent_id' and buyer side.

    Example:
        >>> get_inconsistent_buyer_incident_codes()
        {'7_66'}
    """
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "buyer" in data["sides"] and data["validation_type"] == "inconsistent_id"
    }


def get_inconsistent_seller_incident_codes() -> Set[str]:
    """
    Get seller incident codes requiring inconsistent ID validation.

    Returns:
        Set of incident codes with validation_type='inconsistent_id' and seller side.

    Example:
        >>> get_inconsistent_seller_incident_codes()
        {'16_20'}
    """
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if "seller" in data["sides"] and data["validation_type"] == "inconsistent_id"
    }


def get_non_zero_net_qty_incident_codes() -> Set[str]:
    """
    Get incident codes requiring non-zero net quantity validation.

    Returns:
        Set of incident codes with validation_type='non_zero_net_qty'.

    Example:
        >>> get_non_zero_net_qty_incident_codes()
        {'7_6'}
    """
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if data["validation_type"] == "non_zero_net_qty"
    }


def is_non_zero_net_qty_incident(incident_code: str) -> bool:
    """
    Check if an incident code requires non-zero net quantity validation.

    Args:
        incident_code: Incident code string (e.g., '7_6')

    Returns:
        True if incident uses non_zero_net_qty validation type.

    Example:
        >>> is_non_zero_net_qty_incident('7_6')
        True
        >>> is_non_zero_net_qty_incident('7_37')
        False
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["validation_type"] == "non_zero_net_qty"
    return False


def get_non_zero_net_amt_incident_codes() -> Set[str]:
    """
    Get incident codes requiring non-zero net amount validation.

    Returns:
        Set of incident codes with validation_type='non_zero_net_amt'.

    Example:
        >>> get_non_zero_net_amt_incident_codes()
        {'7_42'}
    """
    return {
        code
        for code, data in INCIDENT_CODE_MATRIX.items()
        if data["validation_type"] == "non_zero_net_amt"
    }


def is_non_zero_net_amt_incident(incident_code: str) -> bool:
    """
    Check if an incident code requires non-zero net amount validation.

    Args:
        incident_code: Incident code string (e.g., '7_42')

    Returns:
        True if incident uses non_zero_net_amt validation type.

    Example:
        >>> is_non_zero_net_amt_incident('7_42')
        True
        >>> is_non_zero_net_amt_incident('7_37')
        False
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["validation_type"] == "non_zero_net_amt"
    return False


def is_inconsistent_id_incident(incident_code: str) -> bool:
    """
    Check if an incident code requires inconsistent ID validation.

    Args:
        incident_code: Incident code string (e.g., '7_66')

    Returns:
        True if incident uses inconsistent_id validation type.

    Example:
        >>> is_inconsistent_id_incident('7_66')
        True
        >>> is_inconsistent_id_incident('7_37')
        False
    """
    if code_data := INCIDENT_CODE_MATRIX.get(incident_code):
        return code_data["validation_type"] == "inconsistent_id"
    return False
