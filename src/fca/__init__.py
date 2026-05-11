"""
FCA Financial Services Register Module
=======================================

Live-lookup access to the UK FCA Financial Services Register API for
firm authorisation checks and regulated permissions retrieval.

The API is free to use but requires registration at the FCA Developer
Portal (https://register.fca.org.uk/Developer/s/) to obtain credentials.

Key exports
-----------
:class:`FcaRegisterClient`
    Low-level HTTP client.  Handles authentication headers, rate limiting
    (50 requests per 10 seconds), and HTTP 429 back-off.

:class:`FcaFirmLookup`
    Primary public API.  Call ``lookup_by_frn(frn)`` to retrieve firm
    details and permissions, or ``search_by_name(name)`` to find firms
    by name.

:class:`FirmLookupResult`
    Dataclass returned by ``lookup_by_frn``, holding the firm record and
    its list of regulated permissions.

:class:`FirmRecord`
    Dataclass describing a single firm entry from the Register.

:class:`FirmPermission`
    Dataclass describing one regulated activity permission held by a firm.

:class:`FcaApiError`
    Exception raised when the FCA API returns a non-200 response or an
    unexpected error occurs.
"""

from .client import FcaApiError, FcaRegisterClient
from .lookup import FcaFirmLookup, FirmLookupResult, FirmPermission, FirmRecord

__all__ = [
    "FcaApiError",
    "FcaRegisterClient",
    "FcaFirmLookup",
    "FirmLookupResult",
    "FirmPermission",
    "FirmRecord",
]
