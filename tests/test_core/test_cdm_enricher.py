"""Unit tests for src/cdm/enricher.py — enrich_transaction()."""

from unittest.mock import MagicMock

import pytest

from src.cdm.enricher import (
    EnrichmentResult,
    InstrumentEnrichment,
    LeiEnrichment,
    enrich_transaction,
)

VALID_LEI = "529900T8BM49AURSDO55"
VALID_ISIN = "GB0001234567"


def _make_gleif_lookup(
    lei: str,
    is_valid: bool = True,
    reason: str = "ISSUED",
    legal_name: str = "TEST ENTITY LTD",
    entity_status: str = "ACTIVE",
    registration_status: str = "ISSUED",
    legal_address_country: str = "GB",
) -> MagicMock:
    """Return a mock GleifLookup whose lookup_lei returns canned data."""
    result = MagicMock()
    result.lei = lei
    result.is_valid = is_valid
    result.reason = reason
    result.legal_name = legal_name
    result.entity_status = entity_status
    result.registration_status = registration_status
    result.legal_address_country = legal_address_country

    mock = MagicMock()
    mock.lookup_lei.return_value = result
    return mock


def _make_firds_cache(
    row: dict | None = None,
    rows: list[dict] | None = None,
) -> MagicMock:
    """Return a mock FirdsCacheManager returning canned ISIN data."""
    mock = MagicMock()
    mock.get_by_isin_mic.return_value = row
    mock.get_by_isin.return_value = (
        rows if rows is not None else ([] if row is None else [row])
    )
    return mock


class TestEnrichTransactionGleif:
    def test_lei_buyer_enriched(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is not None
        assert result.buyer.found is True
        assert result.buyer.is_valid is True
        assert result.buyer.legal_name == "TEST ENTITY LTD"
        assert result.buyer.entity_status == "ACTIVE"

    def test_lei_seller_enriched(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=VALID_LEI,
            seller_id_type="LEI",
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.seller is not None
        assert result.seller.found is True

    def test_not_in_gleif_sets_found_false(self) -> None:
        gleif = _make_gleif_lookup(
            VALID_LEI, is_valid=False, reason="NOT_IN_GLEIF", legal_name=""
        )
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is not None
        assert result.buyer.found is False
        assert result.buyer.is_valid is False
        assert result.buyer.reason == "NOT_IN_GLEIF"

    def test_concat_id_type_skips_gleif(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        result = enrich_transaction(
            buyer_id="GBNJSMITH#1980-01-01#M",
            buyer_id_type="CONCAT",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is None
        gleif.lookup_lei.assert_not_called()

    def test_nidn_id_type_skips_gleif(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        result = enrich_transaction(
            buyer_id="GB1234567",
            buyer_id_type="NIDN",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is None

    def test_none_gleif_lookup_returns_none_enrichment(self) -> None:
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=VALID_LEI,
            seller_id_type="LEI",
            isin=None,
            gleif_lookup=None,
        )
        assert result.buyer is None
        assert result.seller is None

    def test_gleif_exception_returns_lookup_error(self) -> None:
        gleif = MagicMock()
        gleif.lookup_lei.side_effect = RuntimeError("cache error")
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is not None
        assert result.buyer.found is False
        assert result.buyer.reason == "LOOKUP_ERROR"

    def test_lei_id_type_case_insensitive(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="lei",
            seller_id=None,
            seller_id_type=None,
            isin=None,
            gleif_lookup=gleif,
        )
        assert result.buyer is not None


class TestEnrichTransactionFirds:
    def test_isin_enriched_from_cache(self) -> None:
        firds = _make_firds_cache(
            row={
                "isin": VALID_ISIN,
                "full_name": "VODAFONE GROUP PLC ORD",
                "cfi_code": "ESVUFR",
                "mic": "XLON",
            }
        )
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=VALID_ISIN,
            firds_cache=firds,
        )
        assert result.instrument is not None
        assert result.instrument.found is True
        assert result.instrument.full_name == "VODAFONE GROUP PLC ORD"
        assert result.instrument.cfi_code == "ESVUFR"
        assert result.instrument.mic == "XLON"

    def test_isin_not_in_firds(self) -> None:
        firds = _make_firds_cache(rows=[])
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=VALID_ISIN,
            firds_cache=firds,
        )
        assert result.instrument is not None
        assert result.instrument.found is False

    def test_venue_mic_prefers_isin_mic_lookup(self) -> None:
        firds = _make_firds_cache(
            row={
                "isin": VALID_ISIN,
                "full_name": "NAME A",
                "cfi_code": "ESVUFR",
                "mic": "XLON",
            }
        )
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=VALID_ISIN,
            venue="XLON",
            firds_cache=firds,
        )
        firds.get_by_isin_mic.assert_called_once_with(VALID_ISIN, "XLON")
        assert result.instrument is not None
        assert result.instrument.found is True

    def test_none_firds_cache_returns_none_instrument(self) -> None:
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=VALID_ISIN,
            firds_cache=None,
        )
        assert result.instrument is None

    def test_no_isin_returns_none_instrument(self) -> None:
        firds = _make_firds_cache(rows=[])
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=None,
            firds_cache=firds,
        )
        assert result.instrument is None

    def test_firds_exception_returns_not_found(self) -> None:
        firds = MagicMock()
        firds.get_by_isin_mic.side_effect = RuntimeError("db error")
        firds.get_by_isin.side_effect = RuntimeError("db error")
        result = enrich_transaction(
            buyer_id=None,
            buyer_id_type=None,
            seller_id=None,
            seller_id_type=None,
            isin=VALID_ISIN,
            firds_cache=firds,
        )
        assert result.instrument is not None
        assert result.instrument.found is False


class TestEnrichmentResult:
    def test_all_none_by_default(self) -> None:
        result = EnrichmentResult()
        assert result.buyer is None
        assert result.seller is None
        assert result.instrument is None

    def test_both_gleif_and_firds_combined(self) -> None:
        gleif = _make_gleif_lookup(VALID_LEI)
        firds = _make_firds_cache(
            row={
                "isin": VALID_ISIN,
                "full_name": "INSTRUMENT A",
                "cfi_code": "ESVUFR",
                "mic": "XLON",
            }
        )
        result = enrich_transaction(
            buyer_id=VALID_LEI,
            buyer_id_type="LEI",
            seller_id=VALID_LEI,
            seller_id_type="LEI",
            isin=VALID_ISIN,
            gleif_lookup=gleif,
            firds_cache=firds,
        )
        assert result.buyer is not None
        assert result.seller is not None
        assert result.instrument is not None
