#!/usr/bin/env python3
"""
Performance Benchmarking Script
================================

Benchmarks all replay processing scripts and utilities to establish
performance baselines and identify optimization opportunities.

Usage:
    python scripts/benchmark_performance.py [--iterations N] [--profile]
    
Options:
    --iterations N    Number of times to run each benchmark (default: 3)
    --profile        Enable detailed profiling with cProfile
    --output PATH    Output path for results (default: data/output/benchmarks)
"""

import argparse
import time
import subprocess
import json
import sys
import os
import tracemalloc
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from txr_replay_core import DateParser
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False


class BenchmarkResult:
    """Store results from a single benchmark run"""
    
    def __init__(self, name: str):
        self.name = name
        self.execution_times: List[float] = []
        self.memory_peaks: List[float] = []
        self.records_processed: Optional[int] = None
        self.date_cache_hits: Optional[int] = None
        self.files_processed: Optional[int] = None
        self.errors: List[str] = []
        
    def add_run(self, execution_time: float, memory_peak: float):
        """Add results from a single run"""
        self.execution_times.append(execution_time)
        self.memory_peaks.append(memory_peak)
    
    def get_stats(self) -> Dict[str, Any]:
        """Calculate statistics from all runs"""
        if not self.execution_times:
            return {"error": "No successful runs"}
        
        return {
            "name": self.name,
            "runs": len(self.execution_times),
            "execution_time": {
                "mean": statistics.mean(self.execution_times),
                "median": statistics.median(self.execution_times),
                "min": min(self.execution_times),
                "max": max(self.execution_times),
                "stdev": statistics.stdev(self.execution_times) if len(self.execution_times) > 1 else 0,
            },
            "memory_mb": {
                "mean": statistics.mean(self.memory_peaks),
                "median": statistics.median(self.memory_peaks),
                "min": min(self.memory_peaks),
                "max": max(self.memory_peaks),
            },
            "records_processed": self.records_processed,
            "files_processed": self.files_processed,
            "date_cache_hits": self.date_cache_hits,
            "throughput_records_per_sec": (
                self.records_processed / statistics.mean(self.execution_times)
                if self.records_processed and self.execution_times
                else None
            ),
            "errors": self.errors,
        }


class ProcessBenchmarker:
    """Benchmark a subprocess execution"""
    
    @staticmethod
    def benchmark_subprocess(
        command: List[str],
        name: str,
        cwd: Path,
        iterations: int = 3
    ) -> BenchmarkResult:
        """
        Run a subprocess multiple times and collect performance metrics.
        
        Args:
            command: Command to run as list of strings
            name: Name for this benchmark
            cwd: Working directory for command
            iterations: Number of times to run
            
        Returns:
            BenchmarkResult with collected metrics
        """
        result = BenchmarkResult(name)
        
        print(f"\nBenchmarking: {name}")
        print(f"  Command: {' '.join(command)}")
        print(f"  Iterations: {iterations}")
        
        for i in range(iterations):
            print(f"  Run {i + 1}/{iterations}...", end=" ", flush=True)
            
            # Start memory tracking
            tracemalloc.start()
            
            # Set up environment with PYTHONPATH
            env = os.environ.copy()
            pythonpath = str(cwd / "src")
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = f"{pythonpath}:{env['PYTHONPATH']}"
            else:
                env["PYTHONPATH"] = pythonpath
            
            # Run the command
            start_time = time.perf_counter()
            try:
                proc_result = subprocess.run(
                    command,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    env=env
                )
                end_time = time.perf_counter()
                
                # Get peak memory usage
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                execution_time = end_time - start_time
                memory_peak_mb = peak / 1024 / 1024
                
                if proc_result.returncode == 0:
                    result.add_run(execution_time, memory_peak_mb)
                    print(f"✓ {execution_time:.3f}s, {memory_peak_mb:.1f}MB")
                    
                    # Try to extract metrics from output
                    if i == iterations - 1:  # Last run
                        ProcessBenchmarker._extract_metrics(proc_result.stdout, result)
                else:
                    error_msg = f"Exit code {proc_result.returncode}"
                    # Capture stderr for debugging
                    if proc_result.stderr:
                        error_msg += f": {proc_result.stderr[:200]}"
                    result.errors.append(error_msg)
                    print(f"✗ {error_msg}")
                    # Print full error on first failure for debugging
                    if i == 0 and proc_result.stderr:
                        print(f"\n    stderr: {proc_result.stderr}")
                    
            except subprocess.TimeoutExpired:
                tracemalloc.stop()
                result.errors.append("Timeout (>5 minutes)")
                print("✗ Timeout")
            except Exception as e:
                tracemalloc.stop()
                result.errors.append(str(e))
                print(f"✗ {e}")
        
        return result
    
    @staticmethod
    def _extract_metrics(output: str, result: BenchmarkResult):
        """Extract metrics from script output"""
        lines = output.split('\n')
        
        for line in lines:
            # Look for common patterns in output
            if 'records processed' in line.lower() or 'total records' in line.lower():
                try:
                    # Extract number from line
                    words = line.split()
                    for word in words:
                        cleaned = word.strip(',:')
                        if cleaned.isdigit():
                            result.records_processed = int(cleaned)
                            break
                except:
                    pass
            
            if 'date cache' in line.lower():
                try:
                    words = line.split()
                    for word in words:
                        cleaned = word.strip(',:')
                        if cleaned.isdigit():
                            result.date_cache_hits = int(cleaned)
                            break
                except:
                    pass
            
            if 'files processed' in line.lower() or 'processed files' in line.lower():
                try:
                    words = line.split()
                    for word in words:
                        cleaned = word.strip(',:')
                        if cleaned.isdigit():
                            result.files_processed = int(cleaned)
                            break
                except:
                    pass


class BenchmarkSuite:
    """Run complete benchmark suite"""
    
    def __init__(self, project_root: Path, iterations: int = 3, output_dir: Optional[Path] = None):
        self.project_root = project_root
        self.iterations = iterations
        self.output_dir = output_dir or project_root / "data" / "output" / "benchmarks"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: Dict[str, BenchmarkResult] = {}
        
    def run_all(self):
        """Run all benchmarks"""
        print("=" * 80)
        print("PERFORMANCE BENCHMARK SUITE")
        print("=" * 80)
        print(f"Project root: {self.project_root}")
        print(f"Iterations: {self.iterations}")
        print(f"Output directory: {self.output_dir}")
        print()
        
        # Check if configs exist
        configs_ok = self._check_configs()
        if not configs_ok:
            print("\n⚠ Warning: Some config files are missing. Results may be incomplete.")
        
        # Benchmark each script
        benchmarks = [
            ("Phase 2 Processor", ["python", "./src/replay/phase_2_processor.py", "--config", "./config/phase2.yaml"]),
            ("Phase 3 Processor", ["python", "./src/replay/phase_3_processor.py", "--config", "./config/phase3.yaml"]),
            ("Phase 3 Final Lookup", ["python", "./src/replay/phase_3_final_lookup.py", "--config", "./config/phase3_final.yaml"]),
            ("XLSX Converter", ["python", "./src/utils/xlsx_csv_converter.py", "--config", "./config/xlsx_converter.yaml"]),
        ]
        
        for name, command in benchmarks:
            result = ProcessBenchmarker.benchmark_subprocess(
                command=command,
                name=name,
                cwd=self.project_root,
                iterations=self.iterations
            )
            self.results[name] = result
        
        # Generate report
        self._generate_report()
        
    def _check_configs(self) -> bool:
        """Check if all config files exist"""
        configs = [
            "config/phase2.yaml",
            "config/phase3.yaml",
            "config/phase3_final.yaml",
            "config/xlsx_converter.yaml",
        ]
        
        all_exist = True
        for config in configs:
            path = self.project_root / config
            if not path.exists():
                print(f"  ⚠ Missing: {config}")
                all_exist = False
        
        return all_exist
    
    def _generate_report(self):
        """Generate benchmark report"""
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Console report
        for name, result in self.results.items():
            stats = result.get_stats()
            print(f"\n{name}")
            print("-" * 80)
            
            if "error" in stats:
                print(f"  ❌ {stats['error']}")
                continue
            
            exec_stats = stats["execution_time"]
            mem_stats = stats["memory_mb"]
            
            print(f"  Execution Time:")
            print(f"    Mean:   {exec_stats['mean']:.4f}s")
            print(f"    Median: {exec_stats['median']:.4f}s")
            print(f"    Range:  {exec_stats['min']:.4f}s - {exec_stats['max']:.4f}s")
            if stats['runs'] > 1:
                print(f"    StdDev: {exec_stats['stdev']:.4f}s")
            
            print(f"  Memory Usage:")
            print(f"    Mean:   {mem_stats['mean']:.2f} MB")
            print(f"    Median: {mem_stats['median']:.2f} MB")
            print(f"    Range:  {mem_stats['min']:.2f} MB - {mem_stats['max']:.2f} MB")
            
            if stats.get('records_processed'):
                print(f"  Records Processed: {stats['records_processed']}")
            if stats.get('throughput_records_per_sec'):
                print(f"  Throughput: {stats['throughput_records_per_sec']:.1f} records/sec")
            if stats.get('date_cache_hits'):
                print(f"  Date Cache Entries: {stats['date_cache_hits']}")
            if stats.get('files_processed'):
                print(f"  Files Processed: {stats['files_processed']}")
            
            if stats.get('errors'):
                print(f"  ⚠ Errors: {len(stats['errors'])}")
                for error in stats['errors']:
                    print(f"    - {error}")
        
        # Save JSON report
        json_path = self.output_dir / f"benchmark_{timestamp}.json"
        report_data = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "iterations": self.iterations,
            "results": {name: result.get_stats() for name, result in self.results.items()}
        }
        
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📊 Results saved to: {json_path}")
        
        # Save summary CSV
        csv_path = self.output_dir / f"benchmark_{timestamp}.csv"
        self._save_csv(csv_path)
        print(f"📊 CSV saved to: {csv_path}")
        
        print("\n" + "=" * 80)
    
    def _save_csv(self, path: Path):
        """Save results as CSV for easy comparison"""
        with open(path, 'w') as f:
            f.write("Script,Mean Time (s),Median Time (s),Mean Memory (MB),Records,Throughput (rec/s)\n")
            
            for name, result in self.results.items():
                stats = result.get_stats()
                if "error" in stats:
                    continue
                
                exec_time = stats['execution_time']['mean']
                exec_median = stats['execution_time']['median']
                memory = stats['memory_mb']['mean']
                records = stats.get('records_processed', 0) or 0
                throughput = stats.get('throughput_records_per_sec', 0) or 0
                
                f.write(f"{name},{exec_time:.4f},{exec_median:.4f},{memory:.2f},{records},{throughput:.1f}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark performance of all replay processing scripts"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations for each benchmark (default: 3)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for results (default: data/output/benchmarks)"
    )
    
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Run benchmark suite
    suite = BenchmarkSuite(
        project_root=project_root,
        iterations=args.iterations,
        output_dir=args.output
    )
    suite.run_all()


if __name__ == "__main__":
    main()
