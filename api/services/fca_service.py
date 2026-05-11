"""
FCA Lookup Service
==================

Thin service wrapper around :class:`FcaFirmLookup` for use by the
FastAPI router.  Reads credentials from application settings and calls
the lookup directly in-process (no Celery task) for single FRN and name
search endpoints.
"""

import logging
from typing import Any

from api.config import get_settings
from src.fca.lookup import FcaFirmLookup

logger = logging.getLogger(__name__)


class FcaLookupService:
    """Thin wrapper around :class:`FcaFirmLookup` for API use.

    Instantiated once at module level and imported by the FCA router.
    A new :class:`FcaFirmLookup` (and underlying :class:`FcaRegisterClient`)
    is created per call to keep the service stateless and credentials
    always current from settings.
    """

    def lookup_by_frn(self, frn: str) -> dict[str, Any]:
        """Look up a firm by FRN and return a serialisable dict.

        Args:
            frn: Firm Reference Number to look up.

        Returns:
            Dict suitable for constructing a ``FcaLookupResponse``.
        """
        settings = get_settings()
        lookup = FcaFirmLookup(
            api_email=settings.fca_api_email,
            api_key=settings.fca_api_key,
        )
        result = lookup.lookup_by_frn(frn)

        permissions = [
            {
                "activity_name": p.activity_name,
                "customer_types": p.customer_types,
                "investment_types": p.investment_types,
                "limitations": p.limitations,
            }
            for p in result.permissions
        ]

        return {
            "frn": result.frn,
            "organisation_name": result.firm.organisation_name if result.firm else "",
            "status": result.firm.status if result.firm else "NOT FOUND",
            "is_authorised": result.is_authorised,
            "business_type": result.firm.business_type if result.firm else "",
            "companies_house_number": result.firm.companies_house_number if result.firm else "",
            "status_effective_date": result.firm.status_effective_date if result.firm else "",
            "permissions": permissions,
        }

    def search_by_name(self, name: str) -> dict[str, Any]:
        """Search for firms by name and return a serialisable dict.

        Args:
            name: Firm name or name substring to search for.

        Returns:
            Dict suitable for constructing a ``FcaSearchResponse``, with
            ``results`` and ``count`` keys.
        """
        settings = get_settings()
        lookup = FcaFirmLookup(
            api_email=settings.fca_api_email,
            api_key=settings.fca_api_key,
        )
        firms = lookup.search_by_name(name)

        results = [
            {
                "frn": f.frn,
                "organisation_name": f.organisation_name,
                "status": f.status,
            }
            for f in firms
        ]

        return {"results": results, "count": len(results)}


fca_lookup_service = FcaLookupService()
