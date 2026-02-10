#!/usr/bin/env python3
"""Test if assignment to object column with NaN works."""

import pandas as pd
import numpy as np
from pathlib import Path
import tempfile

# Load target file with dtype=str
target_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_37.csv')

df = pd.read_csv(target_file, encoding='utf-8', dtype=str)

print("=" * 80)
print("BEFORE ASSIGNMENT:")
print(f"Error dtype: {df['Error'].dtype}")
print(f"Sample values: {df['Error'].head(10).tolist()}")
print(f"NaN count: {df['Error'].isna().sum()}")
print()

# Find our test transaction
test_index = df[df['Transaction Reference'] == '44625CHP68Q1'].index[0]
print(f"Test transaction at index: {test_index}")
print(f"Before: Error = {repr(df.at[test_index, 'Error'])}")
print()

# Assign 'Y'
df.at[test_index, 'Error'] = 'Y'
print(f"After assignment: Error = {repr(df.at[test_index, 'Error'])}")
print()

# Save to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
    tmp_path = tmp.name

df.to_csv(tmp_path, index=False, encoding='utf-8')
print(f"Saved to: {tmp_path}")
print()

# Read back
df2 = pd.read_csv(tmp_path, encoding='utf-8')
print("AFTER READING BACK:")
print(f"Error dtype: {df2['Error'].dtype}")
test_row = df2[df2['Transaction Reference'] == '44625CHP68Q1'].iloc[0]
print(f"Error value: {repr(test_row['Error'])}")

print("=" * 80)
