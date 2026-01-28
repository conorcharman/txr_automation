#!/usr/bin/env python3
"""
Performance Benchmarks for Accuracy Testing Module
===================================================

Measures execution times for key operations in the accuracy testing pipeline.
Run this script to generate performance baseline metrics.

Usage:
    python -m scripts.benchmark_accuracy_testing
"""

import csv
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple

from accuracy_testing.accuracy_template_generator import AccuracyTemplateGenerator
from accuracy_testing.validators.data_push_processor import DataPushProcessor
from accuracy_testing.models.data_push_record import DataPushConfig, ColumnMapping


def generate_test_data(num_records: int, temp_dir: Path) -> Tuple[Path, Path]:
    """Generate test CSV files with specified number of records."""
    source_path = temp_dir / "source.csv"
    target_path = temp_dir / "target.csv"
    
    header = [
        "Transaction Reference",
        "Account ID",
        "Person Code",
        "Error",
        "Correction Output",
        "Correction Fields",
    ]
    
    # Generate source data
    with open(source_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i in range(num_records):
            error = "Y" if i % 3 == 0 else ("N" if i % 3 == 1 else "TBC")
            writer.writerow([
                f"TXN{i:06d}",
                f"A{i:08d}",
                f"PC{i:04d}",
                error,
                f"CORRECTION{i:04d}" if error == "Y" else "",
                "ID:IDT" if error == "Y" else "",
            ])
    
    # Generate target data (empty for matching)
    with open(target_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i in range(num_records):
            writer.writerow([
                f"TXN{i:06d}",
                "",
                "",
                "",
                "",
                "",
            ])
    
    return source_path, target_path


def benchmark_data_push(num_records: int, iterations: int = 3) -> Dict[str, float]:
    """Benchmark data push processor with specified number of records."""
    results = {
        "load_source": [],
        "load_target": [],
        "match_records": [],
        "push_data": [],
        "total": [],
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        source_path, target_path = generate_test_data(num_records, temp_dir)
        
        column_mappings = [
            ColumnMapping("Account ID", "Account ID", ""),
            ColumnMapping("Person Code", "Person Code", ""),
            ColumnMapping("Error", "Error", ""),
            ColumnMapping("Correction Output", "Correction Output", ""),
            ColumnMapping("Correction Fields", "Correction Fields", ""),
        ]
        
        for _ in range(iterations):
            config = DataPushConfig(
                source_file=source_path,
                target_file=target_path,
                column_mappings=column_mappings,
            )
            
            processor = DataPushProcessor(config)
            
            # Time each operation
            start = time.perf_counter()
            
            t1 = time.perf_counter()
            processor.load_source(source_path)
            results["load_source"].append(time.perf_counter() - t1)
            
            t2 = time.perf_counter()
            processor.load_target(target_path)
            results["load_target"].append(time.perf_counter() - t2)
            
            t3 = time.perf_counter()
            processor.match_records()
            results["match_records"].append(time.perf_counter() - t3)
            
            t4 = time.perf_counter()
            processor.push_data()
            results["push_data"].append(time.perf_counter() - t4)
            
            results["total"].append(time.perf_counter() - start)
    
    # Calculate averages
    return {k: sum(v) / len(v) for k, v in results.items()}


def main():
    """Run all benchmarks and print results."""
    print("=" * 70)
    print("Accuracy Testing Performance Benchmarks")
    print("=" * 70)
    print()
    
    # Benchmark data push at different scales
    record_counts = [100, 1000, 5000, 10000]
    
    print("Data Push Processor Benchmarks")
    print("-" * 70)
    print(f"{'Records':>10} | {'Load Src':>10} | {'Load Tgt':>10} | {'Match':>10} | {'Push':>10} | {'Total':>10}")
    print("-" * 70)
    
    for count in record_counts:
        results = benchmark_data_push(count)
        print(
            f"{count:>10} | "
            f"{results['load_source']*1000:>9.2f}ms | "
            f"{results['load_target']*1000:>9.2f}ms | "
            f"{results['match_records']*1000:>9.2f}ms | "
            f"{results['push_data']*1000:>9.2f}ms | "
            f"{results['total']*1000:>9.2f}ms"
        )
    
    print("-" * 70)
    print()
    
    # Calculate throughput
    print("Throughput Analysis")
    print("-" * 70)
    results_10k = benchmark_data_push(10000, iterations=5)
    records_per_sec = 10000 / results_10k["total"]
    print(f"Processing rate: {records_per_sec:,.0f} records/second")
    print(f"Time per 10,000 records: {results_10k['total']*1000:.2f}ms")
    print()
    
    # Estimate for typical production volumes
    print("Estimated Production Times")
    print("-" * 70)
    typical_volumes = [5000, 25000, 50000, 100000]
    for vol in typical_volumes:
        estimated_time = vol / records_per_sec
        print(f"{vol:>10,} records: {estimated_time:.2f}s ({estimated_time/60:.2f}min)")
    
    print()
    print("=" * 70)
    print("Benchmark complete")


if __name__ == "__main__":
    main()
