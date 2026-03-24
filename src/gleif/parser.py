#!/usr/bin/env python3
"""
GLEIF Golden Copy CSV Parser
=============================

Memory-efficient streaming parser for GLEIF Golden Copy CSV files (LEI-CDF v3.1),
and a companion parser for the GLEIF ISIN-to-LEI mapping CSV.

The Golden Copy CSV is a single file containing all registered LEIs globally
(~3.2 million records as of 2026).  It is parsed row-by-row using the standard
library ``csv`` module, keeping memory usage flat regardless of file size.

The ISIN-to-LEI mapping file is a separate GLEIF publication listing ISIN codes
and their associated LEIs as reported by ANNA (Association of National Numbering
Agencies).  Each row maps one ISIN to one LEI; one LEI may appear on many rows.

Usage:
    parser = GleifCsvParser()
    for record in parser.parse(Path("gleif-goldencopy.csv")):
        print(record.lei, record.legal_name, record.registration_status)

    isin_parser = GleifIsinMapParser()
    for lei, isin in isin_parser.parse(Path("gleif-isin-lei-map.csv")):
        print(isin, "->", lei)
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LEI-CDF v3.1 column name constants
# ---------------------------------------------------------------------------

_COL_LEI = "LEI"
_COL_LEGAL_NAME = "Entity.LegalName"
_COL_JURISDICTION = "Entity.LegalJurisdiction"
_COL_ENTITY_STATUS = "Entity.EntityStatus"
_COL_LEGAL_ADDR_COUNTRY = "Entity.LegalAddress.Country"
_COL_ENTITY_EXPIRATION_DATE = "Entity.EntityExpirationDate"
_COL_ENTITY_EXPIRATION_REASON = "Entity.EntityExpirationReason"
_COL_SUCCESSOR_LEI = "Entity.SuccessorEntity.SuccessorLEI"
_COL_REGISTRATION_STATUS = "Registration.RegistrationStatus"
_COL_INITIAL_REG_DATE = "Registration.InitialRegistrationDate"
_COL_LAST_UPDATE_DATE = "Registration.LastUpdateDate"
_COL_NEXT_RENEWAL_DATE = "Registration.NextRenewalDate"

# Columns whose presence is optional across Golden Copy versions
_OPTIONAL_COLS = {
    "Entity.EntityCategory",
    "Entity.EntityExpirationDate",
    "Entity.EntityExpirationReason",
    "Entity.SuccessorEntity.SuccessorLEI",
}

# Prefix for other entity name sub-columns (e.g. Entity.OtherEntityNames.0.OtherEntityName.name)
_OTHER_NAMES_PREFIX = "Entity.OtherEntityNames"

# Minimum required columns; parser raises if any are absent
_REQUIRED_COLS = {
    _COL_LEI,
    _COL_LEGAL_NAME,
    _COL_REGISTRATION_STATUS,
}

# ISIN mapping CSV expected column names
_ISIN_COL_LEI = "LEI"
_ISIN_COL_ISIN = "ISIN"


@dataclass
class LeiRecord:
    """A single LEI record from the GLEIF Golden Copy.

    Attributes:
        lei: 20-character Legal Entity Identifier code.
        legal_name: Official registered legal name of the entity.
        registration_status: LEI registration status — one of ``ISSUED``,
            ``LAPSED``, ``MERGED``, ``RETIRED``, ``ANNULLED``, ``CANCELLED``,
            ``TRANSFERRED``, ``PENDING_TRANSFER``, ``PENDING_ARCHIVAL``.
        entity_status: Entity lifecycle status — ``ACTIVE`` or ``INACTIVE``.
        entity_category: Legal entity category — e.g. ``GENERAL``, ``FUND``,
            ``SOLE_PROPRIETOR``.  May be empty for older registrations.
        legal_address_country: ISO 3166-1 alpha-2 country code of the entity's
            registered legal address.
        legal_jurisdiction: Full ISO 3166 jurisdiction code (country or
            country + region).
        other_names: Semicolon-separated list of alternative or transliterated
            entity names.  Empty string when none are present.
        initial_registration_date: ISO 8601 date-time of initial LEI registration.
        last_update_date: ISO 8601 date-time of the most recent data update.
        next_renewal_date: ISO 8601 date-time by which the registration must
            be renewed to remain ``ISSUED``.
        entity_expiration_date: Date the legal entity ceased to exist, if applicable.
        entity_expiration_reason: Reason for expiration — ``DISSOLVED``,
            ``MERGED``, or ``CORPORATE_ACTION``.
        successor_lei: LEI of the successor entity following a merger or transfer.
    """

    lei: str
    legal_name: str
    registration_status: str
    entity_status: str = ""
    entity_category: str = ""
    legal_address_country: str = ""
    legal_jurisdiction: str = ""
    other_names: str = ""
    initial_registration_date: str = ""
    last_update_date: str = ""
    next_renewal_date: str = ""
    entity_expiration_date: Optional[str] = None
    entity_expiration_reason: str = ""
    successor_lei: str = ""


class GleifCsvParser:
    """Streaming parser for GLEIF Golden Copy CSV files (LEI-CDF v3.1).

    Yields :class:`LeiRecord` objects row by row without loading the entire
    file into memory.
    """

    def parse(self, csv_path: Path) -> Iterator[LeiRecord]:
        """Parse a GLEIF Golden Copy CSV and yield LEI records.

        Args:
            csv_path: Path to the Golden Copy CSV file (may be extracted from
                the Golden Copy ZIP archive).

        Yields:
            :class:`LeiRecord` for each valid row in the file.

        Raises:
            FileNotFoundError: If ``csv_path`` does not exist.
            ValueError: If required columns are absent from the header.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"GLEIF Golden Copy CSV not found: {csv_path}")

        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)

            if not reader.fieldnames:
                logger.warning("Empty GLEIF CSV file: %s", csv_path)
                return

            fieldnames = set(reader.fieldnames)
            missing = _REQUIRED_COLS - fieldnames
            if missing:
                raise ValueError(
                    f"GLEIF Golden Copy CSV is missing required columns: {missing}"
                )

            # Discover other-name sub-columns dynamically
            other_name_cols: List[str] = sorted(
                c for c in reader.fieldnames if c.startswith(_OTHER_NAMES_PREFIX)
            )

            # Cache the entity category column name (may not exist in all versions)
            cat_col = "Entity.EntityCategory" if "Entity.EntityCategory" in fieldnames else None

            rows_yielded = 0
            rows_skipped = 0

            for row in reader:
                lei = row.get(_COL_LEI, "").strip()
                legal_name = row.get(_COL_LEGAL_NAME, "").strip()
                registration_status = row.get(_COL_REGISTRATION_STATUS, "").strip()

                if not lei or not registration_status:
                    rows_skipped += 1
                    continue

                # Collect all non-empty other entity names and join with "; "
                other_names = "; ".join(
                    row[c].strip()
                    for c in other_name_cols
                    if row.get(c, "").strip()
                )

                expiration_date = row.get(_COL_ENTITY_EXPIRATION_DATE, "").strip() or None

                yield LeiRecord(
                    lei=lei,
                    legal_name=legal_name,
                    registration_status=registration_status,
                    entity_status=row.get(_COL_ENTITY_STATUS, "").strip(),
                    entity_category=row.get(cat_col or "", "").strip() if cat_col else "",
                    legal_address_country=row.get(_COL_LEGAL_ADDR_COUNTRY, "").strip(),
                    legal_jurisdiction=row.get(_COL_JURISDICTION, "").strip(),
                    other_names=other_names,
                    initial_registration_date=row.get(_COL_INITIAL_REG_DATE, "").strip(),
                    last_update_date=row.get(_COL_LAST_UPDATE_DATE, "").strip(),
                    next_renewal_date=row.get(_COL_NEXT_RENEWAL_DATE, "").strip(),
                    entity_expiration_date=expiration_date,
                    entity_expiration_reason=row.get(
                        _COL_ENTITY_EXPIRATION_REASON, ""
                    ).strip(),
                    successor_lei=row.get(_COL_SUCCESSOR_LEI, "").strip(),
                )
                rows_yielded += 1

        logger.info(
            "GLEIF CSV parse complete",
            extra={
                "file": str(csv_path),
                "rows_yielded": rows_yielded,
                "rows_skipped": rows_skipped,
            },
        )


class GleifIsinMapParser:
    """Parser for the GLEIF ISIN-to-LEI mapping CSV.

    The mapping file is published separately from the Golden Copy and lists
    ISIN codes alongside the LEI of the associated issuing entity, as reported
    by ANNA member organisations.

    Yields:
        Tuples of ``(lei: str, isin: str)``
    """

    def parse(self, csv_path: Path) -> Iterator[Tuple[str, str]]:
        """Parse a GLEIF ISIN-to-LEI mapping CSV and yield (lei, isin) pairs.

        Args:
            csv_path: Path to the ISIN-to-LEI mapping CSV file.

        Yields:
            ``(lei, isin)`` tuples, one per valid row.

        Raises:
            FileNotFoundError: If ``csv_path`` does not exist.
            ValueError: If the ``LEI`` or ``ISIN`` column is absent.
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"GLEIF ISIN mapping CSV not found: {csv_path}")

        rows_yielded = 0
        rows_skipped = 0

        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)

            if not reader.fieldnames:
                logger.warning("Empty GLEIF ISIN mapping file: %s", csv_path)
                return

            fieldnames = set(reader.fieldnames)
            for required in (_ISIN_COL_LEI, _ISIN_COL_ISIN):
                if required not in fieldnames:
                    raise ValueError(
                        f"GLEIF ISIN mapping CSV missing required column '{required}' "
                        f"in {csv_path}"
                    )

            for row in reader:
                lei = row.get(_ISIN_COL_LEI, "").strip()
                isin = row.get(_ISIN_COL_ISIN, "").strip()
                if lei and isin:
                    yield (lei, isin)
                    rows_yielded += 1
                else:
                    rows_skipped += 1

        logger.info(
            "GLEIF ISIN mapping parse complete",
            extra={
                "file": str(csv_path),
                "rows_yielded": rows_yielded,
                "rows_skipped": rows_skipped,
            },
        )
