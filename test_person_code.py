#!/usr/bin/env python3
"""Quick test to check if person_code is being read and written correctly"""

from src.accuracy_testing.processor import ClientRecord

# Create a test record
record = ClientRecord(
    row_index=1,
    transaction_ref="TEST001",
    account_id="ACC001",
    person_code="PERSON123",  # This should appear in output
    account_type="IND",
    id_value="AB123456C",
    id_type="NIDN",
    first_name="John",
    surname="Doe",
    date_of_birth="1990-01-01",
    gender="M",
    primary_nationality="GB",
    secondary_nationality="US",
    trade_date_time_raw="2024-01-01-12-00-00-00"
)

print("Record created successfully:")
print(f"  Transaction Ref: {record.transaction_ref}")
print(f"  Account ID: {record.account_id}")
print(f"  Person Code: {record.person_code}")
print(f"  Account Type: {record.account_type}")

# Check output order
output_row = [
    record.transaction_ref,
    record.account_id,
    record.person_code,
    record.account_type,
    record.id_value,
    record.id_type,
    record.first_name,
    record.surname,
    record.date_of_birth,
    record.gender,
    record.primary_nationality,
    record.secondary_nationality,
    record.trade_date_time_raw
]

print("\nOutput row:")
for i, val in enumerate(output_row):
    print(f"  {i}: {val}")

print("\nExpected order:")
print("  0: Transaction Reference")
print("  1: Account ID")
print("  2: Person Code")
print("  3: Account Type")
print("  4: Buyer ID Code")
print("  5: Type of Buyer ID Code")
print("  6: First Name")
print("  7: Surname")
print("  8: Date of Birth")
print("  9: Gender")
print("  10: Primary Nationality")
print("  11: Secondary Nationality")
print("  12: Trade_Date_Time")
