#!/usr/bin/env python3
"""
GLEIF LEI Lookup
================

Public API for validating Legal Entity Identifiers and enriching records with
entity details from the local GLEIF Golden Copy cache.

Validation Logic
----------------
Given a LEI code and an optional trade date, the lookup applies this decision tree:

1.  **Not in cache** → invalid, reason ``NOT_IN_GLEIF``.
2.  ``registration_status == "ISSUED"`` → valid, reason ``ISSUED``.
3.  ``registration_status == "LAPSED"`` with ``trade_date`` provided:
    -   If ``trade_date < next_renewal_date`` — the registration was still valid
        on the trade date → valid, reason ``LAPSED_VALID_AT_TRADE_DATE``.
    -   Otherwise → invalid, reason ``LAPSED``.
4.  ``registration_status == "LAPSED"`` without ``trade_date`` → invalid,
    reason ``LAPSED``.
5.  Any other status (``RETIRED``, ``MERGED``, ``ANNULLED``, etc.) → invalid,
    reason equal to the registration status string.

ISIN and Name Lookups
---------------------
``lookup_by_isin()`` accepts an ISIN code and returns all LEI results found in
the ``lei_isin_map`` table.  If BIC resolution is needed, ``lookup_by_bic()``
falls back to the live GLEIF API because BIC data is not in the Golden Copy.

Usage:
    from pathlib import Path
    from datetime import date

    lookup = GleifLookup(db_path=Path("data/gleif_cache.db"))

    result = lookup.lookup_lei("5493001KJTIIGC8Y1R12", trade_date=date(2025, 6, 15))
    print(result.is_valid, result.reason, result.legal_name)

    results = lookup.lookup_by_isin("DE000ST8MPP0")
    for r in results:
        print(r.lei, r.legal_name)
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

from .cache import GleifCacheManager
from .client import GleifApiClient

# ---------------------------------------------------------------------------
# Reason constants
# ---------------------------------------------------------------------------


class LeiLookupReason:
    """String constants for LEI lookup decision reason codes."""

    ISSUED = "ISSUED"
    """The LEI is active and fully registered."""

    LAPSED_VALID_AT_TRADE_DATE = "LAPSED_VALID_AT_TRADE_DATE"
    """The LEI has since lapsed but was valid on the provided trade date
    (i.e. the trade date falls before the ``next_renewal_date``)."""

    LAPSED = "LAPSED"
    """The LEI registration was not renewed before its expiry date."""

    RETIRED = "RETIRED"
    """The LEI has been retired and is no longer in use."""

    MERGED = "MERGED"
    """The legal entity was merged into another entity.  Check
    ``successor_lei`` on the result for the surviving LEI."""

    ANNULLED = "ANNULLED"
    """The original LEI registration was found to be incorrect and annulled."""

    CANCELLED = "CANCELLED"
    """The LEI registration was cancelled."""

    TRANSFERRED = "TRANSFERRED"
    """The LEI has been transferred to another LEI issuing organisation."""

    PENDING_TRANSFER = "PENDING_TRANSFER"
    """The LEI is in the process of being transferred to another LOU."""

    PENDING_ARCHIVAL = "PENDING_ARCHIVAL"
    """The LEI is being archived (e.g. following a transfer)."""

    NOT_IN_GLEIF = "NOT_IN_GLEIF"
    """No record for this LEI was found in the local GLEIF cache."""


# Set of registration statuses considered inherently invalid regardless of
# trade date.  LAPSED is handled separately via date comparison.
_ALWAYS_INVALID_STATUSES = {
    LeiLookupReason.RETIRED,
    LeiLookupReason.MERGED,
    LeiLookupReason.ANNULLED,
    LeiLookupReason.CANCELLED,
    LeiLookupReason.TRANSFERRED,
    LeiLookupReason.PENDING_TRANSFER,
    LeiLookupReason.PENDING_ARCHIVAL,
}


@dataclass
class LeiLookupResult:
    """The outcome of a LEI lookup.

    Attributes:
        lei: The LEI code that was looked up.
        is_valid: ``True`` if the LEI is considered valid for reporting
            purposes given the supplied (or absent) trade date.
        reason: One of the :class:`LeiLookupReason` string constants
            describing the decision.
        legal_name: Registered legal name of the entity.  Empty string if the
            LEI was not found in the cache.
        entity_status: Entity lifecycle status — ``ACTIVE`` or ``INACTIVE``.
        entity_category: Legal entity category (e.g. ``GENERAL``, ``FUND``).
        legal_address_country: ISO 3166-1 alpha-2 country code of the entity's
            legal address.
        registration_status: Raw registration status string from GLEIF.
        next_renewal_date: ISO 8601 renewal date string (empty if not found).
        successor_lei: LEI of the successor entity (populated when
            ``reason == MERGED``).
        trade_date: The trade date used for the validity check, if provided.
    """

    lei: str
    is_valid: bool
    reason: str
    legal_name: str = ""
    entity_status: str = ""
    entity_category: str = ""
    legal_address_country: str = ""
    registration_status: str = ""
    next_renewal_date: str = ""
    successor_lei: str = ""
    trade_date: Optional[date] = None

    def __str__(self) -> str:
        date_info = f", trade_date={self.trade_date}" if self.trade_date else ""
        return (
            f"LeiLookupResult(lei={self.lei}{date_info}, "
            f"valid={self.is_valid}, reason={self.reason}, "
            f"name={self.legal_name!r})"
        )


class GleifLookup:
    """Validates LEIs and enriches records using the local GLEIF cache.

    For BIC-to-LEI lookups (BIC data is absent from the Golden Copy CSV),
    a live API call is made via :class:`~gleif.client.GleifApiClient`.

    Args:
        db_path: Path to the SQLite cache produced by :class:`~gleif.cache.GleifCacheManager`.
        cache: Optional pre-constructed :class:`~gleif.cache.GleifCacheManager`.
            If supplied, ``db_path`` is ignored.
        api_client: Optional :class:`~gleif.client.GleifApiClient` for live API
            lookups (used for BIC resolution).  Constructed on demand if not
            supplied.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        cache: Optional[GleifCacheManager] = None,
        api_client: Optional[GleifApiClient] = None,
    ) -> None:
        if cache is not None:
            self._cache = cache
        elif db_path is not None:
            self._cache = GleifCacheManager(db_path)
        else:
            raise ValueError("Either db_path or cache must be provided.")
        self._api_client = api_client  # only constructed if needed

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def lookup_lei(
        self,
        lei: str,
        trade_date: Optional[date] = None,
    ) -> LeiLookupResult:
        """Validate a LEI and return entity details.

        Args:
            lei: 20-character Legal Entity Identifier (case-insensitive).
            trade_date: The date on which the associated trade was executed.
                When provided, a ``LAPSED`` LEI is treated as valid if the
                trade date falls before the LEI's ``next_renewal_date``.

        Returns:
            :class:`LeiLookupResult` containing the validity decision and
            entity attributes.
        """
        lei = lei.strip().upper()
        row = self._cache.get_by_lei(lei)

        if row is None:
            return LeiLookupResult(
                lei=lei,
                is_valid=False,
                reason=LeiLookupReason.NOT_IN_GLEIF,
                trade_date=trade_date,
            )

        reg_status = row.get("registration_status", "")
        return _apply_validation_logic(lei, reg_status, row, trade_date)

    def bulk_lookup(
        self,
        leis: List[str],
        trade_date: Optional[date] = None,
    ) -> List[LeiLookupResult]:
        """Validate multiple LEIs efficiently against the local cache.

        Args:
            leis: List of 20-character LEI codes.
            trade_date: Optional trade date applied uniformly to all lookups.
                Pass ``None`` when LEIs should be checked against their current
                status only.

        Returns:
            List of :class:`LeiLookupResult` in the same order as ``leis``.
        """
        return [self.lookup_lei(lei, trade_date) for lei in leis]

    def lookup_by_isin(
        self,
        isin: str,
        trade_date: Optional[date] = None,
    ) -> List[LeiLookupResult]:
        """Return lookup results for all LEIs associated with the given ISIN.

        Queries the ``lei_isin_map`` table populated from the GLEIF ISIN-to-LEI
        mapping file.  If no mapping is found in the cache, an empty list is
        returned (no live API call is made).

        Args:
            isin: ISO 6166 ISIN code.
            trade_date: Optional trade date passed to each LEI lookup.

        Returns:
            List of :class:`LeiLookupResult`, one per LEI mapped to the ISIN.
        """
        isin = isin.strip().upper()
        leis = self._cache.get_leis_for_isin(isin)
        return [self.lookup_lei(lei, trade_date) for lei in leis]

    def search_by_name(
        self,
        name: str,
        limit: int = 20,
        raw_query: bool = False,
        priority_country: Optional[str] = None,
    ) -> List[dict]:
        """Search for legal entities by name using the local FTS5 index.

        Args:
            name: Name fragment or phrase to search for.
            limit: Maximum number of results to return (default: 20).
            raw_query: When ``True``, *name* is passed directly to the FTS5
                ``MATCH`` clause without sanitisation or phrase-quoting.  Use
                this for pre-formed FTS5 expressions such as ``"AJ* Bell*"``.
            priority_country: ISO 3166-1 alpha-2 country code whose results
                are promoted to the top of the list before other FTS5 matches.

        Returns:
            List of row dicts from ``lei_records``, ordered by FTS5 relevance
            with *priority_country* results first.
        """
        return self._cache.search_by_name(
            name, limit=limit, raw_query=raw_query, priority_country=priority_country
        )

    def lookup_by_bic(self, bic: str) -> Optional[LeiLookupResult]:
        """Look up an LEI by BIC code via the live GLEIF API.

        BIC data is not present in the Golden Copy CSV, so this always calls
        the live API.  The resolved LEI is then validated against the local
        cache via :meth:`lookup_lei`.

        Args:
            bic: SWIFT BIC code (e.g. ``"ALETITMMXXX"``).

        Returns:
            :class:`LeiLookupResult` for the resolved LEI, or a
            ``NOT_IN_GLEIF`` result if the BIC is not found.

        Raises:
            requests.HTTPError: On unexpected API errors.
        """
        if self._api_client is None:
            self._api_client = GleifApiClient()

        lei = self._api_client.get_lei_by_bic(bic)
        if not lei:
            return LeiLookupResult(
                lei="",
                is_valid=False,
                reason=LeiLookupReason.NOT_IN_GLEIF,
            )
        return self.lookup_lei(lei)


# ---------------------------------------------------------------------------
# Internal validation logic
# ---------------------------------------------------------------------------


def _apply_validation_logic(
    lei: str,
    reg_status: str,
    row: dict,
    trade_date: Optional[date],
) -> LeiLookupResult:
    """Apply the GLEIF registration status decision tree.

    Args:
        lei: Normalised LEI string.
        reg_status: ``registration_status`` value from the cache row.
        row: Full cache row dict.
        trade_date: Optional trade date for lapse comparison.

    Returns:
        :class:`LeiLookupResult` with the validity decision populated.
    """
    base_kwargs = {
        "lei": lei,
        "legal_name": row.get("legal_name", ""),
        "entity_status": row.get("entity_status", ""),
        "entity_category": row.get("entity_category", ""),
        "legal_address_country": row.get("legal_address_country", ""),
        "registration_status": reg_status,
        "next_renewal_date": row.get("next_renewal_date", ""),
        "successor_lei": row.get("successor_lei", ""),
        "trade_date": trade_date,
    }

    if reg_status == LeiLookupReason.ISSUED:
        return LeiLookupResult(
            is_valid=True, reason=LeiLookupReason.ISSUED, **base_kwargs
        )

    if reg_status == "LAPSED":
        if trade_date is not None:
            renewal_str = row.get("next_renewal_date", "")
            if renewal_str and _trade_before_renewal(trade_date, renewal_str):
                return LeiLookupResult(
                    is_valid=True,
                    reason=LeiLookupReason.LAPSED_VALID_AT_TRADE_DATE,
                    **base_kwargs,
                )
        return LeiLookupResult(
            is_valid=False, reason=LeiLookupReason.LAPSED, **base_kwargs
        )

    # All other statuses — use the status string directly as the reason
    return LeiLookupResult(
        is_valid=False,
        reason=reg_status or LeiLookupReason.NOT_IN_GLEIF,
        **base_kwargs,
    )


def _trade_before_renewal(trade_date: date, renewal_str: str) -> bool:
    """Return ``True`` if ``trade_date`` is strictly before ``renewal_str``.

    Handles ISO 8601 date-time strings (e.g. ``"2027-03-22T22:22:34Z"``) by
    truncating to the date portion before comparison.

    Args:
        trade_date: The trade date to compare.
        renewal_str: ``next_renewal_date`` value from the cache row.

    Returns:
        ``True`` if ``trade_date < renewal_date``; ``False`` on parse failure.
    """
    try:
        renewal_date = date.fromisoformat(renewal_str[:10])
        return trade_date < renewal_date
    except (ValueError, TypeError):
        return False
