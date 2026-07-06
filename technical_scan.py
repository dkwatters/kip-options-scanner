"""Run a TAM-only technical characterization scan without Opportunity Discovery."""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.market_calendar import us_equity_market_status
from src.research_repository import (
    DATABASE_URL_ENV,
    RESEARCH_REPOSITORY_BACKEND_ENV,
    research_repository_from_target,
    research_repository_target_from_env,
)
from src.study_protocol import (
    RUN_MODE_RESEARCH_SCRIPT,
    RUN_MODE_SCHEDULED,
    TAM_STUDY_PROTOCOL,
    RunMode,
)
from src.technical_analysis import technical_analysis_rows_for_symbols
from src.tradier_client import TradierClient
from src.universe import load_universe


ROOT = Path(__file__).resolve().parent
EASTERN_TIME = ZoneInfo("America/New_York")
CLOUD_RUNNER_ENV = "CLOUD_RUNNER"
RESEARCH_RUN_MODE_ENV = "RESEARCH_RUN_MODE"
TAM_RUN_MODE_ENV = "TAM_RUN_MODE"
SCHEDULED_TIME_LABEL_ENV = "SCHEDULED_TIME_LABEL"
RESEARCH_SCHEDULED_TIME_LABEL_ENV = "RESEARCH_SCHEDULED_TIME_LABEL"
TAM_SCHEDULED_TIME_LABEL_ENV = "TAM_SCHEDULED_TIME_LABEL"
TRADIER_API_TOKEN_ENV = "TRADIER_API_TOKEN"
TRADIER_ENVIRONMENT_ENV = "TRADIER_ENVIRONMENT"


def run_tam_technical_scan(
    *,
    run_mode: RunMode = RUN_MODE_RESEARCH_SCRIPT,
    scheduled_time_label: str | None = None,
    enforce_market_calendar: bool = True,
    client: object | None = None,
    scan_timestamp: datetime | None = None,
) -> dict[str, object]:
    """Collect and persist TAM rows without fetching option chains or running CQM."""
    load_dotenv(ROOT / ".env")
    protocol = TAM_STUDY_PROTOCOL
    universe_path = ROOT / protocol.universe_csv
    universe = load_universe(universe_path)
    universe_symbols = [item.symbol for item in universe]
    timestamp = scan_timestamp or datetime.now(EASTERN_TIME)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=EASTERN_TIME)
    market_status = us_equity_market_status(timestamp.date())

    if (
        run_mode == RUN_MODE_SCHEDULED
        and enforce_market_calendar
        and not market_status.trading_day
    ):
        return {
            "scan_id": "",
            "technical_timestamp": timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
            "database_path": "",
            "repository_backend": "",
            "row_counts": {},
            "technical_error_count": 0,
            "run_mode": run_mode,
            "scheduled_time_label": scheduled_time_label,
            "skipped": True,
            "skip_reason": f"U.S. equity market closed: {market_status.reason}",
            "market_early_close": market_status.early_close,
        }

    repository_target = research_repository_target_from_env()
    repository = research_repository_from_target(repository_target)
    repository.initialize()

    scan_id = f"tam-scan-{timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    formatted_timestamp = timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    market_data_client = client or TradierClient()
    technical_rows, technical_errors = technical_analysis_rows_for_symbols(
        market_data_client,
        universe_symbols,
        scan_id=scan_id,
        technical_timestamp=formatted_timestamp,
        end_date=timestamp.date(),
    )
    row_counts = repository.archive_technical_observations(
        scan_id=scan_id,
        technical_rows=technical_rows,
        study_protocol=protocol.metadata(
            scheduled_time_label=scheduled_time_label,
            run_mode=run_mode,
        ),
    )

    return {
        "scan_id": scan_id,
        "technical_timestamp": formatted_timestamp,
        "database_path": repository_target.display_location,
        "repository_backend": repository_target.backend,
        "row_counts": row_counts,
        "technical_error_count": len(technical_errors),
        "run_mode": run_mode,
        "scheduled_time_label": scheduled_time_label,
        "skipped": False,
        "skip_reason": "",
        "market_early_close": market_status.early_close,
    }


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_run_mode(default: str) -> str:
    return os.getenv(TAM_RUN_MODE_ENV) or os.getenv(RESEARCH_RUN_MODE_ENV, default)


def _env_scheduled_time_label() -> str | None:
    return (
        os.getenv(TAM_SCHEDULED_TIME_LABEL_ENV)
        or os.getenv(SCHEDULED_TIME_LABEL_ENV)
        or os.getenv(RESEARCH_SCHEDULED_TIME_LABEL_ENV)
    )


def _validate_cloud_environment(run_mode: RunMode, scheduled_time_label: str | None) -> None:
    missing = [
        name
        for name in (TRADIER_API_TOKEN_ENV, TRADIER_ENVIRONMENT_ENV, DATABASE_URL_ENV)
        if not os.getenv(name)
    ]
    if not os.getenv(RESEARCH_REPOSITORY_BACKEND_ENV):
        missing.append(RESEARCH_REPOSITORY_BACKEND_ENV)
    if not (os.getenv(TAM_RUN_MODE_ENV) or os.getenv(RESEARCH_RUN_MODE_ENV)):
        missing.append(TAM_RUN_MODE_ENV)
    if run_mode == RUN_MODE_SCHEDULED and not scheduled_time_label:
        missing.append(TAM_SCHEDULED_TIME_LABEL_ENV)
    if run_mode != RUN_MODE_SCHEDULED:
        raise RuntimeError("Cloud TAM runner requires TAM_RUN_MODE=scheduled.")
    if missing:
        raise RuntimeError(
            "Missing required cloud environment variable(s): " + ", ".join(sorted(set(missing)))
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TAM-001 technical characterization scan."
    )
    parser.add_argument(
        "--run-mode",
        choices=(RUN_MODE_RESEARCH_SCRIPT, RUN_MODE_SCHEDULED),
        default=RUN_MODE_RESEARCH_SCRIPT,
        help="Archive run mode. Use scheduled for daily TAM observations.",
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
        help='Schedule label archived with scheduled runs, such as "16:30 ET".',
    )
    args = parser.parse_args()
    if args.from_env or _env_flag(CLOUD_RUNNER_ENV):
        args.run_mode = _env_run_mode(args.run_mode)
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
    result = run_tam_technical_scan(
        run_mode=args.run_mode,
        scheduled_time_label=args.scheduled_time_label,
        enforce_market_calendar=not args.allow_non_trading_day,
    )
    if result["skipped"]:
        print(f"skipped: {result['skip_reason']}")
        print(f"technical_timestamp: {result['technical_timestamp']}")
        print(f"run_mode: {result['run_mode']}")
        print(f"scheduled_time_label: {result['scheduled_time_label'] or ''}")
        return
    print(f"scan_id: {result['scan_id']}")
    print(f"technical_timestamp: {result['technical_timestamp']}")
    print(f"run_mode: {result['run_mode']}")
    print(f"scheduled_time_label: {result['scheduled_time_label'] or ''}")
    print(f"repository backend: {result['repository_backend']}")
    print(
        "technical characterization rows: "
        f"{result['row_counts'].get('technical_characterization', 0)}"
    )
    print(f"technical error count: {result['technical_error_count']}")
    print(f"database path: {result['database_path']}")


if __name__ == "__main__":
    main()
