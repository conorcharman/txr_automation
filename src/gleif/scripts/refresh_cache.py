#!/usr/bin/env python3
"""
GLEIF Cache Refresh CLI
=======================

Command-line tool for refreshing the local GLEIF LEI SQLite cache from the
GLEIF Golden Copy bulk data file.

Usage:
    # Full rebuild from the latest GLEIF Golden Copy
    gleif-refresh --type full

    # Full rebuild, skipping the ISIN-to-LEI mapping download
    gleif-refresh --type full --skip-isin-map

    # 24-hour delta update (updates changed records only; no truncation)
    gleif-refresh --type delta

    # Different delta window
    gleif-refresh --type delta --delta-type 7d

    # Use a custom database location
    gleif-refresh --type full --db /data/gleif_cache.db

    # Override the Golden Copy download URL (e.g. manually obtained link)
    gleif-refresh --type full --golden-copy-url "https://leidata.gleif.org/..."

    # Use a config file for common settings
    gleif-refresh --type full --config config/local/gleif_config.yaml
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    _YAML_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from core.progress import ProgressTracker
from gleif.cache import GleifCacheManager
from gleif.client import GleifApiClient
from gleif.refresher import GleifRefresher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the local GLEIF LEI reference data cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--type",
        dest="refresh_type",
        choices=["full", "delta"],
        required=True,
        help=(
            "'full' rebuilds the entire cache from the GLEIF Golden Copy. "
            "'delta' applies incremental updates from a delta file (default window: 24h)."
        ),
    )
    parser.add_argument(
        "--delta-type",
        choices=["8h", "24h", "7d", "31d"],
        default="24h",
        help="Delta window when --type delta is used (default: 24h).",
    )
    parser.add_argument(
        "--skip-isin-map",
        action="store_true",
        help=(
            "When running a full refresh, skip downloading the ISIN-to-LEI mapping "
            "file.  Use this when only LEI validation is needed and ISIN lookups "
            "are not required."
        ),
    )
    parser.add_argument(
        "--golden-copy-url",
        type=str,
        default=None,
        metavar="URL",
        help=(
            "Override the Golden Copy download URL.  Use this when the default "
            "leidata.gleif.org URL returns 403 — supply a manually obtained link "
            "from https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy"
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the SQLite cache database (default: data/gleif_cache.db).",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory for temporary download files.  "
            "Defaults to a system temp directory removed after completion."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a YAML config file.  Defaults to "
            "config/local/gleif_config.yaml if that file exists."
        ),
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
        Parsed config dict, or empty dict if loading fails.
    """
    if not _YAML_AVAILABLE:
        print(
            "WARNING: PyYAML not installed — --config flag ignored. "
            "Run: pip install pyyaml"
        )
        return {}
    if not config_path.exists():
        print(f"WARNING: Config file not found: {config_path}")
        return {}
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}  # type: ignore[union-attr]


def main() -> None:
    """Entry point for the gleif-refresh console script."""
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # --- Resolve config -------------------------------------------------
    _DEFAULT_CONFIG = _REPO_ROOT / "config" / "local" / "gleif_config.yaml"
    config_path: Optional[Path] = args.config or (
        _DEFAULT_CONFIG if _DEFAULT_CONFIG.exists() else None
    )
    cfg: Dict[str, Any] = {}
    if config_path:
        if config_path != args.config:
            logging.getLogger(__name__).info(
                "Using auto-discovered config: %s", config_path
            )
        cfg = _load_yaml_config(config_path)

    # --- Resolve DB path: CLI flag > config > default -------------------
    _default_db = _REPO_ROOT / "data" / "gleif_cache.db"
    db_path: Path = args.db or _default_db
    if args.db is None and (cfg.get("database") or {}).get("path"):
        raw = cfg["database"]["path"]
        db_path = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    # --- Resolve Golden Copy URL: CLI flag > config > default -----------
    golden_copy_url: Optional[str] = args.golden_copy_url
    if golden_copy_url is None and (cfg.get("gleif") or {}).get("golden_copy_url"):
        golden_copy_url = cfg["gleif"]["golden_copy_url"]

    # --- Resolve staging dir: CLI flag > config > None (use temp dir) ---
    staging_dir: Optional[Path] = args.staging_dir
    if staging_dir is None and (cfg.get("gleif") or {}).get("staging_dir"):
        raw = cfg["gleif"]["staging_dir"]
        staging_dir = Path(raw) if Path(raw).is_absolute() else _REPO_ROOT / raw

    # --- Build components -----------------------------------------------
    cache = GleifCacheManager(db_path=db_path)
    cache.initialise_db()

    api_client_kwargs = {}
    if golden_copy_url:
        api_client_kwargs["golden_copy_url"] = golden_copy_url
    api_client = GleifApiClient(**api_client_kwargs)

    # Set up progress tracking if job_id is available (e.g., from Celery task)
    job_id = os.environ.get("JOB_ID")
    redis_url = os.environ.get("REDIS_URL")
    progress_tracker: Optional[ProgressTracker] = None
    progress_callback: Optional[Callable[[str, int], None]] = None
    
    if job_id:
        progress_tracker = ProgressTracker(
            job_id=job_id,
            total_phases=4 if args.skip_isin_map else 4,
            redis_url=redis_url,
        )
        progress_callback = progress_tracker.report_phase_progress

    refresher = GleifRefresher(
        cache=cache,
        api_client=api_client,
        staging_dir=staging_dir,
        progress_callback=progress_callback,
    )

    # --- Run refresh ----------------------------------------------------
    if args.refresh_type == "full":
        print(f"Starting GLEIF full refresh -> {db_path}")
        result = refresher.run_full_refresh(skip_isin_map=args.skip_isin_map)
    else:
        print(
            f"Starting GLEIF delta refresh (type: {args.delta_type}) -> {db_path}"
        )
        result = refresher.run_delta_refresh(delta_type=args.delta_type)
    
    # Signal completion if progress tracker is active
    if progress_tracker:
        progress_tracker.complete()

    # --- Report results -------------------------------------------------
    print(
        f"\nRefresh complete:\n"
        f"  Files processed : {result.files_processed}\n"
        f"  Files skipped   : {result.files_skipped}\n"
        f"  Files failed    : {result.files_failed}\n"
        f"  Total records   : {result.total_records:,}\n"
        f"  Cache location  : {db_path}"
    )

    if result.files_failed > 0:
        print(
            f"\nWARNING: {result.files_failed} file(s) failed to process. "
            "Check the log output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
