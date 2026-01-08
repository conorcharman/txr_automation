#!/usr/bin/env python3
"""
Performance Profiling Script
=============================

Uses cProfile to generate detailed performance profiles of all scripts,
identifying actual bottlenecks and time-consuming functions.

Usage:
    python scripts/profile_performance.py [--script SCRIPT] [--output DIR]
    
Options:
    --script NAME     Profile specific script only (phase2, phase3, phase3final, xlsx)
    --output PATH     Output directory for profiles (default: data/output/profiles)
    --top N           Show top N functions by time (default: 20)
"""

import argparse
import cProfile
import pstats
import io
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class ProfileAnalyzer:
    """Analyze cProfile results and generate reports"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def profile_script(self, script_name: str, script_path: str, config_path: str, top_n: int = 20) -> Dict[str, Any]:
        """
        Profile a script and return analysis results.
        
        Args:
            script_name: Display name for the script
            script_path: Path to the Python script
            config_path: Path to the config file
            top_n: Number of top functions to show
            
        Returns:
            Dictionary with profiling results
        """
        print(f"\n{'=' * 80}")
        print(f"Profiling: {script_name}")
        print(f"{'=' * 80}")
        print(f"Script: {script_path}")
        print(f"Config: {config_path}")
        
        # Set up environment
        env = os.environ.copy()
        project_root = Path(__file__).parent.parent
        env['PYTHONPATH'] = str(project_root / 'src')
        
        # Create profiler
        profiler = cProfile.Profile()
        
        # Profile the script execution
        print("\nProfiling execution...", end=" ", flush=True)
        
        try:
            # Read and compile the script
            with open(script_path, 'r') as f:
                script_code = f.read()
            
            # Set up execution environment
            exec_globals = {
                '__file__': script_path,
                '__name__': '__main__',
            }
            
            # Override sys.argv to pass config argument
            original_argv = sys.argv
            sys.argv = ['profile_script', '--config', config_path]
            
            # Profile execution
            profiler.enable()
            try:
                exec(compile(script_code, script_path, 'exec'), exec_globals)
            except SystemExit:
                pass  # Scripts call sys.exit(), which is fine
            profiler.disable()
            
            # Restore original argv
            sys.argv = original_argv
            
            print("✓ Done")
            
            # Generate statistics
            stats = pstats.Stats(profiler)
            
            # Save raw profile data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            profile_file = self.output_dir / f"{script_name.lower().replace(' ', '_')}_{timestamp}.prof"
            stats.dump_stats(str(profile_file))
            print(f"Raw profile saved: {profile_file}")
            
            # Analyze results
            results = self._analyze_stats(stats, script_name, top_n)
            
            # Save analysis as JSON
            json_file = self.output_dir / f"{script_name.lower().replace(' ', '_')}_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Analysis saved: {json_file}")
            
            # Generate text report
            txt_file = self.output_dir / f"{script_name.lower().replace(' ', '_')}_{timestamp}.txt"
            self._generate_text_report(stats, txt_file, script_name, top_n)
            print(f"Text report saved: {txt_file}")
            
            return results
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def _analyze_stats(self, stats: pstats.Stats, script_name: str, top_n: int) -> Dict[str, Any]:
        """Analyze profiling statistics"""
        # Get statistics
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        
        # Capture stats to string
        s = io.StringIO()
        ps = pstats.Stats(stats.stats, stream=s)
        ps.strip_dirs()
        ps.sort_stats('cumulative')
        
        # Get total time
        total_time = sum(func[2] for func in stats.stats.values())
        total_calls = sum(func[0] for func in stats.stats.values())
        
        # Get top functions by cumulative time
        top_funcs_cumtime = []
        stats_sorted = sorted(stats.stats.items(), key=lambda x: x[1][3], reverse=True)
        for func_key, func_stats in stats_sorted[:top_n]:
            filename, line, func_name = func_key
            ncalls, tottime, cumtime, callers = func_stats
            
            # Calculate percentage
            pct_cumtime = (cumtime / total_time * 100) if total_time > 0 else 0
            pct_tottime = (tottime / total_time * 100) if total_time > 0 else 0
            
            top_funcs_cumtime.append({
                "function": func_name,
                "file": filename,
                "line": line,
                "ncalls": ncalls,
                "tottime": round(tottime, 4),
                "tottime_pct": round(pct_tottime, 2),
                "cumtime": round(cumtime, 4),
                "cumtime_pct": round(pct_cumtime, 2),
                "percall_tot": round(tottime / ncalls, 6) if ncalls > 0 else 0,
                "percall_cum": round(cumtime / ncalls, 6) if ncalls > 0 else 0,
            })
        
        # Get top functions by own time
        top_funcs_tottime = []
        stats_sorted = sorted(stats.stats.items(), key=lambda x: x[1][1], reverse=True)
        for func_key, func_stats in stats_sorted[:top_n]:
            filename, line, func_name = func_key
            ncalls, tottime, cumtime, callers = func_stats
            
            pct_tottime = (tottime / total_time * 100) if total_time > 0 else 0
            
            top_funcs_tottime.append({
                "function": func_name,
                "file": filename,
                "line": line,
                "ncalls": ncalls,
                "tottime": round(tottime, 4),
                "tottime_pct": round(pct_tottime, 2),
            })
        
        return {
            "script": script_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_time": round(total_time, 4),
                "total_calls": total_calls,
            },
            "top_functions_by_cumulative_time": top_funcs_cumtime,
            "top_functions_by_own_time": top_funcs_tottime,
        }
    
    def _generate_text_report(self, stats: pstats.Stats, output_file: Path, script_name: str, top_n: int):
        """Generate human-readable text report"""
        with open(output_file, 'w') as f:
            f.write(f"Performance Profile: {script_name}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Redirect stats output to file
            stats_stream = io.StringIO()
            ps = pstats.Stats(stats.stats, stream=stats_stream)
            ps.strip_dirs()
            
            # Top functions by cumulative time
            f.write(f"TOP {top_n} FUNCTIONS BY CUMULATIVE TIME\n")
            f.write("-" * 80 + "\n")
            ps.sort_stats('cumulative')
            ps.print_stats(top_n)
            f.write(stats_stream.getvalue())
            
            # Top functions by own time
            stats_stream = io.StringIO()
            ps = pstats.Stats(stats.stats, stream=stats_stream)
            ps.strip_dirs()
            f.write(f"\n\nTOP {top_n} FUNCTIONS BY OWN TIME\n")
            f.write("-" * 80 + "\n")
            ps.sort_stats('tottime')
            ps.print_stats(top_n)
            f.write(stats_stream.getvalue())
            
            # Callers
            stats_stream = io.StringIO()
            ps = pstats.Stats(stats.stats, stream=stats_stream)
            ps.strip_dirs()
            f.write(f"\n\nCALLERS OF TOP {min(10, top_n)} FUNCTIONS\n")
            f.write("-" * 80 + "\n")
            ps.sort_stats('cumulative')
            ps.print_callers(min(10, top_n))
            f.write(stats_stream.getvalue())
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print summary of all profiling results"""
        print("\n" + "=" * 80)
        print("PROFILING SUMMARY")
        print("=" * 80)
        
        for result in results:
            if "error" in result:
                continue
            
            print(f"\n{result['script']}")
            print("-" * 80)
            print(f"Total Time: {result['summary']['total_time']:.4f}s")
            print(f"Total Calls: {result['summary']['total_calls']:,}")
            
            print("\nTop 5 Bottlenecks (by cumulative time):")
            for i, func in enumerate(result['top_functions_by_cumulative_time'][:5], 1):
                print(f"  {i}. {func['function']} - {func['cumtime']:.4f}s ({func['cumtime_pct']:.1f}%)")
                print(f"     {func['file']}:{func['line']}")
            
            print("\nTop 5 Hot Spots (by own time):")
            for i, func in enumerate(result['top_functions_by_own_time'][:5], 1):
                print(f"  {i}. {func['function']} - {func['tottime']:.4f}s ({func['tottime_pct']:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Profile performance of replay processing scripts"
    )
    parser.add_argument(
        "--script",
        choices=["phase2", "phase3", "phase3final", "xlsx", "all"],
        default="all",
        help="Script to profile (default: all)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for profiles (default: data/output/profiles)"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top functions to show (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Set up output directory
    output_dir = args.output or project_root / "data" / "output" / "profiles"
    
    # Define scripts to profile
    scripts = {
        "phase2": {
            "name": "Phase 2 Processor",
            "script": project_root / "src" / "replay" / "phase_2_processor.py",
            "config": project_root / "config" / "local" / "replay" / "phase2.yaml",
        },
        "phase3": {
            "name": "Phase 3 Processor",
            "script": project_root / "src" / "replay" / "phase_3_processor.py",
            "config": project_root / "config" / "local" / "replay" / "phase3.yaml",
        },
        "phase3final": {
            "name": "Phase 3 Final Lookup",
            "script": project_root / "src" / "replay" / "phase_3_final_lookup.py",
            "config": project_root / "config" / "local" / "replay" / "phase3_final.yaml",
        },
        "xlsx": {
            "name": "XLSX Converter",
            "script": project_root / "src" / "utils" / "xlsx_csv_converter.py",
            "config": project_root / "config" / "local" / "utils" / "xlsx_converter.yaml",
        },
    }
    
    # Initialize analyzer
    analyzer = ProfileAnalyzer(output_dir)
    
    # Profile selected scripts
    results = []
    scripts_to_profile = [args.script] if args.script != "all" else list(scripts.keys())
    
    for script_key in scripts_to_profile:
        script_info = scripts[script_key]
        
        # Check if files exist
        if not script_info["script"].exists():
            print(f"\n⚠ Warning: Script not found: {script_info['script']}")
            continue
        if not script_info["config"].exists():
            print(f"\n⚠ Warning: Config not found: {script_info['config']}")
            continue
        
        result = analyzer.profile_script(
            script_name=script_info["name"],
            script_path=str(script_info["script"]),
            config_path=str(script_info["config"]),
            top_n=args.top
        )
        results.append(result)
    
    # Print summary
    analyzer.print_summary(results)
    
    print("\n" + "=" * 80)
    print(f"Profiling complete! Results saved to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
