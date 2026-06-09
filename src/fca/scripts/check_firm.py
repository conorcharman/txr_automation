#!/usr/bin/env python3
"""
FCA Register Firm Check CLI
============================

Look up firm authorisation status and regulated activity permissions
against the FCA Financial Services Register API.

Usage:
    # Single FRN lookup
    fca-check --frn 122702

    # Name search (returns all matching firms)
    fca-check --name "Barclays Bank"

    # Batch: CSV file with 'frn' and/or 'firm_name' column
    fca-check --input counterparties.csv

    # Batch: explicit output file
    fca-check --input counterparties.csv --output results.csv

    # Drive entirely from a YAML config file
    fca-check --config config/local/fca_config.yaml

CSV Column Detection
--------------------
The script auto-detects FRN and firm name columns using common names:

    FRN columns:       frn, FRN, firm_reference_number, reference_number
    Name columns:      firm_name, organisation_name, name, company_name,
                       counterparty_name

If both are present, FRN takes precedence (avoids an extra search request).

Output Columns Added
--------------------
    fca_frn           — FRN used or resolved
    fca_status        — Authorisation status from the Register
    fca_authorised    — Y / N
    fca_permissions   — Pipe-delimited list of regulated activity names

Config File (YAML)
------------------
    fca:
      api_email: "your.email@example.com"
      api_key:   "your_api_key_here"
      request_delay_seconds: 0.2

    batch:
      input_file: "data/counterparties.csv"
      output_file: "data/counterparties_fca.csv"
"""

import argparse
import csv
import difflib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    _YAML_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from fca.client import FcaRegisterClient
from fca.lookup import FcaFirmLookup, FirmLookupResult, FirmRecord

# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

_FRN_COLUMNS = {
    "frn",
    "frn_number",
    "frn number",
    "firm_reference_number",
    "firm reference number",
    "firm_reference_no",
    "firm reference no",
    "firm_ref",
    "firm ref",
    "reference_number",
    "reference number",
    "reference_no",
    "reference no",
    "ref_no",
    "ref no",
    "fca_number",
    "fca number",
    "fca_reference_number",
    "fca reference number",
    "fca_ref",
    "fca ref",
}
_NAME_COLUMNS = {
    "firm_name",
    "firm name",
    "organisation_name",
    "organisation name",
    "name",
    "company_name",
    "company name",
    "counterparty_name",
    "counterparty name",
    "entity_name",
    "entity name",
    "legal_name",
    "legal name",
    "business_name",
    "business name",
    "full_name",
    "full name",
}

#: Common FCA regulated activity names used for permission dropdowns.
KNOWN_PERMISSIONS: List[str] = [
    "Accepting deposits",
    "Advising on investments (except pension transfers)",
    "Advising on P2P agreements",
    "Advising on pension transfers and pension opt-outs",
    "Advising on regulated mortgage contracts",
    "Advising on syndicate participation at Lloyd's",
    "Arranging (bringing about) deals in investments",
    "Arranging (bringing about) regulated mortgage contracts",
    "Arranging safeguarding and administration of assets",
    "Communicating financial promotions",
    "Dealing in investments as agent",
    "Dealing in investments as principal",
    "Effecting contracts of insurance",
    "Establishing, operating or winding up a collective investment scheme",
    "Insurance distribution activity",
    "Issuing electronic money",
    "Making arrangements with a view to transactions in investments",
    "Managing a UCITS",
    "Managing an AIF",
    "Managing investments",
    "Operating a multilateral trading facility",
    "Operating an organised trading facility",
    "Safeguarding and administering investments",
    "Sending dematerialised instructions",
    "Undertaking activities in relation to a regulated benchmark",
]

# Output column names appended to each CSV row.
_COL_FCA_FRN = "fca_frn"
_COL_FCA_STATUS = "fca_status"
_COL_FCA_AUTHORISED = "fca_authorised"
_COL_FCA_PERMISSIONS = "fca_permissions"

_OUTPUT_COLUMNS = [
    _COL_FCA_FRN,
    _COL_FCA_STATUS,
    _COL_FCA_AUTHORISED,
    _COL_FCA_PERMISSIONS,
]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check firm authorisation status against the FCA Financial Services Register.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    single = parser.add_argument_group("Single lookup")
    single.add_argument(
        "--frn",
        type=str,
        default=None,
        metavar="FRN",
        help="Firm Reference Number to look up.",
    )
    single.add_argument(
        "--name",
        type=str,
        default=None,
        metavar="NAME",
        help="Firm name to search for (returns all matches).",
    )

    batch = parser.add_argument_group("Batch (CSV)")
    batch.add_argument(
        "--input",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help=(
            "Input CSV file containing an 'frn' and/or 'firm_name' column. "
            "FRN takes precedence when both are present."
        ),
    )
    batch.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="CSV_PATH",
        help=(
            "Output CSV file path. Defaults to <input_stem>_fca_check.csv "
            "in the same directory as the input file."
        ),
    )

    parser.add_argument(
        "--permission",
        type=str,
        default=None,
        metavar="PERMISSION",
        help=(
            "Regulated activity name to verify (e.g. 'Managing investments'). "
            "When specified, adds a column with that permission name to the batch "
            "output containing Y/N, and highlights the result in single-lookup mode."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a YAML config file.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Logging verbosity (default: WARNING).",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load a YAML config file and return its contents as a dict."""
    if not _YAML_AVAILABLE:
        return {}
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}  # type: ignore[union-attr]


def _load_credentials(config: Dict[str, Any]) -> tuple[str, str]:
    """Extract API credentials from a loaded config dict.

    Args:
        config: Parsed YAML config dict.

    Returns:
        Tuple of ``(api_email, api_key)``.

    Raises:
        SystemExit: If credentials are missing.
    """
    fca_section = config.get("fca", {})
    api_email = fca_section.get("api_email", "")
    api_key = fca_section.get("api_key", "")

    if not api_email or not api_key:
        print(
            "ERROR: FCA API credentials not found.\n"
            "Provide them in a YAML config file under 'fca.api_email' and "
            "'fca.api_key', or use --config to specify the config path.\n"
            "See config/templates/fca_config.yaml.template for the expected format.",
            file=sys.stderr,
        )
        sys.exit(1)

    return api_email, api_key


# ---------------------------------------------------------------------------
# Column detection helpers
# ---------------------------------------------------------------------------


def _detect_frn_column(fieldnames: List[str]) -> Optional[str]:
    """Find the FRN column from a list of CSV field names."""
    for field in fieldnames:
        if field.strip().lower() in _FRN_COLUMNS:
            return field
    return None


def _detect_name_column(fieldnames: List[str]) -> Optional[str]:
    """Find the firm name column from a list of CSV field names."""
    for field in fieldnames:
        if field.strip().lower() in _NAME_COLUMNS:
            return field
    return None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _has_permission(result: FirmLookupResult, permission: str) -> str:
    """Return 'Y' if the firm holds the given permission, 'N' otherwise.

    Comparison is case-insensitive and strips surrounding whitespace.

    Args:
        result: Completed :class:`FirmLookupResult`.
        permission: Regulated activity name to check.

    Returns:
        ``"Y"`` or ``"N"``.
    """
    if not result.firm:
        return "N"
    target = permission.strip().lower()
    return (
        "Y"
        if any(p.activity_name.strip().lower() == target for p in result.permissions)
        else "N"
    )


def _format_permissions(result: FirmLookupResult) -> str:
    """Format the permissions list as a pipe-delimited string."""
    if not result.permissions:
        return ""
    return " | ".join(p.activity_name for p in result.permissions)


def _result_to_row(result: FirmLookupResult) -> Dict[str, str]:
    """Convert a FirmLookupResult to a dict of output column values."""
    return {
        _COL_FCA_FRN: result.frn if result.firm else "",
        _COL_FCA_STATUS: result.firm.status if result.firm else "NOT FOUND",
        _COL_FCA_AUTHORISED: "Y" if result.is_authorised else "N",
        _COL_FCA_PERMISSIONS: _format_permissions(result),
    }


# ---------------------------------------------------------------------------
# Single lookup
# ---------------------------------------------------------------------------


def _run_single_frn(
    lookup: FcaFirmLookup, frn: str, permission: Optional[str] = None
) -> None:
    """Look up a single firm by FRN and print results to stdout."""
    result = lookup.lookup_by_frn(frn)

    if result.firm is None:
        print(f"FRN {frn!r}: NOT FOUND in FCA Register.")
        return

    firm = result.firm
    auth = "Authorised" if result.is_authorised else "NOT Authorised"
    print(f"\nFRN:              {firm.frn}")
    print(f"Organisation:     {firm.organisation_name}")
    print(f"Status:           {firm.status} ({auth})")
    print(f"Business Type:    {firm.business_type}")
    print(f"Companies House:  {firm.companies_house_number}")
    print(f"Status From:      {firm.status_effective_date}")

    if permission:
        has_perm = _has_permission(result, permission)
        indicator = "YES" if has_perm == "Y" else "NO"
        print(f"\nPermission check: {permission!r} — {indicator}")

    if result.permissions:
        print(f"\nPermissions ({len(result.permissions)}):")
        for perm in result.permissions:
            print(f"  - {perm.activity_name}")
    else:
        print("\nNo permissions found.")


def _run_name_search(lookup: FcaFirmLookup, name: str) -> None:
    """Search for firms by name, print the single closest-matching result.

    Candidates returned by the FCA register are scored against the original
    query using :func:`difflib.SequenceMatcher`.  Only the highest-scoring
    firm is printed, avoiding ambiguous multi-result lists for single
    lookups.

    Args:
        lookup: Configured :class:`FcaFirmLookup` instance.
        name: Firm name to search for.
    """
    firms = lookup.search_by_name(name)

    if not firms:
        print(f"No firms found matching {name!r}.")
        return

    best = max(
        firms,
        key=lambda f: difflib.SequenceMatcher(
            None,
            f.organisation_name.lower(),
            name.lower(),
        ).ratio(),
    )
    print(f"\nClosest match for {name!r}:\n")
    print(f"{'FRN':<12} {'Status':<25} {'Name'}")
    print("-" * 80)
    print(f"{best.frn:<12} {best.status:<25} {best.organisation_name}")


# ---------------------------------------------------------------------------
# Batch CSV processing
# ---------------------------------------------------------------------------


def _derive_output_path(input_path: Path) -> Path:
    """Derive the default output path from the input path."""
    return input_path.with_name(f"{input_path.stem}_fca_check{input_path.suffix}")


def _run_batch(
    lookup: FcaFirmLookup,
    input_path: Path,
    output_path: Path,
    permission: Optional[str] = None,
) -> None:
    """Process a CSV file and write enriched results to the output path.

    For each row, looks up the firm by FRN if a FRN column is detected,
    otherwise searches by name.  Appends ``fca_frn``, ``fca_status``,
    ``fca_authorised``, and ``fca_permissions`` columns.  If ``permission``
    is specified, also appends a column named after the permission with Y/N.

    Args:
        lookup: Configured :class:`FcaFirmLookup` instance.
        input_path: Path to the input CSV file.
        output_path: Path to write the enriched output CSV.
        permission: Optional regulated activity name to verify per row.
    """
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with input_path.open(encoding="utf-8", newline="") as in_fh:
        reader = csv.DictReader(in_fh)
        if reader.fieldnames is None:
            print("ERROR: Input CSV has no headers.", file=sys.stderr)
            sys.exit(1)

        fieldnames = list(reader.fieldnames)
        frn_col = _detect_frn_column(fieldnames)
        name_col = _detect_name_column(fieldnames)

        if frn_col is None and name_col is None:
            print(
                "ERROR: Input CSV must contain an FRN column "
                f"({', '.join(sorted(_FRN_COLUMNS))}) or a firm name column "
                f"({', '.join(sorted(_NAME_COLUMNS))}).",
                file=sys.stderr,
            )
            sys.exit(1)

        mode = "frn" if frn_col else "name"
        print(
            f"Processing {input_path.name} using "
            f"{'FRN' if mode == 'frn' else 'name'} column "
            f"({frn_col if mode == 'frn' else name_col!r})..."
        )

        out_fieldnames = (
            fieldnames + _OUTPUT_COLUMNS + ([permission] if permission else [])
        )
        rows = list(reader)

    total = len(rows)
    enriched: List[Dict[str, str]] = []

    for i, row in enumerate(rows, start=1):
        print(f"  [{i}/{total}]", end="\r")

        if mode == "frn":
            frn = str(row.get(frn_col, "")).strip()  # type: ignore[arg-type]
            if not frn:
                empty: Dict[str, str] = {**row, **{c: "" for c in _OUTPUT_COLUMNS}}
                if permission:
                    empty[permission] = ""
                enriched.append(empty)
                continue
            result = lookup.lookup_by_frn(frn)
            row_data = _result_to_row(result)
            if permission:
                row_data[permission] = _has_permission(result, permission)
            enriched.append({**row, **row_data})
        else:
            # Name mode: use the first match returned by the search.
            name = str(row.get(name_col, "")).strip()  # type: ignore[arg-type]
            if not name:
                empty = {**row, **{c: "" for c in _OUTPUT_COLUMNS}}
                if permission:
                    empty[permission] = ""
                enriched.append(empty)
                continue

            firms = lookup.search_by_name(name)
            if not firms:
                not_found: Dict[str, str] = {
                    **row,
                    _COL_FCA_FRN: "",
                    _COL_FCA_STATUS: "NOT FOUND",
                    _COL_FCA_AUTHORISED: "N",
                    _COL_FCA_PERMISSIONS: "",
                }
                if permission:
                    not_found[permission] = "N"
                enriched.append(not_found)
                continue

            # Use the first search result's FRN to fetch full details.
            first_frn = firms[0].frn
            result = lookup.lookup_by_frn(first_frn)
            row_data = _result_to_row(result)
            if permission:
                row_data[permission] = _has_permission(result, permission)
            enriched.append({**row, **row_data})

    print()  # newline after progress indicator

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as out_fh:
        writer = csv.DictWriter(
            out_fh, fieldnames=out_fieldnames, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(enriched)

    authorised = sum(1 for r in enriched if r.get(_COL_FCA_AUTHORISED) == "Y")
    not_found = sum(1 for r in enriched if r.get(_COL_FCA_STATUS) == "NOT FOUND")
    print(
        f"\nDone. {total} firms processed — "
        f"{authorised} authorised, {not_found} not found.\n"
        f"Output: {output_path}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> None:
    """Main entry point for the fca-check CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    args = _parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    # ------------------------------------------------------------------
    # Load config
    # ------------------------------------------------------------------
    config: Dict[str, Any] = {}
    if args.config:
        config = _load_yaml_config(args.config)
    else:
        # Try the default local config path.
        default_config = _REPO_ROOT / "config" / "local" / "fca_config.yaml"
        if default_config.exists():
            config = _load_yaml_config(default_config)

    # Resolve effective arguments: CLI args override config file values.
    batch_section = config.get("batch", {})

    effective_frn: Optional[str] = args.frn
    effective_name: Optional[str] = args.name
    effective_input: Optional[Path] = args.input or (
        Path(batch_section["input_file"]) if "input_file" in batch_section else None
    )
    effective_output: Optional[Path] = args.output or (
        Path(batch_section["output_file"]) if "output_file" in batch_section else None
    )

    if not effective_frn and not effective_name and not effective_input:
        print(
            "ERROR: Provide one of --frn, --name, or --input.\n"
            "Run with --help for usage.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Build lookup
    # ------------------------------------------------------------------
    api_email, api_key = _load_credentials(config)
    fca_section = config.get("fca", {})
    request_delay = float(fca_section.get("request_delay_seconds", 0.2))

    client = FcaRegisterClient(
        api_email=api_email,
        api_key=api_key,
    )
    # Apply any configured delay on top of the token-bucket.
    client._bucket._window  # noqa: SLF001 — ensure bucket initialised
    lookup = FcaFirmLookup(client=client)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    effective_permission: Optional[str] = args.permission or None

    if effective_frn:
        _run_single_frn(lookup, effective_frn, permission=effective_permission)

    elif effective_name:
        _run_name_search(lookup, effective_name)

    else:
        assert effective_input is not None
        output_path = effective_output or _derive_output_path(effective_input)
        _run_batch(
            lookup, effective_input, output_path, permission=effective_permission
        )


if __name__ == "__main__":
    main()
