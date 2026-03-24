"""Tests for GLEIF LEI lookup logic (lookup.py)."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gleif.cache import GleifCacheManager
from gleif.lookup import (
    GleifLookup,
    LeiLookupReason,
    LeiLookupResult,
    _trade_before_renewal,
)
from gleif.parser import LeiRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_cache(tmp_path: Path) -> GleifCacheManager:
    """Return a cache seeded with a known set of LEI records."""
    cache = GleifCacheManager(db_path=tmp_path / "gleif.db")
    cache.initialise_db()
    records = [
        LeiRecord(
            lei="5493001KJTIIGC8Y1R12",
            legal_name="Issued Corp",
            registration_status="ISSUED",
            entity_status="ACTIVE",
            entity_category="GENERAL",
            legal_address_country="GB",
            legal_jurisdiction="GB",
            next_renewal_date="2027-01-01T00:00:00Z",
        ),
        LeiRecord(
            lei="213800WAVVOPS85N2205",
            legal_name="Lapsed Corp",
            registration_status="LAPSED",
            entity_status="INACTIVE",
            entity_category="GENERAL",
            legal_address_country="DE",
            legal_jurisdiction="DE",
            next_renewal_date="2024-06-01T00:00:00Z",
        ),
        LeiRecord(
            lei="5493001KJTIIGC8Y9999",
            legal_name="Retired Corp",
            registration_status="RETIRED",
            entity_status="INACTIVE",
            entity_category="GENERAL",
            legal_address_country="FR",
            legal_jurisdiction="FR",
            next_renewal_date="",
        ),
        LeiRecord(
            lei="5493001KJTIIGC8Y8888",
            legal_name="Merged Corp",
            registration_status="MERGED",
            entity_status="INACTIVE",
            entity_category="GENERAL",
            legal_address_country="US",
            legal_jurisdiction="US",
            successor_lei="5493001KJTIIGC8Y1R12",
            next_renewal_date="",
        ),
    ]
    cache.bulk_upsert(records)
    cache.bulk_upsert_isin_map([("5493001KJTIIGC8Y1R12", "GB00B3RBWM25")])
    return cache


@pytest.fixture
def lookup(populated_cache: GleifCacheManager) -> GleifLookup:
    return GleifLookup(cache=populated_cache)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestGleifLookupConstructor:
    def test_requires_db_path_or_cache(self) -> None:
        with pytest.raises(ValueError, match="Either db_path or cache must be provided"):
            GleifLookup()

    def test_accepts_db_path(self, tmp_path: Path) -> None:
        cache = GleifCacheManager(db_path=tmp_path / "gleif.db")
        cache.initialise_db()
        assert GleifLookup(db_path=tmp_path / "gleif.db") is not None

    def test_accepts_cache_object(self, populated_cache: GleifCacheManager) -> None:
        assert GleifLookup(cache=populated_cache) is not None


# ---------------------------------------------------------------------------
# lookup_lei — core validation paths
# ---------------------------------------------------------------------------


class TestLookupLei:
    def test_issued_lei_is_valid(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("5493001KJTIIGC8Y1R12")
        assert result.is_valid is True
        assert result.reason == LeiLookupReason.ISSUED
        assert result.legal_name == "Issued Corp"
        assert result.legal_address_country == "GB"

    def test_unknown_lei_returns_not_in_gleif(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("UNKNOWNLEICODE000000")
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.NOT_IN_GLEIF
        assert result.legal_name == ""

    def test_lei_normalised_to_upper(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("5493001kjtiigc8y1r12")
        assert result.is_valid is True

    def test_lapsed_lei_without_trade_date_is_invalid(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("213800WAVVOPS85N2205")
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.LAPSED

    def test_lapsed_lei_valid_at_trade_date(self, lookup: GleifLookup) -> None:
        # Lapsed on 2024-06-01; trade on 2024-05-15 → still valid
        result = lookup.lookup_lei("213800WAVVOPS85N2205", trade_date=date(2024, 5, 15))
        assert result.is_valid is True
        assert result.reason == LeiLookupReason.LAPSED_VALID_AT_TRADE_DATE

    def test_lapsed_lei_after_renewal_date_is_invalid(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("213800WAVVOPS85N2205", trade_date=date(2024, 8, 1))
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.LAPSED

    def test_lapsed_lei_on_renewal_date_is_invalid(self, lookup: GleifLookup) -> None:
        # trade_date == renewal_date → NOT strictly before → invalid
        result = lookup.lookup_lei("213800WAVVOPS85N2205", trade_date=date(2024, 6, 1))
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.LAPSED

    def test_retired_lei_is_invalid(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("5493001KJTIIGC8Y9999")
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.RETIRED

    def test_merged_lei_is_invalid_with_successor(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("5493001KJTIIGC8Y8888")
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.MERGED
        assert result.successor_lei == "5493001KJTIIGC8Y1R12"

    def test_trade_date_stored_on_result(self, lookup: GleifLookup) -> None:
        td = date(2025, 3, 15)
        result = lookup.lookup_lei("5493001KJTIIGC8Y1R12", trade_date=td)
        assert result.trade_date == td

    def test_result_str_representation(self, lookup: GleifLookup) -> None:
        result = lookup.lookup_lei("5493001KJTIIGC8Y1R12")
        s = str(result)
        assert "5493001KJTIIGC8Y1R12" in s
        assert "valid=True" in s


# ---------------------------------------------------------------------------
# bulk_lookup
# ---------------------------------------------------------------------------


class TestBulkLookup:
    def test_bulk_lookup_returns_in_order(self, lookup: GleifLookup) -> None:
        leis = ["5493001KJTIIGC8Y1R12", "UNKNOWNLEICODE000000", "213800WAVVOPS85N2205"]
        results = lookup.bulk_lookup(leis)
        assert len(results) == 3
        assert results[0].reason == LeiLookupReason.ISSUED
        assert results[1].reason == LeiLookupReason.NOT_IN_GLEIF
        assert results[2].reason == LeiLookupReason.LAPSED

    def test_bulk_lookup_with_shared_trade_date(self, lookup: GleifLookup) -> None:
        leis = ["5493001KJTIIGC8Y1R12", "213800WAVVOPS85N2205"]
        results = lookup.bulk_lookup(leis, trade_date=date(2024, 4, 1))
        assert results[0].is_valid is True
        assert results[1].is_valid is True  # lapsed but trade before renewal

    def test_bulk_lookup_empty_list(self, lookup: GleifLookup) -> None:
        assert lookup.bulk_lookup([]) == []


# ---------------------------------------------------------------------------
# lookup_by_isin
# ---------------------------------------------------------------------------


class TestLookupByIsin:
    def test_found_isin_returns_results(self, lookup: GleifLookup) -> None:
        results = lookup.lookup_by_isin("GB00B3RBWM25")
        assert len(results) == 1
        assert results[0].lei == "5493001KJTIIGC8Y1R12"
        assert results[0].is_valid is True

    def test_unknown_isin_returns_empty_list(self, lookup: GleifLookup) -> None:
        assert lookup.lookup_by_isin("GB9999999999") == []

    def test_isin_normalised_to_upper(self, lookup: GleifLookup) -> None:
        results = lookup.lookup_by_isin("gb00b3rbwm25")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# search_by_name
# ---------------------------------------------------------------------------


class TestSearchByName:
    def test_search_returns_matching_entity(self, lookup: GleifLookup) -> None:
        results = lookup.search_by_name("Issued Corp")
        assert any(r["legal_name"] == "Issued Corp" for r in results)

    def test_search_empty_string_returns_empty(self, lookup: GleifLookup) -> None:
        assert lookup.search_by_name("") == []

    def test_search_unknown_name_returns_empty(self, lookup: GleifLookup) -> None:
        assert lookup.search_by_name("ZZZCompletelyUnknownEntityXXX") == []


# ---------------------------------------------------------------------------
# lookup_by_bic — mocked live API
# ---------------------------------------------------------------------------


class TestLookupByBic:
    def test_bic_resolved_and_validated(self, lookup: GleifLookup) -> None:
        mock_client = MagicMock()
        mock_client.get_lei_by_bic.return_value = "5493001KJTIIGC8Y1R12"
        lookup._api_client = mock_client

        result = lookup.lookup_by_bic("ALETITMMXXX")
        assert result is not None
        assert result.is_valid is True
        mock_client.get_lei_by_bic.assert_called_once_with("ALETITMMXXX")

    def test_bic_not_found_returns_not_in_gleif(self, lookup: GleifLookup) -> None:
        mock_client = MagicMock()
        mock_client.get_lei_by_bic.return_value = None
        lookup._api_client = mock_client

        result = lookup.lookup_by_bic("UNKNOWNBICX")
        assert result is not None
        assert result.is_valid is False
        assert result.reason == LeiLookupReason.NOT_IN_GLEIF

    def test_api_client_constructed_lazily(self, lookup: GleifLookup) -> None:
        """GleifApiClient should only be instantiated on first BIC lookup."""
        assert lookup._api_client is None
        with patch("gleif.lookup.GleifApiClient") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.get_lei_by_bic.return_value = None
            mock_cls.return_value = mock_instance
            lookup.lookup_by_bic("SOMEBIC0XXX")
            mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# _trade_before_renewal helper
# ---------------------------------------------------------------------------


class TestTradeBeforeRenewal:
    def test_trade_strictly_before_renewal(self) -> None:
        assert _trade_before_renewal(date(2024, 5, 1), "2024-06-01T00:00:00Z") is True

    def test_trade_on_renewal_date_is_not_before(self) -> None:
        assert _trade_before_renewal(date(2024, 6, 1), "2024-06-01T00:00:00Z") is False

    def test_trade_after_renewal_date(self) -> None:
        assert _trade_before_renewal(date(2024, 7, 1), "2024-06-01T00:00:00Z") is False

    def test_date_only_renewal_string(self) -> None:
        assert _trade_before_renewal(date(2024, 5, 1), "2024-06-01") is True

    def test_malformed_renewal_string_returns_false(self) -> None:
        assert _trade_before_renewal(date(2024, 5, 1), "not-a-date") is False

    def test_empty_renewal_string_returns_false(self) -> None:
        assert _trade_before_renewal(date(2024, 5, 1), "") is False
