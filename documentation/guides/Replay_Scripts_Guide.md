# Replay Scripts Guide

This guide covers the four scripts in `src/replay/` that process quarterly replay files.
Each script reads YAML configuration, pre-indexes incident template data, and writes corrected
output CSVs (or Excel files) to a configured output directory.

---

## Overview

| Script | Console Command | Purpose |
|---|---|---|
| `phase_2_processor.py` | `phase2-processor` | Phase II replay — match by transaction reference |
| `phase_3_processor.py` | `phase3-processor` | Phase III replay — match by client ID or name/DOB |
| `phase_3_final_lookup.py` | `phase3-final-lookup` | Phase III final validation against UnaVista data |
| `merge_inconsistent_ids.py` | `merge-inconsistent-summaries` | Merge duplicate rows in Inconsistent IDs and Names Summaries |

---

## Correction Decision Logic

All lookup scripts (Phase II and III) apply the same correction decision logic, introduced
in v4.1/v5.1:

1. **If the "Correction" column has a value:**
   - "Agree With Correction" is `Y`, `P`, or empty → **Apply Correction**
   - "Agree With Correction" is `N` or `F` → Apply **Suggested Correction** (if present),
     otherwise **No Change**
2. **If the "Correction" column is empty:**
   - Apply **Suggested Correction** (if present), otherwise **No Change**

> **Note:** The "Error Flag" column (formerly used to gate corrections) is deprecated and
> ignored by all scripts.

---

## Phase II Processor

**Script:** `src/replay/phase_2_processor.py`  
**Config template:** `config/templates/replay/phase2_template.yaml`

### What it does

For each CSV replay file in the input directory, every row contains one or more incident
codes and a transaction reference. The script:

1. Pre-loads and indexes every relevant incident template file (O(1) lookup).
2. Looks up each transaction reference in the matching incident file.
3. Applies the correction decision logic to determine the correction value.
4. Writes a new CSV to the output directory with the "Agrees", "Correction Field", and
   "Correction Value" columns populated.

Filenames containing `+` are treated as **combined incident files** (multiple incident codes
per row); all other files are treated as **single incident files**.

### Running the script

```bash
# From project root, with the conda environment active
python -m src.replay.phase_2_processor --config config/local/replay/phase2.yaml

# Override log level
python -m src.replay.phase_2_processor --config config/local/replay/phase2.yaml --log-level DEBUG

# Load paths from environment variables (TXR_* prefix)
python -m src.replay.phase_2_processor --use-env
```

If no `--config` flag is given, the script falls back to
`config/local/replay/phase2.yaml` automatically.

### Configuration

Copy `config/templates/replay/phase2_template.yaml` to
`config/local/replay/phase2.yaml` and fill in your paths.

```yaml
paths:
  replay_input:    "/path/to/phase_ii/csv"          # Input replay CSVs
  incident_files:  "/path/to/incident_code_files"   # Incident template CSVs
  replay_output:   "/path/to/output"                # Output directory
  log_output:      "/path/to/output/logs"           # Log directory

files:
  replay_patterns:
    - "*.csv"
  # Primary format: "FY25 Q4 7_39.csv"
  # Fallback format: "FY25 Q4 - 7_39.csv"
  incident_pattern: "FY25 Q4 *.csv"

incident_columns:
  transaction_ref:           "Transaction Reference"
  correction:                "Correction"
  correction_field:          "Correction Field"
  agree_with_correction:     "Agree With Correction"
  suggested_correction:      "Suggested Correction"
  suggested_correction_field: "Suggested Correction Field"

processor:
  batch_size: 50
  log_level: "INFO"
  replace_pattern:      # Optional: rename output files
    from: "KR"
    to:   "AJB"
```

#### Key settings

| Setting | Description |
|---|---|
| `incident_pattern` | Glob pattern used to find incident files, e.g. `"FY25 Q4 *.csv"` |
| `incident_columns` | Maps logical names to the exact column headers in your incident files |
| `replace_pattern` | Optional find-and-replace applied to output filenames |
| `batch_size` | Number of rows processed between progress log entries |

---

## Phase III Processor

**Script:** `src/replay/phase_3_processor.py`  
**Config template:** `config/templates/replay/phase3_template.yaml`

### What it does

Phase III replay files contain clients with inconsistent IDs or names. The script:

1. Pre-loads and indexes incident template files by buyer/seller ID and by
   name + date of birth.
2. For each replay record, attempts to match in this order:
   - **ID match** (exact, case-insensitive)
   - **Name + DOB match** (exact)
   - **Fuzzy name match** (configurable similarity threshold, default 0.85)
   - **Decision Maker fallback** — same hierarchy applied to decision maker columns
3. When multiple incident files share the same ID, the script disambiguates by checking
   the client name to select the correct row (v5.1 fix).
4. Writes corrected output CSVs with columns 6 and 7 (Correction and Correction Field)
   populated.

Filenames containing `IDs` are processed as ID-type replay files; filenames containing
`Names` are processed as name-type replay files.

### Running the script

```bash
python -m src.replay.phase_3_processor --config config/local/replay/phase3.yaml

python -m src.replay.phase_3_processor --config config/local/replay/phase3.yaml --log-level DEBUG

python -m src.replay.phase_3_processor --use-env
```

If no `--config` flag is given, the script falls back to
`config/local/replay/phase3.yaml` automatically.

### Configuration

Copy `config/templates/replay/phase3_template.yaml` to
`config/local/replay/phase3.yaml` and fill in your paths.

```yaml
paths:
  replay_input:    'C:\path\to\phase_iii\csv'
  incident_files:  'C:\path\to\incident_code_analysis'
  replay_output:   'C:\path\to\output'
  log_output:      'C:\path\to\output\logs'

files:
  replay_patterns:
    - "Replay_*_PHASE 3_Inconsistent_IDs_Summary_FINAL.csv"
    - "Replay_*_PHASE 3_Inconsistent_Names_Summary_FINAL.csv"
  incident_pattern: "FY25 Q4 *.csv"

incident_columns:
  # Correction columns
  transaction_ref:            "Transaction Reference"
  correction:                 "Correction"
  correction_field:           "Correction Field"
  agree_with_correction:      "Agree With Correction"
  suggested_correction:       "Suggested Correction"
  suggested_correction_field: "Suggested Correction Field"

  # Matching columns — buyer
  buyer_id:         "Buyer identification code"
  buyer_first_name: "Buyer - First name(s)"
  buyer_last_name:  "Buyer - Surname(s)"
  buyer_dob:        "Buyer - Date of birth"

  # Matching columns — seller
  seller_id:         "Seller identification code"
  seller_first_name: "Seller - First name(s)"
  seller_last_name:  "Seller - Surname(s)"
  seller_dob:        "Seller - Date of birth"

  # Decision Maker fallback columns (optional)
  buyer_dm_id:          "Buyer decision maker code"
  buyer_dm_first_name:  "Buy decision maker - First name(s)"
  buyer_dm_last_name:   "Buy decision maker - Surname(s)"
  buyer_dm_dob:         "Buy decision maker - Date of birth"
  seller_dm_id:         "Seller decision maker code"
  seller_dm_first_name: "Sell decision maker - First name(s)"
  seller_dm_last_name:  "Sell decision maker - Surname(s)"
  seller_dm_dob:        "Sell decision maker - Date of birth"

processor:
  batch_size: 100
  log_level: "INFO"
  similarity_threshold: 0.85   # Fuzzy name matching threshold (0.0–1.0)
  replace_pattern:
    from: "_FINAL"
    to:   "_AJB"
```

#### Key settings

| Setting | Description |
|---|---|
| `replay_patterns` | Glob patterns to discover replay input files |
| `incident_columns` | Maps logical names to exact column headers; include Decision Maker columns for fallback matching |
| `similarity_threshold` | Minimum score (0.0–1.0) for fuzzy name matching; lower values are more permissive |
| `replace_pattern` | Optional find-and-replace applied to output filenames |

---

## Phase III Final Lookup

**Script:** `src/replay/phase_3_final_lookup.py`  
**Config template:** `config/templates/replay/phase3_final_template.yaml`

### What it does

This script is run **after** the Phase III Processor. It validates the corrections produced
during Phase III against the live UnaVista transaction data:

1. Loads the Phase III corrected output CSVs (IDs and Names files).
2. For each client (identified by ID + name + DOB), merges corrections from IDs and Names
   sources, flagging any inconsistencies between them.
3. Searches UnaVista transaction records for matching buyers and sellers using the incident
   code matrix to determine client type.
4. Tests each relevant UnaVista field against the expected correction value and writes
   `PASS` / `FAIL` / `No change` into a new `test_result` column.
5. Writes a timestamped output CSV (`output_UnaVista_final_lookup_YYYYMMDD_HHMMSS.csv`) and
   a detailed summary log.

### Running the script

```bash
python -m src.replay.phase_3_final_lookup --config config/local/replay/phase3_final.yaml

python -m src.replay.phase_3_final_lookup --config config/local/replay/phase3_final.yaml --log-level DEBUG

python -m src.replay.phase_3_final_lookup --use-env
```

If no `--config` flag is given, the script falls back to
`config/local/replay/phase3_final.yaml` automatically.

### Configuration

Copy `config/templates/replay/phase3_final_template.yaml` to
`config/local/replay/phase3_final.yaml` and fill in your paths.

```yaml
paths:
  replay_input:    "/path/to/phase_iii/corrected_output"
  incident_files:  "/path/to/incident_code_files"
  unavista_files:  "/path/to/unavista_reference"
  replay_output:   "/path/to/output"
  log_output:      "/path/to/output/logs"

files:
  unavista_pattern:     "UnaVista_MiFIR_Manual_Corrections_*.csv"
  replay_ids_pattern:   "Replay_*_Inconsistent_IDs_Summary_*.csv"
  replay_names_pattern: "Replay_*_Inconsistent_Names_Summary_*.csv"

incident_columns:
  transaction_ref:            "Transaction Reference"
  correction:                 "Correction"
  correction_field:           "Correction Field"
  agree_with_correction:      "Agree With Correction"
  suggested_correction:       "Suggested Correction"
  suggested_correction_field: "Suggested Correction Field"

processor:
  batch_size: 100
  log_level: "INFO"
  skip_duplicates: true
```

### Output

The script inserts a `test_result` column immediately after "Transaction Reference Number"
in the output CSV. Possible values are:

| Value | Meaning |
|---|---|
| `PASS (source): field=value` | All tested fields match the expected correction |
| `FAIL (source): field expected 'X' got 'Y'` | One or more fields do not match |
| `No change` | All corrections for this client are "No change" |
| `Client not found` | No matching transaction could be located in UnaVista data |
| `Inconsistent corrections: ...` | IDs and Names sources disagree on the correction value |

---

## Merge Inconsistent Summaries

**Script:** `src/replay/merge_inconsistent_ids.py`  
**Config template:** `config/templates/replay/merge_inconsistent_ids_template.yaml`  
**Console command:** `merge-inconsistent-summaries`

### What it does

The Phase III output directory typically contains two summary CSVs — one for Inconsistent IDs
and one for Inconsistent Names — each with multiple rows per client (one row per incident code).
This utility:

1. Auto-discovers both files in `paths.input_dir` using configurable glob patterns.
2. Groups rows in each file by a configurable key column (separate settings for IDs and Names).
3. Within each group, merges cell values: single unique values are kept as-is; multiple
   different values are stacked with a separator (default: newline).
4. Exports each merged dataset to an Excel (`.xlsx`) file written alongside the input CSV:
   - Bold, colour-highlighted header row
   - Text wrapping on all data cells
   - Auto-sized column widths (capped at 40 characters)
   - Frozen header row

### Running the script

```bash
# Using a YAML config file
merge-inconsistent-summaries --config config/local/replay/merge_inconsistent_ids.yaml

# Specifying the input directory directly
merge-inconsistent-summaries --input-dir path/to/phase_iii/output

# Dry run — no files written
merge-inconsistent-summaries --input-dir path/to/phase_iii/output --dry-run

# Verbose output
merge-inconsistent-summaries --config config/local/replay/merge_inconsistent_ids.yaml --verbose
```

If no `--config` flag is given, the script falls back to
`config/local/replay/merge_inconsistent_ids.yaml` automatically.

### Configuration

Copy `config/templates/replay/merge_inconsistent_ids_template.yaml` to
`config/local/replay/merge_inconsistent_ids.yaml` and set `paths.input_dir`.

```yaml
paths:
  # Directory containing both Phase III Summary CSV files.
  # Output .xlsx files are written to this same directory.
  input_dir: "C:/path/to/phase_iii/output"

files:
  ids_pattern:   "Replay_*_Inconsistent_IDs_Summary_*.csv"
  names_pattern: "Replay_*_Inconsistent_Names_Summary_*.csv"

merge:
  ids_group_column:   "Reported IDs"          # Column to group IDs Summary rows by
  names_group_column: "Reported Name & DOB"   # Column to group Names Summary rows by
  separator: "\n"                              # Use "|" for pipe-separated stacking

options:
  dry_run: false
  verbose: false

processor:
  log_level: "INFO"
```

#### Key settings

| Setting | Description |
|---|---|
| `paths.input_dir` | Directory containing both Phase III Summary CSV files |
| `files.ids_pattern` | Glob pattern used to find the Inconsistent IDs Summary CSV |
| `files.names_pattern` | Glob pattern used to find the Inconsistent Names Summary CSV |
| `merge.ids_group_column` | Column used to group rows in the IDs Summary |
| `merge.names_group_column` | Column used to group rows in the Names Summary |
| `separator` | String placed between stacked values; `"\n"` for multi-line cells in Excel |
| `dry_run` | When `true`, processes the data but writes no output files |

---

## Typical Workflow

The scripts are designed to be run in sequence each quarter:

```
Phase II replay files
        │
        ▼
phase_2_processor         → output/phase_ii/  (corrected replay CSVs)

Phase III replay files
        │
        ▼
merge-inconsistent-summaries → merged Inconsistent IDs Summary (.xlsx)
                               merged Inconsistent Names Summary (.xlsx)
        │
        ▼
phase_3_processor         → output/phase_iii/ (corrected replay CSVs)
        │
        ▼
phase_3_final_lookup      → output/phase_iii_final_lookup/
                            output_UnaVista_final_lookup_*.csv
```

---

## Common Issues

### "Configuration error: 'files.incident_pattern' is required"

The `files.incident_pattern` key is missing from the config file. Add it, for example:

```yaml
files:
  incident_pattern: "FY25 Q4 *.csv"
```

### "Incident file not found for code: 7_39"

The pattern in `incident_pattern` does not match the filename on disk. Check the exact
prefix (spaces, dashes, quarter label) against the files in `paths.incident_files`.

### Corrections showing "Client not found"

- **Phase II:** The transaction reference in the replay file does not exist in any incident
  template file. Verify the `incident_pattern` is correct for the current quarter.
- **Phase III:** No ID, name+DOB, or fuzzy name match was found. Try lowering
  `similarity_threshold` or enabling `DEBUG` logging to trace individual match attempts.

### Merged Excel cells not wrapping

The output file must have a `.xlsx` extension. Specifying `.csv` as the output for
`merge-inconsistent-ids` will fail with a configuration error.

---

## Environment Variables

All scripts support loading configuration from environment variables using the `--use-env`
flag. Set variables with the `TXR_` prefix, using `_` to separate sections:

```bash
export TXR_PATHS_REPLAY_INPUT="/path/to/replay"
export TXR_PATHS_INCIDENT_FILES="/path/to/incidents"
export TXR_PATHS_REPLAY_OUTPUT="/path/to/output"
export TXR_PATHS_LOG_OUTPUT="/path/to/logs"
export TXR_PROCESSOR_LOG_LEVEL="DEBUG"

python -m src.replay.phase_2_processor --use-env
```
