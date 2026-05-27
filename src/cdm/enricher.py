"""CDM transaction enricher.

Best-effort enrichment of transaction fields using the local GLEIF Golden Copy
cache and the FIRDS instrument reference cache.

Enrichment is always optional — if caches are not populated or lookups fail,
the mapper still produces a valid (but less annotated) CDM JSON.  This design
means the enricher never blocks report generation.

Usage::

    from pathlib import Path
    from src.cdm.enricher import enrich_transaction
    from src.gleif import GleifCacheManager, GleifLookup
    from src.firds import FirdsCacheManager

    gleif = GleifLookup(cache=GleifCacheManager(Path("data/gleif_cache.db")))
    firds = FirdsCacheManager(db_path=Path("data/firds_cache.db"))

    result = enrich_transaction(
        buyer_id="529900T8BM49AURSDO55", buyer_id_type="LEI",
        seller_id="5493001KJTIIGC8Y1R12", seller_id_type="LEI",
        isin="GB0001234567",
        gleif_lookup=gleif,
        firds_cache=firds,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.firds import FirdsCacheManager
    from src.gleif import GleifLookup

logger = logging.getLogger(__name__)


@dataclass
class LeiEnrichment:
    """Result of looking up a single LEI in the GLEIF cache."""

    lei: str
    found: bool
    is_valid: bool
    reason: str
    legal_name: str | None = None
    entity_status: str | None = None
    registration_status: str | None = None
    legal_address_country: str | None = None


@dataclass
class InstrumentEnrichment:
    """Result of looking up an ISIN in the FIRDS cache."""

    isin: str
    found: bool
    full_name: str | None = None
    cfi_code: str | None = None
    mic: str | None = None


@dataclass
class EnrichmentResult:
    """Aggregated enrichment for a single transaction."""

    buyer: LeiEnrichment | None = None
    seller: LeiEnrichment | None = None
    instrument: InstrumentEnrichment | None = None


def _enrich_lei(
    lei: str,
    trade_date: date | None,
    gleif_lookup: "GleifLookup",
) -> LeiEnrichment:
    """Look up a single LEI and return a populated LeiEnrichment."""
    try:
        result = gleif_lookup.lookup_lei(lei, trade_date=trade_date)
        return LeiEnrichment(
            lei=result.lei,
            found=result.reason != "NOT_IN_GLEIF",
            is_valid=result.is_valid,
            reason=result.reason,
            legal_name=result.legal_name or None,
            entity_status=result.entity_status or None,
            registration_status=result.registration_status or None,
            legal_address_country=result.legal_address_country or None,
        )
    except Exception:
        logger.debug("GLEIF lookup failed for LEI %s", lei, exc_info=True)
        return LeiEnrichment(lei=lei, found=False, is_valid=False, reason="LOOKUP_ERROR")


def _enrich_instrument(
    isin: str,
    mic: str | None,
    firds_cache: "FirdsCacheManager",
) -> InstrumentEnrichment:
    """Look up an ISIN in the FIRDS cache and return instrument metadata."""
    try:
        row: dict | None = None
        if mic:
            row = firds_cache.get_by_isin_mic(isin.upper(), mic.upper())
        if row is None:
            rows = firds_cache.get_by_isin(isin.upper())
            row = rows[0] if rows else None

        if row is None:
            return InstrumentEnrichment(isin=isin, found=False)

        return InstrumentEnrichment(
            isin=isin,
            found=True,
            full_name=row.get("full_name") or None,
            cfi_code=row.get("cfi_code") or None,
            mic=row.get("mic") or None,
        )
    except Exception:
        logger.debug("FIRDS lookup failed for ISIN %s", isin, exc_info=True)
        return InstrumentEnrichment(isin=isin, found=False)


def enrich_transaction(
    buyer_id: str | None,
    buyer_id_type: str | None,
    seller_id: str | None,
    seller_id_type: str | None,
    isin: str | None,
    trade_date: date | None = None,
    venue: str | None = None,
    gleif_lookup: "GleifLookup | None" = None,
    firds_cache: "FirdsCacheManager | None" = None,
) -> EnrichmentResult:
    """Enrich transaction party and instrument fields from local caches.

    Only LEI-typed party IDs are looked up in GLEIF.  CONCAT / NIDN / BIC etc.
    are skipped — the enrichment slot remains ``None`` for those.

    All lookups are best-effort: failures are logged at DEBUG level and the
    corresponding enrichment slot is set to a ``found=False`` entry rather than
    propagating an exception.

    Args:
        buyer_id: Buyer identification code.
        buyer_id_type: Buyer ID type (LEI, CONCAT, NIDN, …).
        seller_id: Seller identification code.
        seller_id_type: Seller ID type.
        isin: ISIN of the financial instrument.
        trade_date: Trade date for LEI validity check.
        venue: Venue MIC — used to narrow FIRDS lookup when provided.
        gleif_lookup: Pre-constructed GleifLookup instance.  Pass ``None``
            to skip all LEI enrichment.
        firds_cache: Pre-constructed FirdsCacheManager instance.  Pass
            ``None`` to skip instrument enrichment.

    Returns:
        EnrichmentResult with ``buyer``, ``seller``, and ``instrument`` slots
        populated where applicable.
    """
    result = EnrichmentResult()

    if gleif_lookup is not None:
        if buyer_id and buyer_id_type and buyer_id_type.upper() == "LEI":
            result.buyer = _enrich_lei(buyer_id, trade_date, gleif_lookup)
        if seller_id and seller_id_type and seller_id_type.upper() == "LEI":
            result.seller = _enrich_lei(seller_id, trade_date, gleif_lookup)

    if firds_cache is not None and isin:
        result.instrument = _enrich_instrument(isin, venue, firds_cache)

    return result
