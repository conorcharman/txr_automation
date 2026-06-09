#!/usr/bin/env python3
"""
NIDN Validation Comparison: YAML rules (expected) vs Python IDLogicValidator (actual).
Outputs a JSON array of discrepancy records.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.accuracy_testing.id_logic_validator import IDLogicValidator

# ---------------------------------------------------------------------------
# YAML-derived NIDN format rules (source of truth)
# Regexes are applied to the ID *after* stripping the 2-char country prefix.
# ---------------------------------------------------------------------------
YAML_NIDN_RULES: dict[str, dict] = {
    "BE": {
        "regex": r"^\d{11}$",
        "description": "Belgian National Number: 11 numeric digits (YYMMDD+3order+2check)",
        "source": "YAML regex ^\\d{6}(\\d{3}|\\d{3})\\d{2}$ = 11 digits",
    },
    "BG": {
        "regex": r"^\d{10}$",
        "description": "Bulgarian Personal Number: 10 numeric digits",
        "source": "YAML regex ^\\d{10}$",
    },
    "CZ": {
        # Slash is separator; YAML conditions note 'should be omitted in transactions'
        "regex": r"^\d{9,10}$",
        "description": "Czech NIN: 9 or 10 numeric digits (slash omitted in transactions)",
        "source": "YAML regex ^\\d{6}/\\d{3}(\\d)?$ with slash omitted per conditions",
    },
    "DK": {
        "regex": r"^\d{10}$",
        "description": "Danish CPR: 10 numeric digits (DDMMYY+4)",
        "source": "YAML regex ^\\d{10}$",
    },
    "EE": {
        "regex": r"^[1-6]\d{10}$",
        "description": "Estonian Isikukood: 11 digits, first digit 1-6",
        "source": "YAML regex ^[1-6]\\d{10}$",
    },
    "ES": {
        "regex": r"^\d{8}[A-HJ-NP-TV-Z]$",
        "description": "Spanish NIF: 8 digits + 1 control letter (not I,O,U,N,Ñ)",
        "source": "YAML regex ^\\d{8}[A-HJ-NP-TV-Z]$",
    },
    "FI": {
        "regex": r"^\d{6}[+\-A]\d{3}[0-9A-Y]$",
        "description": "Finnish Personal Identity Code: DDMMYY[+/-/A]NNN[check]",
        "source": "YAML regex ^\\d{6}[+\\-A]\\d{3}[0-9A-Y]$",
    },
    "GB": {
        "regex": r"^(?![DF QUI])[A-Z](?![DFIO])[A-Z]\d{6}[A-D]$",
        "description": "UK NINO: 2 prefix letters + 6 digits + 1 suffix (A-D)",
        "source": "YAML regex ^(?![DF QUI])[A-Z](?![DFIO])[A-Z]\\d{6}[A-D]$",
        # Additional condition: certain prefixes invalid
        "invalid_prefixes": {"OO", "CR", "FY", "MW", "NC", "PP", "PZ", "TN"},
    },
}


def apply_yaml_rules(country_code: str, clean_id: str) -> tuple[bool | None, list[str]]:
    """
    Apply YAML format rules to a stripped NIDN.

    Returns:
        (expected_valid, failed_rules) where expected_valid is None if no rule exists.
    """
    rule = YAML_NIDN_RULES.get(country_code)
    if rule is None:
        return None, []

    failed: list[str] = []

    if not re.match(rule["regex"], clean_id):
        failed.append(
            f"Regex check failed: pattern='{rule['regex']}' value='{clean_id}' "
            f"[{rule['description']}]"
        )
        return False, failed

    # Additional per-country conditions
    if country_code == "GB":
        invalid_prefixes = rule.get("invalid_prefixes", set())
        prefix = clean_id[:2].upper() if len(clean_id) >= 2 else ""
        if prefix in invalid_prefixes:
            failed.append(
                f"Invalid GB NINO administrative prefix '{prefix}' "
                f"(YAML conditions: invalid prefixes = {sorted(invalid_prefixes)})"
            )
            return False, failed

    return True, []


def run() -> None:
    csv_path = ROOT / "validation_sample.csv"
    validator = IDLogicValidator(verbose=False)
    results: list[dict] = []

    # Deduplicate: one discrepancy entry per unique (national_identifier, country_code, dob, gender)
    # Track first txn_ref per unique key; collect all txn refs as sample_transactions
    seen: dict[tuple, dict] = {}

    with open(csv_path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # Normalise header keys (strip whitespace)
        reader.fieldnames = [f.strip() if f else f for f in (reader.fieldnames or [])]
        for row in reader:
            # Normalise keys in the row dict
            row = {(k.strip() if k else k): v for k, v in row.items()}

            txn_ref      = (row.get("Transaction Reference") or "").strip()
            id_value     = (row.get("Buyer ID Code") or "").strip()
            id_type      = (row.get("Type of Buyer ID Code") or "").strip()
            dob          = (row.get("Date of Birth") or "").strip()
            gender       = (row.get("Gender") or "").strip()
            prefixed_nat = (row.get("Prefixed Nationality") or "").strip()
            primary_nat  = (row.get("Primary Nationality") or "").strip()

            # Skip empty, non-NIDN, or pipe-delimited joint-account records
            if not id_value or not id_type:
                continue
            if "|" in id_value or id_type.upper() != "NIDN":
                continue

            # Determine country code (from prefixed nationality, fallback to primary)
            country_code = (prefixed_nat[:2].upper() if prefixed_nat
                            else (primary_nat[:2].upper() if primary_nat
                                  else id_value[:2].upper()))

            # Strip 2-char country prefix for format validation
            clean_id = (id_value[2:] if len(id_value) > 2
                        and id_value[:2].upper() == country_code
                        else id_value)

            # ---- YAML expected ------------------------------------------------
            expected_valid, yaml_failed = apply_yaml_rules(country_code, clean_id)

            # ---- Python actual ------------------------------------------------
            validator.last_failure_reason = ""
            actual_valid: bool = validator.validate_id_logic(
                id_value=id_value,
                id_type=id_type,
                country_code=country_code,
                provided_dob=dob,
                provided_gender=gender,
            )
            python_failure = validator.last_failure_reason

            # ---- Comparison ---------------------------------------------------
            if expected_valid is None:
                continue  # No YAML rule for this country

            discrepancy = expected_valid != actual_valid
            if not discrepancy:
                continue  # Concordant — omit

            dedup_key = (id_value, country_code, dob, gender)

            # Classify discrepancy type
            if not expected_valid and actual_valid:
                diff_types    = ["missing_rule_application"]
                actual_failed = []
                rule_info     = YAML_NIDN_RULES.get(country_code, {})
                analysis = (
                    f"Python validator does not enforce format/length requirements for "
                    f"{country_code}. When the ID does not match the expected structure, "
                    f"Python's {country_code} handler (or absence of one) returns True by "
                    f"default. YAML requires: {rule_info.get('description', 'N/A')} "
                    f"(source: {rule_info.get('source', 'N/A')}). "
                    f"Stripped ID '{clean_id}' failed: {yaml_failed[0] if yaml_failed else 'format check'}"
                )
            elif expected_valid and not actual_valid:
                diff_types    = ["incorrect_rule_application"]
                actual_failed = [python_failure] if python_failure else ["Unknown Python failure"]
                analysis = (
                    f"YAML format check passes for '{clean_id}' ({country_code}) but "
                    f"Python embedded-logic validator returns False. "
                    f"Python failure reason: {python_failure or 'not recorded'}. "
                    f"Possible over-validation: check-digit, DOB, or gender logic mismatch."
                )
            else:
                diff_types    = ["validity_mismatch"]
                actual_failed = [python_failure] if python_failure else []
                analysis      = "Unexpected validity mismatch — review both YAML and Python logic."

            if dedup_key in seen:
                seen[dedup_key]["sample_transaction_refs"].append(txn_ref)
            else:
                entry = {
                    "client_id":               txn_ref,
                    "country_code":            country_code,
                    "national_identifier":     id_value,
                    "expected_is_valid":       bool(expected_valid),
                    "actual_is_valid":         bool(actual_valid),
                    "discrepancy":             True,
                    "difference_type":         diff_types,
                    "expected_failed_rules":   yaml_failed,
                    "actual_failed_rules":     actual_failed,
                    "analysis":                analysis,
                    "sample_transaction_refs": [txn_ref],
                }
                seen[dedup_key] = entry
                results.append(entry)

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
