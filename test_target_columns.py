#!/usr/bin/env python3
"""Debug script to check target file columns."""

import pandas as pd
from pathlib import Path

# Load target file
target_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_37.csv')

df = pd.read_csv(target_file, encoding='utf-8')

print("=" * 80)
print("TARGET FILE COLUMNS:")
print(f"Total columns: {len(df.columns)}")
print()

# Find Error-related columns
error_cols = [col for col in df.columns if 'error' in col.lower()]
print(f"Error-related columns: {error_cols}")
print()

# Check column 13 (0-indexed column 12)
if len(df.columns) > 12:
    print(f"Column 13 (index 12): '{df.columns[12]}'")
    print(f"Sample values: {df[df.columns[12]].head(10).tolist()}")
print()

# Find transaction 44625CHP68Q1
matching_rows = df[df['Transaction Reference'] == '44625CHP68Q1']
if len(matching_rows) > 0:
    row = matching_rows.iloc[0]
    print(f"Found transaction 44625CHP68Q1 at index: {matching_rows.index[0]}")
    print(f"Error column value: '{row.get('Error', 'NOT_FOUND')}'")
    print(f"Correction column value: '{row.get('Correction', 'NOT_FOUND')}'")
else:
    print("Transaction 44625CHP68Q1 NOT FOUND in target file")

print("=" * 80)
