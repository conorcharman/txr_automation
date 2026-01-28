# ID Logic Validation Implementation

## Overview
Comprehensive ID logic validation has been implemented to reduce false CONCAT generation by validating embedded DOB and gender information within NIDN codes across 14 European countries.

## Current Status: ✅ COMPLETE

All 14 country validators have been implemented in `src/accuracy_testing/id_logic_validator.py`:

### Implemented Validators

#### 1. **Belgium (BE) - NIDN**
- **Format**: YYMMDD + sequence (3 digits) + check digit (2 digits)
- **DOB Logic**: YYMMDD format (positions 1-6)
- **Gender Logic**: Sequence number odd=Male, even=Female
- **Check Digit**: Modulus 97 algorithm (handles 2000+ births with '2' prefix)
- **Century Handling**: Pre-2000 vs post-2000 distinction

#### 2. **Bulgaria (BG) - NIDN**
- **Format**: YYMMDD + region (2 digits) + sequence + check digit
- **DOB Logic**: YYMMDD format (positions 1-6)
- **Gender Logic**: Position 9 - even=Male, odd=Female
- **Check Digit**: Weighted sum [2,4,8,5,10,9,7,3,6] modulus 11

#### 3. **Czech Republic (CZ) - NIDN**
- **Format**: YYMMDD + sequence (3-4 digits) + optional check digit
- **DOB Logic**: YYMMDD with month offset for females
- **Gender Logic**: Month +50 or +70 = Female, normal = Male
- **Check Digit**: Modulus 11 (for 10-digit numbers post-1954)

#### 4. **Denmark (DK) - NIDN**
- **Format**: DDMMYY + sequence (4 digits)
- **DOB Logic**: DDMMYY format (positions 1-6)
- **Check Digit**: None

#### 5. **Estonia (EE) - NIDN**
- **Format**: Gender/century code + YYMMDD + sequence + check digit
- **DOB Logic**: YYMMDD format (positions 2-7)
- **Gender & Century Code**: 
  - 1/2 = Male/Female 1800s
  - 3/4 = Male/Female 1900s
  - 5/6 = Male/Female 2000s
- **Check Digit**: Two-stage modulus 11
  - Stage 1 weights: [1,2,3,4,5,6,7,8,9,1]
  - If result = 10, Stage 2 weights: [3,4,5,6,7,8,9,1,2,3]

#### 6. **Finland (FI) - NIDN**
- **Format**: DDMMYY + century char + sequence + check char
- **DOB Logic**: DDMMYY format (positions 1-6)
- **Century Char**: + = 1800s, - = 1900s, A = 2000s
- **Gender Logic**: Sequence (positions 7-9) odd=Male, even=Female
- **Check Character**: Modulus 31 character mapping
  - Characters: '0123456789ABCDEFHJKLMNPRSTUVWXY'

#### 7. **Iceland (IS) - NIDN**
- **Format**: DDMMYY + sequence (4 digits)
- **DOB Logic**: DDMMYY format (positions 1-6)
- **Check Digit**: None

#### 8. **Italy (IT) - NIDN (Fiscal Code)**
- **Format**: 16-character alphanumeric fiscal code
- **DOB Logic**: Positions 7-11 encode year/month/day
- **Month Encoding**: Letters A-T (excluding I,J,K,N,O,Q,U,W,X,Y,Z)
- **Gender Logic**: Day +40 for females (positions 10-11)
- **Century Handling**: 50-99 = 1900s, 00-49 = 2000s

#### 9. **Lithuania (LT) - NIDN**
- **Format**: Gender code + YYMMDD + sequence (4 digits)
- **DOB Logic**: YYMMDD format (positions 2-7)
- **Gender & Century Code**:
  - 3 = Male 1900s
  - 4 = Female 1900s
  - 5 = Male 2000s
  - 6 = Female 2000s

#### 10. **Latvia (LV) - NIDN**
- **Format**: DDMMYY + hyphen + century code + sequence
- **DOB Logic**: DDMMYY format (positions 1-6)
- **Century Code**: 0=1800s, 1=1900s, 2=2000s

#### 11. **Norway (NO) - NIDN**
- **Format**: DDMMYY + sequence (5 digits)
- **DOB Logic**: DDMMYY format (positions 1-6)
- **Check Digit**: None

#### 12. **Romania (RO) - NIDN**
- **Format**: Gender/century + YYMMDD + region + sequence + check digit
- **DOB Logic**: YYMMDD format (positions 2-7)
- **Gender & Century Code**:
  - 1/2 = Male/Female 1900s
  - 3/4 = Male/Female 1800s
  - 5/6 = Male/Female 2000s
- **Check Digit**: Weighted sum [2,7,9,1,4,6,3,5,8,2,7,9] modulus 11 (if 10→1)

#### 13. **Sweden (SE) - NIDN**
- **Format**: CCYYMMDD + sequence (3 digits) + check digit
- **DOB Logic**: Full date CCYYMMDD (positions 1-8)
- **Gender Logic**: Position 10 (penultimate) odd=Male, even=Female
- **Check Digit**: Luhn algorithm

#### 14. **Slovenia (SI) - NIDN**
- **Format**: DDMMYYY + sequence (5 digits) + check digit
- **DOB Logic**: DDMMYYY format (YYY = year - 1000)
- **Gender Logic**: Sequence 000-499=Male, 500-999=Female
- **Check Digit**: Weighted sum [7,6,5,4,3,2,7,6,5,4,3,2] modulus 11
  - Reject if remainder = 1
  - If remainder = 11, check digit = 0

#### 15. **Slovakia (SK) - NIDN**
- **Format**: YYMMDD + sequence (4 digits)
- **DOB Logic**: YYMMDD with month offset for females
- **Gender Logic**: Month +50 = Female, normal = Male
- **Check Digit**: Entire 10-digit number divisible by 11 (post-1954)

## Implementation Details

### Module Structure
```
src/accuracy_testing/id_logic_validator.py
├── IDLogicValidator (main class)
│   ├── validate_id_logic() - Entry point
│   ├── Country-specific validators (14 methods)
│   │   ├── _validate_belgian_nidn()
│   │   ├── _validate_bulgarian_nidn()
│   │   ├── _validate_czech_nidn()
│   │   ├── _validate_danish_nidn()
│   │   ├── _validate_estonian_nidn()
│   │   ├── _validate_finnish_nidn()
│   │   ├── _validate_icelandic_nidn()
│   │   ├── _validate_italian_nidn()
│   │   ├── _validate_lithuanian_nidn()
│   │   ├── _validate_latvian_nidn()
│   │   ├── _validate_norwegian_nidn()
│   │   ├── _validate_romanian_nidn()
│   │   ├── _validate_swedish_nidn()
│   │   ├── _validate_slovenian_nidn()
│   │   └── _validate_slovak_nidn()
│   └── Helper methods
│       ├── _extract_dob_yymmdd()
│       ├── _extract_dob_ddmmyy()
│       ├── _compare_dob()
│       ├── _compare_gender()
│       └── _normalize_date()
```

### Integration with Processor

The ID logic validator is integrated into the validation pipeline in `src/accuracy_testing/processor.py`:

```python
# In IDValidationProcessor.__init__()
self.id_logic_validator = IDLogicValidator(verbose=verbose)

# In process_record()
# After format validation passes
if record.validation_status == 'VALID':
    if not self.id_logic_validator.validate_id_logic(
        id_value=record.id_value,
        id_type=record.id_type,
        country_code=record.country_code,
        dob=record.dob,
        gender=record.gender
    ):
        record.validation_status = 'INVALID'
        record.validation_error = f'INVALID: {record.id_type} | Logic check failed'
        record.actions_taken = f'INVALID: {record.id_type} | Logic check failed'
```

### Validation Flow

1. **Entry Point**: `validate_id_logic()` receives ID, type, country, DOB, gender
2. **Type Check**: Only validates NIDN type IDs (returns True for other types)
3. **Country Routing**: Routes to appropriate country validator based on country code
4. **DOB Extraction**: Extracts embedded DOB from ID structure
5. **DOB Comparison**: Compares extracted DOB against provided DOB
6. **Gender Extraction**: Extracts embedded gender from ID structure
7. **Gender Comparison**: Compares extracted gender against provided gender
8. **Check Digit Validation**: Validates check digits using country-specific algorithms
9. **Result**: Returns False if any mismatch, True otherwise

### Check Digit Algorithms Implemented

1. **Modulus 97** (Belgium)
   - Calculate: 97 - (number % 97)

2. **Modulus 11 Weighted** (Bulgaria, Romania)
   - Country-specific weight arrays
   - Sum = Σ(digit[i] × weight[i])
   - Check = Sum % 11

3. **Modulus 11 Two-Stage** (Estonia)
   - Stage 1 with weights [1,2,3,4,5,6,7,8,9,1]
   - If result = 10, Stage 2 with weights [3,4,5,6,7,8,9,1,2,3]

4. **Modulus 11 Simple** (Czech Republic)
   - For 10-digit numbers only
   - Entire number % 11 = 0

5. **Divisibility by 11** (Slovakia)
   - For post-1954 births
   - Entire number % 11 = 0

6. **Luhn Algorithm** (Sweden)
   - Double every other digit
   - If doubled digit > 9, subtract 9
   - Sum all digits
   - Check = (10 - (sum % 10)) % 10

7. **Modulus 31 Character Mapping** (Finland)
   - Characters: '0123456789ABCDEFHJKLMNPRSTUVWXY'
   - Index = number % 31

8. **Weighted Sum with Special Rules** (Slovenia)
   - Weights: [7,6,5,4,3,2,7,6,5,4,3,2]
   - Reject if remainder = 1
   - If remainder = 11, check digit = 0

## Expected Impact

### Goal
Reduce CONCAT generation from **390** (current) to closer to **347** (VBA baseline).

### How It Helps
- IDs with valid format but embedded DOB/gender mismatches will now be marked INVALID
- This triggers correction attempts instead of immediately generating CONCAT
- Reduces false positives where format is correct but data doesn't match

### Example Scenarios

**Scenario 1: Belgian NIDN with wrong DOB**
- Provided DOB: 1985-10-15
- NIDN: 850110-123-45 (encodes 1985-01-10)
- **Old behavior**: VALID (format correct) → CONCAT if doesn't match
- **New behavior**: INVALID (logic check fails) → Attempt correction

**Scenario 2: Swedish NIDN with wrong gender**
- Provided Gender: F
- NIDN: 198510151234 (last digit before check = 3, odd = Male)
- **Old behavior**: VALID (format correct) → CONCAT
- **New behavior**: INVALID (gender mismatch) → Attempt correction

**Scenario 3: Estonian NIDN with invalid check digit**
- NIDN: 38501101234 (check digit wrong)
- **Old behavior**: VALID (format correct) → CONCAT
- **New behavior**: INVALID (check digit fails) → Attempt correction

## Testing Recommendations

1. **Run buyer_id_validation.py** on full dataset
2. **Compare CONCAT count** to previous 390 baseline
3. **Analyze INVALID records** with "Logic check failed" error
4. **Verify corrections attempted** for previously false positives
5. **Check verbose output** to see specific failures

## Next Steps

1. ✅ **COMPLETE**: Implement all 14 country validators
2. ✅ **COMPLETE**: Add helper methods for DOB extraction/comparison
3. ✅ **COMPLETE**: Integrate into validation pipeline
4. **TODO**: Run validation and measure CONCAT reduction
5. **TODO**: Apply same logic to seller_id_validation.py
6. **TODO**: Document any edge cases discovered during testing
7. **TODO**: Consider adding unit tests for each validator

## Reference
- Source specification: `documentation/reference_data/Check Logic Conditions.yml`
- Implementation: `src/accuracy_testing/id_logic_validator.py`
- Integration: `src/accuracy_testing/processor.py` (lines 80-85, 330-340)
- Related: VBA reference scripts in `legacy/vba/`
