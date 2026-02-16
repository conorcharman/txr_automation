# Correction Decision Logic v2.0 - Quick Reference

**Version:** 2.0  
**Date:** 13 February 2026  
**Applies to:** Phase 2 Processor v4.1, Phase 3 Processor v5.1

---

## What Changed?

### Old Logic (v1.0)
- Checked **Error Flag** column to determine if correction needed
- Only applied corrections when Error Flag = 'Y'
- Complicated multi-condition logic

### New Logic (v2.0)
- Checks **Correction** column existence (not Error Flag)
- Routes based on **Agree With Correction** value
- Simple 4-branch decision tree
- Error Flag column **deprecated** (retained for backwards compatibility)

---

## Decision Tree

```text
┌─────────────────────────────────────────────┐
│ Does Correction column have a value?        │
└────────────┬────────────────────────────────┘
             │
       ┌─────┴─────┐
       │           │  
      YES         NO  
       │           │
       │           └──→ NO CHANGE
       │
       ▼
┌──────────────────────────────────────────────┐
│ What is Agree With Correction value?         │
└────────┬─────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
   Y/P      EMPTY       N/F      UNKNOWN
    │         │          │          │
    │         │          │          │
    ▼         ▼          ▼          ▼
┌───────┐ ┌───────┐  ┌──────────┐ ┌───────┐
│ APPLY │ │ APPLY │  │ SUGGESTED│ │ APPLY │
│ CORR  │ │ CORR  │  │ EXISTS?  │ │ CORR  │
└───────┘ └───────┘  └────┬─────┘ └───────┘
                           │
                      ┌────┴────┐
                      │         │
                     YES       NO
                      │         │
                      ▼         ▼
                  ┌─────────┐ ┌──────────┐
                  │  APPLY  │ │    NO    │
                  │SUGGESTED│ │  CHANGE  │
                  └─────────┘ └──────────┘
```

---

## Code Implementation

### Phase 2 Processor (_create_lookup_result method)

```python
def _create_lookup_result(
    self,
    replay_row: List[str],
    incident_row: Optional[Dict[str, str]],
) -> List[str]:
    """Create lookup result with new correction decision logic v2.0."""
    
    if incident_row:
        # Get values from incident file
        correction_value = incident_row.get(self.incident_mapper.correction, "").strip()
        agree_value = incident_row.get(self.incident_mapper.agree_with_correction, "").strip().upper()
        suggested_correction_value = incident_row.get(self.incident_mapper.suggested_correction, "").strip()
        
        # DECISION LOGIC v2.0
        if correction_value:
            # Correction exists - check Agree With Correction
            if agree_value in ('Y', 'P', ''):
                # Apply Correction
                return [correction_field, correction_value]
            elif agree_value in ('N', 'F'):
                # Disagree - check for Suggested Correction
                if suggested_correction_value:
                    # Apply Suggested Correction
                    return [correction_field, suggested_correction_value]
                else:
                    # No suggested, no change
                    return ["", ""]
            else:
                # Unknown Agree value - default to applying correction
                return [correction_field, correction_value]
        else:
            # No correction available
            return ["", ""]
    else:
        # No match found
        return ["", ""]
```

---

## Agree With Correction Values

| Value | Interpretation | Action |
|-------|---------------|--------|
| `Y` | Yes, agree | Apply Correction |
| `P` | Partially agree | Apply Correction |
| ` ` (empty) | No explicit disagreement | Apply Correction (default) |
| `N` | No, disagree | Check Suggested Correction |
| `F` | Fundamentally disagree | Check Suggested Correction |
| Other | Unknown/unexpected | Apply Correction (safe default) |

**Note:** Matching is case-insensitive (`'y'`, `'Y'`, `'yes'`, `'YES'` all work)

---

## Column Constants

### Phase 2 (14 columns total)
```python
class Phase2SingleColumns:
    CORRECTION_FIELD = 9   # Column index for field name
    CORRECTION_VALUE = 10  # Column index for correction value
```

### Phase 3 (25 columns total)
```python
class Phase3SingleColumns:
    CORRECTION_FIELD = 23  # Column index for field name
    CORRECTION_VALUE = 24  # Column index for correction value
```

---

## YAML Configuration

### Required Columns

```yaml
incident_file:
  columns:
    transaction_reference: Transaction_Reference    # For Phase 2 matching
    buyer_id: Buyer_ID                             # For Phase 3 matching
    seller_id: Seller_ID                           # For Phase 3 matching
    correction: Correction                          # NEW: Primary decision column
    agree_with_correction: Agree With Correction    # NEW: Routing column
    suggested_correction: Suggested Correction      # NEW: Fallback column
    error_flag: Error Flag                         # DEPRECATED: No longer used
```

### Migration Notes

- **No changes required** to existing YAML configs
- Error Flag can remain in config but is not used in logic
- All columns marked as required should be present in incident files

---

## Testing

### Run Tests

```powershell
# All replay tests
pytest tests/test_replay/ -v

# Unit tests only
pytest tests/test_replay/test_correction_logic.py -v

# Integration tests only
pytest tests/test_replay/test_integration.py -v
```

### Expected Results

- **18 tests total:** 14 unit + 4 integration
- **All should pass:** ✅ 18 passed
- **5 teardown errors:** Expected on Windows (file locking), doesn't affect validity

---

## Examples

### Example 1: Apply Correction (Agree = Y)

**Incident File:**
```csv
Transaction_Reference,Correction,Agree With Correction,Suggested Correction
TXN001,NewValue,Y,
```

**Result:** Correction applied → `NewValue`

---

### Example 2: Apply Suggested (Disagree with Suggestion)

**Incident File:**
```csv
Transaction_Reference,Correction,Agree With Correction,Suggested Correction
TXN002,OriginalCorrection,N,BetterValue
```

**Result:** Suggested Correction applied → `BetterValue`

---

### Example 3: No Change (Disagree without Suggestion)

**Incident File:**
```csv
Transaction_Reference,Correction,Agree With Correction,Suggested Correction
TXN003,OriginalCorrection,N,
```

**Result:** No change → `(empty)`

---

### Example 4: Default to Correction (Empty Agree)

**Incident File:**
```csv
Transaction_Reference,Correction,Agree With Correction,Suggested Correction
TXN004,DefaultValue,,
```

**Result:** Correction applied → `DefaultValue`

---

## Debugging

### Enable Debug Logging

```yaml
logging:
  level: DEBUG  # Shows decision path for each record
```

### Debug Log Output

```text
2026-02-13 11:12:07 - phase2_processor - DEBUG - TXN001: Correction exists with Agree='Y' → Applying correction
2026-02-13 11:12:07 - phase2_processor - DEBUG - TXN002: Correction exists with Agree='N' and Suggested → Applying suggested
2026-02-13 11:12:07 - phase2_processor - DEBUG - TXN003: Correction exists with Agree='N' but no Suggested → No change
```

---

## Common Issues

### Issue: Corrections not being applied

**Check:**
1. Correction column has value in incident file?
2. Agree With Correction value is valid (Y/P/N/F/empty)?
3. If Agree=N/F, is Suggested Correction column populated?
4. Column names in YAML match actual CSV headers exactly?

### Issue: Wrong correction applied

**Check:**
1. Agree With Correction value case (should be case-insensitive but check logs)
2. Suggested Correction fallback logic working correctly
3. Debug logs showing which decision branch taken

---

## Migration Checklist

- [x] Update Phase 2 Processor to v4.1
- [x] Update Phase 3 Processor to v5.1
- [x] Update Phase 3 Final Processor (uses same logic as Phase 3)
- [x] Update YAML templates with v2.0 documentation
- [x] Mark Error Flag as deprecated in all templates
- [x] Create comprehensive test suite (18 tests)
- [x] Validate all tests pass
- [ ] Test with real production data samples
- [ ] Update user guides if needed
- [ ] Deploy to production

---

## Further Reading

- **Full Testing Summary:** [Correction_Logic_Testing_Summary.md](Correction_Logic_Testing_Summary.md)
- **Phase 2 Processor:** [src/replay/phase_2_processor.py](../src/replay/phase_2_processor.py)
- **Phase 3 Processor:** [src/replay/phase_3_processor.py](../src/replay/phase_3_processor.py)
- **Test Suite:** [tests/test_replay/](../tests/test_replay/)

---

*Quick Reference prepared by: GitHub Copilot*  
*Last updated: 13 February 2026*
