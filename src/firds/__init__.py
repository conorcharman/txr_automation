"""
FCA FIRDS Module
================

Local-cache-based access to FCA Financial Instruments Reference Data System
(FIRDS) for automated reportability determination under UK MiFIR.

Key exports
-----------
:class:`FirdsReportabilityChecker`
    Primary public API.  Call ``is_reportable(isin, trade_date, mic)`` to
    check whether an instrument was reportable at a given point in time.

:class:`ReportabilityResult`
    Dataclass returned by the checker holding the decision, reason code, and
    matched trading venues.

:class:`ReportabilityReason`
    String constants for reason codes: ``ACTIVE``, ``NOT_IN_FIRDS``,
    ``TERMINATED_BEFORE_TRADE``, ``ADMISSION_AFTER_TRADE``, ``CANCELLED``.

:class:`FirdsRefresher`
    Orchestrates downloading and caching FIRDS data from the FCA API.

:class:`FirdsCacheManager`
    Low-level SQLite cache manager (advanced use).
"""

from .cache import FirdsCacheManager
from .client import FirdsApiClient, FirdsFileRecord
from .parser import FirdsXmlParser, InstrumentRecord
from .refresher import FirdsRefresher, RefreshResult
from .reportability import (
    FirdsReportabilityChecker,
    ReportabilityReason,
    ReportabilityResult,
)

__all__ = [
    "FirdsCacheManager",
    "FirdsApiClient",
    "FirdsFileRecord",
    "FirdsXmlParser",
    "InstrumentRecord",
    "FirdsRefresher",
    "RefreshResult",
    "FirdsReportabilityChecker",
    "ReportabilityReason",
    "ReportabilityResult",
]
