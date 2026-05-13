#!/usr/bin/env python3
"""
Automation CLI
==============

External CLI entry points for Power Automate and system-level automation.
All commands emit JSON to stdout for machine parsing.

Commands:
    run-pipeline     Run a pipeline immediately and write _run_status.json
    list-schedules   List all saved schedules as JSON
    trigger-schedule Trigger a named schedule immediately by ID

Note:
    ``list-schedules`` and ``trigger-schedule`` depend on PySide6 via
    :class:`~src.gui.scheduler.store.ScheduleStore` (QSettings backend).
    Ensure a display is available or use a virtual display when calling
    these commands from headless environments.

Version 1.0 Changes:
- Initial implementation for Phase 4 Power Automate integration
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to sys.path so ``src.*`` imports resolve when the script
# is run directly or via an editable install.
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.gui.scheduler import PipelineExecutor, ScheduleStore
from src.gui.scheduler.models import (
    PipelineStep,
    RunStatus,
    ScheduleConfig,
    SchedulePeriod,
    ValidationType,
)

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

_VALIDATION_TYPE_MAP: dict[str, ValidationType] = {
    "buyer_id": ValidationType.BUYER_ID,
    "seller_id": ValidationType.SELLER_ID,
    "inconsistent_buyer_id": ValidationType.INCONSISTENT_BUYER_ID,
    "inconsistent_seller_id": ValidationType.INCONSISTENT_SELLER_ID,
    "fund_trade_buyer_dm": ValidationType.FUND_TRADE_BUYER_DM,
    "fund_trade_seller_dm": ValidationType.FUND_TRADE_SELLER_DM,
    "non_zero_net_qty": ValidationType.NON_ZERO_NET_QTY,
    "non_zero_net_amt": ValidationType.NON_ZERO_NET_AMT,
    "incorrect_net_amount": ValidationType.INCORRECT_NET_AMOUNT,
}

_STEP_MAP: dict[str, PipelineStep] = {s.value: s for s in PipelineStep}


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_run_pipeline(args: argparse.Namespace) -> int:
    """Run a pipeline immediately and write _run_status.json.

    Args:
        args: Parsed CLI arguments.

    Returns:
        0 on success, 1 on failure.
    """
    vtypes = [
        _VALIDATION_TYPE_MAP[v.strip()]
        for v in args.validation_types.split(",")
        if v.strip()
    ]
    steps = [
        _STEP_MAP[s.strip()]
        for s in args.steps.split(",")
        if s.strip()
    ]
    period = SchedulePeriod(fiscal_year=args.fiscal_year, quarter=args.quarter)

    if args.dry_run:
        out = {
            "status": "dry_run",
            "validation_types": [v.value for v in vtypes],
            "fiscal_year": args.fiscal_year,
            "quarter": args.quarter,
            "steps": [s.value for s in steps],
            "output_dir": args.output_dir,
        }
        print(json.dumps(out, indent=2))
        return 0

    config = ScheduleConfig(
        schedule_id=str(uuid.uuid4()),
        name=f"ad-hoc-{args.fiscal_year}-{args.quarter}",
        enabled=True,
        validation_types=vtypes,
        pipeline_steps=steps,
        schedule_period=period,
        output_directory=args.output_dir,
    )

    executor = PipelineExecutor()
    record = executor.execute(config)

    output_dir = Path(args.output_dir)
    status_path = output_dir / "_run_status.json"
    status = {
        "run_id": record.run_id,
        "schedule_id": record.schedule_id,
        "status": record.status.value,
        "started_at": record.started_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "output_files": record.output_files,
        "error_message": record.error_message,
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if record.status == RunStatus.SUCCESS else 1


def cmd_list_schedules(args: argparse.Namespace) -> int:  # noqa: ARG001
    """List all saved schedules as JSON.

    Args:
        args: Parsed CLI arguments (unused).

    Returns:
        Always 0.
    """
    store = ScheduleStore()
    schedules = store.list_schedules()
    out = [
        {
            "schedule_id": s.schedule_id,
            "name": s.name,
            "enabled": s.enabled,
            "frequency": s.frequency.value,
            "next_run": s.next_run.isoformat() if s.next_run else None,
            "last_run": s.last_run.isoformat() if s.last_run else None,
        }
        for s in schedules
    ]
    print(json.dumps(out, indent=2))
    return 0


def cmd_trigger_schedule(args: argparse.Namespace) -> int:
    """Trigger a named schedule immediately.

    Args:
        args: Parsed CLI arguments; uses ``args.schedule_id``.

    Returns:
        0 on success, 1 if the schedule is not found or execution fails.
    """
    store = ScheduleStore()
    config = store.load_schedule(args.schedule_id)
    if not config:
        print(json.dumps({"error": f"Schedule {args.schedule_id!r} not found"}))
        return 1

    executor = PipelineExecutor()
    record = executor.execute(config)

    output_dir = Path(config.output_directory or ".")
    status_path = output_dir / "_run_status.json"
    status = {
        "run_id": record.run_id,
        "schedule_id": record.schedule_id,
        "status": record.status.value,
        "started_at": record.started_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "output_files": record.output_files,
        "error_message": record.error_message,
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if record.status == RunStatus.SUCCESS else 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the txr-automate Power Automate CLI."""
    parser = argparse.ArgumentParser(
        prog="txr-automate",
        description="TXR Automation — Power Automate integration CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run-pipeline
    p_run = sub.add_parser("run-pipeline", help="Run a pipeline immediately")
    p_run.add_argument(
        "--validation-types",
        required=True,
        help="Comma-separated validation types, e.g. buyer_id,seller_id",
    )
    p_run.add_argument("--fiscal-year", required=True, help="e.g. FY26")
    p_run.add_argument("--quarter", required=True, help="e.g. Q2")
    p_run.add_argument(
        "--steps",
        default="validate",
        help="Comma-separated pipeline steps: extract,collate,validate,push",
    )
    p_run.add_argument("--output-dir", required=True, help="Output directory for results")
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without executing",
    )
    p_run.set_defaults(func=cmd_run_pipeline)

    # list-schedules
    p_list = sub.add_parser("list-schedules", help="List saved schedules as JSON")
    p_list.set_defaults(func=cmd_list_schedules)

    # trigger-schedule
    p_trigger = sub.add_parser("trigger-schedule", help="Trigger a schedule immediately")
    p_trigger.add_argument("--schedule-id", required=True, help="UUID of the schedule")
    p_trigger.set_defaults(func=cmd_trigger_schedule)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
