"""
Non-Zero Net Quantity Validator
=================================

Core validation logic for non-zero net quantity checking (Incident Code 7_6).

For each parent order reference, all associated child transaction quantities
are summed (after deduplication by child reference) and compared against the
parent order quantity. A mismatch is flagged as an error.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple

from ..models.net_quantity_record import NetQuantityRecord

logger = logging.getLogger(__name__)


class NetQuantityValidator:
    """
    Validates that the sum of child transaction quantities matches the parent
    order quantity for each parent reference group.

    Processing steps per group:
        1. Deduplicate by child_ref, keeping the first occurrence by row order.
        2. Sum child_qty across the deduplicated records.
        3. Compare the net sum against parent_qty (exact Decimal comparison).
        4. Set error = "N" (match) or "Y" (mismatch) on every record in the
           original group (including duplicates, so all rows for that parent
           carry the same outcome).
        5. Populate net_qty and difference on all records.

    Usage:
        validator = NetQuantityValidator(verbose=True)
        stats = validator.validate_all(records)
    """

    def __init__(self, verbose: bool = False):
        """
        Initialise the validator.

        Args:
            verbose: Enable verbose debug logging (default False)
        """
        self.verbose = verbose

        if self.verbose:
            logger.info("NetQuantityValidator initialised")

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def deduplicate_group(
        self,
        records: List[NetQuantityRecord],
    ) -> Tuple[List[NetQuantityRecord], Dict[str, int]]:
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
        deduplicated: List[NetQuantityRecord] = []
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

    def validate_group(self, records: List[NetQuantityRecord]) -> int:
        """Validate all records belonging to a single bulk_ref group.

        Steps:
            1. Sum one parent_qty per unique parent_ref to produce bulk_qty.
            2. Deduplicate by child_ref (first occurrence wins).
            3. Log a warning for each removed duplicate.
            4. Sum child_qty across the deduplicated records to produce net_qty.
            5. Calculate difference (net_qty - bulk_qty) and error flag.
            6. Apply bulk_qty, net_qty, difference, and error to *all* records
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

        # Step 1 — sum one parent_qty per unique parent_ref within the bulk group.
        # Handles contracts split across multiple sub-parent references, e.g.
        # "44625CPNJMN1G01", "44625CPNJMN1G02", "44625CPNJMN1G03" each carrying
        # their own portion of the total contract quantity.
        seen_parent_refs: set = set()
        bulk_qty = Decimal('0')
        for record in records:
            if record.parent_ref not in seen_parent_refs:
                seen_parent_refs.add(record.parent_ref)
                bulk_qty += record.parent_qty

        # Step 2 & 3 — deduplicate and warn
        deduplicated, duplicates = self.deduplicate_group(records)
        for child_ref, count in duplicates.items():
            logger.warning(
                f"Removed {count} duplicate(s) of child_ref '{child_ref}' "
                f"under bulk_ref '{bulk_ref}'"
            )

        # Step 4 — sum child quantities across unique records
        net_qty = sum(
            (r.child_qty for r in deduplicated),
            start=Decimal('0'),
        )

        # Step 5 — compare net child quantity against total bulk quantity
        difference = net_qty - bulk_qty
        error = "N" if difference == Decimal('0') else "Y"

        if self.verbose:
            logger.debug(
                f"bulk_ref='{bulk_ref}' | "
                f"parent_refs={len(seen_parent_refs)} | "
                f"children={len(deduplicated)} (deduped from {len(records)}) | "
                f"bulk_qty={bulk_qty} | net_qty={net_qty} | "
                f"difference={difference} | error={error}"
            )

        # Step 6 — write results back to all original records
        for record in records:
            record.bulk_qty = bulk_qty
            record.net_qty = net_qty
            record.difference = difference
            record.error = error

        return sum(duplicates.values())

    # ------------------------------------------------------------------
    # Batch validation
    # ------------------------------------------------------------------

    def validate_all(self, records: List[NetQuantityRecord]) -> Dict[str, int]:
        """
        Validate a full batch of records, grouping by bulk_ref.

        Records are grouped by the first 10 characters of parent_ref (bulk_ref)
        so that sub-parent references such as "44625CPNJMN1G01", "44625CPNJMN1G02"
        and "44625CPNJMN1G03" are all treated as part of the same contract.

        Args:
            records: All NetQuantityRecord objects from the CSV extract

        Returns:
            Dictionary of processing statistics:
                - total_records: Total input records
                - parents_processed: Number of distinct bulk_ref groups
                - duplicates_removed: Total duplicate child rows removed
                - error_groups: Number of bulk groups with a mismatch
                - match_groups: Number of bulk groups with a match

        Example:
            >>> stats = validator.validate_all(records)
            >>> print(f"{stats['error_groups']} group(s) with quantity mismatch")
        """
        # Group records by bulk_ref, preserving original row order
        groups: Dict[str, List[NetQuantityRecord]] = defaultdict(list)
        for record in records:
            groups[record.bulk_ref].append(record)

        stats: Dict[str, int] = {
            'total_records': len(records),
            'parents_processed': 0,
            'duplicates_removed': 0,
            'error_groups': 0,
            'match_groups': 0,
        }

        for bulk_ref, group_records in groups.items():
            dupes_removed = self.validate_group(group_records)
            stats['parents_processed'] += 1
            stats['duplicates_removed'] += dupes_removed

            # All records in the group have the same error flag after validation
            if group_records[0].error == "Y":
                stats['error_groups'] += 1
            else:
                stats['match_groups'] += 1

        if self.verbose or logger.isEnabledFor(logging.INFO):
            logger.info(
                f"Validation complete: {stats['parents_processed']} parent(s) | "
                f"{stats['match_groups']} match | {stats['error_groups']} mismatch | "
                f"{stats['duplicates_removed']} duplicate(s) removed"
            )

        return stats
