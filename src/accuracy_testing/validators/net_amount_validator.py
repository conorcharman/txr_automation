"""
Non-Zero Net Amount Validator
==============================

Core validation logic for non-zero net amount checking (Incident Code 7_42).

For each parent order reference, all associated child transaction net amounts
are summed (after deduplication by child reference) and compared against the
parent order net amount. The effective tolerance per group is
max(tolerance, tolerance_per_record × record_count), so large bulks
automatically receive a wider allowance to account for accumulated decimal
rounding across many records.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple

from ..models.net_amount_record import NetAmountRecord

logger = logging.getLogger(__name__)


class NetAmountValidator:
    """
    Validates that the sum of child transaction net amounts matches the parent
    order net amount for each parent reference group.

    Processing steps per group:
        1. Read parent_netamt from the first record as bulk_netamt. The SQL
           fetches parent_netamt via a truncated join key (SUBSTR of parent_ref,
           12 chars), so every sub-parent in the bulk group carries the same
           bulk-level total. Summing per unique parent_ref would double-count.
        2. Deduplicate by child_ref, keeping the first occurrence by row order.
        3. Sum child_netamt across the deduplicated records.
        4. Compute effective_tolerance = max(tolerance, tolerance_per_record ×
           deduplicated_count). Differences with abs(difference) <=
           effective_tolerance are treated as matches (error = "N"); larger
           differences are flagged (error = "Y").
        5. Set error = "N" (match) or "Y" (mismatch) on every record in the
           original group (including duplicates, so all rows for that parent
           carry the same outcome).
        6. Populate net_amt and difference on all records.

    Usage:
        validator = NetAmountValidator(verbose=True)
        stats = validator.validate_all(records)
    """

    def __init__(
        self,
        verbose: bool = False,
        tolerance: Decimal = Decimal("1.0"),
        tolerance_per_record: Decimal = Decimal("0.005"),
    ):
        """
        Initialise the validator.

        Args:
            verbose: Enable verbose debug logging (default False)
            tolerance: Fixed floor for the acceptable absolute difference.
                Acts as the minimum effective tolerance regardless of group size.
                Defaults to Decimal('1.0').
            tolerance_per_record: Additional tolerance contributed by each
                deduplicated record, reflecting the maximum rounding error a
                single net amount value can introduce (±0.005 for 2 d.p. values).
                The effective tolerance for a group is:
                    max(tolerance, tolerance_per_record × record_count)
                Defaults to Decimal('0.005').
        """
        self.verbose = verbose
        self.tolerance = tolerance
        self.tolerance_per_record = tolerance_per_record

        if self.verbose:
            logger.info(
                f"NetAmountValidator initialised | "
                f"tolerance=±{self.tolerance} | "
                f"tolerance_per_record=±{self.tolerance_per_record}"
            )

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def deduplicate_group(
        self,
        records: List[NetAmountRecord],
    ) -> Tuple[List[NetAmountRecord], Dict[str, int]]:
        """
        Remove duplicate child_ref entries within a parent group.

        The first occurrence of each child_ref (by list order, which reflects
        original CSV row order) is retained. All subsequent occurrences of the
        same child_ref are collected as duplicates.

        Args:
            records: All records sharing a common parent_ref

        Returns:
            Tuple of:
                - deduplicated: List of unique records (first occurrence kept)
                - duplicates: Dict mapping child_ref → number of extra copies removed

        Example:
            >>> deduped, dupes = validator.deduplicate_group(records)
            >>> # dupes == {'ABC123': 2} means 'ABC123' appeared 3 times, 2 removed
        """
        seen: set = set()
        deduplicated: List[NetAmountRecord] = []
        duplicates: Dict[str, int] = defaultdict(int)

        for record in records:
            if record.child_ref not in seen:
                seen.add(record.child_ref)
                deduplicated.append(record)
            else:
                duplicates[record.child_ref] += 1

        return deduplicated, dict(duplicates)

    # ------------------------------------------------------------------
    # Group validation
    # ------------------------------------------------------------------

    def validate_group(self, records: List[NetAmountRecord]) -> int:
        """Validate all records belonging to a single bulk_ref group.

        Steps:
            1. Take parent_netamt from the first record as bulk_netamt. All
               records in the group carry the same bulk-level total because the
               SQL joins on SUBSTR(parent_ref, 1, 12), stripping the G-suffix.
               Unlike 7_6 (Net Quantity), sub-parents do NOT carry individual
               portions — summing would double-count.
            2. Deduplicate by child_ref (first occurrence wins).
            3. Log a warning for each removed duplicate.
            4. Sum child_netamt across the deduplicated records to produce net_amt.
            5. Compute effective_tolerance = max(self.tolerance,
               self.tolerance_per_record × len(deduplicated)). Calculate
               difference (net_amt - bulk_netamt). If abs(difference) <=
               effective_tolerance the group is a match (error "N"), otherwise
               an error (error "Y").
            6. Apply bulk_netamt, net_amt, difference, and error to *all* records
               in the original group (including any duplicate rows).

        Args:
            records: All records for one bulk_ref (in CSV row order)

        Returns:
            Number of duplicate records removed from this group

        Raises:
            ValueError: If the records list is empty
        """
        if not records:
            raise ValueError("validate_group received an empty record list")

        bulk_ref = records[0].bulk_ref

        # Step 1 — read bulk_netamt directly from the first record.
        # The SQL for 7_42 fetches parent_netamt via SUBSTR(parent_ref, 1, 12),
        # stripping the G-suffix. Every sub-parent in the bulk group (1G01, 1G02,
        # …) therefore carries the same bulk-level total — NOT an individual
        # portion. Summing across unique parent_refs would multiply the value by
        # the number of sub-parents (double-counting). This contrasts with 7_6
        # (Net Quantity), where the SQL joins on the full suffix so each
        # sub-parent genuinely carries its own portion.
        bulk_netamt = records[0].parent_netamt

        # Step 2 & 3 — deduplicate and warn
        deduplicated, duplicates = self.deduplicate_group(records)
        for child_ref, count in duplicates.items():
            logger.warning(
                f"Removed {count} duplicate(s) of child_ref '{child_ref}' "
                f"under bulk_ref '{bulk_ref}'"
            )

        # Step 4 — sum child net amounts across unique records
        net_amt = sum(
            (r.child_netamt for r in deduplicated),
            start=Decimal("0"),
        )

        # Step 5 — compute effective tolerance and compare.
        # effective_tolerance is the larger of the fixed floor (self.tolerance)
        # and a per-record scaling (self.tolerance_per_record × record count).
        # This means large bulks automatically receive a wider allowance to
        # account for accumulated decimal rounding across many records.
        effective_tolerance = max(
            self.tolerance,
            self.tolerance_per_record * len(deduplicated),
        )
        difference = net_amt - bulk_netamt
        error = "N" if abs(difference) <= effective_tolerance else "Y"

        if self.verbose:
            logger.debug(
                f"bulk_ref='{bulk_ref}' | "
                f"children={len(deduplicated)} (deduped from {len(records)}) | "
                f"bulk_netamt={bulk_netamt} | net_amt={net_amt} | "
                f"difference={difference} | "
                f"effective_tolerance=±{effective_tolerance} | error={error}"
            )

        # Step 6 — write results back to all original records
        for record in records:
            record.bulk_netamt = bulk_netamt
            record.net_amt = net_amt
            record.difference = difference
            record.error = error

        return sum(duplicates.values())

    # ------------------------------------------------------------------
    # Batch validation
    # ------------------------------------------------------------------

    def validate_all(self, records: List[NetAmountRecord]) -> Dict[str, int]:
        """
        Validate a full batch of records, grouping by bulk_ref.

        Records are grouped by the first 11 characters of parent_ref (bulk_ref)
        so that sub-parent references such as "44625CPNJMN1G01", "44625CPNJMN1G02"
        and "44625CPNJMN1G03" are all treated as part of the same contract.

        Args:
            records: All NetAmountRecord objects from the CSV extract

        Returns:
            Dictionary of processing statistics:
                - total_records: Total input records
                - parents_processed: Number of distinct bulk_ref groups
                - duplicates_removed: Total duplicate child rows removed
                - error_groups: Number of bulk groups with a mismatch
                - match_groups: Number of bulk groups with a match

        Example:
            >>> stats = validator.validate_all(records)
            >>> print(f"{stats['error_groups']} group(s) with net amount mismatch")
        """
        # Group records by bulk_ref, preserving original row order
        groups: Dict[str, List[NetAmountRecord]] = defaultdict(list)
        for record in records:
            groups[record.bulk_ref].append(record)

        stats: Dict[str, int] = {
            "total_records": len(records),
            "parents_processed": 0,
            "duplicates_removed": 0,
            "error_groups": 0,
            "match_groups": 0,
        }

        for bulk_ref, group_records in groups.items():
            dupes_removed = self.validate_group(group_records)
            stats["parents_processed"] += 1
            stats["duplicates_removed"] += dupes_removed

            # All records in the group have the same error flag after validation
            if group_records[0].error == "Y":
                stats["error_groups"] += 1
            else:
                stats["match_groups"] += 1

        if self.verbose or logger.isEnabledFor(logging.INFO):
            logger.info(
                f"Validation complete: {stats['parents_processed']} parent(s) | "
                f"{stats['match_groups']} match | {stats['error_groups']} mismatch | "
                f"{stats['duplicates_removed']} duplicate(s) removed"
            )

        return stats
