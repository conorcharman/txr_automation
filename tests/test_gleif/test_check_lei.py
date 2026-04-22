"""Tests for _search_name_with_fallback and _normalise_company_suffixes
in gleif/scripts/check_lei.py."""

from pathlib import Path

import pytest

from gleif.cache import GleifCacheManager
from gleif.lookup import GleifLookup
from gleif.parser import LeiRecord
from gleif.scripts.check_lei import (
    _normalise_company_suffixes,
    _search_name_with_fallback,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    lei: str,
    legal_name: str,
    registration_status: str = "ISSUED",
    entity_status: str = "ACTIVE",
    legal_address_country: str = "GB",
) -> LeiRecord:
    return LeiRecord(
        lei=lei,
        legal_name=legal_name,
        registration_status=registration_status,
        entity_status=entity_status,
        entity_category="GENERAL",
        legal_address_country=legal_address_country,
        legal_jurisdiction=legal_address_country,
        next_renewal_date="2027-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lookup(tmp_path: Path) -> GleifLookup:
    """Return a GleifLookup backed by a cache seeded with test entities."""
    cache = GleifCacheManager(db_path=tmp_path / "gleif_test.db")
    cache.initialise_db()
    cache.bulk_upsert([
        _make_record("5493001KJTIIGC8Y1R12", "Citibank Europe PLC"),
        _make_record("213800WAVVOPS85N2205", "Deutsche Bank AG"),
        _make_record("AAAAAAAAAAAAAAAAAAAA", "Barclays Capital Holdings (UK) Ltd"),
        _make_record("BBBBBBBBBBBBBBBBBBBB", "Smith & Jones (Nominees) Limited"),
        # Suffix-normalisation test records — stored under full legal names
        _make_record("CCCCCCCCCCCCCCCCCCCC", "RETAIL BOOK LIMITED"),
        _make_record("DDDDDDDDDDDDDDDDDDDD", "Global Trading Corporation"),
        _make_record("EEEEEEEEEEEEEEEEEEEE", "Alpha Services Group"),
        _make_record("FFFFFFFFFFFFFFFFFFFF", "Beta Holdings Management"),
        _make_record("GGGGGGGGGGGGGGGGGGGG", "Pacific Brothers Manufacturing"),
        # GB-priority test records — two entities with similar names, one GB one non-GB
        _make_record("HHHHHHHHHHHHHHHHHHHH", "ZEUS CAPITAL LIMITED", legal_address_country="GB"),
        _make_record("IIIIIIIIIIIIIIIIIIII", "Zeus US Capital Managers Limited", legal_address_country="VG"),
    ])
    return GleifLookup(cache=cache)


# ---------------------------------------------------------------------------
# _search_name_with_fallback tests
# ---------------------------------------------------------------------------


class TestSearchNameWithFallback:
    def test_phrase_match_returns_result_and_phrase_score(
        self, lookup: GleifLookup
    ) -> None:
        """Exact phrase match returns a non-empty list with 1_PHRASE score."""
        results, score = _search_name_with_fallback(lookup, "Citibank Europe PLC")
        assert results
        assert results[0]["legal_name"] == "Citibank Europe PLC"
        assert score == "1_PHRASE"

    def test_prefix_match_returns_result_and_prefix_score(
        self, lookup: GleifLookup
    ) -> None:
        """Partial prefix match (phrase fails, prefix succeeds) returns 1_PREFIX."""
        results, score = _search_name_with_fallback(lookup, "Deutsche")
        assert results
        assert "Deutsche" in results[0]["legal_name"]
        assert score in ("1_PHRASE", "1_PREFIX")

    def test_no_match_returns_empty_list_and_no_match_score(
        self, lookup: GleifLookup
    ) -> None:
        """Name with no matching records returns ([], 'NO_MATCH')."""
        results, score = _search_name_with_fallback(lookup, "ZZZNonExistentFirmXXX")
        assert results == []
        assert score == "NO_MATCH"

    def test_empty_string_returns_no_match(self, lookup: GleifLookup) -> None:
        """Empty name string returns ([], 'NO_MATCH') without hitting the cache."""
        results, score = _search_name_with_fallback(lookup, "")
        assert results == []
        assert score == "NO_MATCH"

    def test_whitespace_only_returns_no_match(self, lookup: GleifLookup) -> None:
        """Whitespace-only name returns ([], 'NO_MATCH')."""
        results, score = _search_name_with_fallback(lookup, "   ")
        assert results == []
        assert score == "NO_MATCH"

    def test_name_with_parentheses_does_not_raise(
        self, lookup: GleifLookup
    ) -> None:
        """Name containing parentheses must not raise an FTS5 OperationalError."""
        results, score = _search_name_with_fallback(
            lookup, "Barclays Capital Holdings (UK) Ltd"
        )
        assert results
        assert score in ("1_PHRASE", "1_PREFIX", "1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_name_with_ampersand_does_not_raise(
        self, lookup: GleifLookup
    ) -> None:
        """Name containing '&' must not raise an FTS5 OperationalError."""
        results, score = _search_name_with_fallback(
            lookup, "Smith & Jones (Nominees) Limited"
        )
        assert results
        assert score in ("1_PHRASE", "1_PREFIX")

    def test_name_with_only_special_chars_returns_no_match(
        self, lookup: GleifLookup
    ) -> None:
        """Name that reduces to no tokens after sanitisation returns NO_MATCH."""
        results, score = _search_name_with_fallback(lookup, "(&)")
        assert results == []
        assert score == "NO_MATCH"

    def test_match_result_contains_expected_fields(
        self, lookup: GleifLookup
    ) -> None:
        """First result dict must contain lei, legal_name, registration_status."""
        results, _ = _search_name_with_fallback(lookup, "Citibank Europe PLC")
        assert results
        assert "lei" in results[0]
        assert "legal_name" in results[0]
        assert "registration_status" in results[0]

    def test_limit_respected(self, lookup: GleifLookup) -> None:
        """limit parameter caps the number of results returned."""
        results, _ = _search_name_with_fallback(lookup, "Zeus", limit=5)
        assert len(results) <= 5

    def test_limit_one_returns_single_element_list(
        self, lookup: GleifLookup
    ) -> None:
        """Default limit=1 returns a list with exactly one element."""
        results, score = _search_name_with_fallback(lookup, "Citibank Europe PLC")
        assert len(results) == 1
        assert score != "NO_MATCH"


# ---------------------------------------------------------------------------
# _normalise_company_suffixes unit tests
# ---------------------------------------------------------------------------


class TestNormaliseCompanySuffixes:
    def test_ltd_expanded_to_limited(self) -> None:
        assert _normalise_company_suffixes("Retail Book Ltd") == "Retail Book Limited"

    def test_ltd_with_period_expanded(self) -> None:
        assert _normalise_company_suffixes("Retail Book Ltd.") == "Retail Book Limited"

    def test_corp_expanded(self) -> None:
        assert _normalise_company_suffixes("Global Trading Corp") == "Global Trading Corporation"

    def test_inc_expanded(self) -> None:
        assert _normalise_company_suffixes("Acme Inc") == "Acme Incorporated"

    def test_grp_expanded(self) -> None:
        assert _normalise_company_suffixes("Alpha Services Grp") == "Alpha Services Group"

    def test_hldgs_expanded(self) -> None:
        assert _normalise_company_suffixes("Beta Hldgs Management") == "Beta Holdings Management"

    def test_mgmt_expanded(self) -> None:
        assert _normalise_company_suffixes("Beta Holdings Mgmt") == "Beta Holdings Management"

    def test_mfg_expanded(self) -> None:
        assert _normalise_company_suffixes("Pacific Bros Mfg") == "Pacific Brothers Manufacturing"

    def test_svcs_expanded(self) -> None:
        assert _normalise_company_suffixes("Alpha Svcs Group") == "Alpha Services Group"

    def test_intl_expanded(self) -> None:
        assert _normalise_company_suffixes("Acme Intl Corp") == "Acme International Corporation"

    def test_case_insensitive(self) -> None:
        assert _normalise_company_suffixes("Retail Book LTD") == "Retail Book Limited"

    def test_no_abbreviations_unchanged(self) -> None:
        assert _normalise_company_suffixes("RETAIL BOOK LIMITED") == "RETAIL BOOK LIMITED"

    def test_multiple_abbreviations_in_one_name(self) -> None:
        result = _normalise_company_suffixes("Acme Intl Bros Corp")
        assert "International" in result
        assert "Brothers" in result
        assert "Corporation" in result

    def test_whitespace_stripped(self) -> None:
        assert _normalise_company_suffixes("  Acme Ltd  ") == "Acme Limited"


# ---------------------------------------------------------------------------
# _search_name_with_fallback — suffix normalisation paths
# ---------------------------------------------------------------------------


class TestSearchNameNormalisedFallback:
    def test_ltd_matches_limited_in_db(self, lookup: GleifLookup) -> None:
        """The original failing case: 'Retail Book Ltd' finds 'RETAIL BOOK LIMITED'."""
        results, score = _search_name_with_fallback(lookup, "Retail Book Ltd")
        assert results
        assert results[0]["legal_name"] == "RETAIL BOOK LIMITED"
        assert score in ("1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_corp_matches_corporation_in_db(self, lookup: GleifLookup) -> None:
        """'Global Trading Corp' finds 'Global Trading Corporation'.

        Corp* is a valid FTS5 prefix for Corporation so this may be satisfied
        by the prefix-search step without needing full normalisation.
        """
        results, score = _search_name_with_fallback(lookup, "Global Trading Corp")
        assert results
        assert "Corporation" in results[0]["legal_name"]
        assert score != "NO_MATCH"

    def test_grp_matches_group_in_db(self, lookup: GleifLookup) -> None:
        """'Alpha Services Grp' finds 'Alpha Services Group'."""
        results, score = _search_name_with_fallback(lookup, "Alpha Services Grp")
        assert results
        assert "Group" in results[0]["legal_name"]
        assert score in ("1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_mgmt_matches_management_in_db(self, lookup: GleifLookup) -> None:
        """'Beta Holdings Mgmt' finds 'Beta Holdings Management'."""
        results, score = _search_name_with_fallback(lookup, "Beta Holdings Mgmt")
        assert results
        assert "Management" in results[0]["legal_name"]
        assert score in ("1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_mfg_and_bros_match_in_db(self, lookup: GleifLookup) -> None:
        """'Pacific Bros Mfg' finds 'Pacific Brothers Manufacturing'."""
        results, score = _search_name_with_fallback(lookup, "Pacific Bros Mfg")
        assert results
        assert "Manufacturing" in results[0]["legal_name"]
        assert score in ("1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_norm_score_not_returned_when_phrase_matches(
        self, lookup: GleifLookup
    ) -> None:
        """When the original phrase matches, normalised steps are not reached."""
        _, score = _search_name_with_fallback(lookup, "RETAIL BOOK LIMITED")
        assert score == "1_PHRASE"

    def test_truly_absent_name_still_returns_no_match(
        self, lookup: GleifLookup
    ) -> None:
        """No fallback produces a result for a completely unknown name."""
        results, score = _search_name_with_fallback(lookup, "Nonexistent Firm Ltd")
        assert results == []
        assert score == "NO_MATCH"


# ---------------------------------------------------------------------------
# _search_name_with_fallback — GB country prioritisation
# ---------------------------------------------------------------------------


class TestSearchNameGbPriority:
    def test_gb_result_returned_ahead_of_non_gb_for_ltd_query(
        self, lookup: GleifLookup
    ) -> None:
        """When searching 'Zeus Capital Ltd', the GB entity 'ZEUS CAPITAL LIMITED'
        must be returned before the non-GB 'Zeus US Capital Managers Limited'.

        The old bug: raw prefix 'Zeus* Capital* Ltd*' matched 'Zeus US Capital
        Managers Ltd.' (VG, contains literal 'Ltd') before the normalised search
        reached 'ZEUS CAPITAL LIMITED' (GB).  The fix is to normalise the query
        first so 'Zeus* Capital* Limited*' only matches entities whose name uses
        the full 'Limited' spelling, and GB results are promoted via SQL ordering.
        """
        results, score = _search_name_with_fallback(lookup, "Zeus Capital Ltd")
        assert results, "Expected at least one result"
        assert results[0]["legal_address_country"] == "GB", (
            f"Expected GB result first, got {results[0]['legal_address_country']!r} "
            f"({results[0]['legal_name']!r})"
        )
        assert results[0]["lei"] == "HHHHHHHHHHHHHHHHHHHH"
        assert score in ("1_PHRASE_NORM", "1_PREFIX_NORM")

    def test_gb_result_returned_for_full_name_search(
        self, lookup: GleifLookup
    ) -> None:
        """Searching 'Zeus Capital Limited' (full name) returns GB result first."""
        results, score = _search_name_with_fallback(lookup, "Zeus Capital Limited")
        assert results
        assert results[0]["legal_address_country"] == "GB"
        assert score in ("1_PHRASE", "1_PHRASE_NORM")

    def test_limit_multi_includes_gb_first(
        self, lookup: GleifLookup
    ) -> None:
        """With limit=2, both Zeus entities are returned with GB entity first."""
        results, _ = _search_name_with_fallback(
            lookup, "Zeus Capital Limited", limit=2
        )
        countries = [r["legal_address_country"] for r in results]
        assert "GB" in countries
        assert countries[0] == "GB"

