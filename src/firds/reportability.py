#!/usr/bin/env python3
"""
FCA FIRDS Reportability Checker
================================

Public API for determining whether a financial instrument is reportable under
UK MiFIR at a given point in time.

An instrument is considered **reportable** if, at the trade date:

1.  It appears in the FCA FIRDS cache (i.e. it has been admitted to at least
    one trading venue covered by FIRDS).
2.  Its ``admission_date`` is on or before the trade date.
3.  Its ``termination_date`` is either absent (still active) or strictly
    after the trade date.
4.  It has not been cancelled (``is_cancelled = 0``).

When a ``mic`` (Market Identifier Code) is supplied the check is scoped to
that specific trading venue first.  If the instrument is **not** active on
that venue but IS active on at least one other venue in the cache, the
result is still considered reportable (``is_reportable=True``) with reason
``ACTIVE_OTHER_VENUE`` and the alternative active venues returned in
``matched_mics``.  When no ``mic`` is supplied the instrument is considered
reportable if it meets the criteria on **any** venue in the cache.

Usage:
    from pathlib import Path
    from datetime import date

    checker = FirdsReportabilityChecker(db_path=Path("data/firds_cache.db"))

    result = checker.is_reportable(
        isin="GB00B3RBWM25",
        trade_date=date(2025, 6, 15),
        mic="XLON",
    )
    print(result.is_reportable, result.reason)
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

from .cache import FirdsCacheManager

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


class ReportabilityReason:
    """String constants for reportability decision reasons."""

    ACTIVE = "ACTIVE"
    """The instrument is active in FIRDS at the trade date."""

    NOT_IN_FIRDS = "NOT_IN_FIRDS"
    """No record found in the FIRDS cache for the given ISIN (and MIC)."""

    ADMISSION_AFTER_TRADE = "ADMISSION_AFTER_TRADE"
    """The instrument's admission date is after the trade date."""

    TERMINATED_BEFORE_TRADE = "TERMINATED_BEFORE_TRADE"
    """The instrument was terminated before (or on) the trade date."""

    CANCELLED = "CANCELLED"
    """The instrument has been cancelled."""

    ACTIVE_OTHER_VENUE = "ACTIVE_OTHER_VENUE"
    """The instrument is not active on the requested MIC but is active on at
    least one other trading venue in the FIRDS cache.  ``matched_mics`` on
    the result lists those alternative venues."""


@dataclass
class ReportabilityResult:
    """The outcome of a reportability check.

    Attributes:
        is_reportable: ``True`` if the instrument is reportable at the trade date.
        reason: One of the :class:`ReportabilityReason` string constants explaining
            the decision.
        isin: The ISIN that was checked.
        trade_date: The trade date used for the check.
        mic: The specific MIC checked, or ``None`` if checked across all venues.
        matched_mics: List of MICs for which the instrument was active at the
            trade date (only populated when ``mic`` is ``None``).
    """

    is_reportable: bool
    reason: str
    isin: str
    trade_date: date
    mic: Optional[str] = None
    matched_mics: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        mic_info = f", MIC={self.mic}" if self.mic else ""
        return (
            f"ReportabilityResult(isin={self.isin}{mic_info}, "
            f"date={self.trade_date}, "
            f"reportable={self.is_reportable}, "
            f"reason={self.reason})"
        )


class FirdsReportabilityChecker:
    """Checks whether instruments are reportable using the local FIRDS cache.

    Args:
        db_path: Path to the SQLite cache database produced by
            :class:`~firds.cache.FirdsCacheManager`.
        cache: Optional pre-constructed :class:`~firds.cache.FirdsCacheManager`.
            If supplied, ``db_path`` is ignored.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        cache: Optional[FirdsCacheManager] = None,
    ) -> None:
        if cache is not None:
            self._cache = cache
        elif db_path is not None:
            self._cache = FirdsCacheManager(db_path)
        else:
            raise ValueError("Either db_path or cache must be provided.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_reportable(
        self,
        isin: str,
        trade_date: date,
        mic: Optional[str] = None,
    ) -> ReportabilityResult:
        """Determine whether an instrument is reportable at a given trade date.

        Args:
            isin: ISO 6166 instrument identifier.
            trade_date: The date on which the trade was executed.
            mic: Optional ISO 10383 Market Identifier Code.  When supplied the
                check is restricted to that specific trading venue.  When
                omitted the instrument is considered reportable if it is active
                on any venue in FIRDS.

        Returns:
            :class:`ReportabilityResult` containing the decision and reason.
        """
        isin = isin.strip().upper()
        if mic:
            mic = mic.strip().upper()

        if mic:
            return self._check_with_mic(isin, trade_date, mic)
        return self._check_any_venue(isin, trade_date)

    def bulk_check(
        self,
        checks: List[dict],
    ) -> List[ReportabilityResult]:
        """Run multiple reportability checks efficiently.

        Args:
            checks: List of dicts, each with keys ``isin`` (str),
                ``trade_date`` (:class:`~datetime.date`), and optionally
                ``mic`` (str).

        Returns:
            List of :class:`ReportabilityResult` in the same order as
            ``checks``.
        """
        return [
            self.is_reportable(
                isin=c["isin"],
                trade_date=c["trade_date"],
                mic=c.get("mic"),
            )
            for c in checks
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_with_mic(
        self, isin: str, trade_date: date, mic: str
    ) -> ReportabilityResult:
        """Check reportability for a specific (ISIN, MIC) pair.

        If the instrument is not active on the requested MIC, the checker
        falls back to scanning all venues.  If any other venue is active at
        the trade date, the result is returned as reportable with reason
        :attr:`~ReportabilityReason.ACTIVE_OTHER_VENUE` and the alternative
        MICs populated in ``matched_mics``.

        Args:
            isin: Instrument ISIN.
            trade_date: Trade execution date.
            mic: Trading venue MIC.

        Returns:
            :class:`ReportabilityResult`.
        """
        row = self._cache.get_by_isin_mic(isin, mic)

        if row is None:
            single_result = ReportabilityResult(
                is_reportable=False,
                reason=ReportabilityReason.NOT_IN_FIRDS,
                isin=isin,
                trade_date=trade_date,
                mic=mic,
            )
        else:
            single_result = self._evaluate_row(row, isin, trade_date, mic)

        if single_result.is_reportable:
            return single_result

        # Instrument is not reportable on the requested MIC – check whether
        # it is active on any other venue before returning a negative result.
        any_venue = self._check_any_venue(isin, trade_date)
        if any_venue.is_reportable:
            return ReportabilityResult(
                is_reportable=True,
                reason=ReportabilityReason.ACTIVE_OTHER_VENUE,
                isin=isin,
                trade_date=trade_date,
                mic=mic,
                matched_mics=any_venue.matched_mics,
            )

        return single_result

    def _check_any_venue(self, isin: str, trade_date: date) -> ReportabilityResult:
        """Check reportability across all venues for an ISIN.

        Returns reportable if *any* venue row is active at the trade date.

        Args:
            isin: Instrument ISIN.
            trade_date: Trade execution date.

        Returns:
            :class:`ReportabilityResult` with ``matched_mics`` populated.
        """
        rows = self._cache.get_by_isin(isin)

        if not rows:
            return ReportabilityResult(
                is_reportable=False,
                reason=ReportabilityReason.NOT_IN_FIRDS,
                isin=isin,
                trade_date=trade_date,
            )

        active_mics: List[str] = []
        last_reason = ReportabilityReason.NOT_IN_FIRDS

        for row in rows:
            candidate = self._evaluate_row(row, isin, trade_date, row["mic"])
            if candidate.is_reportable:
                active_mics.append(row["mic"])
            else:
                last_reason = candidate.reason

        if active_mics:
            return ReportabilityResult(
                is_reportable=True,
                reason=ReportabilityReason.ACTIVE,
                isin=isin,
                trade_date=trade_date,
                matched_mics=active_mics,
            )

        # Return the last non-active reason as an indicative reason
        # (there may be multiple rows with different reasons; this surfaces one)
        return ReportabilityResult(
            is_reportable=False,
            reason=last_reason,
            isin=isin,
            trade_date=trade_date,
        )

    @staticmethod
    def _evaluate_row(
        row: dict, isin: str, trade_date: date, mic: str
    ) -> ReportabilityResult:
        """Evaluate a single cache row against the reportability criteria.

        Args:
            row: Dict of instrument columns from the SQLite cache.
            isin: Instrument ISIN (for result object).
            trade_date: Trade execution date.
            mic: Trading venue MIC (for result object).

        Returns:
            :class:`ReportabilityResult`.
        """
        trade_str = trade_date.isoformat()

        # 1. Cancellation check (takes precedence over termination)
        if row.get("is_cancelled"):
            return ReportabilityResult(
                is_reportable=False,
                reason=ReportabilityReason.CANCELLED,
                isin=isin,
                trade_date=trade_date,
                mic=mic,
            )

        # 2. Admission date check
        admission = row.get("admission_date") or ""
        if admission and admission > trade_str:
            return ReportabilityResult(
                is_reportable=False,
                reason=ReportabilityReason.ADMISSION_AFTER_TRADE,
                isin=isin,
                trade_date=trade_date,
                mic=mic,
            )

        # 3. Termination check – terminated ON the trade date means the
        #    instrument is not available for trading on that day.
        termination = row.get("termination_date") or ""
        if termination and termination <= trade_str:
            return ReportabilityResult(
                is_reportable=False,
                reason=ReportabilityReason.TERMINATED_BEFORE_TRADE,
                isin=isin,
                trade_date=trade_date,
                mic=mic,
            )

        return ReportabilityResult(
            is_reportable=True,
            reason=ReportabilityReason.ACTIVE,
            isin=isin,
            trade_date=trade_date,
            mic=mic,
        )
