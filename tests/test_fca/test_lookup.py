"""Tests for FCA firm lookup logic (lookup.py)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fca.client import FcaApiError, FcaRegisterClient
from fca.lookup import (
    FcaFirmLookup,
    FirmLookupResult,
    FirmPermission,
    FirmRecord,
    _parse_firm_record,
    _parse_firm_record_from_search,
    _parse_permissions,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# _parse_firm_record
# ---------------------------------------------------------------------------


class TestParseFirmRecord:
    def test_parses_all_fields(self) -> None:
        data = _load("firm_response.json")["Data"][0]
        record = _parse_firm_record(data)
        assert record.frn == "122702"
        assert record.organisation_name == "Barclays Bank PLC"
        assert record.status == "Authorised"
        assert record.business_type == "Credit Institution"
        assert record.companies_house_number == "01026167"
        assert record.status_effective_date == "01/12/2001"

    def test_missing_optional_fields_default_to_empty_string(self) -> None:
        data = {"FRN": "999", "Organisation Name": "Test Firm", "Status": "Authorised"}
        record = _parse_firm_record(data)
        assert record.business_type == ""
        assert record.companies_house_number == ""
        assert record.status_effective_date == ""


# ---------------------------------------------------------------------------
# _parse_firm_record_from_search
# ---------------------------------------------------------------------------


class TestParseFirmRecordFromSearch:
    def test_parses_search_keys(self) -> None:
        data = _load("search_response.json")["Data"][0]
        record = _parse_firm_record_from_search(data)
        assert record.frn == "122702"
        assert record.organisation_name == "Barclays Bank PLC"
        assert record.status == "Authorised"

    def test_optional_fields_empty_from_search(self) -> None:
        data = {"Reference Number": "123", "Name": "Foo", "Status": "Authorised"}
        record = _parse_firm_record_from_search(data)
        assert record.business_type == ""
        assert record.companies_house_number == ""


# ---------------------------------------------------------------------------
# _parse_permissions
# ---------------------------------------------------------------------------


class TestParsePermissions:
    def test_parses_permissions_from_fixture(self) -> None:
        raw = _load("permissions_response.json")["Data"]
        permissions = _parse_permissions(raw)
        assert len(permissions) == 2
        # Sorted alphabetically by activity_name
        assert permissions[0].activity_name == "Accepting deposits"
        assert permissions[1].activity_name == "Dealing in investments as agent"

    def test_customer_types_populated(self) -> None:
        raw = _load("permissions_response.json")["Data"]
        permissions = _parse_permissions(raw)
        ct = permissions[0].customer_types
        assert "Commercial customers" in ct
        assert "Retail customers" in ct

    def test_limitations_populated(self) -> None:
        raw = _load("permissions_response.json")["Data"]
        permissions = _parse_permissions(raw)
        assert "Subject to limitations" in permissions[0].limitations

    def test_empty_dict_returns_empty_list(self) -> None:
        assert _parse_permissions({}) == []

    def test_non_list_detail_value_skipped(self) -> None:
        raw = {"Some Activity": "not-a-list"}
        permissions = _parse_permissions(raw)
        assert len(permissions) == 1
        assert permissions[0].activity_name == "Some Activity"
        assert permissions[0].customer_types == []


# ---------------------------------------------------------------------------
# FcaFirmLookup.lookup_by_frn
# ---------------------------------------------------------------------------


def _make_mock_client(
    firm_data: dict | None = None,
    permissions_data: dict | None = None,
    firm_raises: FcaApiError | None = None,
) -> MagicMock:
    """Return a mock FcaRegisterClient."""
    client = MagicMock(spec=FcaRegisterClient)
    if firm_raises is not None:
        client.get_firm.side_effect = firm_raises
    else:
        client.get_firm.return_value = (
            firm_data or _load("firm_response.json")["Data"][0]
        )
    client.get_firm_permissions.return_value = (
        permissions_data
        if permissions_data is not None
        else _load("permissions_response.json")["Data"]
    )
    client.search_firms.return_value = _load("search_response.json")["Data"]
    return client


class TestLookupByFrn:
    def test_authorised_firm_returns_is_authorised_true(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        result = lookup.lookup_by_frn("122702")
        assert result.is_authorised is True
        assert result.firm is not None
        assert result.firm.organisation_name == "Barclays Bank PLC"

    def test_non_authorised_firm_returns_is_authorised_false(self) -> None:
        firm = {
            **_load("firm_response.json")["Data"][0],
            "Status": "No longer authorised",
        }
        lookup = FcaFirmLookup(client=_make_mock_client(firm_data=firm))
        result = lookup.lookup_by_frn("122702")
        assert result.is_authorised is False

    def test_permissions_parsed(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        result = lookup.lookup_by_frn("122702")
        assert len(result.permissions) == 2
        names = [p.activity_name for p in result.permissions]
        assert "Accepting deposits" in names

    def test_frn_not_found_returns_none_firm(self) -> None:
        err = FcaApiError("Not found", status_code=404)
        lookup = FcaFirmLookup(client=_make_mock_client(firm_raises=err))
        result = lookup.lookup_by_frn("999999")
        assert result.firm is None
        assert result.is_authorised is False
        assert result.frn == "999999"

    def test_permissions_api_error_returns_empty_list(self) -> None:
        client = _make_mock_client()
        client.get_firm_permissions.side_effect = FcaApiError(
            "Permission error", status_code=500
        )
        lookup = FcaFirmLookup(client=client)
        result = lookup.lookup_by_frn("122702")
        assert result.permissions == []

    def test_frn_is_stripped(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        lookup.lookup_by_frn("  122702  ")
        lookup._client.get_firm.assert_called_once_with("122702")

    def test_non_404_api_error_propagates(self) -> None:
        err = FcaApiError("Server error", status_code=500)
        lookup = FcaFirmLookup(client=_make_mock_client(firm_raises=err))
        with pytest.raises(FcaApiError) as exc_info:
            lookup.lookup_by_frn("122702")
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# FcaFirmLookup.search_by_name
# ---------------------------------------------------------------------------


class TestSearchByName:
    def test_returns_list_of_firm_records(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        results = lookup.search_by_name("Barclays")
        assert len(results) == 2
        assert all(isinstance(r, FirmRecord) for r in results)

    def test_returns_empty_list_on_api_error(self) -> None:
        client = _make_mock_client()
        client.search_firms.side_effect = FcaApiError("Search failed")
        lookup = FcaFirmLookup(client=client)
        results = lookup.search_by_name("Barclays")
        assert results == []

    def test_returns_empty_list_on_no_results(self) -> None:
        client = _make_mock_client()
        client.search_firms.return_value = []
        lookup = FcaFirmLookup(client=client)
        results = lookup.search_by_name("unknownfirmxyz")
        assert results == []

    def test_frns_correct_in_search_results(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        results = lookup.search_by_name("Barclays")
        frns = {r.frn for r in results}
        assert "122702" in frns
        assert "759576" in frns

    def test_name_is_stripped(self) -> None:
        lookup = FcaFirmLookup(client=_make_mock_client())
        lookup.search_by_name("  Barclays  ")
        lookup._client.search_firms.assert_called_once_with("Barclays")
