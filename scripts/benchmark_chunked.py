#!/usr/bin/env python3
"""
Chunked Processing Benchmark
=============================

Compares memory-efficient chunked processing vs full in-memory processing.
"""

import csv
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accuracy_testing.processor import ClientRecord, IDValidationProcessor


@dataclass
class ChunkedBenchmarkResult:
    """Results from chunked benchmark."""
    mode: str  # "full" or "chunked"
    dataset_size: int
    chunk_size: int
    processing_time_sec: float
    peak_memory_mb: float
    throughput_records_per_sec: float
    memory_per_record_kb: float
    timestamp: str


def process_full(input_file: Path, dataset_size: int) -> ChunkedBenchmarkResult:
    """Process all records at once (current approach)."""
    print(f"\n{'='*70}")
    print(f"FULL IN-MEMORY PROCESSING")
    print(f"{'='*70}")
    
    tracemalloc.start()
    start_time = time.time()
    
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    
    # Load all records
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
    
    print(f"Loaded {len(records):,} records into memory")
    
    # Process all
    for record in records:
        processor.process_record(record)
    
    end_time = time.time()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    processing_time = end_time - start_time
    peak_memory_mb = peak_mem / 1024 / 1024
    throughput = dataset_size / processing_time
    memory_per_record_kb = (peak_mem / dataset_size) / 1024
    
    print(f"✓ Time: {processing_time:.2f}s")
    print(f"✓ Peak Memory: {peak_memory_mb:.2f} MB")
    print(f"✓ Throughput: {throughput:,.2f} records/sec")
    
    return ChunkedBenchmarkResult(
        mode="full",
        dataset_size=dataset_size,
        chunk_size=dataset_size,
        processing_time_sec=round(processing_time, 2),
        peak_memory_mb=round(peak_memory_mb, 2),
        throughput_records_per_sec=round(throughput, 2),
        memory_per_record_kb=round(memory_per_record_kb, 2),
        timestamp=datetime.now().isoformat(),
    )


def process_chunked(input_file: Path, dataset_size: int, chunk_size: int) -> ChunkedBenchmarkResult:
    """Process in chunks to save memory."""
    print(f"\n{'='*70}")
    print(f"CHUNKED PROCESSING (chunk_size={chunk_size:,})")
    print(f"{'='*70}")
    
    tracemalloc.start()
    start_time = time.time()
    
    processor = IDValidationProcessor(client_type="buyer", verbose=False)
    
    total_processed = 0
    chunk_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        chunk = []
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
            chunk.append(record)
            
            if len(chunk) >= chunk_size:
                # Process chunk
                for rec in chunk:
                    processor.process_record(rec)
                total_processed += len(chunk)
                chunk_count += 1
                chunk = []  # Clear for next chunk
        
        # Process remaining records
        if chunk:
            for rec in chunk:
                processor.process_record(rec)
            total_processed += len(chunk)
            chunk_count += 1
    
    end_time = time.time()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    processing_time = end_time - start_time
    peak_memory_mb = peak_mem / 1024 / 1024
    throughput = dataset_size / processing_time
    memory_per_record_kb = (peak_mem / dataset_size) / 1024
    
    print(f"✓ Processed {chunk_count:,} chunks")
    print(f"✓ Time: {processing_time:.2f}s")
    print(f"✓ Peak Memory: {peak_memory_mb:.2f} MB")
    print(f"✓ Throughput: {throughput:,.2f} records/sec")
    
    return ChunkedBenchmarkResult(
        mode="chunked",
        dataset_size=dataset_size,
        chunk_size=chunk_size,
        processing_time_sec=round(processing_time, 2),
        peak_memory_mb=round(peak_memory_mb, 2),
        throughput_records_per_sec=round(throughput, 2),
        memory_per_record_kb=round(memory_per_record_kb, 2),
        timestamp=datetime.now().isoformat(),
    )


def main():
    # Use existing 1.5M dataset
    input_file = Path("benchmarks/temp_data/test_data_1500000.csv")
    
    if not input_file.exists():
        print(f"Error: {input_file} not found. Run benchmark_scalability.py first with --keep-data")
        return
    
    dataset_size = 1_500_000
    chunk_size = 50_000
    
    print(f"\n{'='*70}")
    print(f"CHUNKED PROCESSING COMPARISON BENCHMARK")
    print(f"{'='*70}")
    print(f"Dataset: {dataset_size:,} records")
    print(f"Chunk size: {chunk_size:,} records")
    
    # Run full processing
    full_result = process_full(input_file, dataset_size)
    
    # Run chunked processing
    chunked_result = process_chunked(input_file, dataset_size, chunk_size)
    
    # Compare results
    print(f"\n{'='*70}")
    print(f"COMPARISON")
    print(f"{'='*70}")
    
    time_overhead = ((chunked_result.processing_time_sec - full_result.processing_time_sec) 
                     / full_result.processing_time_sec * 100)
    memory_savings = ((full_result.peak_memory_mb - chunked_result.peak_memory_mb) 
                      / full_result.peak_memory_mb * 100)
    throughput_change = ((chunked_result.throughput_records_per_sec - full_result.throughput_records_per_sec) 
                         / full_result.throughput_records_per_sec * 100)
    
    print(f"\n{'Metric':<25} {'Full':<15} {'Chunked':<15} {'Difference':<15}")
    print("-" * 70)
    print(f"{'Processing Time (s)':<25} {full_result.processing_time_sec:<15.2f} "
          f"{chunked_result.processing_time_sec:<15.2f} {time_overhead:+.1f}%")
    print(f"{'Peak Memory (MB)':<25} {full_result.peak_memory_mb:<15.2f} "
          f"{chunked_result.peak_memory_mb:<15.2f} {-memory_savings:+.1f}%")
    print(f"{'Throughput (rec/s)':<25} {full_result.throughput_records_per_sec:<15,.2f} "
          f"{chunked_result.throughput_records_per_sec:<15,.2f} {throughput_change:+.1f}%")
    print(f"{'Memory/Record (KB)':<25} {full_result.memory_per_record_kb:<15.2f} "
          f"{chunked_result.memory_per_record_kb:<15.2f}")
    
    # Save results
    output_file = Path("benchmarks/chunked_comparison_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "benchmark_type": "chunked_comparison",
            "timestamp": datetime.now().isoformat(),
            "dataset_size": dataset_size,
            "chunk_size": chunk_size,
            "full_processing": asdict(full_result),
            "chunked_processing": asdict(chunked_result),
            "comparison": {
                "time_overhead_percent": round(time_overhead, 2),
                "memory_savings_percent": round(memory_savings, 2),
                "throughput_change_percent": round(throughput_change, 2),
            }
        }, f, indent=2)
    
    print(f"\n✓ Results saved to {output_file}")
    
    # Verdict
    print(f"\n{'='*70}")
    print(f"VERDICT")
    print(f"{'='*70}")
    if memory_savings > 50:
        print(f"✅ Chunked processing provides {memory_savings:.1f}% memory savings")
    if abs(time_overhead) < 10:
        print(f"✅ Performance overhead is minimal ({time_overhead:+.1f}%)")
    elif time_overhead > 10:
        print(f"⚠️  Performance overhead is {time_overhead:.1f}%")
    
    print(f"\nRecommendation: ", end="")
    if memory_savings > 50 and abs(time_overhead) < 20:
        print("Use chunked processing for production (better memory efficiency)")
    elif time_overhead > 30:
        print("Full processing is faster, but chunked is more scalable")
    else:
        print("Chunked processing is a good balance of memory and performance")


if __name__ == "__main__":
    main()
