"""Import reviewed canonical RCE benchmark JSON fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rce_benchmark_repository import (  # noqa: E402
    DEFAULT_BENCHMARK_DB_PATH, BenchmarkValidationError, DuplicateBenchmarkError,
    import_fixture_directory,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--path", type=Path, required=True, help="Directory of reviewed JSON fixtures")
    result.add_argument("--database", type=Path, default=DEFAULT_BENCHMARK_DB_PATH)
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Validate and report without writes")
    mode.add_argument("--apply", action="store_true", help="Import all fixtures transactionally")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        report = import_fixture_directory(args.path, database_path=args.database, apply=args.apply)
    except (BenchmarkValidationError, DuplicateBenchmarkError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
