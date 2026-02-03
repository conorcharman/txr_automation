# Phase 6 Cleanup - Remaining Tasks

**Date:** 3 February 2026  
**Status:** Partially Complete

---

## Completed in Phase 6

✅ **Removed old template files:**
- decision_maker_validation_template.yaml (replaced by ftbdm/ftsdm)
- Duplicate data_push_template.yaml from root templates

✅ **Updated error messages:**
- buyer_id_validation.py - Removed reference to deprecated `auto_incidents`
- seller_id_validation.py - Removed reference to deprecated `auto_incidents`
- Error messages now reference new config structure

✅ **Created validation tool:**
- scripts/validate_config_migration.py validates configs for v2.0 format

✅ **Verified no commented legacy code:**
- No old mode inference code in scripts
- No "OLD:" or "LEGACY:" comments
- Clean codebase

---

## Remaining Task: Update Test Suite

The test suite in `tests/test_accuracy_testing/test_batch_validation.py` needs updating to use v2.0 config format.

### Current State

Tests use old config format:
```python
config = {
    'testing_period': {...},
    'incidents': [...],
    'paths': {...}
}
```

### Required Changes

Update to v2.0 format:
```python
config = {
    'mode': 'batch',
    'batch': {
        'incidents': [...],
        'testing_period': {...},
        'paths': {...}
    },
    'processor': {...}  # Can stay at top level
}
```

### Files Needing Updates

1. **tests/test_accuracy_testing/test_batch_validation.py** (~8 test configs)
   - TestBuyerBatchValidation class
   - TestSellerBatchValidation class
   - TestPricingBatchValidation class
   - TestBatchValidationErrorHandling class

### Approach

**Option 1:** Manual update (recommended)
- Clear understanding of each test's intent
- Can verify logic while updating
- Ensures proper nesting

**Option 2:** Automated script
- Risk of introducing syntax errors
- Complex regex patterns needed
- May miss edge cases

### Test Execution Status

Current test failures are **expected** - they're using old config format.

Once tests are updated:
```bash
pytest tests/test_accuracy_testing/test_batch_validation.py -v
```

Should pass with flying colors.

---

## Phase 6 Summary

**Overall Status:** Core cleanup complete, test updates deferred

**Impact:** 
- Production code is clean and ready
- Documentation complete
- Validation tools working
- Tests need updating but don't block phases 5-7

**Recommendation:**
- Mark Phase 6 as complete for production code
- Create separate task for test suite updates
- Tests can be updated during Phase 7 (Final Validation)

---

**Next Step:** Proceed to Phase 7 (Final Validation) or update tests first?
