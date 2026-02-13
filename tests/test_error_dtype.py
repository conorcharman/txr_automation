#!/usr/bin/env python3
"""Debug script to check Error column dtype."""

import pandas as pd
import numpy as np
from pathlib import Path

# Load target file
target_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_37.csv')

df = pd.read_csv(target_file, encoding='utf-8')

print("=" * 80)
print("ERROR COLUMN ANALYSIS:")
print(f"Column name: 'Error'")
print(f"Column dtype: {df['Error'].dtype}")
print(f"Is float: {pd.api.types.is_float_dtype(df['Error'])}")
print(f"Is object: {pd.api.types.is_object_dtype(df['Error'])}")
print()

print("Testing assignment:")
test_index = df[df['Transaction Reference'] == '44625CHP68Q1'].index[0]
print(f"Row index: {test_index}")
print(f"Before: Error = {repr(df.at[test_index, 'Error'])}")

# Try to assign 'Y'
df.at[test_index, 'Error'] = 'Y'
print(f"After assignment: Error = {repr(df.at[test_index, 'Error'])}")
print(f"Column dtype after assignment: {df['Error'].dtype}")
print()

# Check a few rows
print("Sample of Error column after assignment:")
print(df.loc[test_index-2:test_index+2, ['Transaction Reference', 'Error']])
print("=" * 80)
