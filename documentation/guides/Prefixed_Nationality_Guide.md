# Prefixed Nationality Column User Guide

**Version:** 1.0  
**Date:** 6 February 2026  
**Feature Added:** Phase 4 ID Validation Enhancement  

---

## Overview

The **Prefixed Nationality** column is a new feature added to all ID validation outputs in February 2026. It automatically extracts and validates the 2-letter country code prefix from identification numbers when present.

### What Problem Does This Solve?

Previously, when a client's ID included a nationality prefix (e.g., "NLNPPD7P215" where "NL" = Netherlands), the system would:
- Incorrectly validate against the wrong pattern length
- Produce false positives for "inconsistent ID" errors when a person's nationality changed between trades
- Make it difficult to verify that prefixed IDs matched the person's actual nationality

### How It Works

The system now:
1. **Automatically detects** 2-letter country code prefixes at the start of ID values
2. **Validates** the prefix against the global country code database
3. **Extracts and stores** the prefix separately in the "Prefixed Nationality" column
4. **Strips the prefix** before validating the ID format
5. **Groups inconsistent ID detection** by prefix to avoid false positives

---

## Column Location

The "Prefixed Nationality" column appears in **all ID validation outputs** after the "Gender" column:

```
Transaction Reference | Account ID | Person Code | ... | Gender | Prefixed Nationality | Primary Nationality | Secondary Nationality | ...
```

---

## Valid Prefix Examples

| Original ID | Extracted Prefix | ID After Prefix Removal | Validation Country |
|-------------|------------------|-------------------------|-------------------|
| `NLNPPD7P215` | `NL` | `NPPD7P215` | Netherlands |
| `GBSG500496A` | `GB` | `SG500496A` | United Kingdom |
| `FRNJ6783321` | `FR` | `NJ6783321` | France |
| `SE197007100329` | `SE` | `197007100329` | Sweden |
| `123456789` | *(empty)* | `123456789` | *(no prefix)* |

---

## When Prefixes Appear

Prefixes are extracted and validated for these ID types:
- **NIDN** (National ID Number)
- **CCPT** (Passport Number)
- **CONCAT** (Concatenated IDs)

Prefixes are **NOT** extracted for:
- **LEI** (Legal Entity Identifier) - These are standardised 20-character codes without country prefixes

---

## Reading the Output

### Example 1: Valid Prefixed ID

```csv
Transaction Reference,Gender,Prefixed Nationality,Primary Nationality,Secondary Nationality,Buyer ID Code,Type of Buyer ID Code
TXN001,M,NL,NL,,NLNPPD7P215,CCPT
```

**Interpretation:**
- ✅ Prefix "NL" extracted successfully
- ✅ Prefix matches Primary Nationality (NL)
- ✅ ID "NPPD7P215" validated against Netherlands CCPT pattern (9 characters)
- ✅ No issues detected

### Example 2: Nationality Change (Not an Error)

```csv
Transaction Reference,Trade Date,Prefixed Nationality,Primary Nationality,Buyer ID Code
TXN001,2025-01-15,NL,NL,NLNPPD7P215
TXN002,2025-06-20,GB,GB,GBSG500496A
```

**Interpretation:**
- ✅ Person had NL nationality in January
- ✅ Person obtained GB nationality by June
- ✅ Different prefixes = Different nationality groups
- ✅ **NOT flagged as "Inconsistent ID"** (this is a legitimate nationality change)

### Example 3: True Inconsistency (Error Detected)

```csv
Transaction Reference,Trade Date,Prefixed Nationality,Primary Nationality,Buyer ID Code
TXN001,2025-01-15,NL,NL,NLNPPD7P215
TXN002,2025-01-20,NL,NL,NLABCD1234
```

**Interpretation:**
- ⚠️ Both records have NL prefix
- ⚠️ Both in same nationality group
- ⚠️ IDs are different: "NPPD7P215" vs "ABCD1234"
- ❌ **FLAGGED as "Inconsistent ID"** (same nationality, different IDs within 5 days)

### Example 4: No Prefix (Standard Validation)

```csv
Transaction Reference,Gender,Prefixed Nationality,Primary Nationality,Buyer ID Code,Type of Buyer ID Code
TXN003,F,,GB,AB123456C,NIDN
```

**Interpretation:**
- ℹ️ No prefix detected in ID "AB123456C"
- ℹ️ Prefixed Nationality column is empty
- ✅ ID validated directly against GB NIDN pattern (no prefix stripping needed)
- ✅ Standard validation applied

---

## Technical Implementation

### How Prefixes Are Validated

1. **Length Check:** First 2 characters extracted
2. **Format Check:** Must be uppercase letters (A-Z)
3. **Country Code Validation:** Checked against ISO-3166 Alpha-2 country code database
4. **Nationality Matching:** Verified against Primary Nationality and/or Secondary Nationality fields

### Prefix-Aware Inconsistency Detection

When checking for inconsistent IDs within a person group:

```
Person ABC123 - Records:
├─ NL Group
│  ├─ TXN001: NLNPPD7P215
│  └─ TXN002: NLNPPD7P215  ✅ Consistent
├─ GB Group
│  ├─ TXN003: GBSG500496A
│  └─ TXN004: GBSG500496A  ✅ Consistent
└─ No Inconsistency (different prefixes = different nationalities)
```

Previously, TXN001 and TXN003 would be flagged as inconsistent because the IDs differ. Now the system correctly recognizes they belong to different nationality groups.

---

## Benefits

### 1. **Accurate Validation**
- IDs validated against correct country patterns
- Correct expected length shown in error messages
- NL IDs no longer fail with "expected 11 characters" error

### 2. **Fewer False Positives**
- Nationality changes no longer flagged as "Inconsistent ID"
- System only flags true inconsistencies (within same nationality)
- Reduces manual review burden

### 3. **Better Data Quality**
- Easy to spot mismatched nationality prefixes
- Verify prefix matches declared nationality
- Identify data entry errors

### 4. **Audit Trail**
- Clear record of which nationality was indicated in the ID
- Track nationality changes over time
- Support compliance requirements

---

## Common Scenarios

### Scenario 1: Dual Nationality

```csv
Person Code,Primary Nationality,Secondary Nationality,Prefixed Nationality,ID Code
P001,NL,GB,NL,NLNPPD7P215
```

**Result:** ✅ Valid - Prefix matches one of the two nationalities

### Scenario 2: Prefix Doesn't Match Any Nationality

```csv
Person Code,Primary Nationality,Secondary Nationality,Prefixed Nationality,ID Code
P002,FR,BE,NL,NLNPPD7P215
```

**Result:** ⚠️ Warning - Prefix "NL" doesn't match declared nationalities (FR/BE)

### Scenario 3: Same Person, Nationality Change Over Time

```csv
Transaction Ref,Trade Date,Person Code,Prefixed Nationality,ID Code
TXN001,2024-01-01,P003,PL,PLAB12345678
TXN002,2025-01-01,P003,GB,GBAB123456C
```

**Result:** ✅ Valid - Different prefix groups, not flagged as inconsistent

---

## Scripts Affected

All ID validation scripts now output the "Prefixed Nationality" column:

| Script | Command | Status |
|--------|---------|--------|
| Buyer ID Validation | `validate-buyer` | ✅ Updated |
| Seller ID Validation | `validate-seller` | ✅ Updated |
| Inconsistent Buyer ID | `validate-inconsistent-buyer` | ✅ Updated |
| Inconsistent Seller ID | `validate-inconsistent-seller` | ✅ Updated |

---

## CSV Schema Changes

### Main Output Files

**New Column:** "Prefixed Nationality" (after "Gender", before "Primary Nationality")

### Errors-Only Output Files

**New Column:** "Prefixed Nationality" (same position)

### Backward Compatibility

⚠️ **Breaking Change:** If you have automated processes that expect a specific column order, you'll need to update them to account for the new column position.

**Migration:**
- Old column 11 (Primary Nationality) → Now column 12
- Old column 12 (Secondary Nationality) → Now column 13
- All subsequent columns shifted right by one position

---

## Troubleshooting

### Q: My ID previously validated, now it fails with "expected 9 characters"

**A:** This is likely a Netherlands (NL) or Spanish (ES) ID. The patterns were corrected in February 2026:
- **NL:** Fixed from 11-char to 9-char format (matches ESMA guidance)
- **ES:** Fixed from 10-char to 9-char format (matches ESMA guidance)

If your ID was incorrectly formatted, it will now be caught. Check the ESMA guidance document for correct formats.

### Q: Why is "Prefixed Nationality" empty for my UK ID?

**A:** Not all UK IDs have prefixes. Format "AB123456C" doesn't start with "GB", so no prefix is extracted. The ID is validated directly against the UK NIDN pattern.

However, if you have "GBAB123456C", the "GB" prefix will be extracted.

### Q: My person changed nationality, why isn't it flagged as inconsistent?

**A:** This is the correct behaviour! The system now recognizes that different nationality prefixes indicate legitimate nationality changes, not data errors.

**Old behaviour (incorrect):** Flagged as inconsistent  
**New behaviour (correct):** Not flagged, treated as separate nationality groups

---

## Related Documentation

- [ID_Validation_Guide.md](ID_Validation_Guide.md) - General ID validation help
- [ESMA_Validation_Report.md](../planning/ESMA_Validation_Report.md) - Regex pattern validation details
- [Accuracy_Testing_IO.md](../reference/Accuracy_Testing_IO.md) - CSV column specifications

---

## Technical Details

### Implementation Files

- **Core Logic:** `src/accuracy_testing/processor.py`
  - `extract_id_prefix()` function (line 916)
  - `_determine_priority_country()` method (line 1170)
  - `_extract_nationality_prefix()` helper (line 621)

- **Pattern Fixes:** `src/core/data/id_formats.py`
  - NL patterns (lines 156-158)
  - ES patterns (lines 117-119)
  - GB patterns (line 133)

### Feature Version

- **Added:** February 2026 (Phase 4 enhancement)
- **Included in:** Version 3.0+ of all ID validation scripts
- **Git Commit:** `fix(accuracy): Fix ESMA regex patterns and implement prefix-aware inconsistency detection`

---

## Feedback

If you encounter issues with the Prefixed Nationality feature or have questions:

1. Check the troubleshooting section above
2. Review the ESMA guidance document for your country
3. Examine the "Failure Reason" column for specific validation errors
4. Contact the development team with:
   - Transaction Reference
   - ID Value
   - Prefixed Nationality shown
   - Expected behaviour

---

**Document Version:** 1.0  
**Last Updated:** 6 February 2026  
**Author:** Development Team  
