#!/usr/bin/env python3
"""
Phase 3 Final Lookup — "Client not found" Diagnostic
=====================================================

Reads the Phase 3 Final Lookup output CSV and the two replay input XLSX files,
then for every UnaVista row annotated "Client not found" it checks whether the
buyer or seller identity appears anywhere in the replay files.

Reports three categories per missing row:
  FOUND_BY_ID   — the ID appears in the replay file (matching bug)
  FOUND_BY_NAME — the name+DOB appears but not the ID (matching bug)
  NOT_IN_REPLAY — genuinely absent from the replay sample (expected)

Usage (inside the Docker container or with txr_automation conda env):
    python scripts/diagnose_p3_client_not_found.py \\
        --output  data/FY26/Q1/replay/phase_3/final_lookup/output/output_UnaVista_*.csv \\
        --ids     data/FY26/Q1/replay/phase_3/feedback/output/Replay_*IDs*.xlsx \\
        --names   data/FY26/Q1/replay/phase_3/feedback/output/Replay_*Names*.xlsx
"""

import argparse
import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# openpyxl helper
# ---------------------------------------------------------------------------

try:
    import openpyxl
    _OPENPYXL = True
except ImportError:
    _OPENPYXL = False


def _read_rows(path: str) -> List[List[str]]:
    if str(path).lower().endswith(".xlsx"):
        if not _OPENPYXL:
            raise ImportError("openpyxl is required: pip install openpyxl")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = [
            [str(c) if c is not None else "" for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
        wb.close()
        return rows
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.reader(f))


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def _norm(v: str) -> str:
    return v.strip().lower()


def build_replay_indexes(ids_path: str, names_path: str):
    """Build dicts: id_set, name_set from both replay files."""
    id_set = set()       # normalised client IDs
    name_set = set()     # (norm_first, norm_last, norm_dob)
    details = {}         # norm_id -> {first, last, dob, row_num, file}

    # --- IDs file: col 0 = "FN~SN~DOB", col 1 = "IDType: IDValue\n..." ---
    ids_rows = _read_rows(ids_path)
    for i, row in enumerate(ids_rows[1:], start=2):
        if len(row) < 2:
            continue
        name_dob = row[0].strip().split("~")
        fn = _norm(name_dob[0]) if len(name_dob) > 0 else ""
        sn = _norm(name_dob[1]) if len(name_dob) > 1 else ""
        dob = _norm(name_dob[2]) if len(name_dob) > 2 else ""
        if fn and sn:
            name_set.add((fn, sn, dob))
            name_set.add((fn, sn, ""))  # DOB-agnostic fallback
        # ID field may contain multiple entries separated by newlines
        for entry in row[1].replace(";", "\n").split("\n"):
            if ":" in entry:
                cid = _norm(entry.split(":", 1)[1])
            else:
                cid = _norm(entry)
            if cid:
                id_set.add(cid)
                details[cid] = {"first": fn, "last": sn, "dob": dob,
                                "row": i, "file": "IDs"}

    # --- Names file: col 0 = "ID[~...]", col 1 = "FN:SN:DOB" ---
    names_rows = _read_rows(names_path)
    for i, row in enumerate(names_rows[1:], start=2):
        if len(row) < 2:
            continue
        cid = _norm(row[0].split("~")[0]) if row[0] else ""
        if cid:
            id_set.add(cid)
        name_dob = row[1].strip().split(":")
        fn = _norm(name_dob[0]) if len(name_dob) > 0 else ""
        sn = _norm(name_dob[1]) if len(name_dob) > 1 else ""
        dob = _norm(name_dob[2]) if len(name_dob) > 2 else ""
        if fn and sn:
            name_set.add((fn, sn, dob))
            name_set.add((fn, sn, ""))
        if cid and cid not in details:
            details[cid] = {"first": fn, "last": sn, "dob": dob,
                            "row": i, "file": "Names"}

    return id_set, name_set, details


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyse(output_path: str, ids_path: str, names_path: str) -> None:
    print(f"\nReading replay indexes...")
    id_set, name_set, details = build_replay_indexes(ids_path, names_path)
    print(f"  IDs file:   {ids_path}")
    print(f"  Names file: {names_path}")
    print(f"  Unique IDs indexed:   {len(id_set)}")
    print(f"  Unique names indexed: {len(name_set)}")

    print(f"\nReading output file: {output_path}")
    output_rows = _read_rows(output_path)
    if not output_rows:
        print("ERROR: output file is empty")
        return

    hdr = output_rows[0]
    # Locate columns by name (robust to column order changes)
    def col(name: str) -> Optional[int]:
        try:
            return hdr.index(name)
        except ValueError:
            return None

    c_txn    = col("Transaction Reference Number") or 1
    c_result = col("test_result") or 2
    c_bid    = col("Buyer ID") or 9
    c_bfn    = col("Buyer First Name") or 11
    c_bsn    = col("Buyer Surname") or 12
    c_bdob   = col("Buyer DOB") or 13
    c_sid    = col("Seller ID") or 22
    c_sfn    = col("Seller First Name") or 25
    c_ssn    = col("Seller Surname") or 26
    c_sdob   = col("Seller DOB") or 27

    not_found_rows = [
        r for r in output_rows[1:]
        if len(r) > c_result and r[c_result].strip().lower() == "client not found"
    ]

    print(f"\nTotal UnaVista rows:         {len(output_rows) - 1}")
    print(f"'Client not found' rows:     {len(not_found_rows)}")

    found_by_id   = []
    found_by_name = []
    not_in_replay = []

    for row in not_found_rows:
        txn  = row[c_txn] if len(row) > c_txn else ""
        bid  = _norm(row[c_bid])  if len(row) > c_bid  else ""
        bfn  = _norm(row[c_bfn])  if len(row) > c_bfn  else ""
        bsn  = _norm(row[c_bsn])  if len(row) > c_bsn  else ""
        bdob = _norm(row[c_bdob]) if len(row) > c_bdob  else ""
        sid  = _norm(row[c_sid])  if len(row) > c_sid   else ""
        sfn  = _norm(row[c_sfn])  if len(row) > c_sfn   else ""
        ssn  = _norm(row[c_ssn])  if len(row) > c_ssn   else ""
        sdob = _norm(row[c_sdob]) if len(row) > c_sdob  else ""

        matched_by_id   = None
        matched_by_name = None

        # Check buyer
        if bid and bid in id_set:
            matched_by_id = f"buyer ID={bid}"
        elif bfn and bsn and (bfn, bsn, bdob) in name_set:
            matched_by_name = f"buyer name={bfn} {bsn} dob={bdob}"
        elif bfn and bsn and (bfn, bsn, "") in name_set:
            matched_by_name = f"buyer name={bfn} {bsn} (no DOB match)"

        # Check seller (only if buyer didn't match)
        if not matched_by_id and not matched_by_name:
            if sid and sid in id_set:
                matched_by_id = f"seller ID={sid}"
            elif sfn and ssn and (sfn, ssn, sdob) in name_set:
                matched_by_name = f"seller name={sfn} {ssn} dob={sdob}"
            elif sfn and ssn and (sfn, ssn, "") in name_set:
                matched_by_name = f"seller name={sfn} {ssn} (no DOB match)"

        entry = {
            "txn": txn, "buyer_id": bid, "seller_id": sid,
            "buyer_name": f"{bfn} {bsn}", "seller_name": f"{sfn} {ssn}",
            "match": matched_by_id or matched_by_name or "",
        }

        if matched_by_id:
            found_by_id.append(entry)
        elif matched_by_name:
            found_by_name.append(entry)
        else:
            not_in_replay.append(entry)

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  FOUND_BY_ID   (matching bug — ID present in replay):  {len(found_by_id)}")
    print(f"  FOUND_BY_NAME (matching bug — name present in replay): {len(found_by_name)}")
    print(f"  NOT_IN_REPLAY (legitimately absent):                   {len(not_in_replay)}")

    if found_by_id:
        print("\n--- FOUND_BY_ID (should have matched) ---")
        for e in found_by_id[:30]:
            print(f"  Txn={e['txn']}  {e['match']}")
        if len(found_by_id) > 30:
            print(f"  ... and {len(found_by_id) - 30} more")

    if found_by_name:
        print("\n--- FOUND_BY_NAME (should have matched) ---")
        for e in found_by_name[:30]:
            print(f"  Txn={e['txn']}  {e['match']}")
        if len(found_by_name) > 30:
            print(f"  ... and {len(found_by_name) - 30} more")

    if not_in_replay:
        print("\n--- NOT_IN_REPLAY sample (first 20) ---")
        for e in not_in_replay[:20]:
            print(f"  Txn={e['txn']}  buyer={e['buyer_id'] or e['buyer_name']}  "
                  f"seller={e['seller_id'] or e['seller_name']}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _glob_first(pattern: str, label: str) -> str:
    matches = sorted(glob.glob(pattern))
    if not matches:
        print(f"ERROR: no file matching '{pattern}' for {label}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"WARNING: multiple files matching '{pattern}' — using most recent")
        matches = sorted(matches, key=lambda p: Path(p).stat().st_mtime)
    return matches[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True,
                        help="Glob pattern or path to the output_UnaVista_*.csv file")
    parser.add_argument("--ids", required=True,
                        help="Glob pattern or path to Replay_*IDs*.xlsx")
    parser.add_argument("--names", required=True,
                        help="Glob pattern or path to Replay_*Names*.xlsx")
    args = parser.parse_args()

    output_path = _glob_first(args.output, "--output")
    ids_path    = _glob_first(args.ids,    "--ids")
    names_path  = _glob_first(args.names,  "--names")

    analyse(output_path, ids_path, names_path)


if __name__ == "__main__":
    main()
