"""Cloud cron entry point for scheduled Study Protocol research scans."""
from __future__ import annotations

from dotenv import load_dotenv

from research_scan import (
    RUN_MODE_SCHEDULED,
    _env_scheduled_time_label,
    _validate_cloud_environment,
    run_default_research_scan,
)


def main() -> None:
    load_dotenv()
    run_mode = RUN_MODE_SCHEDULED
    scheduled_time_label = _env_scheduled_time_label()
    _validate_cloud_environment(run_mode, scheduled_time_label)
    result = run_default_research_scan(
        run_mode=run_mode,
        scheduled_time_label=scheduled_time_label,
    )
    if result["skipped"]:
        print(f"skipped: {result['skip_reason']}")
        return
    print(f"scan_id: {result['scan_id']}")
    print(f"repository backend: {result['repository_backend']}")
    print(f"contracts evaluated: {result['contracts_evaluated']}")


if __name__ == "__main__":
    main()
