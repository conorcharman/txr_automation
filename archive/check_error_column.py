#!/usr/bin/env python3
import pandas as pd

df = pd.read_csv(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\incident_code_analysis\FY25 Q4 7_37.csv')

print("Checking Error column after data push:")
print(f"Error dtype: {df['Error'].dtype}")
print()

row = df[df['Transaction Reference'] == '44625CHP68Q1'].iloc[0]
print(f"Transaction 44625CHP68Q1:")
print(f"  Error: '{row['Error']}'")
print(f"  Correction: '{row['Correction']}'")
print()

print("Error column value counts:")
print(df['Error'].value_counts(dropna=False))
