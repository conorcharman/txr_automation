#!/usr/bin/env python3
"""
FIRDS Cache Refresh CLI
=======================

Command-line tool for refreshing the local FCA FIRDS SQLite cache.

Usage:
    # Full rebuild from the most recent Saturday's FULINS files
    python -m firds.scripts.refresh_cache --type full

    # Full rebuild for a specific publication date
    python -m firds.scripts.refresh_cache --type full --date 2026-03-07

    # Delta refresh (yesterday's DLTINS by default)
    python -m firds.scripts.refresh_cache --type delta

    # Delta refresh from a specific date up to today
    python -m firds.scripts.refresh_cache --type delta --since 2026-03-01

    # Use a custom config file
    python -m firds.scripts.refresh_cache --type delta --config config/local/firds.yaml
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Allow running as `python -m firds.scripts.refresh_cache` from the repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from core.progress import ProgressTracker
from firds.cache import FirdsCacheManager
from firds.client import FirdsApiClient
from firds.refresher import FirdsRefresher, _most_recent_saturday


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the local FCA FIRDS instrument reference data cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--type",
        dest="refresh_type",
        choices=["full"],
        required=True,
        help="Type of refresh: 'full' rebuilds the cache from in-scope FULINS files "
             "(C = Collective Investment Vehicles, D = Debt, E = Equities) and FULCAN "
             "cancellation files.  Run weekly on Saturdays.",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Publication date for the full refresh (must be a Saturday). "
             "Defaults to the most recent Saturday.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_REPO_ROOT / "data" / "firds_cache.db",
        metavar="PATH",
        help="Path to the SQLite cache database (default: data/firds_cache.db).",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Directory for temporary ZIP/XML files during download. "
             "Defaults to a system temp directory that is removed after completion.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to a YAML config file. Defaults to config/local/firds_config.yaml "
             "if that file exists. Sets defaults for --db and --staging-dir; "
             "explicit CLI flags take precedence.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args()


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load a YAML config file and return its contents as a dict.

    Args:
        config_path: Path to the YAML file.

    Returns:
        Parsed configuration dictionary, or an empty dict if loading fails.
    """
    if not _YAML_AVAILABLE:
        print("WARNING: PyYAML not installed — --config flag ignored. Run: pip install pyyaml")
        return {}
    if not config_path.exists():
        print(f"WARNING: Config file not found: {config_path}")
        return {}
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def main() -> None:
    """Entry point for the firds-refresh console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # --- Resolve config file: explicit flag > auto-discovered default ---
    _DEFAULT_CONFIG = _REPO_ROOT / "config" / "local" / "firds_config.yaml"
    config_path: Optional[Path] = args.config or (_DEFAULT_CONFIG if _DEFAULT_CONFIG.exists() else None)

    cfg: Dict[str, Any] = {}
    if config_path:
        if config_path != args.config:  # auto-discovered, not user-supplied
            logging.getLogger(__name__).info("Using auto-discovered config: %s", config_path)
        cfg = _load_yaml_config(config_path)

    db_path: Path = args.db
    if db_path == _REPO_ROOT / "data" / "firds_cache.db" and cfg.get("database", {}).get("path"):
        db_path = Path(cfg["database"]["path"])
        if not db_path.is_absolute():
            db_path = _REPO_ROOT / db_path

    staging_dir: Optional[Path] = args.staging_dir
    if staging_dir is None and cfg.get("staging", {}).get("directory"):
        staging_dir = Path(cfg["staging"]["directory"])

    db_path.parent.mkdir(parents=True, exist_ok=True)

    cache = FirdsCacheManager(db_path=db_path)
    cache.initialise_db()

    # Set up progress tracking if job_id is available (e.g., from Celery task)
    job_id = os.environ.get("JOB_ID")
    redis_url = os.environ.get("REDIS_URL")
    progress_tracker: Optional[ProgressTracker] = None
    progress_callback: Optional[Callable[[str, int], None]] = None
    
    if job_id:
        progress_tracker = ProgressTracker(
            job_id=job_id,
            total_phases=2,  # fulins and fulcan
            redis_url=redis_url,
        )
        progress_callback = progress_tracker.report_phase_progress

    refresher = FirdsRefresher(
        cache=cache,
        api_client=FirdsApiClient(),
        staging_dir=staging_dir,
        progress_callback=progress_callback,
    )

    target = args.date or _most_recent_saturday()
    _print_banner(f"FIRDS Full Refresh  |  target date: {target}  |  DB: {db_path}")
    result = refresher.run_full_refresh(target_date=target)
    
    # Signal completion if progress tracker is active
    if progress_tracker:
        progress_tracker.complete()

    _print_separator()
    status = "OK" if result.files_failed == 0 else f"FAILED ({result.files_failed} error(s))"
    print(
        f"  Result   : {status}\n"
        f"  Processed: {result.files_processed} file(s)\n"
        f"  Skipped  : {result.files_skipped} file(s) (already in sync log)\n"
        f"  Failed   : {result.files_failed} file(s)\n"
        f"  Records  : {result.total_records:,} written to DB"
    )
    _print_separator()

    if result.files_failed > 0:
        sys.exit(1)


def _print_banner(title: str) -> None:
    """Print a clearly visible step banner to stdout."""
    bar = "=" * (len(title) + 4)
    print(f"\n{bar}\n  {title}\n{bar}")


def _print_separator() -> None:
    """Print a short horizontal rule."""
    print("-" * 60)


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a :class:`~datetime.date`.

    Args:
        value: Date string in YYYY-MM-DD format.

    Returns:
        Parsed :class:`~datetime.date`.

    Raises:
        argparse.ArgumentTypeError: If the string cannot be parsed.
    """
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM-DD format."
        )


if __name__ == "__main__":
    main()
