"""
Tests for Phase 3 decision maker fallback matching.

Covers the additional lookup paths introduced to handle replay clients who
appear in the incident files as buyer/seller *decision makers* rather than
as the principal buyer or seller.

Affected classes:
    - IncidentFileIndex  (phase_3_processor.py)
        - lookup_by_id: DM ID fallback + name disambiguation
        - lookup_by_name: DM name fallback (already tested, confirmed correct)
    - UnaVistaIndex  (phase_3_final_lookup.py)
        - lookup_by_id: DM ID fallback
        - lookup_by_name: DM name fallback (with and without DOB)
"""

import logging
from collections import defaultdict
from unittest.mock import patch

import pytest

from core import UnaVistaTransaction
from src.replay.phase_3_final_lookup import UnaVistaIndex
from src.replay.phase_3_processor import IncidentColumnMapper, IncidentFileIndex

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _null_logger() -> logging.Logger:
    logger = logging.getLogger("test_dm_fallback")
    logger.addHandler(logging.NullHandler())
    return logger


def _make_incident_index(header, data_rows, column_config):
    """Build an IncidentFileIndex with pre-loaded data, without file I/O."""
    with patch.object(IncidentFileIndex, "load_and_index"):
        idx = IncidentFileIndex("fake.csv", column_config, logger=_null_logger())

    idx.header = header
    idx.data_rows = data_rows
    idx.column_mapper = IncidentColumnMapper(
        header, column_config, logger=_null_logger()
    )
    # Reset all indexes; individual tests populate what they need.
    idx.buyer_id_index = {}
    idx.seller_id_index = {}
    idx.buyer_name_index = {}
    idx.seller_name_index = {}
    idx.buyer_dm_id_index = {}
    idx.seller_dm_id_index = {}
    idx.buyer_dm_name_index = {}
    idx.seller_dm_name_index = {}
    return idx


def _make_unavista_index(transactions=None):
    """Build a UnaVistaIndex with pre-loaded transactions, without file I/O."""
    with patch.object(UnaVistaIndex, "load_and_index"):
        idx = UnaVistaIndex([], logger=_null_logger())

    idx.transactions = transactions or []
    idx.buyer_id_index = defaultdict(list)
    idx.seller_id_index = defaultdict(list)
    idx.buyer_name_index = defaultdict(list)
    idx.seller_name_index = defaultdict(list)
    idx.buyer_dm_id_index = defaultdict(list)
    idx.seller_dm_id_index = defaultdict(list)
    idx.buyer_dm_name_index = defaultdict(list)
    idx.seller_dm_name_index = defaultdict(list)
    idx.dm_match_count = 0
    return idx


def _txn(row_index: int) -> UnaVistaTransaction:
    return UnaVistaTransaction(
        transaction_ref=f"REF{row_index:03d}",
        row_data=["" for _ in range(35)],
        row_index=row_index,
    )


# ===========================================================================
# IncidentFileIndex — ID lookup DM fallback
# ===========================================================================

# Minimal column config: correction columns + buyer/seller DM columns
_COLUMN_CONFIG = {
    "transaction_ref": "Transaction Reference",
    "correction": "Correction",
    "correction_field": "Correction Field",
    "agree_with_correction": "Agree With Correction",
    "suggested_correction": "Suggested Correction",
    "suggested_correction_field": "Suggested Correction Field",
    "buyer_id": "Buyer identification code",
    "buyer_first_name": "Buyer - First name(s)",
    "buyer_last_name": "Buyer - Surname(s)",
    "buyer_dob": "Buyer - Date of birth",
    "seller_id": "Seller identification code",
    "seller_first_name": "Seller - First name(s)",
    "seller_last_name": "Seller - Surname(s)",
    "seller_dob": "Seller - Date of birth",
    "buyer_dm_id": "Buyer decision maker code",
    "buyer_dm_first_name": "Buy decision maker - First name(s)",
    "buyer_dm_last_name": "Buy decision maker - Surname(s)",
    "buyer_dm_dob": "Buy decision maker - Date of birth",
    "seller_dm_id": "Seller decision maker code",
    "seller_dm_first_name": "Sell decision maker - First name(s)",
    "seller_dm_last_name": "Sell decision maker - Surname(s)",
    "seller_dm_dob": "Sell decision maker - Date of birth",
    "error_flag": "Error",
}

_HEADER = [
    "Transaction Reference",
    "Correction",
    "Correction Field",
    "Agree With Correction",
    "Suggested Correction",
    "Suggested Correction Field",
    "Buyer identification code",
    "Buyer - First name(s)",
    "Buyer - Surname(s)",
    "Buyer - Date of birth",
    "Seller identification code",
    "Seller - First name(s)",
    "Seller - Surname(s)",
    "Seller - Date of birth",
    "Buyer decision maker code",
    "Buy decision maker - First name(s)",
    "Buy decision maker - Surname(s)",
    "Buy decision maker - Date of birth",
    "Seller decision maker code",
    "Sell decision maker - First name(s)",
    "Sell decision maker - Surname(s)",
    "Sell decision maker - Date of birth",
    "Error",
]


def _blank_row() -> list:
    return ["" for _ in _HEADER]


class TestIncidentFileIndexDMIdFallback:
    """IncidentFileIndex.lookup_by_id falls back to DM indexes."""

    def test_buyer_dm_id_match_returns_id_buyer_dm(self):
        """Client ID present only in the buyer DM column returns 'id_buyer_dm'."""
        row = _blank_row()
        row[_HEADER.index("Transaction Reference")] = "TXN001"
        row[_HEADER.index("Buyer decision maker code")] = "DM_BUYER_001"

        idx = _make_incident_index(_HEADER, [row], _COLUMN_CONFIG)
        idx.buyer_dm_id_index["dm_buyer_001"] = [0]

        result = idx.lookup_by_id(["DM_BUYER_001"])

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 0
        assert match_type == "id_buyer_dm"

    def test_seller_dm_id_match_returns_id_seller_dm(self):
        """Client ID present only in the seller DM column returns 'id_seller_dm'."""
        row = _blank_row()
        row[_HEADER.index("Transaction Reference")] = "TXN002"
        row[_HEADER.index("Seller decision maker code")] = "DM_SELLER_001"

        idx = _make_incident_index(_HEADER, [row], _COLUMN_CONFIG)
        idx.seller_dm_id_index["dm_seller_001"] = [0]

        result = idx.lookup_by_id(["DM_SELLER_001"])

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 0
        assert match_type == "id_seller_dm"

    def test_buyer_id_takes_precedence_over_buyer_dm_id(self):
        """When the same ID exists in both buyer and buyer DM indexes, buyer wins."""
        row = _blank_row()
        row[_HEADER.index("Buyer identification code")] = "SHARED_ID"
        row[_HEADER.index("Buyer decision maker code")] = "SHARED_ID"

        idx = _make_incident_index(_HEADER, [row], _COLUMN_CONFIG)
        idx.buyer_id_index["shared_id"] = [0]
        idx.buyer_dm_id_index["shared_id"] = [0]

        _, match_type = idx.lookup_by_id(["SHARED_ID"])
        assert match_type == "id_buyer"

    def test_dm_id_not_found_returns_none(self):
        """Lookup returns None when ID is absent from both primary and DM indexes."""
        idx = _make_incident_index(_HEADER, [], _COLUMN_CONFIG)
        result = idx.lookup_by_id(["UNKNOWN_ID"])
        assert result is None

    def test_buyer_dm_id_multi_match_disambiguates_by_name(self):
        """When multiple rows share the same DM ID, the correct row is selected by name."""
        row0 = _blank_row()
        row0[_HEADER.index("Transaction Reference")] = "TXN_A"
        row0[_HEADER.index("Buyer decision maker code")] = "DM_SHARED"
        row0[_HEADER.index("Buy decision maker - First name(s)")] = "Alice"
        row0[_HEADER.index("Buy decision maker - Surname(s)")] = "Smith"

        row1 = _blank_row()
        row1[_HEADER.index("Transaction Reference")] = "TXN_B"
        row1[_HEADER.index("Buyer decision maker code")] = "DM_SHARED"
        row1[_HEADER.index("Buy decision maker - First name(s)")] = "Bob"
        row1[_HEADER.index("Buy decision maker - Surname(s)")] = "Smith"

        idx = _make_incident_index(_HEADER, [row0, row1], _COLUMN_CONFIG)
        idx.buyer_dm_id_index["dm_shared"] = [0, 1]

        result = idx.lookup_by_id(
            ["DM_SHARED"], client_first="Bob", client_surname="Smith"
        )

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 1
        assert match_type == "id_buyer_dm"

    def test_buyer_dm_id_multi_match_falls_back_to_first_when_no_name(self):
        """With no name provided, first row is returned for a multi-match DM ID."""
        row0 = _blank_row()
        row0[_HEADER.index("Buyer decision maker code")] = "DM_SHARED"
        row1 = _blank_row()
        row1[_HEADER.index("Buyer decision maker code")] = "DM_SHARED"

        idx = _make_incident_index(_HEADER, [row0, row1], _COLUMN_CONFIG)
        idx.buyer_dm_id_index["dm_shared"] = [0, 1]

        row_idx, match_type = idx.lookup_by_id(["DM_SHARED"])
        assert row_idx == 0
        assert match_type == "id_buyer_dm"

    def test_seller_dm_id_multi_match_disambiguates_by_name(self):
        """Disambiguation also works for seller DM ID multi-matches."""
        row0 = _blank_row()
        row0[_HEADER.index("Seller decision maker code")] = "SELL_DM"
        row0[_HEADER.index("Sell decision maker - First name(s)")] = "Carol"
        row0[_HEADER.index("Sell decision maker - Surname(s)")] = "Jones"

        row1 = _blank_row()
        row1[_HEADER.index("Seller decision maker code")] = "SELL_DM"
        row1[_HEADER.index("Sell decision maker - First name(s)")] = "Dave"
        row1[_HEADER.index("Sell decision maker - Surname(s)")] = "Jones"

        idx = _make_incident_index(_HEADER, [row0, row1], _COLUMN_CONFIG)
        idx.seller_dm_id_index["sell_dm"] = [0, 1]

        result = idx.lookup_by_id(
            ["SELL_DM"], client_first="Dave", client_surname="Jones"
        )

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 1
        assert match_type == "id_seller_dm"


# ===========================================================================
# IncidentFileIndex — Name lookup DM fallback  (pre-existing, regression)
# ===========================================================================


class TestIncidentFileIndexDMNameFallback:
    """IncidentFileIndex.lookup_by_name falls back to DM name indexes."""

    def test_buyer_dm_name_match_returns_name_buyer_dm(self):
        row = _blank_row()
        row[_HEADER.index("Buy decision maker - First name(s)")] = "Alice"
        row[_HEADER.index("Buy decision maker - Surname(s)")] = "Smith"

        idx = _make_incident_index(_HEADER, [row], _COLUMN_CONFIG)
        idx.buyer_dm_name_index[("alice", "smith", "")] = [0]

        result = idx.lookup_by_name("Alice", "Smith", "")

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 0
        assert match_type == "name_buyer_dm"

    def test_seller_dm_name_match_returns_name_seller_dm(self):
        row = _blank_row()
        row[_HEADER.index("Sell decision maker - First name(s)")] = "Bob"
        row[_HEADER.index("Sell decision maker - Surname(s)")] = "Brown"

        idx = _make_incident_index(_HEADER, [row], _COLUMN_CONFIG)
        idx.seller_dm_name_index[("bob", "brown", "")] = [0]

        result = idx.lookup_by_name("Bob", "Brown", "")

        assert result is not None
        row_idx, match_type = result
        assert row_idx == 0
        assert match_type == "name_seller_dm"

    def test_buyer_name_takes_precedence_over_buyer_dm_name(self):
        """Primary buyer name index is preferred over buyer DM name index."""
        idx = _make_incident_index(_HEADER, [_blank_row()], _COLUMN_CONFIG)
        idx.buyer_name_index[("alice", "smith", "")] = [0]
        idx.buyer_dm_name_index[("alice", "smith", "")] = [0]

        _, match_type = idx.lookup_by_name("Alice", "Smith", "")
        assert match_type == "name_buyer"


# ===========================================================================
# UnaVistaIndex — ID lookup DM fallback
# ===========================================================================


class TestUnaVistaIndexDMIdFallback:
    """UnaVistaIndex.lookup_by_id falls back to DM indexes."""

    def test_buyer_dm_id_returns_transactions(self):
        """When buyer ID misses but buyer DM ID matches, transactions are returned."""
        txn = _txn(0)
        idx = _make_unavista_index([txn])
        idx.buyer_dm_id_index["dm_001"] = [0]

        result = idx.lookup_by_id("DM_001", "buyer")

        assert result == [txn]

    def test_seller_dm_id_returns_transactions(self):
        txn = _txn(5)
        idx = _make_unavista_index([txn])
        idx.seller_dm_id_index["sell_dm_x"] = [0]

        result = idx.lookup_by_id("SELL_DM_X", "seller")

        assert result == [txn]

    def test_buyer_id_takes_precedence_over_buyer_dm_id(self):
        """Primary buyer index result is returned without touching the DM index."""
        txn_primary = _txn(0)
        txn_dm = _txn(1)
        idx = _make_unavista_index([txn_primary, txn_dm])
        idx.buyer_id_index["shared"] = [0]
        idx.buyer_dm_id_index["shared"] = [1]

        result = idx.lookup_by_id("SHARED", "buyer")

        assert result == [txn_primary]

    def test_no_match_returns_empty_list(self):
        idx = _make_unavista_index([])
        result = idx.lookup_by_id("UNKNOWN", "buyer")
        assert result == []

    def test_dm_match_increments_dm_match_count(self):
        txn = _txn(0)
        idx = _make_unavista_index([txn])
        idx.buyer_dm_id_index["dm_x"] = [0]

        assert idx.dm_match_count == 0
        idx.lookup_by_id("DM_X", "buyer")
        assert idx.dm_match_count == 1

    def test_primary_match_does_not_increment_dm_match_count(self):
        txn = _txn(0)
        idx = _make_unavista_index([txn])
        idx.buyer_id_index["id_x"] = [0]

        idx.lookup_by_id("ID_X", "buyer")
        assert idx.dm_match_count == 0

    def test_empty_client_id_returns_empty_list(self):
        idx = _make_unavista_index([])
        assert idx.lookup_by_id("", "buyer") == []


# ===========================================================================
# UnaVistaIndex — Name lookup DM fallback
# ===========================================================================


class TestUnaVistaIndexDMNameFallback:
    """UnaVistaIndex.lookup_by_name falls back to DM name indexes."""

    def test_buyer_dm_name_match(self):
        txn = _txn(3)
        idx = _make_unavista_index([txn])
        idx.buyer_dm_name_index[("alice", "smith", "")] = [0]

        result = idx.lookup_by_name("Alice", "Smith", "", "buyer")

        assert result == [txn]

    def test_seller_dm_name_match(self):
        txn = _txn(7)
        idx = _make_unavista_index([txn])
        idx.seller_dm_name_index[("bob", "jones", "")] = [0]

        result = idx.lookup_by_name("Bob", "Jones", "", "seller")

        assert result == [txn]

    def test_buyer_name_takes_precedence_over_dm_name(self):
        txn_primary = _txn(0)
        txn_dm = _txn(1)
        idx = _make_unavista_index([txn_primary, txn_dm])
        idx.buyer_name_index[("alice", "smith", "")] = [0]
        idx.buyer_dm_name_index[("alice", "smith", "")] = [1]

        result = idx.lookup_by_name("Alice", "Smith", "", "buyer")

        assert result == [txn_primary]

    def test_no_match_returns_empty_list(self):
        idx = _make_unavista_index([])
        result = idx.lookup_by_name("Unknown", "Person", "", "buyer")
        assert result == []

    def test_dm_name_match_without_dob_when_exact_dob_absent(self):
        """DM name-without-DOB fallback fires when the exact-DOB key is missing."""
        from core import DateParser

        txn = _txn(2)
        idx = _make_unavista_index([txn])
        # Index only has the no-DOB key
        idx.buyer_dm_name_index[("carol", "white", "")] = [0]

        # A DOB is provided but no exact-DOB key exists in the index; the
        # no-DOB fallback should locate the record.
        dob = "1990-01-01"
        dob_parsed = DateParser.parse_date(dob) or dob
        # Confirm the exact-DOB key is absent (sanity-check the fixture)
        assert ("carol", "white", dob_parsed) not in idx.buyer_dm_name_index

        result = idx.lookup_by_name("Carol", "White", dob, "buyer")

        assert result == [txn]

    def test_dm_name_match_increments_dm_match_count(self):
        txn = _txn(0)
        idx = _make_unavista_index([txn])
        idx.buyer_dm_name_index[("dave", "black", "")] = [0]

        assert idx.dm_match_count == 0
        idx.lookup_by_name("Dave", "Black", "", "buyer")
        assert idx.dm_match_count == 1
