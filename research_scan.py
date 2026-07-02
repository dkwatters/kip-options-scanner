"""Run the default Study Protocol without using the Streamlit UI."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from app import (
    EASTERN_TIME,
    discover_universe_opportunities,
    evaluated_contract_export_rows,
    rule_evaluation_export_rows,
)
from src.evaluation_profile import evaluation_profile_export_fields
from src.quality_diagnostics import discovery_diagnostic_summary
from src.research_repository import DEFAULT_RESEARCH_DB_PATH, archive_opportunity_scan
from src.study_protocol import (
    DEFAULT_STUDY_PROTOCOL,
    RUN_MODE_RESEARCH_SCRIPT,
    RUN_MODE_SCHEDULED,
    RunMode,
)
from src.tradier_client import TradierClient
from src.universe import load_universe


ROOT = Path(__file__).resolve().parent


def run_default_research_scan(
    *,
    run_mode: RunMode = RUN_MODE_RESEARCH_SCRIPT,
    scheduled_time_label: str | None = None,
) -> dict[str, object]:
    load_dotenv(ROOT / ".env")
    protocol = DEFAULT_STUDY_PROTOCOL
    universe_path = ROOT / protocol.universe_csv
    universe = load_universe(universe_path)
    universe_symbols = [item.symbol for item in universe]
    scan_timestamp = datetime.now(EASTERN_TIME)
    scan_id = f"research-scan-{scan_timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    formatted_scan_timestamp = scan_timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z")

    _opportunity_rows, discovery_errors, evaluated_rows = discover_universe_opportunities(
        TradierClient(),
        universe_symbols,
        scan_timestamp.date(),
        option_type=protocol.option_type,
        min_dte=protocol.dte_min,
        max_dte=protocol.dte_max,
    )
    contract_rows = evaluated_contract_export_rows(
        evaluated_rows,
        scan_id,
        formatted_scan_timestamp,
        protocol.study_name,
        universe_symbols,
    )
    rule_rows = rule_evaluation_export_rows(evaluated_rows, scan_id)
    row_counts = archive_opportunity_scan(
        scan_id=scan_id,
        scan_timestamp=formatted_scan_timestamp,
        universe_name=protocol.study_name,
        option_type=protocol.option_type,
        dte_min=protocol.dte_min,
        dte_max=protocol.dte_max,
        evaluation_profile=evaluation_profile_export_fields(),
        evaluated_contract_rows=evaluated_rows,
        contract_export_rows=contract_rows,
        rule_export_rows=rule_rows,
        study_protocol=protocol.metadata(
            scheduled_time_label=scheduled_time_label,
            run_mode=run_mode,
        ),
        database_path=DEFAULT_RESEARCH_DB_PATH,
    )
    summary = discovery_diagnostic_summary(evaluated_rows)
    return {
        "scan_id": scan_id,
        "scan_timestamp": formatted_scan_timestamp,
        "contracts_evaluated": summary["Contracts Evaluated"],
        "passing_count": summary["Passing Contracts Count"],
        "near_miss_count": summary["True Near Miss Count"],
        "rejected_count": summary["Rejected Count"],
        "database_path": str(DEFAULT_RESEARCH_DB_PATH),
        "row_counts": row_counts,
        "discovery_error_count": len(discovery_errors),
        "run_mode": run_mode,
        "scheduled_time_label": scheduled_time_label,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the default SP-001 research scan."
    )
    parser.add_argument(
        "--run-mode",
        choices=(RUN_MODE_RESEARCH_SCRIPT, RUN_MODE_SCHEDULED),
        default=RUN_MODE_RESEARCH_SCRIPT,
        help=(
            "Archive run mode. Default is research-script. Use scheduled for "
            "Windows Task Scheduler runs."
        ),
    )
    parser.add_argument(
        "--scheduled-time-label",
        help='Schedule label archived with scheduled runs, such as "10:00 ET".',
    )
    args = parser.parse_args()
    if args.run_mode == RUN_MODE_SCHEDULED and not args.scheduled_time_label:
        parser.error("--scheduled-time-label is required when --run-mode scheduled")
    if args.run_mode != RUN_MODE_SCHEDULED and args.scheduled_time_label:
        parser.error("--scheduled-time-label is only valid with --run-mode scheduled")
    return args


def main() -> None:
    args = parse_args()
    result = run_default_research_scan(
        run_mode=args.run_mode,
        scheduled_time_label=args.scheduled_time_label,
    )
    print(f"scan_id: {result['scan_id']}")
    print(f"scan_timestamp: {result['scan_timestamp']}")
    print(f"run_mode: {result['run_mode']}")
    print(f"scheduled_time_label: {result['scheduled_time_label'] or ''}")
    print(f"contracts evaluated: {result['contracts_evaluated']}")
    print(f"passing count: {result['passing_count']}")
    print(f"near miss count: {result['near_miss_count']}")
    print(f"rejected count: {result['rejected_count']}")
    print(f"database path: {result['database_path']}")


if __name__ == "__main__":
    main()
