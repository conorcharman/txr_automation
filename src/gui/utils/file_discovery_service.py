#!/usr/bin/env python3
"""
FileDiscoveryService
====================

Pure-Python (no Qt, no API) file discovery utilities for the GUI.

Resolves smart directory paths from a base directory + fiscal
period, discovers per-incident files using the project naming
conventions, and surfaces file candidates with metadata for the
auto-detect picker.

Naming conventions (from config/templates/):
    Extract  : ``{code}_{fy}_{q}_extract.csv``   e.g. ``7_37_FY26_Q1_extract.csv``
    Template : ``{fy} {q} {code}.csv``            e.g. ``FY26 Q1 7_37.csv``
    Output   : ``validated_{fy}_{q}_{code}.csv``  e.g. ``validated_FY26_Q1_7_37.csv``

Usage:
    svc = FileDiscoveryService()
    paths = svc.resolve_smart_paths("/data/txr", "FY26", "Q1")
    candidates = svc.find_candidates(paths.extracts, "7_37_*.csv")
    files = svc.discover_incident_files(paths, "FY26", "Q1", ["7_37", "7_39"])
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from core.utils.file_discovery import FileDiscovery


# ---------------------------------------------------------------------------
# Data classes and enums
# ---------------------------------------------------------------------------


class PathStatus(Enum):
    """Existence status of a resolved directory."""

    FOUND = "found"
    MISSING = "missing"
    EMPTY = "empty"


@dataclass
class FileCandidate:
    """A file discovered by pattern matching with associated metadata."""

    path: str
    filename: str
    mtime: float          # Unix timestamp
    size_bytes: int
    score: int = 0        # Higher is a better/more-recent match

    @property
    def mtime_label(self) -> str:
        """Human-readable modification timestamp."""
        from datetime import datetime

        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")

    @property
    def size_label(self) -> str:
        """Human-readable file size."""
        kb = self.size_bytes / 1024
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024:.1f} MB"


@dataclass
class IncidentFiles:
    """Resolved file paths for a single incident code."""

    incident_code: str
    input_file: str = ""      # extract CSV
    template_file: str = ""   # template CSV
    output_file: str = ""     # output CSV
    input_found: bool = False
    template_found: bool = False


@dataclass
class SmartPaths:
    """Directory paths derived from base_dir + fiscal period."""

    base_dir: str
    fiscal_year: str
    quarter: str
    extracts: str = ""
    templates: str = ""
    output: str = ""
    logs: str = ""
    kaizen: str = ""

    # Status per stage (populated by FileDiscoveryService.check_paths)
    statuses: Dict[str, PathStatus] = field(default_factory=dict)
    file_counts: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FileDiscoveryService:
    """Discovers files on the local filesystem using project conventions.

    All methods are stateless; the class is provided for convenience
    and testability.  A module-level singleton ``file_discovery_service``
    is available for GUI use.
    """

    # Subdirectory names under base / FY / Q
    _STAGE_DIRS = ("extracts", "templates", "output", "logs", "kaizen")

    def resolve_smart_paths(
        self,
        base_dir: str,
        fiscal_year: str,
        quarter: str,
        populate_status: bool = True,
    ) -> SmartPaths:
        """Derive stage directories and check their existence.

        Args:
            base_dir: Root directory, e.g. ``C:/data/txr``.
            fiscal_year: Fiscal year string, e.g. ``"FY26"``.
            quarter: Quarter string, e.g. ``"Q1"``.
            populate_status: When ``True``, stat each directory
                and populate ``SmartPaths.statuses`` and
                ``SmartPaths.file_counts``.

        Returns:
            :class:`SmartPaths` with resolved paths.
        """
        period_root = os.path.join(base_dir, fiscal_year, quarter)
        paths = SmartPaths(
            base_dir=base_dir,
            fiscal_year=fiscal_year,
            quarter=quarter,
            extracts=os.path.join(period_root, "extracts"),
            templates=os.path.join(period_root, "templates"),
            output=os.path.join(period_root, "output"),
            logs=os.path.join(period_root, "logs"),
            kaizen=os.path.join(period_root, "kaizen"),
        )
        if populate_status:
            for stage in self._STAGE_DIRS:
                stage_path = getattr(paths, stage)
                paths.statuses[stage] = self.check_path(stage_path)
                paths.file_counts[stage] = self._count_csv_files(stage_path)
        return paths

    def check_path(self, path: str) -> PathStatus:
        """Return the :class:`PathStatus` of *path*.

        Args:
            path: Filesystem path to check.

        Returns:
            ``FOUND`` if directory exists and contains files,
            ``EMPTY`` if directory exists but has no files,
            ``MISSING`` if directory does not exist.
        """
        if not os.path.isdir(path):
            return PathStatus.MISSING
        if not any(os.scandir(path)):
            return PathStatus.EMPTY
        return PathStatus.FOUND

    def find_candidates(
        self,
        directory: str,
        pattern: str,
    ) -> List[FileCandidate]:
        """Return all files in *directory* matching *pattern*, newest first.

        Args:
            directory: Directory to search.
            pattern: Glob pattern, e.g. ``"7_37_*.csv"``.

        Returns:
            List of :class:`FileCandidate` sorted by mtime descending.
        """
        if not os.path.isdir(directory):
            return []
        all_paths = FileDiscovery.find_all_files(directory, pattern)
        candidates: List[FileCandidate] = []
        for p in all_paths:
            try:
                stat = os.stat(p)
                candidates.append(
                    FileCandidate(
                        path=p,
                        filename=os.path.basename(p),
                        mtime=stat.st_mtime,
                        size_bytes=stat.st_size,
                    )
                )
            except OSError:
                continue
        # Sort newest first; assign scores (0 = newest)
        candidates.sort(key=lambda c: c.mtime, reverse=True)
        for idx, c in enumerate(candidates):
            c.score = len(candidates) - idx
        return candidates

    def discover_incident_files(
        self,
        paths: SmartPaths,
        fiscal_year: str,
        quarter: str,
        incident_codes: List[str],
    ) -> Dict[str, IncidentFiles]:
        """Discover extract, template, and output files for each incident.

        Uses the project naming conventions:
        - Extract:  ``{code}_{fy}_{q}_extract.csv``
        - Template: ``{fy} {q} {code}.csv``
        - Output:   ``validated_{fy}_{q}_{code}.csv``

        Falls back to a glob pattern if the exact name is not found.

        Args:
            paths: Resolved :class:`SmartPaths` (provides directories).
            fiscal_year: e.g. ``"FY26"``.
            quarter: e.g. ``"Q1"``.
            incident_codes: List of incident codes, e.g. ``["7_35", "7_37"]``.

        Returns:
            Mapping of incident code → :class:`IncidentFiles`.
        """
        result: Dict[str, IncidentFiles] = {}
        for code in incident_codes:
            inc_files = IncidentFiles(incident_code=code)

            # --- Extract ---
            extract_name = f"{code}_{fiscal_year}_{quarter}_extract.csv"
            extract_path = os.path.join(paths.extracts, extract_name)
            if os.path.isfile(extract_path):
                inc_files.input_file = extract_path
                inc_files.input_found = True
            else:
                # Glob fallback: code_*.csv
                candidates = self.find_candidates(paths.extracts, f"{code}_*.csv")
                if candidates:
                    inc_files.input_file = candidates[0].path
                    inc_files.input_found = True
                else:
                    inc_files.input_file = extract_path  # suggest canonical name

            # --- Template ---
            template_name = f"{fiscal_year} {quarter} {code}.csv"
            template_path = os.path.join(paths.templates, template_name)
            if os.path.isfile(template_path):
                inc_files.template_file = template_path
                inc_files.template_found = True
            else:
                candidates = self.find_candidates(
                    paths.templates, f"*{code}*.csv"
                )
                if candidates:
                    inc_files.template_file = candidates[0].path
                    inc_files.template_found = True
                else:
                    inc_files.template_file = template_path  # suggest canonical

            # --- Output ---
            output_name = f"validated_{fiscal_year}_{quarter}_{code}.csv"
            inc_files.output_file = os.path.join(paths.output, output_name)

            result[code] = inc_files
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _count_csv_files(self, directory: str) -> int:
        """Count CSV files in *directory* (non-recursive)."""
        if not os.path.isdir(directory):
            return 0
        try:
            return sum(
                1
                for entry in os.scandir(directory)
                if entry.is_file() and entry.name.lower().endswith(".csv")
            )
        except OSError:
            return 0

    def make_extract_auto_detect(
        self,
        incident_code: str,
        paths: SmartPaths,
    ):
        """Return a zero-argument callable for FilePickerWidget auto_detect_fn.

        The callable, when invoked, scans the extracts directory for
        files matching the incident code and returns a list of
        :class:`FileCandidate`.

        Args:
            incident_code: e.g. ``"7_37"``.
            paths: Resolved smart paths (extracts dir is used).

        Returns:
            ``Callable[[], List[FileCandidate]]``
        """
        def _detect() -> List[FileCandidate]:
            return self.find_candidates(paths.extracts, f"{incident_code}_*.csv")

        return _detect


# Module-level singleton
file_discovery_service = FileDiscoveryService()
