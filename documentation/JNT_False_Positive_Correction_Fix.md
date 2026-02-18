# JNT (Joint Account) False Positive Correction Bug Fix

**Date:** 18 February 2026  
**Status:** ✅ Fixed and Tested

---

## Bug Description

All joint account (JNT) records were generating corrections in the output, even when both individual records passed validation. The corrections were identical to the original IDs, creating false positives.

### Example of the Bug

**Input:** Two JNT records with valid UK NINOs
- Record 1: ID=AB123456C, Type=NIDN (VALID)
- Record 2: ID=JK987654L, Type=NIDN (VALID)

**Before Fix (Incorrect):**
- correction_output: `AB123456C|JK987654L:NIDN|NIDN`
- correction_fields: `ID|ID:IDT|IDT`
- **Result:** False positive - suggests correction needed when IDs are already valid

**After Fix (Correct):**
- correction_output: `` (empty)
- correction_fields: `` (empty)
- **Result:** No correction, as expected for valid IDs

---

## Root Cause

The bug was in the `_aggregate_jnt_pair()` method in [processor.py](../src/accuracy_testing/processor.py) at lines 2376-2412.

### Problematic Code

```python
# Get final IDs and types (corrected if available, otherwise original)
final_id1 = extract_id_from_correction(rec1.correction_output) or orig_id1
final_id2 = extract_id_from_correction(rec2.correction_output) or orig_id2
final_type1 = extract_type_from_correction(rec1.correction_output) or orig_type1
final_type2 = extract_type_from_correction(rec2.correction_output) or orig_type2

# Always build correction_output showing final state of both clients
rec1.correction_output = f"{final_id1}|{final_id2}:{final_type1}|{final_type2}"
```

**Issue:** This code **always** built a `correction_output`, even when both individual records had empty `correction_output` (meaning they passed validation).

When both records passed:
- `rec1.correction_output` = `""` (empty)
- `rec2.correction_output` = `""` (empty)
- The extractions returned `None`, falling back to original IDs
- Final output: `"ID1|ID2:TYPE1|TYPE2"` using original values
- This created a false "correction" identical to the original data

---

## The Fix

Added a conditional check to only build `correction_output` when at least one record actually has a correction:

```python
# Check if either record has a correction (non-empty correction_output)
has_correction1 = bool(rec1.correction_output and rec1.correction_output.strip())
has_correction2 = bool(rec2.correction_output and rec2.correction_output.strip())

if has_correction1 or has_correction2:
    # At least one record has a correction - build aggregated correction_output
    final_id1 = extract_id_from_correction(rec1.correction_output) or orig_id1
    final_id2 = extract_id_from_correction(rec2.correction_output) or orig_id2
    final_type1 = extract_type_from_correction(rec1.correction_output) or orig_type1
    final_type2 = extract_type_from_correction(rec2.correction_output) or orig_type2
    
    rec1.correction_output = f"{final_id1}|{final_id2}:{final_type1}|{final_type2}"
    rec1.correction_fields = "ID|ID:IDT|IDT"
else:
    # Both records passed validation - no correction needed
    rec1.correction_output = ""
    rec1.correction_fields = ""
```

---

## Test Coverage

Created comprehensive test suite in [test_jnt_correction_fix.py](../tests/test_jnt_correction_fix.py):

### Test 1: Both Records Pass Validation
- ✅ **Expected:** No correction_output
- ✅ **Result:** correction_output = "" (empty)

### Test 2: One Record Fails, One Passes
- ✅ **Expected:** correction_output with mixed valid/corrected IDs
- ✅ **Result:** correction_output = "AB123456C|IN67890:NIDN|NIDN"

### Test 3: Both Records Fail Validation
- ✅ **Expected:** correction_output with both corrections
- ✅ **Result:** correction_output = "IN12345|IN67890:NIDN|NIDN"

---

## Regression Testing

All existing tests pass:
- ✅ 7/7 buyer ID validation tests
- ✅ 80/80 CONCAT generation and validator tests
- ✅ No breaking changes to existing functionality

---

## Impact

### Before Fix
- Every JNT account pair generated a correction entry
- False positives inflated correction counts
- Harder to identify actual issues requiring attention
- Output files cluttered with unnecessary corrections

### After Fix
- JNT accounts only show corrections when validation actually fails
- Accurate correction counts and reporting
- Cleaner output files
- Easier to identify real issues

---

## Files Changed

1. **[processor.py](../src/accuracy_testing/processor.py)** (lines 2376-2412)
   - Modified `_aggregate_jnt_pair()` method
   - Added conditional check before building correction_output

2. **[test_jnt_correction_fix.py](../tests/test_jnt_correction_fix.py)** (new file)
   - Comprehensive test suite for JNT correction logic
   - Covers all three scenarios: both pass, one fails, both fail

---

## Verification Steps

To verify the fix works in your environment:

```bash
# 1. Activate the environment
conda activate txr_automation

# 2. Run the JNT correction tests
python tests/test_jnt_correction_fix.py

# 3. Run existing tests to ensure no regression
python -m pytest tests/test_accuracy_testing/test_buyer_id_validation.py -v
```

Expected output: All tests pass ✅

---

## Related Documentation

- [Python Migration Plan](../documentation/planning/Python_Migration_Plan.md) - Overall migration strategy
- [Buyer ID Validation Documentation](../archive/vba_docs/BuyerIDValidation_Documentation.md) - Original VBA behaviour
- [Processor Module](../src/accuracy_testing/processor.py) - Core validation logic

---

## Notes

- This fix aligns Python behaviour with VBA logic
- Joint account aggregation still works correctly for all scenarios
- The change is backwards compatible (doesn't change valid correction behaviour)
- Only affects JNT account pairs, no impact on other account types
