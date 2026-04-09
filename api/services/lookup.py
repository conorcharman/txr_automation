"""
Lookup Service
==============

Synchronous in-process lookup wrappers for FIRDS reportability checks and
GLEIF LEI lookups.  These bypass Celery and the CLI scripts, calling the
underlying Python APIs directly for instant results.
"""

import logging
from datetime import date
from pathlib import Path

from api.config import get_settings
from src.firds import FirdsCacheManager, FirdsReportabilityChecker
from src.gleif import GleifCacheManager, GleifLookup

logger = logging.getLogger(__name__)


class FirdsLookupService:
    """Thin wrapper around ``FirdsReportabilityChecker`` for API use."""

    def check_reportability(
        self,
        isin: str,
        trade_date: date,
        mic: str | None = None,
    ) -> dict:
        """Check whether an ISIN is reportable under FIRDS.

        Args:
            isin: The ISIN code to check.
            trade_date: The trade date for the reportability check.
            mic: Optional MIC code to narrow venue matching.

        Returns:
            A dictionary with reportability result fields.
        """
        settings = get_settings()
        db_path = Path(settings.firds_db_path)
        cache = FirdsCacheManager(db_path=db_path)
        checker = FirdsReportabilityChecker(cache=cache)

        result = checker.is_reportable(isin, trade_date, mic)
        return {
            "is_reportable": result.is_reportable,
            "reason": result.reason,
            "isin": result.isin,
            "trade_date": str(result.trade_date),
            "mic": result.mic,
            "matched_mics": result.matched_mics,
        }


class GleifLookupService:
    """Thin wrapper around ``GleifLookup`` for API use."""

    def lookup_lei(
        self,
        lei: str,
        trade_date: date | None = None,
    ) -> dict:
        """Look up a single LEI.

        Args:
            lei: The LEI code to look up.
            trade_date: Optional trade date for the lookup.

        Returns:
            A dictionary with all ``LeiLookupResult`` fields.
        """
        settings = get_settings()
        db_path = Path(settings.gleif_db_path)
        cache = GleifCacheManager(db_path=db_path)
        lookup = GleifLookup(cache=cache)

        result = lookup.lookup_lei(lei, trade_date)
        return {
            "lei": result.lei,
            "is_valid": result.is_valid,
            "reason": result.reason,
            "legal_name": result.legal_name,
            "entity_status": result.entity_status,
            "entity_category": result.entity_category,
            "legal_address_country": result.legal_address_country,
            "registration_status": result.registration_status,
            "next_renewal_date": result.next_renewal_date,
            "successor_lei": result.successor_lei,
            "trade_date": str(result.trade_date) if result.trade_date else None,
        }

    def search_by_name(
        self,
        name: str,
        limit: int = 20,
    ) -> list[dict]:
        """Search for legal entities by name.

        Args:
            name: The company name to search for.
            limit: Maximum number of results to return.

        Returns:
            A list of dictionaries with LEI, name, status, and country.
        """
        settings = get_settings()
        db_path = Path(settings.gleif_db_path)
        cache = GleifCacheManager(db_path=db_path)
        lookup = GleifLookup(cache=cache)

        results = lookup.search_by_name(name, limit=limit)
        return results


firds_lookup_service = FirdsLookupService()
gleif_lookup_service = GleifLookupService()
