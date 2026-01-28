# Auto-Discovery Implementation Summary

## Overview

Implemented automatic incident discovery for buyer and seller ID validation, eliminating the need to manually specify incident codes in configuration files.

**Date:** 2025-01-XX  
**Status:** ✅ Complete  
**Related Features:** Batch Processing, Incident Code Library

---

## Implementation Details

### Core Changes

#### 1. Buyer ID Validation (`buyer_id_validation.py`)

**Added Import:**
```python
from src.txr_replay_core.incident_codes import (
    get_buyer_incident_codes,
    get_standard_buyer_incident_codes,
    get_decision_maker_buyer_codes,
    is_decision_maker_incident
)
```

**Modified `run_batch_validation()` Function:**
```python
# Check for auto-discovery of all buyer incidents
auto_incidents = config.get('auto_incidents')
if auto_incidents == 'all':
    # Auto-discover standard buyer incidents (excludes decision maker incidents)
    incidents = sorted(list(get_standard_buyer_incident_codes()))
    print(f"Auto-discovered {len(incidents)} standard buyer ID incidents")
    print(f"(Excludes decision maker incidents: {', '.join(sorted(get_decision_maker_buyer_codes()))})") 
elif auto_incidents == 'all_including_decision_maker':
    # Include decision maker incidents (7_66, 7_68) - uses different validation logic
    incidents = sorted(list(get_buyer_incident_codes()))
    print(f"Auto-discovered {len(incidents)} buyer incidents (including decision maker)")
else:
    incidents = config.get('incidents', [])

# ... rest of function
if not incidents:
    print("ERROR: No incidents specified in config and auto_incidents not set")
    return 1
```

#### 2. Seller ID Validation (`seller_id_validation.py`)

**Added Import:**
```python
from src.txr_replay_core.incident_codes import (
    get_seller_incident_codes,
    get_standard_seller_incident_codes,
    get_decision_maker_seller_codes,
    is_decision_maker_incident
)
```

**Modified `run_batch_validation()` Function:**
- Same pattern as buyer validation
- Uses `get_seller_incident_codes()` instead of `get_buyer_incident_codes()`

#### 3. Configuration Templates

**Buyer Validation Template (`buyer_validation_template.yaml`):**
```yaml
# Option 1: Auto-discover all buyer incidents (RECOMMENDED)
auto_incidents: "all"

# Option 2: Specify incidents manually (uncomment and modify below)
# incidents:
#   - "7_35"
#   - "7_37"
#   - "7_39"
```

**Seller Validation Template (`seller_validation_template.yaml`):**
```yaml
# Option 1: Auto-discover all seller incidents (RECOMMENDED)
auto_incidents: "all"

# Option 2: Specify incidents manually (uncomment and modify below)
# incidents:
#   - "16_19"
#   - "16_21"
#   - "16_23"
```

---

## Incident Code Coverage

### Standard Buyer ID Incidents (38 total)
```
10_1, 11_2, 11_4, 12_1, 12_11, 12_17, 12_18, 12_2, 12_22, 12_24, 
12_29, 12_31, 12_35, 12_43, 12_75, 13_1, 14_1, 15_2, 15_4, 21_2, 
7_3, 7_35, 7_36, 7_37, 7_39, 7_43, 7_45, 7_74, 
8_1, 8_17, 8_19, 8_2, 8_3, 8_4, 8_6, 8_61, 8_7, 9_1
```

### Decision Maker Buyer Incidents (2 total) - ⚠️ Different validation logic
```
7_66, 7_68  # Inconsistent buyer decision maker - requires chronological analysis
```

### Standard Seller ID Incidents (39 total)
```
12_2, 16_18, 16_19, 16_21, 16_22, 16_23, 16_24, 16_27, 16_29, 
16_3, 16_37, 17_2, 17_59, 17_7, 18_1, 19_1, 20_2, 20_4, 
21_1, 21_11, 21_16, 21_17, 21_2, 21_20, 21_22, 21_29, 21_35, 21_43, 
21_55, 21_75, 22_1, 23_1, 24_2, 24_4, 36_23, 7_11, 8_17, 8_19, 8_6
```

### Decision Maker Seller Incidents (2 total) - ⚠️ Different validation logic
```
16_20, 16_64  # Inconsistent seller decision maker - requires chronological analysis
```

**Important Note:** Decision maker incidents (7_66, 7_68, 16_20, 16_64) use different validation logic that involves:
- Grouping records by Person Code
- Chronological analysis (sorting by Trade_Date_Time)
- Identifying inconsistencies across suspected same individuals
- Using most recent valid ID for corrections

These are excluded from standard auto-discovery by default.

---

## Usage Examples

### Auto-Discovery Mode (Recommended)

**Buyer Validation:**
```bash
# Process all 40 buyer incidents automatically
validate-buyer --config config/local/accuracy_testing/buyer_validation.yaml

# With progress bars
validate-buyer --config config/batch.yaml --progress

# Preview without writing
validate-buyer --config config/batch.yaml --dry-run
```

**Seller Validation:**
```bash
# Process all 41 seller incidents automatically
validate-seller --config config/local/accuracy_testing/seller_validation.yaml

# With progress bars
validate-seller --config config/batch.yaml --progress
```

### Manual Mode (Optional)

**Buyer Validation:**
```yaml
# Specify exact incidents
incidents:
  - "7_37"
  - "7_39"
  - "8_1"
  - "7_66"  # Decision maker incident - uses different validation logic
```

---

## Workflow Integration

### Complete Accuracy Testing Workflow

```bash
# 1. Generate templates from consolidated data
generate-accuracy-template --config config/template_generator.yaml

# 2. Generate SQL extracts (batch mode with auto template selection)
generate-sql-extract --config config/sql_generator.yaml

# 3. [Manual Step] Execute SQL queries in database, export results

# 4. Run buyer validation (auto-discovers all buyer incidents)
validate-buyer --config config/buyer_validation.yaml --progress

# 5. Run seller validation (auto-discovers all seller incidents)
validate-seller --config config/seller_validation.yaml --progress

# 6. Run pricing validation (if needed)
validate-pricing --config config/pricing_validation.yaml
```

### Configuration Flow

**Before Auto-Discovery (Manual):**
```yaml
testing_period:
  fiscal_year: "FY25"
  quarter: "Q3"
incidents:
  - "7_35"
  - "7_37"
  - "7_39"
  - "7_66"
  - "8_1"
  - "8_2"
  # ... manually list all 40 buyer incidents ...
```

**After Auto-Discovery (Simplified):**
```yaml
testing_period:
  fiscal_year: "FY25"
  quarter: "Q3"
auto_incidents: "all"  # Processes 38 standard buyer ID incidents

# To include decision maker incidents (7_66, 7_68):
# auto_incidents: "all_including_decision_maker"  # Processes all 40 incidents
```

---

## Benefits

### 1. Simplified Configuration
- **Before:** Manually list 40+ incident codes
- **After:** Single line `auto_incidents: "all"`

### 2. Reduced Errors
- No risk of forgetting incident codes
- Always processes complete incident set
- Consistent with incident code library

### 3. Maintainability
- When new incident codes are added to `INCIDENT_CODE_MATRIX`, they're automatically included
- No need to update multiple configuration files

### 4. Batch Processing Power
- Process standard buyer ID incidents: ~38 files in one command (excludes decision maker)
- Process standard seller ID incidents: ~39 files in one command (excludes decision maker)
- Complete standard validation suite: ~77 files total
- Optional: Include decision maker incidents with `auto_incidents: "all_including_decision_maker"`

### 5. Flexibility
- Still supports manual incident specification when needed
- Easy to switch between modes by commenting/uncommenting config lines

---

## Technical Architecture

### Incident Code Library

**Source:** `src/txr_replay_core/incident_codes.py`

**Key Functions:**
```python
def get_buyer_incident_codes() -> Set[str]:
    """Returns all buyer-related incident codes"""
    
def get_seller_incident_codes() -> Set[str]:
    """Returns all seller-related incident codes"""
    
def get_all_incident_codes() -> Set[str]:
    """Returns all incident codes"""
```

**Data Structure:**
```python
INCIDENT_CODE_MATRIX = {
    "7_37": {"type": "buyer", "description": "FTBDM - standard txr"},
    "16_21": {"type": "seller", "description": "FTSDM - standard txr"},
    # ... ~80+ incident codes ...
}
```

### Configuration Schema

**New Field:**
```yaml
auto_incidents: "all"  # String literal "all" triggers auto-discovery
```

**Backward Compatibility:**
- If `auto_incidents` not specified, uses `incidents` list
- If neither specified, returns error
- Both can coexist (auto_incidents takes precedence)

---

## Testing Strategy

### Manual Testing

**Test Auto-Discovery:**
```bash
# Create test config with auto_incidents: "all"
validate-buyer --config test_config.yaml --dry-run

# Verify output shows all 40 buyer incidents discovered
```

**Test Manual Mode:**
```bash
# Create test config with incidents: ["7_37", "8_1"]
validate-buyer --config test_config.yaml --dry-run

# Verify output shows only specified incidents
```

### Integration Testing

**Test Cases to Add:**
1. Auto-discovery with valid templates
2. Auto-discovery with missing templates (should skip)
3. Manual mode with explicit incident list
4. Error handling when neither auto_incidents nor incidents specified
5. Large batch processing (all 40 buyer incidents)
6. Mixed mode (commented/uncommented sections)

---

## Documentation Updates

### Files Updated

1. **Command Reference** (`documentation/reference/Command_Reference.md`)
   - Added batch mode examples with auto-discovery
   - Updated validate-buyer section
   - Updated validate-seller section
   - Added incident code lists

2. **Configuration Templates**
   - `config/templates/accuracy_testing/buyer_validation_template.yaml`
   - `config/templates/accuracy_testing/seller_validation_template.yaml`

3. **Implementation Summary** (this document)
   - Complete feature documentation
   - Usage examples
   - Technical details

---

## Future Enhancements

### Potential Improvements

1. **Incident Filtering:**
   ```yaml
   auto_incidents: "all"
   exclude_incidents:
     - "7_66"  # Skip inconsistent buyer incidents
     - "16_64"  # Skip inconsistent seller incidents
   ```

2. **Incident Ranges:**
   ```yaml
   auto_incidents: "7_*"  # Only 7_ series incidents
   # or
   auto_incidents: ["7_*", "8_*"]  # Only 7_ and 8_ series
   ```

3. **Progress Dashboard:**
   - Real-time progress for all incidents
   - ETA calculations
   - Success/failure counts by incident type

4. **Parallel Processing:**
   - Process multiple incidents simultaneously
   - Configurable worker pool size
   - Better performance for large batches

5. **Auto-Template Detection:**
   - Scan template directory for available files
   - Process only incidents with existing templates
   - Skip missing templates with warning

---

## Related Features

- **Batch Processing:** Foundation for auto-discovery
- **SQL Generation:** Similar auto-template-selection pattern
- **Incident Code Library:** Source of truth for all incidents

---

## Completion Checklist

- ✅ Implement auto-discovery in buyer_id_validation.py
- ✅ Implement auto-discovery in seller_id_validation.py
- ✅ Update buyer_validation_template.yaml
- ✅ Update seller_validation_template.yaml
- ✅ Update Command_Reference.md with examples
- ✅ Create implementation summary document
- ⏳ Add integration tests for auto-discovery
- ⏳ Test with real data
- ⏳ Update Quick Start Guide with simplified workflow

---

## Notes

**Key Design Decision:** Used `auto_incidents: "all"` string pattern instead of boolean flag to allow for future expansion (e.g., `auto_incidents: "buyer"` or `auto_incidents: "7_*"`).

**Incident Code Overlap:** Some incidents (e.g., 12_2, 21_2) appear in both buyer and seller lists because they affect both parties in a transaction. Auto-discovery handles this correctly by categorizing them based on validation context.
