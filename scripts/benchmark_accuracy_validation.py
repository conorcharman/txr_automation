#!/usr/bin/env python3
"""
Accuracy Testing Validation Scripts Benchmark
==============================================

Benchmarks the core accuracy testing validation scripts (buyer ID, seller ID, pricing)
to measure performance with varying dataset sizes.

Usage:
    python scripts/benchmark_accuracy_validation.py [--sizes SIZE1,SIZE2,...]
"""

import argparse
import csv
import tempfile
import time
import subprocess
from pathlib import Path
from typing import Dict
import statistics
import sys


def generate_test_csv(num_records: int, output_path: Path, validation_type: str = "buyer"):
    """Generate test CSV file for validation."""
    if validation_type == "buyer":
        headers = [
            "Transaction Reference",
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
    elif validation_type == "seller":
        headers = [
            "Transaction Reference",
            "Person Code",
            "Account Type",
            "Seller ID Code",
            "Type of Seller ID Code",
            "First Name",
            "Surname",
            "Date of Birth",
            "Gender",
            "Primary Nationality",
            "Secondary Nationality",
        ]
    elif validation_type == "pricing":
        headers = [
            "Transaction Reference",
            "ExecutionPriceTotalConsideration",
            "CalculatedTotalConsideration",
        ]
    else:
        raise ValueError(f"Unknown validation type: {validation_type}")
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for i in range(num_records):
            if validation_type in ["buyer", "seller"]:
                writer.writerow([
                    f"TXN{i:08d}",          # Transaction Reference
                    f"P{i:06d}",            # Person code
                    "ORDINARY",             # Account Type
                    "QQ123456A",            # Valid UK NINO format
                    "NIDN",                 # Type
                    "John",                 # First Name
                    "Smith",                # Surname
                    "19800101",             # Date of Birth
                    "M",                    # Gender
                    "GB",                   # Primary Nationality
                    "",                     # Secondary Nationality
                ])
            elif validation_type == "pricing":
                price = 1000.00 + (i % 100)
                writer.writerow([
                    f"TXN{i:08d}",          # Transaction Reference
                    f"{price:.2f}",         # Execution price
                    f"{price:.2f}",         # Calculated price (matches)
                ])


def benchmark_validation_script(
    script_name: str,
    script_path: str,
    num_records: int,
    validation_type: str,
    iterations: int = 3
) -> Dict[str, float]:
    """Benchmark a validation script by running it as a subprocess."""
    times = []
    project_root = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        input_path = temp_dir / "input.csv"
        output_path = temp_dir / "output.csv"
        
        # Generate test data
        generate_test_csv(num_records, input_path, validation_type)
        
        for iteration in range(iterations):
            start_time = time.perf_counter()
            
            try:
                # Run validation script as subprocess
                result = subprocess.run(
                    [
                        sys.executable, "-m",
                        f"src.accuracy_testing.scripts.{script_path}",
                        str(input_path),
                        str(output_path),
                        "--log-level", "ERROR",  # Suppress logging for benchmark
                    ],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                
                if result.returncode != 0:
                    print(f"  Error in iteration {iteration + 1}: Exit code {result.returncode}")
                    if result.stderr:
                        print(f"    stderr: {result.stderr[:200]}")
                    continue
                
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)
            except subprocess.TimeoutExpired:
                print(f"  Error in iteration {iteration + 1}: Timeout")
                continue
            except Exception as e:
                print(f"  Error in iteration {iteration + 1}: {e}")
                continue
    
    if not times:
        return {"error": "All iterations failed"}
    
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "iterations": len(times),
    }


def format_time(seconds: float) -> str:
    """Format time in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"


def main():
    """Run benchmarks."""
    parser = argparse.ArgumentParser(description="Benchmark accuracy testing validation scripts")
    parser.add_argument(
        "--sizes",
        type=str,
        default="100,1000,5000,10000",
        help="Comma-separated list of dataset sizes to test (default: 100,1000,5000,10000)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations per benchmark (default: 3)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/benchmarks"),
        help="Output directory for results"
    )
    
    args = parser.parse_args()
    sizes = [int(s.strip()) for s in args.sizes.split(",")]
    
    print("=" * 80)
    print("ACCURACY TESTING VALIDATION SCRIPTS BENCHMARK")
    print("=" * 80)
    print()
    
    validation_scripts = [
        ("Buyer ID Validation", "buyer_id_validation", "buyer"),
        ("Seller ID Validation", "seller_id_validation", "seller"),
        ("Pricing Validation", "pricing_validation", "pricing"),
    ]
    
    all_results = {}
    
    for script_name, script_path, validation_type in validation_scripts:
        print(f"{script_name}")
        print("-" * 80)
        print(f"{'Records':>10} | {'Mean':>12} | {'Median':>12} | {'Min':>12} | {'Max':>12} | {'Records/sec':>15}")
        print("-" * 80)
        
        script_results = {}
        
        for size in sizes:
            results = benchmark_validation_script(
                script_name,
                script_path,
                size,
                validation_type,
                args.iterations
            )
            
            if "error" not in results:
                records_per_sec = size / results["mean"]
                print(
                    f"{size:>10,} | "
                    f"{format_time(results['mean']):>12} | "
                    f"{format_time(results['median']):>12} | "
                    f"{format_time(results['min']):>12} | "
                    f"{format_time(results['max']):>12} | "
                    f"{records_per_sec:>15,.0f}"
                )
                script_results[size] = results
            else:
                print(f"{size:>10,} | ERROR: {results['error']}")
        
        all_results[script_name] = script_results
        print()
    
    # Throughput analysis
    print("=" * 80)
    print("THROUGHPUT ANALYSIS")
    print("=" * 80)
    print()
    
    for script_name, results in all_results.items():
        if results:
            # Use largest successful dataset for throughput calc
            largest_size = max(results.keys())
            largest_results = results[largest_size]
            throughput = largest_size / largest_results["mean"]
            
            print(f"{script_name}:")
            print(f"  Processing rate: {throughput:,.0f} records/second")
            print(f"  Time per 10,000 records: {format_time(10000 / throughput)}")
            print()
    
    # Estimated production times
    print("=" * 80)
    print("ESTIMATED PRODUCTION TIMES (based on largest test dataset)")
    print("=" * 80)
    print()
    
    production_sizes = [5000, 25000, 50000, 100000, 250000]
    
    for script_name, results in all_results.items():
        if results:
            largest_size = max(results.keys())
            largest_results = results[largest_size]
            throughput = largest_size / largest_results["mean"]
            
            print(f"{script_name}:")
            for prod_size in production_sizes:
                est_time = prod_size / throughput
                print(f"  {prod_size:>8,} records: {format_time(est_time)}")
            print()
    
    print("=" * 80)
    print("Benchmark complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
