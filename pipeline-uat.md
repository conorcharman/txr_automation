# Web APP UAT

## Accuracy Testing

***Template Generator*** No errors - but malformed unicode strings in the HTML are causing display errors:

```html
'<span class="transition-transform text-[10px]">â–¾</span>' 
```

'â–¾' should be an inverted '^' (or similar shape).



***Extract Generator*** Receiving this error when trying to run the script:

```log
usage: src.accuracy_testing.scripts.sql_extract_generator [-h] [--config CONFIG] [--template TEMPLATE] [--input INPUT]
                                                          [--output OUTPUT] [--batch-size BATCH_SIZE]
                                                          [--placeholder PLACEHOLDER] [--column COLUMN]
                                                          [--output-format {sql,dtf,both}]
                                                          [--incident-code INCIDENT_CODE]
                                                          [--dtf-template DTF_TEMPLATE] [--dry-run] [--verbose]
src.accuracy_testing.scripts.sql_extract_generator: error: unrecognized arguments: --log-level INFO
RuntimeError: Script exited with code 2
```

The element *class="rounded-md border border-border px-3 py-3 space-y-2"* should be collapsible, as should *class="rounded-lg border border-border p-4 space-y-1"*

***Collate CSV Extracts*** Receiving this error when trying to run the script:

```log
Loading default configuration from C:\Users\ccharm\Documents\GitHub\txr_automation\data\tmp\tmpefi7nndk.yaml...
Error: --input-dir or config paths.input_dir required
```

***Validation Scripts*** The script starts running, but stalls at 5% with no further progress after 20 minutes; log shows 'Waiting for output...'

***Data Push*** Receiving this error when trying to run the script:

```log
2026-05-14 09:59:30 - data_push_batch - ERROR - Failed to process 16_20_FY26_Q1: Target file not found for 16_20_FY26_Q1. Tried patterns: ['16_20_FY26_Q1_FY26_Q1.csv', 'FY26 Q1 16_20_FY26_Q1.csv', 'FY26 Q1 - 16_20_FY26_Q1.csv', '16_20_FY26_Q1.csv']
```

It is failing because none of the (target) template file patterns match what the template generator actually produces - they are in the format {FY} {Q} {incident_code}.

## Replay

### Phase 2

***Feedback*** More HTML issues:

```html
<p class="text-sm text-muted-foreground">Process replay Phase 2 â€” initial replay processing against the input file.</p>
```

```html
<p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Source Files (Accuracy Testing â€” Templates)</p>
```

```html
<span class="transition-transform text-[10px]">â–¾</span>
```

***Final Lookup*** No errors.

### Phase 3

***Feedback*** Receiving this error when trying to run the script:

```log
Loading configuration from C:\Users\ccharm\Documents\GitHub\txr_automation\data\tmp\tmpa2bbe3ch.yaml...
Fatal error: Configuration error: 'incident_columns' section is required in config file
Traceback (most recent call last):
  File "C:\Users\ccharm\Documents\GitHub\txr_automation\src\replay\phase_3_processor.py", line 1183, in main
    processor = Phase3Processor(config_dict=config)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ccharm\Documents\GitHub\txr_automation\src\replay\phase_3_processor.py", line 631, in __init__
    raise ValueError("Configuration error: 'incident_columns' section is required in config file")
ValueError: Configuration error: 'incident_columns' section is required in config file
```

To fix this, we need to set the incident column mapping in the config.

***Final Lookup*** More HTML issues:

```html
<p class="text-sm text-muted-foreground">Phase 3 final lookup â€” perform final ID resolution pass on the replay output.</p>
```

```html
<span class="transition-transform text-[10px] rotate-180">â–¾</span>
```

***Merge*** Receiving this error when trying to run the script:

```log
2026-05-14 10:37:23 - src.replay.merge_inconsistent_ids - INFO - merge-inconsistent-summaries starting
2026-05-14 10:37:23 - src.replay.merge_inconsistent_ids - INFO - Input directory: C:\Users\ccharm\Documents\GitHub\txr_automation\data\FY26\Q1\replay\output
2026-05-14 10:37:23 - src.replay.merge_inconsistent_ids - WARNING - Multiple files match the IDs pattern 'Replay_*_Inconsistent_IDs_Summary_*.csv' — skipping:
  C:\Users\ccharm\Documents\GitHub\txr_automation\data\FY26\Q1\replay\output\Replay_2025Q3_Inconsistent_IDs_Summary_FINAL.csv
  C:\Users\ccharm\Documents\GitHub\txr_automation\data\FY26\Q1\replay\output\Replay_2025Q3_PHASE 3_Inconsistent_IDs_Summary_FINAL.csv
2026-05-14 10:37:23 - src.replay.merge_inconsistent_ids - WARNING - Multiple files match the Names pattern 'Replay_*_Inconsistent_Names_Summary_*.csv' — skipping:
  C:\Users\ccharm\Documents\GitHub\txr_automation\data\FY26\Q1\replay\output\Replay_2025Q3_Inconsistent_Names_Summary_FINAL.csv
  C:\Users\ccharm\Documents\GitHub\txr_automation\data\FY26\Q1\replay\output\Replay_2025Q3_PHASE 3_Inconsistent_Names_Summary_FINAL.csv
2026-05-14 10:37:23 - src.replay.merge_inconsistent_ids - ERROR - No files could be processed.
RuntimeError: Script exited with code 1
```

## FIRDS

***Refresh Database*** Script stuck on 'pending status'; no progress after a minute.

## GLEIF

***Refresh Database*** Script stuck on 'pending status'; no progress after a minute.