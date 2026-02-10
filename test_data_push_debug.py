#!/usr/bin/env python3
"""Debug script to trace Error column values through data push."""

import csv
from pathlib import Path
from src.accuracy_testing.models.data_push_record import DataPushRecord, ColumnMapping

# Load one record from validation output
validation_file = Path(r'c:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2025\Q4\validated\validated_FY25_Q4_7_37.csv')

with open(validation_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['Transaction Reference'] == '44625CHP68Q1':
            print("=" * 80)
            print("SOURCE ROW DATA:")
            print(f"Transaction Ref: {row['Transaction Reference']}")
            print(f"Error column value: '{row.get('Error', 'NOT_FOUND')}'")
            print(f"Correction: '{row.get('Correction', '')}'")
            print()
            
            # Create DataPushRecord
            record = DataPushRecord.from_dict(
                data=row,
                error_column="Error",
                transaction_ref_column="Transaction Reference",
                row_index=1
            )
            
            print("DATAPUSHRECORD OBJECT:")
            print(f"transaction_ref: {record.transaction_ref}")
            print(f"error_flag: '{record.error_flag}'")
            print(f"action: {record.action}")
            print(f"source_data keys: {list(record.source_data.keys())[:10]}")
            print(f"'Error' in source_data: {'Error' in record.source_data}")
            print(f"source_data['Error']: '{record.source_data.get('Error', 'NOT_FOUND')}'")
            print()
            
            # Create column mappings
            column_mappings = [
                ColumnMapping(source_col="Error", target_col="Error"),
                ColumnMapping(source_col="Correction", target_col="Correction"),
                ColumnMapping(source_col="Correction Field", target_col="Correction Field"),
            ]
            
            # Get push values
            push_values = record.get_push_values(column_mappings)
            
            print("PUSH VALUES:")
            for key, value in push_values.items():
                print(f"  {key}: '{value}' (type: {type(value).__name__})")
            print()
            
            print("=" * 80)
            break
