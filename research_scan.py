"""Run the default Study Protocol without using the Streamlit UI."""
from __future__ import annotations

import argparse
import os
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
from src.market_calendar import us_equity_market_status
from src.quality_diagnostics import discovery_diagnostic_summary
from src.research_repository import (
    DATABASE_URL_ENV,
    RESEARCH_REPOSITORY_BACKEND_ENV,
    research_repository_from_target,
    research_repository_target_from_env,
)
from src.study_protocol import (
    DEFAULT_STUDY_PROTOCOL,
    RUN_MODE_RESEARCH_SCRIPT,
    RUN_MODE_SCHEDULED,
    RunMode,
)
from src.technical_analysis import technical_analysis_rows_for_symbols
from src.signal_repository import SignalRepository
from src.technical_observation_service import archive_technical_observations_and_signals
from src.tradier_client import TradierClient
from src.universe import load_universe


ROOT = Path(__file__).resolve().parent
CLOUD_RUNNER_ENV = "CLOUD_RUNNER"
RESEARCH_RUN_MODE_ENV = "RESEARCH_RUN_MODE"
SCHEDULED_TIME_LABEL_ENV = "SCHEDULED_TIME_LABEL"
RESEARCH_SCHEDULED_TIME_LABEL_ENV = "RESEARCH_SCHEDULED_TIME_LABEL"
TRADIER_API_TOKEN_ENV = "TRADIER_API_TOKEN"
TRADIER_ENVIRONMENT_ENV = "TRADIER_ENVIRONMENT"


def run_default_research_scan(
    *,
    run_mode: RunMode = RUN_MODE_RESEARCH_SCRIPT,
    scheduled_time_label: str | None = None,
    enforce_market_calendar: bool = True,
) -> dict[str, object]:
    load_dotenv(ROOT / ".env")
    protocol = DEFAULT_STUDY_PROTOCOL
    universe_path = ROOT / protocol.universe_csv
    universe = load_universe(universe_path)
    universe_symbols = [item.symbol for item in universe]
    scan_timestamp = datetime.now(EASTERN_TIME)
    market_status = us_equity_market_status(scan_timestamp.date())
    if (
        run_mode == RUN_MODE_SCHEDULED
        and enforce_market_calendar
        and not market_status.trading_day
    ):
        return {
            "scan_id": "",
            "scan_timestamp": scan_timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
            "contracts_evaluated": 0,
            "passing_count": 0,
            "near_miss_count": 0,
            "rejected_count": 0,
            "database_path": "",
            "repository_backend": "",
            "row_counts": {},
            "discovery_error_count": 0,
            "run_mode": run_mode,
            "scheduled_time_label": scheduled_time_label,
            "skipped": True,
            "skip_reason": f"U.S. equity market closed: {market_status.reason}",
            "market_early_close": market_status.early_close,
        }

    repository_target = research_repository_target_from_env()
    repository = research_repository_from_target(repository_target)
    repository.initialize()

    scan_id = f"research-scan-{scan_timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    formatted_scan_timestamp = scan_timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z")

    client = TradierClient()
    _opportunity_rows, discovery_errors, evaluated_rows = discover_universe_opportunities(
        client,
        universe_symbols,
        scan_timestamp.date(),
        option_type=protocol.option_type,
        min_dte=protocol.dte_min,
        max_dte=protocol.dte_max,
    )
    technical_rows, technical_errors = technical_analysis_rows_for_symbols(
        client,
        universe_symbols,
        scan_id=scan_id,
        technical_timestamp=formatted_scan_timestamp,
        end_date=scan_timestamp.date(),
    )
    contract_rows = evaluated_contract_export_rows(
        evaluated_rows,
        scan_id,
        formatted_scan_timestamp,
        protocol.study_name,
        universe_symbols,
    )
    rule_rows = rule_evaluation_export_rows(evaluated_rows, scan_id)
    persistence = archive_technical_observations_and_signals(
        technical_rows,
        archive_observations=lambda rows: repository.archive_opportunity_scan(
            scan_id=scan_id, scan_timestamp=formatted_scan_timestamp,
            universe_name=protocol.study_name, option_type=protocol.option_type,
            dte_min=protocol.dte_min, dte_max=protocol.dte_max,
            evaluation_profile=evaluation_profile_export_fields(),
            evaluated_contract_rows=evaluated_rows, contract_export_rows=contract_rows,
            rule_export_rows=rule_rows, technical_rows=rows,
            study_protocol=protocol.metadata(
                scheduled_time_label=scheduled_time_label, run_mode=run_mode,
            ),
        ),
        signal_repository=SignalRepository(repository_target),
    )
    summary = discovery_diagnostic_summary(evaluated_rows)
    return {
        "scan_id": scan_id,
        "scan_timestamp": formatted_scan_timestamp,
        "contracts_evaluated": summary["Contracts Evaluated"],
        "passing_count": summary["Passing Contracts Count"],
        "near_miss_count": summary["True Near Miss Count"],
        "rejected_count": summary["Rejected Count"],
        "database_path": repository_target.display_location,
        "repository_backend": repository_target.backend,
        "row_counts": persistence.archive_result,
        "signal_persistence_error": persistence.signal_persistence_error,
        "discovery_error_count": len(discovery_errors),
        "technical_error_count": len(technical_errors),
        "run_mode": run_mode,
        "scheduled_time_label": scheduled_time_label,
        "skipped": False,
        "skip_reason": "",
        "market_early_close": market_status.early_close,
    }


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_scheduled_time_label() -> str | None:
    return os.getenv(SCHEDULED_TIME_LABEL_ENV) or os.getenv(RESEARCH_SCHEDULED_TIME_LABEL_ENV)


def _validate_cloud_environment(run_mode: RunMode, scheduled_time_label: str | None) -> None:
    missing = [
        name
        for name in (TRADIER_API_TOKEN_ENV, TRADIER_ENVIRONMENT_ENV, DATABASE_URL_ENV)
        if not os.getenv(name)
    ]
    if not os.getenv(RESEARCH_REPOSITORY_BACKEND_ENV):
        missing.append(RESEARCH_REPOSITORY_BACKEND_ENV)
    if not os.getenv(RESEARCH_RUN_MODE_ENV):
        missing.append(RESEARCH_RUN_MODE_ENV)
    if run_mode == RUN_MODE_SCHEDULED and not scheduled_time_label:
        missing.append(SCHEDULED_TIME_LABEL_ENV)
    if run_mode != RUN_MODE_SCHEDULED:
        raise RuntimeError("Cloud runner requires RESEARCH_RUN_MODE=scheduled.")
    if missing:
        raise RuntimeError(
            "Missing required cloud environment variable(s): " + ", ".join(sorted(set(missing)))
        )


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
        "--from-env",
        action="store_true",
        help="Read run mode and schedule label from environment variables.",
    )
    parser.add_argument(
        "--cloud-runner",
        action="store_true",
        help="Validate cloud cron environment before running.",
    )
    parser.add_argument(
        "--allow-non-trading-day",
        action="store_true",
        help="Bypass scheduled-run market-calendar skipping for manual validation.",
    )
    parser.add_argument(
        "--scheduled-time-label",
        help='Schedule label archived with scheduled runs, such as "10:00 ET".',
    )
    args = parser.parse_args()
    if args.from_env or _env_flag(CLOUD_RUNNER_ENV):
        args.run_mode = os.getenv(RESEARCH_RUN_MODE_ENV, args.run_mode)
        args.scheduled_time_label = _env_scheduled_time_label() or args.scheduled_time_label
    if args.run_mode not in (RUN_MODE_RESEARCH_SCRIPT, RUN_MODE_SCHEDULED):
        parser.error("--run-mode must be research-script or scheduled")
    if args.cloud_runner or _env_flag(CLOUD_RUNNER_ENV):
        _validate_cloud_environment(args.run_mode, args.scheduled_time_label)
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
        enforce_market_calendar=not args.allow_non_trading_day,
    )
    if result["skipped"]:
        print(f"skipped: {result['skip_reason']}")
        print(f"scan_timestamp: {result['scan_timestamp']}")
        print(f"run_mode: {result['run_mode']}")
        print(f"scheduled_time_label: {result['scheduled_time_label'] or ''}")
        return
    print(f"scan_id: {result['scan_id']}")
    print(f"scan_timestamp: {result['scan_timestamp']}")
    print(f"run_mode: {result['run_mode']}")
    print(f"scheduled_time_label: {result['scheduled_time_label'] or ''}")
    print(f"repository backend: {result['repository_backend']}")
    print(f"contracts evaluated: {result['contracts_evaluated']}")
    print(f"passing count: {result['passing_count']}")
    print(f"near miss count: {result['near_miss_count']}")
    print(f"rejected count: {result['rejected_count']}")
    print(f"technical characterization rows: {result['row_counts'].get('technical_characterization', 0)}")
    print(f"technical error count: {result['technical_error_count']}")
    if result["signal_persistence_error"]:
        print("Analysis archived, but derived Signals were not persisted: " + result["signal_persistence_error"])
    print(f"database path: {result['database_path']}")


if __name__ == "__main__":
    main()
