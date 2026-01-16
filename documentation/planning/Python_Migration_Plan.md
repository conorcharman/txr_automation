# Transaction Reporting Automation: VBA to Python Migration Plan

**Version:** 2.1  
**Date:** 23 December 2025  
**Status:** Phase 0 In Progress  

---

## Git Branch Strategy

**Phase 0 (Refactoring):** Use `phase0-refactoring` branch  
**Phases 1-7 (VBA Migration):** Use `vba-migration` branch (created after Phase 0 completes)

See [Git_Branching_Guide.md](Git_Branching_Guide.md) for detailed instructions on:

- Branch creation and workflow
- Commit best practices
- Merging strategies

**Quick Reference:**

```bash
# Currently on Phase 0
git checkout phase0-refactoring

# When starting VBA migration (after Phase 0 merges to main)
git checkout main
git pull origin main
git checkout -b vba-migration
git push -u origin vba-migration
```

---

## Executive Summary

This document outlines the comprehensive plan to migrate transaction reporting automation from VBA macros to Python scripts. The migration eliminates Excel dependencies in favor of CSV-based workflows, significantly reducing complexity and improving performance.

### Key Benefits of CSV-First Approach

- **40-50% reduction in code complexity** (no Excel library dependencies)
- **5-10x performance improvement** (CSV I/O vs Excel)
- **Platform independence** (no Windows/Excel requirements)
- **Better version control** (plain text diffs)
- **Simplified testing** (easy to create test fixtures)
- **Cloud/container ready** (no GUI dependencies)

---

## Questions & Answers

### 1. How difficult would this be?

**Difficulty Level: Moderate** (reduced from "Moderate to Complex")

The CSV-first approach significantly reduces conversion complexity:

- **Code Volume**: Still substantial (10,000+ lines of VBA), but simpler to convert
- **Business Logic**: Complex validation logic remains, but I/O is much simpler
- **Dependencies**: Minimal - just `pandas`, `pytest`, and standard library
- **Excel Integration**: ELIMINATED - major simplification
- **File Operations**: Simple CSV read/write operations
- **Testing**: Easier with plain text fixtures

### 2. How would you approach conversion to ensure full functionality?

**Multi-Phase Validation Approach:**

1. **Decomposition & Documentation**
   - Map all VBA functions to business logic requirements
   - Document data structures (ClientRecord, ValidationContext)
   - Identify shared functions across macros
   - Define CSV schemas for all inputs/outputs

2. **CSV Schema Definition**
   - Document expected columns for each input file type
   - Define validation rules for CSV structure
   - Create sample CSV files for testing
   - Implement schema validation in Python

3. **Incremental Conversion with Testing**
   - Convert one macro at a time, starting with simpler ones
   - Create unit tests for each validation function
   - Build integration tests using CSV test fixtures
   - Compare Python CSV outputs with VBA Excel outputs (converted to CSV)

4. **Parallel Running Period**
   - Run both VBA and Python versions side-by-side
   - Convert Excel outputs to CSV for comparison
   - Identify and resolve discrepancies
   - Iterate until outputs match exactly

5. **Reference Data Management**
   - Load `country_codes.csv` and `id_formats.csv` at initialization
   - Cache regex patterns for performance
   - Use pandas DataFrames for efficient lookups

### 3. How will you ensure consistency throughout the project?

**Standardization Framework:**

1. **Create Shared Core Library** (`txr_core` module)

   ```markdown
   txr_core/
   ├── __init__.py
   ├── config.py          # Configuration constants
   ├── data_structures.py # ClientRecord, ValidationContext classes
   ├── validators.py      # Core validation functions
   ├── id_validation.py   # ID format/logic validation
   ├── reference_data.py  # Country codes, ID formats loader
   ├── csv_utils.py       # CSV reading/writing utilities
   ├── regex_engine.py    # Regex pattern matching
   └── schema.py          # CSV schema definitions & validation
   ```

2. **Common Functions Must Be Identical**
   - ID validation logic (NIDN, CONCAT, CCPT)
   - Date parsing and formatting
   - Country code lookups
   - Regex pattern matching
   - Swedish century logic
   - Joint account aggregation
   - CSV reading/writing with consistent encoding

3. **Shared Configuration**
   - All file paths in one config file (`config/settings.yaml`)
   - Column mappings defined centrally in schema module
   - Incident code metadata centralized
   - CSV schemas versioned and validated

4. **Code Review & Testing Protocol**
   - Each script imports from shared core
   - Unit tests verify shared functions
   - Integration tests use CSV fixtures
   - Style guide enforcement (PEP 8, type hints)
   - Pre-commit hooks for code quality

### 4. How will you handle inconsistencies in existing VBA macros?

**Normalization Strategy:**

1. **Standardize Structure**
   - All scripts follow the same pattern:

     ```python
     1. Parse CLI arguments
     2. Load configuration
     3. Validate input CSV schema
     4. Load reference data (cached)
     5. Process records (batch/stream)
     6. Validate outputs
     7. Write results to CSV
     8. Generate summary report
     ```

2. **Unified Data Structures**
   - Use same `ClientRecord` dataclass across all scripts
   - Consistent CSV column mappings
   - Standardized error handling and logging
   - Common result types (success/error tuples)

3. **Consistent Function Signatures**
   - Validation functions return same result types
   - Error handling follows same pattern
   - Logging structured identically (JSON format)
   - Type hints enforced throughout

4. **Document and Harmonize Divergences**
   - Where VBA macros differ in approach, analyze and document
   - Implement the most efficient approach consistently
   - Example: Joint account handling - choose single best method
   - Create decision log for architectural choices

### 5. How will you handle country_codes and id_formats data?

**External CSV Files (ALREADY IN PLACE)** ✅

**Implementation:**

```python
class ReferenceDataManager:
    """
    Singleton manager for reference data.
    Loads CSV files once and caches for all scripts.
    """
    _instance = None
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, data_dir: str = 'documentation'):
        if not ReferenceDataManager._loaded:
            self.data_dir = data_dir
            self.load_data()
            ReferenceDataManager._loaded = True
    
    def load_data(self):
        """Load all reference data from CSV files"""
        # Load country codes
        country_path = os.path.join(self.data_dir, 'country_codes.csv')
        self.country_df = pd.read_csv(country_path)
        self.country_dict = dict(zip(
            self.country_df['Alpha-2 code'], 
            self.country_df['Country']
        ))
        self.eea_dict = dict(zip(
            self.country_df['Alpha-2 code'],
            self.country_df['EEA?']
        ))
        
        # Load ID formats and compile regex patterns
        formats_path = os.path.join(self.data_dir, 'id_formats.csv')
        self.id_formats_df = pd.read_csv(formats_path)
        self.format_patterns = defaultdict(list)
        
        for _, row in self.id_formats_df.iterrows():
            country = row['Country Code in order of priority (descending)']
            id_type = row['ID Type  in order of priority (descending)']
            pattern = row['Regex']
            key = (country, id_type)
            self.format_patterns[key].append(re.compile(pattern))
        
        logging.info(f"Loaded {len(self.country_dict)} countries")
        logging.info(f"Loaded {len(self.format_patterns)} ID format patterns")
    
    def get_country_name(self, code: str) -> Optional[str]:
        """Get country name from 2-letter code"""
        return self.country_dict.get(code.upper())
    
    def is_eea_country(self, code: str) -> bool:
        """Check if country is in EEA"""
        return self.eea_dict.get(code.upper()) == 'Y'
    
    def validate_id_format(self, country_code: str, id_type: str, 
                          id_value: str) -> bool:
        """Validate ID against country/type patterns"""
        key = (country_code.upper(), id_type.upper())
        patterns = self.format_patterns.get(key, [])
        return any(pattern.match(id_value) for pattern in patterns)
```

**Why CSV Storage:**

- ✅ Already in place in `documentation/` folder
- ✅ Easy to update without code changes
- ✅ Same data shared across all scripts
- ✅ Version controlled with code
- ✅ Non-technical users can update
- ✅ Plain text = easy to review/audit

---

## Comprehensive Conversion Plan

### **Phase 1: Foundation (Weeks 1-2)**

**Objectives:**

- Create shared core library with CSV utilities
- Establish testing framework with CSV fixtures
- Document all business rules and CSV schemas
- Set up development environment

**Deliverables:**

1. **`txr_core` Package Structure**

   ```md
   txr_core/
   ├── __init__.py
   ├── config.py              # Configuration management
   ├── data_structures.py     # Dataclasses for records
   ├── validators.py          # Core validation logic
   ├── id_validation.py       # ID-specific validation
   ├── reference_data.py      # ReferenceDataManager
   ├── csv_utils.py           # CSV I/O utilities
   ├── regex_engine.py        # Compiled regex patterns
   ├── schema.py              # CSV schema definitions
   └── logger.py              # Structured logging
   ```

2. **CSV Schema Definitions**
   - Document all input CSV formats
   - Define validation rules (column names, types, constraints)
   - Create `schemas/` directory with JSON schema files
   - Implement schema validator class

3. **Testing Framework**

   ```markdown
   tests/
   ├── conftest.py                    # pytest fixtures
   ├── fixtures/                      # CSV test data
   │   ├── buyer_id_validation/
   │   ├── seller_id_validation/
   │   └── reference_data/
   ├── unit/
   │   ├── test_validators.py
   │   ├── test_id_validation.py
   │   ├── test_reference_data.py
   │   └── test_csv_utils.py
   └── integration/
       └── test_end_to_end.py
   ```

4. **Documentation**
   - VBA→Python function mapping document
   - CSV schema documentation
   - Development setup guide
   - Testing guidelines

**Activities:**

- Extract shared functions from VBA macros
- Convert core validation logic to Python
- Set up pytest with CSV fixtures
- Create sample CSV files for each macro type
- Implement `ReferenceDataManager` class
- Create `CSVValidator` class for schema checking
- Set up logging infrastructure
- Configure CI/CD pipeline

**Success Criteria:**

- ✅ Core library modules created and documented
- ✅ Reference data loader working with tests
- ✅ CSV schema validator implemented
- ✅ Test framework running successfully
- ✅ All developers can run tests locally

---

### **Phase 2: Simple Scripts First (Weeks 3-4)**

**Priority Order:**

#### 1. **Pricing Data Validation** (pricing_data_validation_v1.0.vb → pricing_validation.py)

- **VBA Lines:** 120
- **Complexity:** LOW
- **Why First:** Pure calculation logic, no complex lookups
- **Input:** CSV with columns: Transaction_Ref, Net_Amount, Consideration, Interest
- **Output:** CSV with added columns: Error, Correction, Correction_Field, Total, Expected_Interest, Net_Difference

#### 2. **SQL Extract Generators**

- **ExtractBuyerID4_1.vb → extract_buyer_id.py**
- **ExtractInconsistentBuyerID1_0.vb → extract_inconsistent_buyer_id.py**
- **SCR_extract_generator_v1_0.vb → scr_extract_generator.py**
- **Complexity:** LOW-MEDIUM
- **Why Next:** String manipulation, file generation, no validation logic
- **Input:** CSV with transaction references
- **Output:** SQL files grouped by batch size

**Approach for Each:**

1. Define input CSV schema
2. Create test CSV fixtures
3. Implement core logic using `txr_core` utilities
4. Add CLI interface with `click`
5. Write unit tests
6. Compare outputs with VBA results (via CSV conversion)
7. Document usage and examples

**Testing Strategy:**

```python
# Example test structure
def test_pricing_validation_basic(tmp_path):
    """Test basic pricing validation logic"""
    # Given: Input CSV with test data
    input_csv = tmp_path / "input.csv"
    write_test_csv(input_csv, test_data)
    
    # When: Run validation
    output_csv = tmp_path / "output.csv"
    pricing_validation.process(input_csv, output_csv)
    
    # Then: Verify output matches expected
    result = pd.read_csv(output_csv)
    assert_csv_matches(result, expected_output)
```

**Success Criteria:**

- ✅ All 4 simple scripts converted and tested
- ✅ CLI interfaces working
- ✅ Outputs match VBA results exactly
- ✅ Performance benchmarks documented
- ✅ User documentation complete

---

### **Phase 3: Decision Maker Validation (Weeks 5-6)**

**Scripts:**

1. **ValidateFTBDM3_0.vb → validate_ftbdm.py** (Buyer Decision Maker)
2. **ValidateFTSDM3_0.vb → validate_ftsdm.py** (Seller Decision Maker)

**Complexity:** MEDIUM

**Key Features:**

- Account type determination
- Service level checks
- LEI lookups (from CSV file, not Excel)
- Branch code validation
- ID format validation

**CSV Structure:**

**Input:**

```csv
Transaction_Reference,Account_ID,Buyer_Code,Buyer_DM_Code,Product,Account_Type,Service_Level,Branch_Code
```

**LEI Reference CSV:**

```csv
Branch_Code,LEI
```

**Output (appends columns):**

```csv
...,Type_of_Buyer_ID_Code,Type_of_Buyer_DM_Code,Error,Correction,Correction_Field
```

**Approach:**

1. Define CSV schemas for inputs/outputs
2. Convert account type determination logic
3. Implement LEI lookup from CSV (not Excel)
4. Port ID format validation
5. Implement decision maker validation rules
6. Add comprehensive test cases
7. Performance test with large datasets

**Success Criteria:**

- ✅ Both scripts converted and tested
- ✅ LEI lookups working from CSV
- ✅ ID format validation accurate
- ✅ Error handling comprehensive
- ✅ Documentation complete

---

### **Phase 4: Core ID Validation (Weeks 7-10)**

**Scripts (in order):**

#### 1. **BuyerIDValidation5_6.vb → buyer_id_validation.py** (Week 7-8)

- **VBA Lines:** 1,853
- **Complexity:** HIGH
- **Key Features:**
  - Multi-step validation (format → logic → alternative types)
  - CONCAT generation and validation
  - Swedish century logic for NIDN
  - Joint account aggregation
  - Tracker file lookups (from CSV, not Excel)
  - Template lookups (deprecated - removed)
  - Correction priority hierarchy

#### 2. **SellerIDValidation5_6.vb → seller_id_validation.py** (Week 8-9)

- **VBA Lines:** 1,780
- **Complexity:** HIGH
- **Similar to Buyer but with seller-specific logic**

#### 3. **InconsistentBuyerIDValidation1_3.vb → inconsistent_buyer_id_validation.py** (Week 9-10)

- **VBA Lines:** 2,548
- **Complexity:** VERY HIGH
- **Key Features:**
  - Groups records by Person Code
  - Chronological sorting by Trade_Date_Time
  - Identifies inconsistent IDs across time
  - Only corrects invalid IDs
  - Uses most recent valid ID for correction
  - Alternating row highlighting (can be CSV metadata)

#### 4. **InconsistentSellerIDValidation1_3.vb → inconsistent_seller_id_validation.py** (Week 10)

- Similar to inconsistent buyer

**CSV Structures:**

**Input (Buyer/Seller ID Validation):**

```csv
Transaction_Reference,Account_ID,BEN_Link,OWN_Link,TPA_Link,Person_Code,Account_Type,
ID_Code,ID_Type,First_Name,Surname,DOB,Gender,Nationality_1,Nationality_2,
DM_ID_Code,DM_ID_Type,DM_First_Name,DM_Surname,DM_DOB
```

**Tracker CSV (replaces Excel tracker):**

```csv
Transaction_Reference,Tracker_Status,Comments,Last_Updated
```

**Output (appends columns):**

```csv
...,Correction,Correction_Field,Tracker_Status,Actions,Error_Flag,Kaizen_Error,Match
```

**Conversion Strategy:**

1. **Week 7: Core Buyer Validation**
   - Convert data structures to Python dataclasses
   - Implement multi-step validation pipeline
   - Port CONCAT generation logic
   - Implement Swedish century logic
   - Add fallback type testing
   - Create comprehensive unit tests

2. **Week 8: Buyer Validation Advanced Features**
   - Joint account aggregation logic
   - Tracker CSV integration (replaces Excel)
   - Remove template lookup (no longer needed)
   - Correction priority hierarchy
   - Integration testing
   - Performance optimization (indexing like Phase 3 processor)

3. **Week 8-9: Seller Validation**
   - Adapt buyer validation for seller
   - Reuse shared functions from `txr_core`
   - Test against buyer for consistency
   - Document differences

4. **Week 9-10: Inconsistent ID Validation**
   - Implement chronological grouping
   - Port ID consistency detection logic
   - Implement correction selection (most recent valid)
   - Add data sorting functionality
   - Implement block highlighting metadata in CSV
   - Extensive testing with complex scenarios

**Optimization Techniques (from existing Phase 3 processor):**

```python
class ClientRecordIndex:
    """
    Pre-build indexes for O(1) lookups
    (Pattern from phase_3_processor_v4_2.py)
    """
    def __init__(self, records_df: pd.DataFrame):
        # Build hash indexes
        self.person_code_index = defaultdict(list)
        self.id_value_index = {}
        
        for idx, row in records_df.iterrows():
            person_code = row['Person_Code']
            self.person_code_index[person_code].append(idx)
            
            id_value = row['ID_Code']
            if id_value not in self.id_value_index:
                self.id_value_index[id_value] = idx
    
    def lookup_by_person_code(self, person_code: str) -> List[int]:
        """O(1) lookup of all records for person"""
        return self.person_code_index.get(person_code, [])
```

**Success Criteria:**

- ✅ All 4 core validation scripts converted
- ✅ Shared validation logic in `txr_core`
- ✅ Performance meets or exceeds VBA (likely 5-10x faster)
- ✅ Output CSVs match VBA Excel outputs (converted)
- ✅ Comprehensive test coverage (>85%)
- ✅ Documentation complete

---

### **Phase 5: Data Operations (Weeks 11-12)**

**Scripts:**

#### 1. **IncidentLookup1_1.vb → incident_lookup.py** (Week 11)

- **Complexity:** MEDIUM
- **Function:** Looks up transaction references in validation CSVs
- **Changes:**
  - No Excel file to open - direct CSV reads
  - Much simpler without Excel COM operations
  - Can use pandas merge operations

**Input:**

```csv
Transaction_Reference
```

**Lookup CSV (previously in Excel):**

```csv
Transaction_Reference,Account_ID,Person_Code,Correction,Correction_Field,Tracker_Status,Actions
```

**Output:**

```csv
Transaction_Reference,Account_ID,Person_Code,Correction,Correction_Field,Tracker_Status,Actions
```

#### 2. **DataPush1_0.vb → data_push.py** (Week 11-12)

- **Complexity:** MEDIUM
- **Function:** Pushes data from source to target CSV files
- **Changes:**
  - No Excel file locking issues
  - Simple CSV read → merge → write
  - Can process in batch
  - Much faster than Excel

**Approach:**

```python
def data_push(source_csv: str, target_csv: str, 
              join_column: str = 'Transaction_Reference'):
    """
    Push data from source to target CSV based on transaction reference.
    Much simpler than VBA version - no Excel operations!
    """
    # Load CSVs
    source_df = pd.read_csv(source_csv)
    target_df = pd.read_csv(target_csv)
    
    # Merge and update
    merged = target_df.merge(
        source_df, 
        on=join_column, 
        how='left', 
        suffixes=('', '_new')
    )
    
    # Update specified columns
    for col in update_columns:
        merged[col] = merged[f'{col}_new'].combine_first(merged[col])
    
    # Write back
    merged.to_csv(target_csv, index=False)
    
    return len(merged)
```

**Success Criteria:**

- ✅ Both scripts converted and tested
- ✅ CSV operations working correctly
- ✅ Performance significantly improved vs Excel
- ✅ No file locking issues
- ✅ Documentation complete

---

### **Phase 6: Integration & Testing (Weeks 13-14)**

**Activities:**

1. **End-to-End Testing**
   - Create full workflow tests using real quarterly data
   - Test all scripts in sequence
   - Verify data flows correctly between scripts
   - Test error handling and recovery

2. **Performance Benchmarking**
   - Measure execution time for each script
   - Compare with VBA timings (where available)
   - Profile and optimize bottlenecks
   - Document performance characteristics

3. **Data Migration**
   - Convert existing Excel files to CSV
   - Create conversion utilities if needed
   - Validate converted data
   - Archive Excel files

4. **User Acceptance Testing**
   - Train users on new CSV workflow
   - Gather feedback on CLI interfaces
   - Test on user machines
   - Refine based on feedback

5. **Documentation**
   - Complete user guides for each script
   - Create quick reference cards
   - Document common troubleshooting
   - Create video tutorials (optional)

6. **Code Quality**
   - Final code review
   - Ensure >85% test coverage
   - Run static analysis (mypy, pylint)
   - Update all docstrings

**Test Suite Structure:**

```md
tests/
├── unit/                          # Fast isolated tests
│   ├── test_validators.py
│   ├── test_id_validation.py
│   ├── test_reference_data.py
│   ├── test_csv_utils.py
│   └── test_regex_engine.py
├── integration/                   # Script-level tests
│   ├── test_buyer_id_validation.py
│   ├── test_seller_id_validation.py
│   ├── test_pricing_validation.py
│   └── ...
├── end_to_end/                    # Full workflow tests
│   ├── test_quarterly_accuracy.py
│   └── test_replay_workflow.py
├── performance/                   # Benchmarks
│   └── test_performance.py
└── fixtures/                      # Test data (CSV files)
    ├── reference_data/
    ├── buyer_validation/
    └── ...
```

**Success Criteria:**

- ✅ All end-to-end tests passing
- ✅ Performance benchmarks documented
- ✅ User acceptance testing complete
- ✅ All documentation finalized
- ✅ Code quality metrics met (>85% coverage, no critical issues)
- ✅ Ready for production deployment

---

### **Phase 7: Deployment & Transition (Weeks 15-16)**

**Activities:**

1. **Production Environment Setup**
   - Set up Python environment on user machines
   - Configure file paths and settings
   - Test access to network drives
   - Set up logging directories

2. **Parallel Running Period** (2 weeks minimum)
   - Run VBA and Python versions side-by-side
   - Users export Excel to CSV for Python scripts
   - Compare all outputs
   - Track and fix any discrepancies
   - Build confidence in Python versions

3. **Cutover Plan**
   - Schedule cutover date
   - Create rollback plan
   - Define success criteria
   - Plan communication to stakeholders

4. **Training**
   - Conduct training sessions
   - Provide hands-on practice
   - Create cheat sheets
   - Set up support channel

5. **Monitoring**
   - Monitor initial production runs
   - Gather user feedback
   - Track execution times
   - Log any issues

6. **VBA Deprecation**
   - Archive VBA code
   - Document migration completion
   - Celebrate! 🎉

**Success Criteria:**

- ✅ All users trained
- ✅ Python scripts running in production
- ✅ No critical issues identified
- ✅ Users comfortable with new workflow
- ✅ VBA macros officially deprecated

---

## Risk Assessment & Mitigation

### **High Priority Risks**

| Risk | Impact | Probability | Mitigation |
| ------ | -------- | ------------- | ------------ |
| **Logic Errors in Conversion** | High | Medium | - Extensive testing with known datasets<br>- Side-by-side comparison (VBA vs Python)<br>- Independent code review<br>- 2-week parallel running period |
| **CSV Format Inconsistencies** | Medium | Medium | - Define strict CSV schemas<br>- Implement schema validation<br>- Provide CSV export templates<br>- Validate inputs before processing |
| **Data Migration Issues** | High | Low | - Create Excel→CSV conversion utilities<br>- Validate all converted data<br>- Keep Excel files as backup during transition |

### **Medium Priority Risks**

| Risk | Impact | Probability | Mitigation |
| ------ | -------- | ------------- | ------------ |
| **Regex Pattern Differences** | Medium | Low | - Test all patterns extensively<br>- Document Python regex differences<br>- Use raw strings consistently |
| **Date Parsing Edge Cases** | Low | Medium | - Implement robust DateParser class<br>- Test with various formats<br>- Handle missing/invalid dates gracefully |
| **Performance Issues** | Medium | Low | - Use indexing patterns (Phase 3 style)<br>- Profile and optimize<br>- Batch processing for large datasets |
| **User Adoption** | Medium | Medium | - Comprehensive training<br>- Good documentation<br>- Responsive support<br>- Gradual rollout |

### **Low Priority Risks**

| Risk | Impact | Probability | Mitigation |
| ------ |--------|-------------|------------|
| **Library Dependencies** | Low | Low | - Use standard libraries where possible<br>- Pin versions in requirements.txt<br>- Test in clean environment |
| **Platform Compatibility** | Low | Low | - Test on user machines early<br>- Document system requirements<br>- Use virtual environments |
| **Network Path Access** | Low | Low | - Test network access early<br>- Implement retry logic<br>- Consider local caching |

---

## Technical Architecture

### **Technology Stack**

```yaml
Core:
  - Python: 3.10+
  - pandas: 2.0+       # CSV/data manipulation
  - pytest: 7.0+       # Testing framework
  - click: 8.0+        # CLI interface

Optional:
  - pyyaml: 6.0+       # Configuration files
  - jsonschema: 4.0+   # CSV schema validation
  - rich: 13.0+        # Beautiful CLI output
  - tqdm: 4.0+         # Progress bars
```

**No Excel dependencies!** ✅

### **Project Structure**

```markdown
txr_automation/
├── txr_core/                           # Shared core library
│   ├── __init__.py
│   ├── config.py                       # Configuration management
│   ├── data_structures.py              # Dataclasses (ClientRecord, etc.)
│   ├── validators.py                   # Core validation functions
│   ├── id_validation.py                # ID format/logic validation
│   ├── reference_data.py               # ReferenceDataManager
│   ├── csv_utils.py                    # CSV I/O utilities
│   ├── regex_engine.py                 # Compiled regex patterns
│   ├── schema.py                       # CSV schema definitions
│   └── logger.py                       # Structured logging
│
├── scripts/                            # Individual automation scripts
│   ├── buyer_id_validation.py
│   ├── seller_id_validation.py
│   ├── inconsistent_buyer_id_validation.py
│   ├── inconsistent_seller_id_validation.py
│   ├── validate_ftbdm.py
│   ├── validate_ftsdm.py
│   ├── pricing_validation.py
│   ├── extract_buyer_id.py
│   ├── extract_inconsistent_buyer_id.py
│   ├── scr_extract_generator.py
│   ├── data_push.py
│   └── incident_lookup.py
│
├── tests/                              # Comprehensive test suite
│   ├── conftest.py                     # Pytest fixtures
│   ├── fixtures/                       # CSV test data
│   │   ├── reference_data/
│   │   ├── buyer_validation/
│   │   └── ...
│   ├── unit/                           # Fast unit tests
│   │   ├── test_validators.py
│   │   ├── test_id_validation.py
│   │   ├── test_reference_data.py
│   │   └── test_csv_utils.py
│   ├── integration/                    # Script-level tests
│   │   ├── test_buyer_id_validation.py
│   │   └── ...
│   ├── end_to_end/                     # Full workflow tests
│   │   └── test_quarterly_accuracy.py
│   └── performance/                    # Benchmarks
│       └── test_performance.py
│
├── documentation/                      # Reference data & docs
│   ├── country_codes.csv              # Already in place ✅
│   ├── id_formats.csv                 # Already in place ✅
│   ├── incident_fields.csv            # Already in place ✅
│   ├── schemas/                       # CSV schema definitions
│   │   ├── buyer_id_validation.json
│   │   ├── seller_id_validation.json
│   │   └── ...
│   └── user_guides/                   # User documentation
│       ├── getting_started.md
│       ├── buyer_id_validation.md
│       └── ...
│
├── config/                            # Configuration files
│   ├── settings.yaml                  # Main configuration
│   └── logging.yaml                   # Logging configuration
│
├── vba/                               # Legacy VBA (archived post-migration)
│   └── ...
│
├── python/                            # Current Python scripts (replay)
│   └── ...
│
├── requirements.txt                   # Python dependencies
├── setup.py                          # Package installation
├── pytest.ini                        # Pytest configuration
├── .gitignore
└── README.md
```

### **Key Design Patterns**

1. **Strategy Pattern** - Different validation strategies
2. **Factory Pattern** - Validator creation
3. **Singleton Pattern** - Reference data manager
4. **Template Method** - Common processing flow
5. **Builder Pattern** - CSV schema construction
6. **Observer Pattern** - Logging and auditing

### **CSV Schema Example**

```json
{
  "name": "buyer_id_validation_input",
  "version": "1.0",
  "description": "Input schema for Buyer ID Validation script",
  "columns": [
    {
      "name": "Transaction_Reference",
      "type": "string",
      "required": true,
      "pattern": "^[A-Z0-9]+$"
    },
    {
      "name": "Person_Code",
      "type": "string",
      "required": true
    },
    {
      "name": "Account_Type",
      "type": "string",
      "required": true,
      "enum": ["IND", "JNT", "SIPP", "CUSTODY SOLUTIONS"]
    },
    {
      "name": "ID_Code",
      "type": "string",
      "required": true
    },
    {
      "name": "DOB",
      "type": "date",
      "required": false,
      "formats": ["YYYY-MM-DD", "DD/MM/YYYY"]
    }
  ]
}
```

---

## Success Criteria

### **Functional Requirements**

- ✅ **Exact Functionality**: Python scripts produce identical results to VBA on test datasets
- ✅ **CSV I/O**: All scripts read/write CSVs correctly with proper encoding
- ✅ **Reference Data**: Country codes and ID formats loaded correctly
- ✅ **Validation Logic**: All validation rules implemented accurately
- ✅ **Error Handling**: Robust error handling with helpful messages
- ✅ **Schema Validation**: All input CSVs validated before processing

### **Performance Requirements**

- ✅ **Speed**: Python scripts run 5-10x faster than VBA (CSV vs Excel)
- ✅ **Memory**: Efficient memory usage for large datasets
- ✅ **Scalability**: Can handle 10,000+ records without issues

### **Quality Requirements**

- ✅ **Test Coverage**: >85% code coverage
- ✅ **Code Quality**: Pass pylint/mypy checks
- ✅ **Documentation**: All functions documented with docstrings
- ✅ **Type Hints**: All functions have complete type hints
- ✅ **Maintainability**: Code is modular and easy to understand

### **Operational Requirements**

- ✅ **User Training**: All users trained and comfortable
- ✅ **Documentation**: Complete user guides for all scripts
- ✅ **Support**: Clear support process established
- ✅ **Monitoring**: Execution logs and error tracking in place
- ✅ **Backup**: VBA code archived, rollback plan ready

---

## Timeline Summary

### **Complete Project Timeline**

| Phase | Duration | Focus | Key Deliverables |
| ------- | ---------- | ------- | ------------------ |
| **0. Python Refactoring** | 8 weeks | Refactor existing scripts | txr_replay_core, consistent CLI, tests |
| **1. Foundation** | 2 weeks | Core library, schemas, tests | txr_core package, CSV schemas, test framework |
| **2. Simple Scripts** | 2 weeks | Easy conversions | Pricing validation, SQL generators |
| **3. DM Validation** | 2 weeks | Medium complexity | FTBDM, FTSDM validation scripts |
| **4. Core ID Validation** | 4 weeks | High complexity | Buyer/Seller ID validation, Inconsistent ID scripts |
| **5. Data Operations** | 2 weeks | Lookups, data push | Incident lookup, data push scripts |
| **6. Integration & Testing** | 2 weeks | E2E tests, UAT | Complete test suite, documentation |
| **7. Deployment** | 2 weeks | Production rollout | Training, parallel running, cutover |
| **Total** | **24 weeks** | **6 months** | **Fully migrated system** |

### **Phase Breakdown:**

- **Weeks 1-8:** Refactor existing Python replay scripts (see [Existing_Python_Scripts_Refactoring_Plan.md](Existing_Python_Scripts_Refactoring_Plan.md))
- **Weeks 9-10:** Foundation for VBA migration
- **Weeks 11-22:** VBA conversion (12 weeks)
- **Weeks 23-24:** Final integration and deployment

**Critical Path:** Phase 0 (refactoring) must complete before VBA migration begins.

---

## Prerequisites: Existing Python Scripts Refactoring

⚠️ **IMPORTANT:** Before starting the VBA migration, the existing Python replay scripts must be refactored to establish consistent architecture and shared libraries.

### **Refactoring Timeline: 8 weeks (2 months)**

This work is detailed in **[Existing_Python_Scripts_Refactoring_Plan.md](Existing_Python_Scripts_Refactoring_Plan.md)** and must be completed first because:

1. **Establishes Shared Core Library** - The VBA conversion will use `txr_core` modules
2. **Defines Architecture Patterns** - CLI interfaces, configuration management, logging
3. **Creates Testing Framework** - Patterns to be reused for VBA conversions
4. **Eliminates Technical Debt** - Fixes inconsistencies before adding more code

### **Key Deliverables from Refactoring:**

- `txr_replay_core/` package with shared utilities
- Consistent CLI interfaces for all scripts
- Configuration management system
- CSV schema validation framework
- Comprehensive test suite
- Updated documentation

**Timeline Adjustment:** Add 8 weeks to the beginning of the project for refactoring.

**New Total Timeline:** 24 weeks (6 months) = 8 weeks refactoring + 16 weeks VBA migration

---

## Next Steps

### **Phase 0: Refactor Existing Python Scripts (Weeks 1-8)**

See **[Existing_Python_Scripts_Refactoring_Plan.md](Existing_Python_Scripts_Refactoring_Plan.md)** for detailed plan.

**Summary:**

- Weeks 1-2: Extract shared core library (`txr_replay_core`)
- Weeks 3-6: Refactor individual scripts (Phase 2, 3, 3 Final, XLSX Converter)
- Week 7: Integration testing and parallel running
- Week 8: Documentation and training

**Critical Success Factor:** All existing scripts must work identically after refactoring before proceeding to VBA migration.

---

### **Phase 1: Foundation (Weeks 9-10, formerly Weeks 1-2)**

**Note:** This phase now builds on the `txr_replay_core` library created during refactoring.

**Objectives:**

- Extend `txr_replay_core` for accuracy testing workflows
- Create `txr_core` package for VBA conversion
- Establish testing framework for VBA conversions
- Document all business rules and CSV schemas

**Activities:**

1. **Environment Setup**
   - [ ] Verify Python 3.10+ environment
   - [ ] Extend virtual environment with VBA conversion dependencies
   - [ ] Install additional dependencies (if needed)
   - [ ] Verify IDE setup for VBA conversion work

2. **Core Library Extension**
   - [ ] Create `txr_core/` directory structure (separate from `txr_replay_core`)
   - [ ] Identify shared code between replay and accuracy testing
   - [ ] Create adapter layer between `txr_replay_core` and `txr_core`
   - [ ] Port relevant utilities to `txr_core`

3. **Project Initialization**
   - [ ] Extend git repository structure
   - [ ] Update `requirements.txt` with VBA conversion needs
   - [ ] Extend CI/CD pipeline for VBA conversions
   - [ ] Set up project tracking for VBA migration phase

4. **Planning & Documentation**
   - [ ] Review and approve VBA migration plan (this document)
   - [ ] Schedule kickoff meeting for VBA migration
   - [ ] Identify additional stakeholders
   - [ ] Review existing VBA code in detail
   - [ ] Document current workflows
   - [ ] Create CSV templates for accuracy testing workflows
   - [ ] Define CSV schemas for accuracy testing

### **Week 9-10 Deliverables**

- `txr_core` package initialized (builds on `txr_replay_core`)
- `ReferenceDataManager` class implemented
- CSV utilities for accuracy testing
- VBA→Python function mapping document
- Test framework extended for VBA conversions
- Development environment fully documented

---

## Additional Recommendations

### **1. Version Control Strategy**

```markdown
main (production)
├── develop (integration)
│   ├── feature/phase-1-foundation
│   ├── feature/phase-2-simple-scripts
│   └── feature/phase-3-dm-validation
└── hotfix/critical-bug (if needed)
```

- Create feature branch for each phase
- Require code review before merging to develop
- Tag releases after each phase
- Protect main branch

### **2. CI/CD Pipeline**

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=txr_core --cov-report=html
      - run: pylint txr_core/
      - run: mypy txr_core/
```

### **3. Documentation Standards**

All functions must have docstrings:

```python
def validate_id_format(country_code: str, id_type: str, 
                      id_value: str) -> bool:
    """
    Validate ID value against country-specific format patterns.
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'GB', 'US')
        id_type: Type of ID (e.g., 'NIDN', 'CONCAT', 'CCPT')
        id_value: The ID value to validate
    
    Returns:
        True if ID matches country/type format, False otherwise
    
    Examples:
        >>> validate_id_format('GB', 'NIDN', 'AB123456C')
        True
        >>> validate_id_format('GB', 'NIDN', 'invalid')
        False
    
    Raises:
        ValueError: If country_code is not recognized
    """
```

### **4. Logging Standards**

Use structured logging:

```python
import logging
import json

logger = logging.getLogger(__name__)

# Log structured data
logger.info("Processing batch", extra={
    "batch_size": 100,
    "file_path": input_csv,
    "timestamp": datetime.now().isoformat()
})

# Log validation results
logger.warning("Validation failed", extra={
    "transaction_ref": txn_ref,
    "error": error_message,
    "row_number": row_num
})
```

### **5. Performance Monitoring**

Track performance metrics:

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(operation_name: str):
    """Context manager to time operations"""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"{operation_name} took {elapsed:.2f}s")

# Usage
with timer("Load reference data"):
    ref_data = ReferenceDataManager()

with timer("Process validation"):
    results = process_validation(records)
```

### **6. CSV Best Practices**

```python
# Always specify encoding
df = pd.read_csv(path, encoding='utf-8')

# Validate schema before processing
validate_csv_schema(df, expected_schema)

# Handle missing values consistently
df = df.fillna('')  # or pd.NA

# Write with proper quoting
df.to_csv(output_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
```

---

## Conclusion

**The CSV-first approach dramatically simplifies this migration:**

- **40-50% less complex** than Excel-based conversion
- **5-10x faster** performance expected
- **Much simpler** codebase to maintain
- **Better suited** for future automation and scaling

**Key Success Factors:**

1. ✅ Methodical phase-by-phase approach
2. ✅ Rigorous testing at every step
3. ✅ Shared core library ensures consistency
4. ✅ CSV schemas provide data validation
5. ✅ Comprehensive documentation supports long-term maintenance
6. ✅ Parallel running period builds confidence

**Timeline: 16 weeks (4 months)** for complete, well-tested migration.

---

## Appendices

### **Appendix A: CSV Templates**

Templates for all input CSVs will be created in `documentation/templates/`:

- `buyer_id_validation_input.csv`
- `seller_id_validation_input.csv`
- `inconsistent_buyer_id_validation_input.csv`
- `pricing_validation_input.csv`
- `lei_reference.csv`
- `tracker.csv`
- etc.

### **Appendix B: VBA to Python Function Mapping**

Detailed mapping document to be created in Phase 1.

### **Appendix C: Performance Benchmarks**

Performance comparison (VBA vs Python) to be documented in Phase 6.

### **Appendix D: Training Materials**

User guides and training materials to be created in Phase 6.

---

**Document Version History:**

- v2.0 (22 Dec 2025): Updated for CSV-first approach, removed Excel dependencies
- v1.0 (22 Dec 2025): Initial plan with Excel integration

**Approved By:** _[To be signed]_

**Date:** _[To be dated]_
