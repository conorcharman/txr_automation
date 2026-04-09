"""
GLEIF Schemas
=============

Pydantic v2 schemas for the GLEIF (Global Legal Entity Identifier Foundation)
LEI lookup endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class GleifRefreshRequest(_CamelModel):
    """Request body for refreshing the GLEIF local SQLite cache.

    Attributes:
        refresh_type: Type of refresh to perform — ``"full"`` (default) or ``"delta"``.
        delta_type: Delta interval for delta mode; one of ``"8h"``, ``"24h"``,
            ``"7d"``, or ``"31d"``.  Ignored unless ``refresh_type`` is ``"delta"``.
        db_path: Optional path to the SQLite database file. When omitted the
            server-side default from ``GLEIF_DB_PATH`` is used.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    refresh_type: str = "full"
    delta_type: str | None = None
    db_path: str | None = None
    skip_isin_map: bool = False
    log_level: str = "INFO"


class GleifCheckRequest(_CamelModel):
    """Request body for looking up GLEIF LEI data.

    Attributes:
        mode: Processing mode — ``"single"`` (default), ``"name_search"``, or ``"batch"``.
        lei: LEI code to look up; used in ``"single"`` mode.
        name: Legal entity name to search; used in ``"name_search"`` mode.
        limit: Maximum number of results for name search (default: ``20``).
        input_file: Path to a CSV file of LEIs to check; used in ``"batch"`` mode.
        output_file: Path for the batch results output CSV; used in ``"batch"`` mode.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "single"
    lei: str | None = None
    name: str | None = None
    limit: int = 20
    input_file: str | None = None
    output_file: str | None = None
    log_level: str = "INFO"


class GleifBackfillRequest(_CamelModel):
    """Request body for backfilling GLEIF LEI data onto a CSV file.

    Attributes:
        input_file: Path to the input CSV file to annotate.
        output_file: Path for the annotated output CSV file.
        format: CSV format hint — ``"auto"`` (default), ``"incident"``, or ``"generic"``.
        db_path: Optional path to the SQLite database file. When omitted the
            server-side default from ``GLEIF_DB_PATH`` is used.
        skip_refresh: If ``True``, skip the automatic cache refresh before
            backfilling (default: ``False``).
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    input_file: str
    output_file: str
    format: str = "auto"
    db_path: str | None = None
    skip_refresh: bool = False
    log_level: str = "INFO"


class GleifLookupResponse(_CamelModel):
    """Response body for a synchronous GLEIF LEI lookup.

    Attributes:
        lei: The LEI code that was looked up.
        is_valid: Whether the LEI is valid.
        reason: Reason for the validity determination.
        legal_name: Legal name of the entity.
        entity_status: Entity status (e.g. ``"ACTIVE"``).
        entity_category: Entity category classification.
        legal_address_country: ISO country code of the legal address.
        registration_status: LEI registration status.
        next_renewal_date: Next renewal date for the LEI registration.
        successor_lei: Successor LEI if the entity has been merged or acquired.
        trade_date: The trade date used for the lookup, if any.
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
    trade_date: str | None = None


class GleifSearchResult(_CamelModel):
    """A single result from a GLEIF name search.

    Attributes:
        lei: The matched LEI code.
        legal_name: Legal name of the entity.
        status: Registration status.
        country: ISO country code.
    """

    lei: str = ""
    legal_name: str = ""
    status: str = ""
    country: str = ""


class GleifSearchResponse(_CamelModel):
    """Response body for a GLEIF name search.

    Attributes:
        results: List of matching search results.
        count: Total number of results returned.
    """

    results: list[GleifSearchResult] = []
    count: int = 0
