"""
FCA Schemas
===========

Pydantic v2 schemas for the FCA Financial Services Register lookup
endpoints.

All schemas use camelCase aliases for JSON serialisation to match the
React frontend convention, whilst still accepting snake_case attribute
names in Python code.
"""

from api.schemas.common import _CamelModel


class FcaCheckRequest(_CamelModel):
    """Request body for a batch FCA firm check.

    Attributes:
        mode: Processing mode — ``"single"`` (default), ``"name_search"``,
            or ``"batch"``.
        frn: Firm Reference Number to look up; used in ``"single"`` mode.
        name: Firm name to search for; used in ``"name_search"`` mode.
        input_file: Path to a CSV file of firms to check; used in
            ``"batch"`` mode.  Must contain an ``frn`` and/or
            ``firm_name`` column.
        output_file: Path for the batch results output CSV; used in
            ``"batch"`` mode.
        log_level: Logging verbosity (default: ``"INFO"``).
    """

    mode: str = "single"
    frn: str | None = None
    name: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    permission: str | None = None
    log_level: str = "INFO"


class FcaPermissionResponse(_CamelModel):
    """A single regulated activity permission held by a firm.

    Attributes:
        activity_name: Name of the regulated activity.
        customer_types: Customer categories covered by this permission.
        investment_types: Investment types in scope.
        limitations: Any restrictions on this permission.
    """

    activity_name: str
    customer_types: list[str] = []
    investment_types: list[str] = []
    limitations: list[str] = []


class FcaLookupResponse(_CamelModel):
    """Response body for a synchronous FCA firm lookup by FRN.

    Attributes:
        frn: The FRN that was looked up.
        organisation_name: Registered legal name of the firm.
        status: Current authorisation status from the Register.
        is_authorised: ``True`` if the firm is currently authorised.
        business_type: Nature of the firm's regulated business.
        companies_house_number: Companies House registration number.
        status_effective_date: Date the current status came into effect.
        permissions: List of regulated activity permissions held by the firm.
    """

    frn: str
    organisation_name: str = ""
    status: str = ""
    is_authorised: bool = False
    business_type: str = ""
    companies_house_number: str = ""
    status_effective_date: str = ""
    permissions: list[FcaPermissionResponse] = []


class FcaSearchResult(_CamelModel):
    """A single result from an FCA firm name search.

    Attributes:
        frn: Firm Reference Number.
        organisation_name: Registered name of the firm.
        status: Current authorisation status.
    """

    frn: str = ""
    organisation_name: str = ""
    status: str = ""


class FcaSearchResponse(_CamelModel):
    """Response body for an FCA firm name search.

    Attributes:
        results: List of matching firms.
        count: Total number of results returned.
    """

    results: list[FcaSearchResult] = []
    count: int = 0


class FcaLeiSearchResponse(_CamelModel):
    """Response body for an FCA firm lookup resolved via an LEI.

    The LEI is first resolved to a legal name using the local GLEIF
    database, then that name is searched against the FCA register.  The
    single closest-matching firm (by name similarity) is returned.

    Attributes:
        lei: The LEI that was submitted.
        resolved_name: The legal entity name resolved from the GLEIF
            database for this LEI.
        result: The closest-matching FCA firm, or ``None`` if no firms
            were found on the register for the resolved name.
    """

    lei: str
    resolved_name: str
    result: FcaSearchResult | None = None
