"""Tests for GLEIF REST API client (client.py)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from gleif.client import (
    GleifApiClient,
    GoldenCopyInfo,
    _extract_fuzzy_attributes,
    _extract_lei_attributes,
)

# ---------------------------------------------------------------------------
# Helpers — build minimal JSON:API responses
# ---------------------------------------------------------------------------

_PUBLISH_DATE = "2026-03-23T00:00:00Z"
_CSV_URL = "https://leidata-preview.gleif.org/storage/golden-copy-files/2026/03/23/1/20260323-0800-gleif-goldencopy-lei2-golden-copy.csv.zip"

# Response from the publishes API (leidata-preview.gleif.org/api/v2/golden-copies/publishes)
_PUBLISHES_RESPONSE = {
    "data": [
        {
            "publish_date": "2026-03-23 08:00:00",
            "lei2": {
                "full_file": {
                    "csv": {
                        "url": _CSV_URL,
                        "record_count": 3255743,
                        "size_human_readable": "452.4 MB",
                    }
                }
            },
        }
    ]
}

_META_RESPONSE = {
    "meta": {"goldenCopy": {"publishDate": _PUBLISH_DATE}},
    "data": [
        {
            "id": "5493001KJTIIGC8Y1R12",
            "attributes": {
                "lei": "5493001KJTIIGC8Y1R12",
                "entity": {
                    "legalName": {"name": "Test Entity Ltd"},
                    "status": "ACTIVE",
                    "category": "GENERAL",
                    "legalAddress": {"country": "GB"},
                    "jurisdiction": "GB",
                    "otherNames": [],
                    "expiration": None,
                    "successorEntity": None,
                },
                "registration": {
                    "status": "ISSUED",
                    "initialRegistrationDate": "2020-01-01T00:00:00Z",
                    "lastUpdateDate": "2025-01-01T00:00:00Z",
                    "nextRenewalDate": "2027-01-01T00:00:00Z",
                },
            },
        }
    ],
}

_SINGLE_LEI_RESPONSE = {
    "data": {
        "id": "5493001KJTIIGC8Y1R12",
        "attributes": {
            "lei": "5493001KJTIIGC8Y1R12",
            "entity": {
                "legalName": {"name": "Test Entity Ltd"},
                "status": "ACTIVE",
                "category": "GENERAL",
                "legalAddress": {"country": "GB"},
                "jurisdiction": "GB",
                "otherNames": [{"name": "TE Ltd"}],
                "expiration": {"date": None, "reason": ""},
                "successorEntity": None,
            },
            "registration": {
                "status": "ISSUED",
                "initialRegistrationDate": "2020-01-01T00:00:00Z",
                "lastUpdateDate": "2025-01-01T00:00:00Z",
                "nextRenewalDate": "2027-01-01T00:00:00Z",
            },
        },
    }
}


def _make_response(json_body: dict, status_code: int = 200) -> MagicMock:
    """Build a mock ``requests.Response``."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    if status_code >= 400:
        http_err = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> MagicMock:
    """Return a mock session with rate-limiting suppressed."""
    return MagicMock()


@pytest.fixture
def client(session: MagicMock) -> GleifApiClient:
    """Return a GleifApiClient backed by a mock session without rate-limit delay."""
    return GleifApiClient(session=session, request_delay=0.0)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestGleifApiClientConstructor:
    def test_default_construction(self) -> None:
        with patch("gleif.client.requests.Session"):
            c = GleifApiClient(request_delay=0.0)
            assert c is not None

    def test_custom_session_used(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        assert client._session is session

    def test_accept_header_set(self, session: MagicMock) -> None:
        GleifApiClient(session=session, request_delay=0.0)
        session.headers.update.assert_called_once()
        headers_arg = session.headers.update.call_args[0][0]
        assert headers_arg.get("Accept") == "application/vnd.api+json"


# ---------------------------------------------------------------------------
# get_latest_golden_copy_info
# ---------------------------------------------------------------------------


class TestGetLatestGoldenCopyInfo:
    def test_returns_golden_copy_info(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(_PUBLISHES_RESPONSE)
        info = client.get_latest_golden_copy_info()
        assert isinstance(info, GoldenCopyInfo)
        assert info.publish_date == "2026-03-23T08:00:00Z"

    def test_download_url_is_csv_url(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(_PUBLISHES_RESPONSE)
        info = client.get_latest_golden_copy_info()
        assert info.download_url == _CSV_URL
        assert info.download_url.startswith("https://")

    def test_empty_data_raises(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        with pytest.raises(ValueError, match="no data"):
            client.get_latest_golden_copy_info()

    def test_missing_csv_url_raises(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        broken = {
            "data": [{"publish_date": "2026-03-23 08:00:00", "lei2": {"full_file": {}}}]
        }
        session.get.return_value = _make_response(broken)
        with pytest.raises(ValueError, match="CSV download URL"):
            client.get_latest_golden_copy_info()

    def test_api_error_raises(self, client: GleifApiClient, session: MagicMock) -> None:
        session.get.return_value = _make_response({}, status_code=500)
        with pytest.raises(requests.HTTPError):
            client.get_latest_golden_copy_info()

    def test_overridden_url_skips_publishes_api(self, session: MagicMock) -> None:
        """When golden_copy_url is set explicitly, the publish date comes from the LEI records API."""
        custom_url = "https://example.com/my-golden-copy.zip"
        c = GleifApiClient(
            session=session, request_delay=0.0, golden_copy_url=custom_url
        )
        session.get.return_value = _make_response(_META_RESPONSE)
        info = c.get_latest_golden_copy_info()
        assert info.download_url == custom_url
        assert info.publish_date == _PUBLISH_DATE


# ---------------------------------------------------------------------------
# get_by_lei
# ---------------------------------------------------------------------------


class TestGetByLei:
    def test_found_lei_returns_dict(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(_SINGLE_LEI_RESPONSE)
        result = client.get_by_lei("5493001KJTIIGC8Y1R12")
        assert result is not None
        assert result["lei"] == "5493001KJTIIGC8Y1R12"
        assert result["legal_name"] == "Test Entity Ltd"
        assert result["registration_status"] == "ISSUED"

    def test_other_names_joined(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(_SINGLE_LEI_RESPONSE)
        result = client.get_by_lei("5493001KJTIIGC8Y1R12")
        assert result is not None
        assert "TE Ltd" in result["other_names"]

    def test_lei_normalised_to_upper(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(_SINGLE_LEI_RESPONSE)
        client.get_by_lei("5493001kjtiigc8y1r12")
        call_url = session.get.call_args[0][0]
        assert "5493001KJTIIGC8Y1R12" in call_url

    def test_404_returns_none(self, client: GleifApiClient, session: MagicMock) -> None:
        session.get.return_value = _make_response({}, status_code=404)
        result = client.get_by_lei("UNKNOWNLEICODE000000")
        assert result is None

    def test_500_raises(self, client: GleifApiClient, session: MagicMock) -> None:
        session.get.return_value = _make_response({}, status_code=500)
        with pytest.raises(requests.HTTPError):
            client.get_by_lei("5493001KJTIIGC8Y1R12")

    def test_empty_data_returns_none(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": None})
        result = client.get_by_lei("5493001KJTIIGC8Y1R12")
        assert result is None


# ---------------------------------------------------------------------------
# get_leis_by_isin
# ---------------------------------------------------------------------------


class TestGetLeisByIsin:
    def test_returns_lei_list(self, client: GleifApiClient, session: MagicMock) -> None:
        session.get.return_value = _make_response(
            {
                "data": [
                    {"id": "5493001KJTIIGC8Y1R12"},
                    {"id": "213800WAVVOPS85N2205"},
                ]
            }
        )
        result = client.get_leis_by_isin("GB00B3RBWM25")
        assert result == ["5493001KJTIIGC8Y1R12", "213800WAVVOPS85N2205"]

    def test_empty_data_returns_empty_list(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        assert client.get_leis_by_isin("GB9999999999") == []

    def test_isin_normalised_to_upper(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        client.get_leis_by_isin("gb00b3rbwm25")
        params = session.get.call_args[1]["params"]
        assert params.get("filter[isin]") == "GB00B3RBWM25"


# ---------------------------------------------------------------------------
# get_lei_by_bic
# ---------------------------------------------------------------------------


class TestGetLeiBic:
    def test_returns_lei(self, client: GleifApiClient, session: MagicMock) -> None:
        session.get.return_value = _make_response(
            {"data": [{"id": "5493001KJTIIGC8Y1R12"}]}
        )
        assert client.get_lei_by_bic("ALETITMMXXX") == "5493001KJTIIGC8Y1R12"

    def test_not_found_returns_none(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        assert client.get_lei_by_bic("UNKNOWNBICX") is None

    def test_bic_normalised_to_upper(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        client.get_lei_by_bic("aletitmmxxx")
        params = session.get.call_args[1]["params"]
        assert params.get("filter[bic]") == "ALETITMMXXX"


# ---------------------------------------------------------------------------
# search_by_name
# ---------------------------------------------------------------------------


class TestSearchByName:
    def test_standard_search_returns_list(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response(
            {"data": [_SINGLE_LEI_RESPONSE["data"]]}
        )
        results = client.search_by_name("Test Entity")
        assert len(results) == 1
        assert results[0]["legal_name"] == "Test Entity Ltd"

    def test_fuzzy_search_uses_fuzzycompletions_endpoint(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        client.search_by_name("Test Entity", fuzzy=True)
        call_url = session.get.call_args[0][0]
        assert "fuzzycompletions" in call_url

    def test_standard_search_uses_lei_records_endpoint(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        client.search_by_name("Test Entity", fuzzy=False)
        call_url = session.get.call_args[0][0]
        assert "lei-records" in call_url

    def test_limit_passed_as_page_size(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        """Non-fuzzy search passes ``limit`` as the API page[size] parameter."""
        session.get.return_value = _make_response({"data": []})
        client.search_by_name("Entity", limit=5)
        params = session.get.call_args[1]["params"]
        assert params.get("page[size]") == 5


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_sleep_called_after_request(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        """Verify time.sleep is called with the configured delay."""
        session.get.return_value = _make_response({"data": []})
        # Replace client's delay and check sleep is invoked
        with patch("gleif.client.time.sleep") as mock_sleep:
            c = GleifApiClient(session=session, request_delay=1.5)
            c.get_leis_by_isin("GB00B3RBWM25")
            mock_sleep.assert_called_once_with(1.5)

    def test_zero_delay_skips_sleep(
        self, client: GleifApiClient, session: MagicMock
    ) -> None:
        session.get.return_value = _make_response({"data": []})
        with patch("gleif.client.time.sleep") as mock_sleep:
            client.get_leis_by_isin("GB00B3RBWM25")
            mock_sleep.assert_called_once_with(0.0)


# ---------------------------------------------------------------------------
# _extract_lei_attributes helper
# ---------------------------------------------------------------------------


class TestExtractLeiAttributes:
    def test_extracts_flat_dict(self) -> None:
        item = _SINGLE_LEI_RESPONSE["data"]
        result = _extract_lei_attributes(item)
        assert result["lei"] == "5493001KJTIIGC8Y1R12"
        assert result["legal_name"] == "Test Entity Ltd"
        assert result["legal_address_country"] == "GB"
        assert result["registration_status"] == "ISSUED"
        assert result["next_renewal_date"] == "2027-01-01T00:00:00Z"

    def test_other_names_joined_by_semicolon(self) -> None:
        item = {
            "id": "ABC",
            "attributes": {
                "lei": "ABC",
                "entity": {
                    "legalName": {"name": "Main"},
                    "otherNames": [{"name": "Alt1"}, {"name": "Alt2"}],
                    "status": "ACTIVE",
                    "category": "GENERAL",
                    "legalAddress": {"country": "DE"},
                    "jurisdiction": "DE",
                    "expiration": None,
                    "successorEntity": None,
                },
                "registration": {
                    "status": "ISSUED",
                    "initialRegistrationDate": "",
                    "lastUpdateDate": "",
                    "nextRenewalDate": "",
                },
            },
        }
        result = _extract_lei_attributes(item)
        assert result["other_names"] == "Alt1; Alt2"

    def test_successor_lei_extracted(self) -> None:
        item = {
            "id": "MERGED001",
            "attributes": {
                "lei": "MERGED001",
                "entity": {
                    "legalName": {"name": "Merged Co"},
                    "otherNames": [],
                    "status": "INACTIVE",
                    "category": "GENERAL",
                    "legalAddress": {"country": "GB"},
                    "jurisdiction": "GB",
                    "expiration": None,
                    "successorEntity": {"lei": "SUCCESSOR001"},
                },
                "registration": {
                    "status": "MERGED",
                    "initialRegistrationDate": "",
                    "lastUpdateDate": "",
                    "nextRenewalDate": "",
                },
            },
        }
        result = _extract_lei_attributes(item)
        assert result["successor_lei"] == "SUCCESSOR001"


# ---------------------------------------------------------------------------
# _extract_fuzzy_attributes helper
# ---------------------------------------------------------------------------


class TestExtractFuzzyAttributes:
    def test_extracts_lei_and_name(self) -> None:
        item = {"id": "5493001KJTIIGC8Y1R12", "attributes": {"value": "Test Corp"}}
        result = _extract_fuzzy_attributes(item)
        assert result["lei"] == "5493001KJTIIGC8Y1R12"
        assert result["legal_name"] == "Test Corp"

    def test_missing_fields_return_defaults(self) -> None:
        result = _extract_fuzzy_attributes({})
        assert result["lei"] == ""
        assert result["legal_name"] == ""
        assert result["registration_status"] == ""
