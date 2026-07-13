"""Run, export, compare, and review the versioned RCE benchmark corpus."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rce_benchmark_repository import DEFAULT_BENCHMARK_DB_PATH  # noqa: E402
from src.rce_benchmark_run_repository import (  # noqa: E402
    REVIEW_DIMENSIONS, list_unresolved_candidates, load_runs, record_qualitative_review,
    review_candidate,
)
from src.rce_benchmark_runner import (  # noqa: E402
    BenchmarkProviderError, compare_run_sets, create_provider, load_all_fixtures,
    markdown_report, run_benchmarks,
)
from src.research_conversation import DEFAULT_RCE_PROMPT_VERSION  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Run all 17 approved corpus fixtures")
    selection.add_argument("--benchmark", help="Run one benchmark id")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="Run without database or artifact writes")
    mode.add_argument("--persist", action="store_true", help="Persist run rows and raw/parsed artifacts")
    parser.add_argument("--provider", choices=("openai", "mock"))
    parser.add_argument("--model")
    parser.add_argument("--prompt-version", default=DEFAULT_RCE_PROMPT_VERSION)
    parser.add_argument("--label", default=f"benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--database", type=Path, default=DEFAULT_BENCHMARK_DB_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=Path("tests/fixtures/rce_benchmarks"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/research/rce_benchmark_runs"))
    parser.add_argument("--export-json", type=Path)
    parser.add_argument("--export-markdown", type=Path)
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"))
    parser.add_argument("--list-unresolved", action="store_true")
    parser.add_argument("--review-candidate", type=int, metavar="CANDIDATE_RESULT_ID")
    parser.add_argument("--status")
    parser.add_argument("--reviewer")
    parser.add_argument("--notes", default="")
    parser.add_argument("--review-score", metavar="BENCHMARK_RUN_ID")
    parser.add_argument("--dimension", choices=sorted(REVIEW_DIMENSIONS))
    parser.add_argument("--score", type=float)
    return parser


def _write(path: Path | None, content: str) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.compare:
        left, right = (load_runs(selector, args.database) for selector in args.compare)
        if not left or not right:
            print("Comparison failed: one or both run selectors matched no persisted runs.", file=sys.stderr)
            return 2
        report = compare_run_sets(left, right)
        payload = json.dumps(report, indent=2)
        print(payload)
        _write(args.export_json, payload + "\n")
        if args.export_markdown:
            lines = [
                f"# RCE Benchmark Comparison: {args.compare[0]} vs {args.compare[1]}", "",
                "Overall score changes are not improvement labels. Review all metric changes and tradeoffs.", "",
            ]
            for item in report["benchmarks"]:
                lines.extend([f"## {item['benchmark_id']}", "", "```json", json.dumps(item, indent=2), "```", ""])
            _write(args.export_markdown, "\n".join(lines))
        return 0
    if args.list_unresolved:
        rows = list_unresolved_candidates(args.database)
        print(json.dumps(rows, indent=2))
        return 0
    if args.review_candidate is not None:
        if not args.status or not args.reviewer:
            print("--review-candidate requires --status and --reviewer", file=sys.stderr)
            return 2
        review_id = review_candidate(args.review_candidate, args.status, args.reviewer, args.notes, database_path=args.database)
        print(json.dumps({"review_id": review_id}, indent=2))
        return 0
    if args.review_score:
        if args.dimension is None or args.score is None or not args.reviewer:
            print("--review-score requires --dimension, --score, and --reviewer", file=sys.stderr)
            return 2
        review_id = record_qualitative_review(args.review_score, args.dimension, args.score, args.reviewer, notes=args.notes, database_path=args.database)
        print(json.dumps({"review_id": review_id}, indent=2))
        return 0
    if not (args.all or args.benchmark) or not args.provider:
        print("A run requires --all or --benchmark and an explicit --provider.", file=sys.stderr)
        return 2
    fixtures = load_all_fixtures(args.fixture_dir)
    if args.benchmark:
        fixtures = [row for row in fixtures if row["benchmark"]["benchmark_id"] == args.benchmark]
        if not fixtures:
            print(f"Unknown benchmark: {args.benchmark}", file=sys.stderr)
            return 2
    try:
        provider = create_provider(args.provider, args.model)
    except BenchmarkProviderError as error:
        print(f"Provider validation failed: {error}", file=sys.stderr)
        return 2
    results = run_benchmarks(
        fixtures, provider, run_label=args.label, prompt_version=args.prompt_version,
        persist=args.persist, database_path=args.database, artifact_dir=args.artifact_dir,
        resume=args.resume,
    )
    payload = json.dumps(results, indent=2)
    report = markdown_report(results, f"RCE Benchmark Report: {args.label}")
    _write(args.export_json, payload + "\n")
    _write(args.export_markdown, report)
    for row in results:
        marker = "PASS" if row["run_status"] == "success" else "FAIL"
        score = f"{row['overall_score']:.4f}" if row.get("overall_score") is not None else "n/a"
        print(f"{marker} {row['benchmark_id']} score={score} latency={row['latency_seconds']:.3f}s")
        if row["error_message"]:
            print(f"  {row['error_type']}: {row['error_message']}")
    print(f"Completed {len(results)} benchmark(s): {sum(row['run_status'] == 'success' for row in results)} successful, {sum(row['run_status'] != 'success' for row in results)} failed.")
    return 1 if any(row["run_status"] != "success" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
