#!/usr/bin/env python3
"""
AutoFileNamer
=============

Generates deterministic, human-readable output file paths for scheduled
pipeline runs.

All methods are static and have no Qt or GUI dependencies, making this
module safe to import in non-Qt contexts (e.g. unit tests, CLI tools).

Naming pattern::

    {output_dir}/{type_slug}_{fiscal_year}_{quarter}_{YYYYMMDD_HHMM}.csv

Example::

    data/output/buyer_id_FY26_Q2_20260401_0900.csv

Version 1.0 Changes:
- Initial implementation for Phase 1 scheduler foundation
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import TestingPeriod, ValidationType


class AutoFileNamer:
    """Generates deterministic output file paths for scheduled pipeline runs.

    All methods are static; instantiation is optional.

    Example:
        >>> path = AutoFileNamer.generate_output_path(
        ...     ValidationType.BUYER_ID,
        ...     TestingPeriod("FY26", "Q2"),
        ...     "data/output",
        ... )
        >>> path.name
        'buyer_id_FY26_Q2_20260401_0900.csv'
    """

    @staticmethod
    def generate_output_path(
        validation_type: ValidationType,
        testing_period: TestingPeriod,
        output_dir: str | Path,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """Generate a deterministic output CSV path.

        The filename follows the pattern::

            {type_slug}_{fiscal_year}_{quarter}_{YYYYMMDD_HHMM}.csv

        Args:
            validation_type: The validation script type.
            testing_period: Fiscal year and quarter for the run.
            output_dir: Directory where the output file should be written.
            timestamp: Datetime to embed in the filename.  Defaults to
                :func:`datetime.now` if ``None``.

        Returns:
            Absolute-or-relative :class:`Path` for the output CSV.
        """
        ts = timestamp or datetime.now()
        slug = AutoFileNamer._type_slug(validation_type)
        filename = (
            f"{slug}_{testing_period.fiscal_year}_{testing_period.quarter}"
            f"_{ts.strftime('%Y%m%d_%H%M')}.csv"
        )
        return Path(output_dir) / filename

    @staticmethod
    def generate_log_path(
        validation_type: ValidationType,
        testing_period: TestingPeriod,
        log_dir: str | Path,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """Generate a matching log file path (```.log``` extension).

        Uses the same stem as :meth:`generate_output_path` with a ``.log``
        extension instead of ``.csv``.

        Args:
            validation_type: The validation script type.
            testing_period: Fiscal year and quarter for the run.
            log_dir: Directory where the log file should be written.
            timestamp: Datetime to embed in the filename.  Defaults to
                :func:`datetime.now` if ``None``.

        Returns:
            :class:`Path` for the log file.
        """
        ts = timestamp or datetime.now()
        slug = AutoFileNamer._type_slug(validation_type)
        filename = (
            f"{slug}_{testing_period.fiscal_year}_{testing_period.quarter}"
            f"_{ts.strftime('%Y%m%d_%H%M')}.log"
        )
        return Path(log_dir) / filename

    @staticmethod
    def generate_extract_path(
        validation_type: ValidationType,
        testing_period: TestingPeriod,
        output_dir: str | Path,
        timestamp: Optional[datetime] = None,
    ) -> Path:
        """Generate an SQL extract output path (suffix: ``_extract.csv``).

        Args:
            validation_type: The validation script type.
            testing_period: Fiscal year and quarter for the run.
            output_dir: Directory where the extract file should be written.
            timestamp: Datetime to embed in the filename.  Defaults to
                :func:`datetime.now` if ``None``.

        Returns:
            :class:`Path` for the extract CSV file.
        """
        ts = timestamp or datetime.now()
        slug = AutoFileNamer._type_slug(validation_type)
        filename = (
            f"{slug}_{testing_period.fiscal_year}_{testing_period.quarter}"
            f"_{ts.strftime('%Y%m%d_%H%M')}_extract.csv"
        )
        return Path(output_dir) / filename

    @staticmethod
    def _type_slug(validation_type: ValidationType) -> str:
        """Convert a :class:`ValidationType` to a filename-safe slug.

        Replaces hyphens with underscores so the value is safe as a filename
        component on all platforms.

        Args:
            validation_type: Validation type to convert.

        Returns:
            Lowercase, underscore-separated slug string
            (e.g. ``BUYER_ID`` → ``"buyer_id"``).

        Example:
            >>> AutoFileNamer._type_slug(ValidationType.INCONSISTENT_BUYER_ID)
            'inconsistent_buyer_id'
        """
        return validation_type.name.lower()
