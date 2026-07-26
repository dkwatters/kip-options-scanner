"""Run human-review Context-Aware RCE Enrichment benchmarks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rce_benchmark_runner import create_provider  # noqa: E402
from src.rce_enrichment_benchmark import (  # noqa: E402
    ENRICHMENT_BENCHMARK_MAX_OUTPUT_TOKENS,
    render_enrichment_markdown,
    run_enrichment_scenarios,
)
from src.candidate_identity_validation import MarketDataSecurityEvidenceLookup  # noqa: E402


def _write_requested(path: str | None, content: str) -> None:
    if path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("mock", "openai"), default="mock")
    parser.add_argument("--model")
    parser.add_argument(
        "--fixture",
        default=str(ROOT / "tests" / "fixtures" / "rce_enrichment_scenarios_v01.json"),
    )
    parser.add_argument("--export-json")
    parser.add_argument("--export-markdown")
    parser.add_argument(
        "--identity-fixture",
        default=str(ROOT / "tests" / "fixtures" / "candidate_identity_validation_v01.json"),
        help="Provider-free authoritative identity evidence used by the validation gate.",
    )
    parser.add_argument(
        "--case-id",
        help="Run exactly one fixture case by id.",
    )
    parser.add_argument(
        "--identity-resolution-mode",
        choices=("fixture", "production_cascade"),
        default="fixture",
        help=(
            "fixture is deterministic and provider-free; production_cascade explicitly uses "
            "the configured read-only current-security lookup before frozen lifecycle evidence."
        ),
    )
    args = parser.parse_args()
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    identity_fixture = json.loads(Path(args.identity_fixture).read_text(encoding="utf-8"))
    fixture["identity_evidence"] = identity_fixture.get("evidence", ())
    if args.case_id:
        matching_cases = [
            case for case in fixture.get("cases", ())
            if case.get("id") == args.case_id
        ]
        if not matching_cases:
            parser.error(f"Fixture does not contain case id: {args.case_id}")
        fixture = {**fixture, "cases": matching_cases}
    provider = create_provider(
        args.provider,
        model=args.model,
        max_output_tokens=(
            ENRICHMENT_BENCHMARK_MAX_OUTPUT_TOKENS if args.provider == "openai" else None
        ),
    )
    current_security_lookup = None
    if args.identity_resolution_mode == "production_cascade":
        from src.tradier_client import TradierClient
        current_security_lookup = MarketDataSecurityEvidenceLookup(TradierClient())
    report = run_enrichment_scenarios(
        fixture,
        provider,
        identity_resolution_mode=args.identity_resolution_mode,
        current_security_lookup=current_security_lookup,
    )
    json_output = json.dumps(report, indent=2, sort_keys=True)
    _write_requested(args.export_json, json_output + "\n")
    _write_requested(args.export_markdown, render_enrichment_markdown(report))
    print(json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
