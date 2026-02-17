#!/usr/bin/env python3
"""
Scalability Benchmarking Tool
==============================

Tests processing performance with datasets of varying sizes (100K, 500K, 1M, 1.5M rows).
Measures:
- Processing time
- Memory usage (peak and average)
- Throughput (records/second)
- Memory per record

Usage:
    python scripts/benchmark_scalability.py --output benchmarks/scalability_results.json
"""

import argparse
import csv
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accuracy_testing.processor import ClientRecord, IDValidationProcessor


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    dataset_size: int
    processing_time_sec: float
    peak_memory_mb: float
    avg_memory_mb: float
    throughput_records_per_sec: float
    memory_per_record_kb: float
    valid_records: int
    invalid_records: int
    corrected_records: int
    timestamp: str


def generate_test_data(num_records: int, output_file: Path) -> None:
    """
    Generate test CSV data with realistic patterns.
    
    Args:
        num_records: Number of records to generate
        output_file: Path to output CSV file
    """
    print(f"Generating {num_records:,} test records...")
    
    header = [
        "Transaction Reference",
        "Account ID",
        "Person Code",
        "Account Type",
        "Buyer ID Code",
        "Type of Buyer ID Code",
        "First Name",
        "Surname",
        "Date of Birth",
        "Gender",
        "Primary Nationality",
        "Secondary Nationality",
    ]
    
    # Sample data patterns
    valid_patterns = [
        ("AB123456C", "NIDN", "GB"),  # Valid UK NINO
        ("549300VALIDLEI01234", "LEI", "GB"),  # Valid LEI
        ("123456789", "CCPT", "CY"),  # Valid Cyprus CCPT
    ]
    
    invalid_patterns = [
        ("INVALID", "NIDN", "GB"),  # Invalid format
        ("", "", ""),  # Empty
        ("AB123456X", "NIDN", "GB"),  # Invalid checksum
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        
        for i in range(num_records):
            # Mix of valid and invalid (80% valid, 20% invalid)
            if i % 5 == 0:
                id_code, id_type, nationality = invalid_patterns[i % len(invalid_patterns)]
            else:
                id_code, id_type, nationality = valid_patterns[i % len(valid_patterns)]
            
            row = [
                f"TXN{i:010d}",
                f"ACC{i:08d}",
                f"PER{i:08d}",
                "IND",
                id_code,
                id_type,
                f"First{i % 100}",
                f"Last{i % 100}",
                f"{1950 + (i % 50):04d}-{1 + (i % 12):02d}-{1 + (i % 28):02d}",
                "M" if i % 2 == 0 else "F",
                nationality,
                "",
            ]
            writer.writerow(row)
    
    print(f"✓ Generated {num_records:,} records to {output_file}")


def benchmark_processing(
    input_file: Path,
    dataset_size: int,
) -> BenchmarkResult:
    """
    Benchmark processing for a dataset.
    
    Args:
        input_file: Path to input CSV
        dataset_size: Number of records in dataset
        
    Returns:
        BenchmarkResult with metrics
    """
    print(f"\nBenchmarking {dataset_size:,} records...")
    
    # Start memory tracking
    tracemalloc.start()
    start_time = time.time()
    
    # Initialize processor
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    
    # Read and process records
    records = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            record = ClientRecord(
                row_index=idx + 1,
                transaction_ref=row["Transaction Reference"],
                account_id=row["Account ID"],
                person_code=row["Person Code"],
                account_type=row["Account Type"],
                id_value=row["Buyer ID Code"],
                id_type=row["Type of Buyer ID Code"],
                first_name=row["First Name"],
                surname=row["Surname"],
                date_of_birth=row["Date of Birth"],
                gender=row["Gender"],
                primary_nationality=row["Primary Nationality"],
                secondary_nationality=row["Secondary Nationality"],
                original_row=list(row.values()),
            )
            records.append(record)
    
    # Process all records
    processed_records = []
    memory_samples = []
    
    for i, record in enumerate(records):
        processed = processor.process_record(record)
        processed_records.append(processed)
        
        # Sample memory every 10,000 records
        if i % 10000 == 0:
            current, peak = tracemalloc.get_traced_memory()
            memory_samples.append(current / 1024 / 1024)  # MB
    
    end_time = time.time()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Calculate statistics
    processing_time = end_time - start_time
    peak_memory_mb = peak_mem / 1024 / 1024
    avg_memory_mb = sum(memory_samples) / len(memory_samples) if memory_samples else 0
    throughput = dataset_size / processing_time if processing_time > 0 else 0
    memory_per_record_kb = (peak_mem / dataset_size) / 1024 if dataset_size > 0 else 0
    
    # Count results
    valid_count = sum(1 for r in processed_records if r.is_valid)
    invalid_count = sum(1 for r in processed_records if not r.is_valid)
    corrected_count = sum(1 for r in processed_records if r.correction)
    
    result = BenchmarkResult(
        dataset_size=dataset_size,
        processing_time_sec=round(processing_time, 2),
        peak_memory_mb=round(peak_memory_mb, 2),
        avg_memory_mb=round(avg_memory_mb, 2),
        throughput_records_per_sec=round(throughput, 2),
        memory_per_record_kb=round(memory_per_record_kb, 2),
        valid_records=valid_count,
        invalid_records=invalid_count,
        corrected_records=corrected_count,
        timestamp=datetime.now().isoformat(),
    )
    
    print(f"✓ Completed in {processing_time:.2f}s")
    print(f"  Throughput: {throughput:,.2f} records/sec")
    print(f"  Peak memory: {peak_memory_mb:.2f} MB")
    print(f"  Memory/record: {memory_per_record_kb:.2f} KB")
    
    return result


def main():
    """Run scalability benchmarks."""
    parser = argparse.ArgumentParser(
        description="Benchmark processing performance at scale"
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[100_000, 500_000, 1_000_000, 1_500_000],
        help="Dataset sizes to test (default: 100K, 500K, 1M, 1.5M)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/scalability_results.json"),
        help="Output file for results (JSON)",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep generated test data files",
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Create temp directory for test data
    data_dir = Path("benchmarks/temp_data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("SCALABILITY BENCHMARK")
    print("=" * 70)
    print(f"Dataset sizes: {[f'{s:,}' for s in args.sizes]}")
    print(f"Output: {args.output}")
    print()
    
    results = []
    
    try:
        for size in args.sizes:
            # Generate test data
            data_file = data_dir / f"test_data_{size}.csv"
            generate_test_data(size, data_file)
            
            # Run benchmark
            result = benchmark_processing(data_file, size)
            results.append(asdict(result))
            
            # Clean up data file unless --keep-data
            if not args.keep_data:
                data_file.unlink()
                print(f"  Cleaned up {data_file.name}")
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump({
                "benchmark_type": "scalability",
                "timestamp": datetime.now().isoformat(),
                "results": results,
            }, f, indent=2)
        
        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"{'Size':<12} {'Time (s)':<10} {'Mem (MB)':<10} {'Records/s':<12} {'KB/rec':<10}")
        print("-" * 70)
        for r in results:
            print(
                f"{r['dataset_size']:<12,} "
                f"{r['processing_time_sec']:<10.2f} "
                f"{r['peak_memory_mb']:<10.2f} "
                f"{r['throughput_records_per_sec']:<12,.2f} "
                f"{r['memory_per_record_kb']:<10.2f}"
            )
        
        print()
        print(f"✓ Results saved to {args.output}")
        
    finally:
        # Clean up temp directory if empty
        if not args.keep_data and data_dir.exists():
            try:
                data_dir.rmdir()
            except OSError:
                pass  # Directory not empty


if __name__ == "__main__":
    main()
