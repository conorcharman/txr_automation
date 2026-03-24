"""
GLEIF LEI Module
================

Local-cache-based access to GLEIF (Global Legal Entity Identifier Foundation)
data for LEI validation, name lookup, and ISIN-to-LEI mapping.

Key exports
-----------
:class:`GleifLookup`
    Primary public API.  Call ``lookup_lei(lei, trade_date)`` to validate a
    Legal Entity Identifier and retrieve entity details.

:class:`LeiLookupResult`
    Dataclass returned by the lookup, holding the validity decision, reason
    code, legal name, and other entity attributes.

:class:`LeiLookupReason`
    String constants for lookup reason codes: ``ISSUED``,
    ``LAPSED_VALID_AT_TRADE_DATE``, ``LAPSED``, ``NOT_IN_GLEIF``, etc.

:class:`GleifRefresher`
    Orchestrates downloading and caching GLEIF Golden Copy data.

:class:`GleifCacheManager`
    Low-level SQLite cache manager (advanced use).
"""

from .cache import GleifCacheManager
from .client import GleifApiClient, GoldenCopyInfo
from .downloader import GleifDownloader, GleifDownloadResult
from .lookup import GleifLookup, LeiLookupReason, LeiLookupResult
from .parser import GleifCsvParser, GleifIsinMapParser, LeiRecord
from .refresher import GleifRefresher, RefreshResult

__all__ = [
    "GleifCacheManager",
    "GleifApiClient",
    "GoldenCopyInfo",
    "GleifDownloader",
    "GleifDownloadResult",
    "GleifLookup",
    "LeiLookupReason",
    "LeiLookupResult",
    "GleifCsvParser",
    "GleifIsinMapParser",
    "LeiRecord",
    "GleifRefresher",
    "RefreshResult",
]
