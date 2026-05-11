#!/usr/bin/env python3
"""
FCA Firm Lookup
===============

Public API for retrieving firm authorisation status and regulated activity
permissions from the FCA Financial Services Register.

All lookups are live — there is no local cache.  Each call to
``lookup_by_frn`` makes two API requests (firm details + permissions).
Each call to ``search_by_name`` makes one request.

Usage:
    from fca.lookup import FcaFirmLookup

    lookup = FcaFirmLookup(api_email="user@example.com", api_key="key")

    # Look up a firm by FRN
    result = lookup.lookup_by_frn("122702")
    print(result.is_authorised, result.firm.organisation_name)
    for perm in result.permissions:
        print(perm.activity_name)

    # Search by name (returns multiple candidates)
    firms = lookup.search_by_name("Barclays")
    for firm in firms:
        print(firm.frn, firm.organisation_name, firm.status)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import FcaApiError, FcaRegisterClient

logger = logging.getLogger(__name__)

# FCA Register status string for authorised firms.
_AUTHORISED_STATUS = "Authorised"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FirmRecord:
    """A firm entry from the FCA Financial Services Register.

    Attributes:
        frn: Firm Reference Number — unique identifier assigned by the FCA.
        organisation_name: Registered legal name of the firm.
        status: Current authorisation status, e.g. ``"Authorised"`` or
            ``"No longer authorised"``.
        business_type: Nature of the firm's regulated business, e.g.
            ``"Regulated"`` or ``"Appointed Representative"``.
        companies_house_number: Companies House registration number, if held.
        status_effective_date: Date the current status came into effect
            (``DD/MM/YYYY`` format as returned by the API).
    """

    frn: str
    organisation_name: str
    status: str
    business_type: str = ""
    companies_house_number: str = ""
    status_effective_date: str = ""

    def __str__(self) -> str:
        return (
            f"FirmRecord(frn={self.frn!r}, name={self.organisation_name!r}, "
            f"status={self.status!r})"
        )


@dataclass
class FirmPermission:
    """A single regulated activity permission held by a firm.

    Attributes:
        activity_name: Name of the regulated activity, e.g.
            ``"Accepting Deposits"`` or ``"Dealing in investments as agent"``.
        customer_types: Customer categories covered by this permission,
            e.g. ``["Retail", "Professional"]``.
        investment_types: Investment types in scope, e.g. ``["Deposit"]``.
        limitations: Any restrictions or limitations on this permission.
    """

    activity_name: str
    customer_types: List[str] = field(default_factory=list)
    investment_types: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"FirmPermission(activity={self.activity_name!r})"


@dataclass
class FirmLookupResult:
    """The outcome of a firm lookup by FRN.

    Attributes:
        frn: The FRN that was looked up.
        firm: The :class:`FirmRecord` for the firm, or ``None`` if not found.
        is_authorised: ``True`` if the firm's current status is
            ``"Authorised"``.
        permissions: List of :class:`FirmPermission` objects representing
            the firm's regulated activities.  Empty list if the firm has no
            permissions or was not found.
    """

    frn: str
    firm: Optional[FirmRecord]
    is_authorised: bool
    permissions: List[FirmPermission] = field(default_factory=list)

    def __str__(self) -> str:
        name = self.firm.organisation_name if self.firm else "NOT FOUND"
        return (
            f"FirmLookupResult(frn={self.frn!r}, name={name!r}, "
            f"authorised={self.is_authorised}, "
            f"permissions={len(self.permissions)})"
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_firm_record(data: Dict[str, Any]) -> FirmRecord:
    """Parse a raw API firm dict into a :class:`FirmRecord`.

    Args:
        data: Dict from ``GET /V0.1/Firm/{FRN}`` ``Data[0]``.

    Returns:
        Populated :class:`FirmRecord`.
    """
    return FirmRecord(
        frn=str(data.get("FRN", "")),
        organisation_name=str(data.get("Organisation Name", "")),
        status=str(data.get("Status", "")),
        business_type=str(data.get("Business Type", "")),
        companies_house_number=str(data.get("Companies House Number", "")),
        status_effective_date=str(data.get("Status Effective Date", "")),
    )


def _parse_firm_record_from_search(data: Dict[str, Any]) -> FirmRecord:
    """Parse a raw search result dict into a :class:`FirmRecord`.

    Search results use different key names from the full firm endpoint.

    Args:
        data: Dict from ``GET /V0.1/Search`` ``Data[]``.

    Returns:
        Partially populated :class:`FirmRecord` (no business_type,
        companies_house_number, or status_effective_date).
    """
    return FirmRecord(
        frn=str(data.get("Reference Number", "")),
        organisation_name=str(data.get("Name", "")),
        status=str(data.get("Status", "")),
    )


def _parse_permissions(raw: Dict[str, Any]) -> List[FirmPermission]:
    """Parse the raw permissions dict into a list of :class:`FirmPermission`.

    The API returns a dict mapping activity name to a list of detail dicts,
    where each detail dict may have ``Customer Type``, ``Investment Type``,
    and ``Limitation Not Found`` / ``Limitation`` keys.

    Args:
        raw: Dict from ``GET /V0.1/Firm/{FRN}/Permissions`` ``Data``.

    Returns:
        List of :class:`FirmPermission` objects, one per activity.
    """
    permissions: List[FirmPermission] = []

    for activity_name, detail_list in raw.items():
        customer_types: List[str] = []
        investment_types: List[str] = []
        limitations: List[str] = []

        if isinstance(detail_list, list):
            for detail in detail_list:
                if not isinstance(detail, dict):
                    continue
                ct = detail.get("Customer Type")
                if isinstance(ct, list):
                    customer_types.extend(str(v) for v in ct)
                it = detail.get("Investment Type")
                if isinstance(it, list):
                    investment_types.extend(str(v) for v in it)
                lim = detail.get("Limitation")
                if isinstance(lim, list):
                    limitations.extend(str(v) for v in lim)

        permissions.append(
            FirmPermission(
                activity_name=activity_name,
                customer_types=customer_types,
                investment_types=investment_types,
                limitations=limitations,
            )
        )

    return sorted(permissions, key=lambda p: p.activity_name)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class FcaFirmLookup:
    """Live lookup wrapper for the FCA Financial Services Register.

    Each instance holds a configured :class:`FcaRegisterClient`.  All
    lookups are live — there is no local cache.

    Args:
        api_email: FCA Developer Portal signup email.
        api_key: FCA Developer Portal API key.
        client: Optional pre-configured :class:`FcaRegisterClient`.
            When supplied, ``api_email`` and ``api_key`` are ignored.
            Useful for testing with a mock client.

    Example:
        >>> lookup = FcaFirmLookup(api_email="user@example.com", api_key="key")
        >>> result = lookup.lookup_by_frn("122702")
        >>> result.is_authorised
        True
    """

    def __init__(
        self,
        api_email: str = "",
        api_key: str = "",
        client: Optional[FcaRegisterClient] = None,
    ) -> None:
        self._client = client or FcaRegisterClient(
            api_email=api_email,
            api_key=api_key,
        )

    def lookup_by_frn(self, frn: str) -> FirmLookupResult:
        """Look up a firm by Firm Reference Number.

        Makes two API requests: one for firm details, one for permissions.

        Args:
            frn: Firm Reference Number (FRN) as a string, e.g. ``"122702"``.

        Returns:
            :class:`FirmLookupResult` containing the firm record,
            authorisation status, and permissions list.
            If the FRN is not found, returns a result with ``firm=None``
            and ``is_authorised=False``.

        Example:
            >>> result = lookup.lookup_by_frn("122702")
            >>> result.firm.organisation_name
            'Barclays Bank Plc'
        """
        frn = frn.strip()
        logger.info("FCA lookup by FRN: %r", frn)

        try:
            firm_data = self._client.get_firm(frn)
        except FcaApiError as exc:
            if exc.status_code == 404:
                logger.warning("FRN %r not found in FCA Register.", frn)
                return FirmLookupResult(frn=frn, firm=None, is_authorised=False)
            raise

        firm = _parse_firm_record(firm_data)
        is_authorised = firm.status == _AUTHORISED_STATUS

        try:
            raw_permissions = self._client.get_firm_permissions(frn)
            permissions = _parse_permissions(raw_permissions)
        except FcaApiError:
            logger.warning(
                "Could not retrieve permissions for FRN %r — returning empty list.",
                frn,
            )
            permissions = []

        return FirmLookupResult(
            frn=frn,
            firm=firm,
            is_authorised=is_authorised,
            permissions=permissions,
        )

    def search_by_name(self, name: str) -> List[FirmRecord]:
        """Search for firms by name.

        Makes one API request.  Returns all matching firms; the list may
        be long for common name substrings.

        Args:
            name: Firm name or name substring to search for.

        Returns:
            List of :class:`FirmRecord` objects matching the search term.
            Returns an empty list when no results are found or an API
            error occurs.

        Example:
            >>> firms = lookup.search_by_name("Barclays")
            >>> firms[0].frn
            '759676'
        """
        name = name.strip()
        logger.info("FCA search by name: %r", name)

        try:
            results = self._client.search_firms(name)
        except FcaApiError:
            logger.warning("FCA name search failed for %r — returning empty list.", name)
            return []

        return [_parse_firm_record_from_search(r) for r in results]
