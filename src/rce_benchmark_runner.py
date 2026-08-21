"""Execution, instrumentation, export, and comparison for RCE benchmarks."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable

from src.rce_benchmark_metrics import evaluate_benchmark, estimate_cost, load_scoring_config
from src.rce_benchmark_repository import (
    DEFAULT_BENCHMARK_DB_PATH, import_fixtures, initialize_benchmark_repository,
    load_fixture_directory,
)
from src.rce_benchmark_run_repository import load_runs, persist_run
from src.research_conversation import (
    DEFAULT_RCE_PROMPT_VERSION, MockResearchConversationProvider, ResearchConversationRequest,
    ResearchConversationResponse, apply_research_launch_policy, with_rce_diagnostics,
)
from src.research_conversation.openai_provider import (
    DEFAULT_RCE_OPENAI_MODEL, LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER,
    OpenAIResearchConversationProvider,
)


DEFAULT_FIXTURE_DIR = Path("tests/fixtures/rce_benchmarks")
DEFAULT_ARTIFACT_DIR = Path("data/research/rce_benchmark_runs")


class BenchmarkProviderError(RuntimeError):
    pass


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    return {"type": type(value).__name__, "representation": str(value)}


def _usage(raw_response: Any) -> dict[str, int]:
    raw = _jsonable(raw_response)
    usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
    input_details = usage.get("input_tokens_details", {}) or {}
    output_details = usage.get("output_tokens_details", {}) or {}
    return {
        "input": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "cached_input": int(input_details.get("cached_tokens") or usage.get("cached_input_tokens") or 0),
        "output": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "reasoning": int(output_details.get("reasoning_tokens") or usage.get("reasoning_tokens") or 0),
    }


def create_provider(
    name: str,
    model: str | None = None,
    env: dict[str, str] | None = None,
    max_output_tokens: int | None = None,
) -> Any:
    environment = env if env is not None else os.environ
    normalized = name.strip().casefold()
    if normalized == "mock":
        if model and model != MockResearchConversationProvider.model_name:
            raise BenchmarkProviderError("The mock provider model is fixed; do not supply a different --model.")
        return MockResearchConversationProvider()
    if normalized == "openai":
        api_key = environment.get("OPENAI_API_KEY")
        if not api_key:
            raise BenchmarkProviderError("OPENAI_API_KEY is required for an OpenAI benchmark run; mock fallback is forbidden.")
        return OpenAIResearchConversationProvider(
            api_key=api_key,
            model_name=model or DEFAULT_RCE_OPENAI_MODEL,
            max_output_tokens=max_output_tokens,
        )
    raise BenchmarkProviderError(f"Unsupported RCE benchmark provider: {name}. Expected openai or mock.")


def _validate_response(response: ResearchConversationResponse, selected_provider: str) -> tuple[bool, bool]:
    if response.metadata.provider_name != selected_provider:
        raise BenchmarkProviderError(
            f"Selected provider {selected_provider!r} returned provider {response.metadata.provider_name!r}; fallback is forbidden."
        )
    if response.metadata.fallback_used or (selected_provider != "mock" and response.metadata.mock_provider_used):
        raise BenchmarkProviderError("Provider fallback or mock substitution detected; benchmark result rejected.")
    artifact = response.structured_response
    schema_valid = not response.errors and isinstance(artifact, dict) and isinstance(artifact.get("candidate_securities"), list)
    if selected_provider == "openai":
        provider_valid = artifact.get("provider_verification_marker") == LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER
    else:
        provider_valid = selected_provider == "mock"
    return schema_valid, provider_valid


def _response_integrity(response: ResearchConversationResponse, selected_provider: str) -> tuple[bool, bool]:
    artifact = response.structured_response
    schema_valid = not response.errors and isinstance(artifact, dict) and isinstance(artifact.get("candidate_securities"), list)
    provider_valid = response.metadata.provider_name == selected_provider
    if selected_provider == "openai":
        provider_valid = provider_valid and artifact.get("provider_verification_marker") == LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER
    elif selected_provider == "mock":
        provider_valid = provider_valid and not response.metadata.fallback_used
    else:
        provider_valid = False
    return schema_valid, provider_valid


def _ensure_fixture(database_path: Path | str, fixture: dict[str, Any]) -> None:
    initialize_benchmark_repository(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        exists = connection.execute(
            "SELECT 1 FROM rce_benchmark WHERE benchmark_id=? AND version=?",
            (fixture["benchmark"]["benchmark_id"], fixture["benchmark"]["version"]),
        ).fetchone()
    if not exists:
        import_fixtures([fixture], database_path=database_path, apply=True)


def run_benchmark(
    fixture: dict[str, Any], provider: Any, *, run_label: str, prompt_version: str = DEFAULT_RCE_PROMPT_VERSION,
    persist: bool = False, database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
    artifact_dir: Path | str = DEFAULT_ARTIFACT_DIR,
    clock: Callable[[], float] = perf_counter,
) -> dict[str, Any]:
    metadata = fixture["benchmark"]
    run_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    selected_provider = str(getattr(provider, "provider_name", "unknown"))
    selected_model = str(getattr(provider, "model_name", "unknown"))
    config = load_scoring_config()
    response: ResearchConversationResponse | None = None
    elapsed = 0.0
    try:
        start = clock()
        response = provider.interpret(ResearchConversationRequest(
            original_question=metadata["research_question"], prompt_version=prompt_version,
            context={"benchmark_id": metadata["benchmark_id"], "benchmark_version": metadata["version"]},
        ))
        elapsed = max(0.0, clock() - start)
        response = apply_research_launch_policy(response)
        response = with_rce_diagnostics(response, selected_provider_name=selected_provider)
        schema_valid, provider_valid = _validate_response(response, selected_provider)
        if not schema_valid:
            raise BenchmarkProviderError("RCE response failed parser/schema validation.")
        if response.has_errors:
            raise BenchmarkProviderError("; ".join(response.errors))
        if not provider_valid:
            raise BenchmarkProviderError("Provider verification marker is invalid or missing.")
        artifact = response.structured_response
        evaluation = evaluate_benchmark(
            fixture, artifact, schema_valid=schema_valid,
            provider_verification_valid=provider_valid, fallback_used=response.metadata.fallback_used,
            config=config,
        )
        usage = _usage(response.raw_response)
        run_status, error_type, error_message = "success", None, None
    except Exception as error:
        if response is not None:
            artifact = response.structured_response if isinstance(response.structured_response, dict) else {}
            usage = _usage(response.raw_response)
            fallback = bool(response.metadata.fallback_used)
            schema_valid, provider_valid = _response_integrity(response, selected_provider)
        else:
            artifact, usage, fallback = {}, {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}, False
            schema_valid = provider_valid = False
        evaluation = evaluate_benchmark(
            fixture, artifact, schema_valid=schema_valid, provider_verification_valid=provider_valid,
            fallback_used=fallback, config=config,
        )
        run_status, error_type, error_message = "failed", type(error).__name__, str(error)
    raw_path = parsed_path = None
    raw = _jsonable(response.raw_response) if response is not None else None
    fallback_used = bool(response.metadata.fallback_used) if response is not None else False
    raw_count = int(response.metadata.raw_candidate_count) if response is not None else 0
    candidates = artifact.get("candidate_securities", []) if isinstance(artifact, dict) else []
    parsed_count = len(candidates) if isinstance(candidates, list) else 0
    verified_count = sum(bool(row.get("verified_public")) for row in evaluation.candidate_results if row["returned"])
    if persist:
        target = Path(artifact_dir) / run_label / run_id
        target.mkdir(parents=True, exist_ok=False)
        raw_file, parsed_file = target / "raw_response.json", target / "parsed_artifact.json"
        raw_file.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
        parsed_file.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
        raw_path, parsed_path = str(raw_file), str(parsed_file)
    result = {
        "benchmark_run_id": run_id, "benchmark_id": metadata["benchmark_id"],
        "benchmark_name": metadata["benchmark_name"], "benchmark_question": metadata["research_question"],
        "benchmark_version": metadata["version"], "run_label": run_label,
        "provider": selected_provider, "model": selected_model, "prompt_version": prompt_version,
        "run_timestamp": started_at, "latency_seconds": elapsed,
        "usage": usage, "estimated_cost": estimate_cost(selected_model, usage, config),
        "raw_candidate_count": raw_count, "parsed_candidate_count": parsed_count,
        "verified_candidate_count": verified_count, "run_status": run_status,
        "schema_valid": bool(schema_valid), "provider_verification_valid": bool(provider_valid),
        "fallback_used": fallback_used, "error_type": error_type, "error_message": error_message,
        "raw_response_path": raw_path, "parsed_artifact_path": parsed_path,
        "overall_score": evaluation.overall_score if run_status == "success" else None,
        "limitations": evaluation.limitations, "evaluation": evaluation.as_dict(),
        "scoring_config": config,
    }
    if persist:
        _ensure_fixture(database_path, fixture)
        persist_run(result, database_path=database_path)
    return result


def run_benchmarks(
    fixtures: Iterable[dict[str, Any]], provider: Any, *, run_label: str,
    prompt_version: str = DEFAULT_RCE_PROMPT_VERSION, persist: bool = False,
    database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
    artifact_dir: Path | str = DEFAULT_ARTIFACT_DIR, resume: bool = False,
) -> list[dict[str, Any]]:
    completed: set[str] = set()
    if resume and persist and Path(database_path).exists():
        completed = {row["benchmark_id"] for row in load_runs(run_label, database_path) if row["run_status"] == "success"}
    results = []
    for fixture in fixtures:
        if fixture["benchmark"]["benchmark_id"] in completed:
            continue
        results.append(run_benchmark(
            fixture, provider, run_label=run_label, prompt_version=prompt_version,
            persist=persist, database_path=database_path, artifact_dir=artifact_dir,
        ))
    return results


def compare_run_sets(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_by_id = {row["benchmark_id"]: row for row in left}
    right_by_id = {row["benchmark_id"]: row for row in right}
    comparisons = []
    for benchmark_id in sorted(left_by_id.keys() & right_by_id.keys()):
        old, new = left_by_id[benchmark_id], right_by_id[benchmark_id]
        old_metrics, new_metrics = old.get("metrics", {}), new.get("metrics", {})
        def expected_set(run: dict[str, Any], outcome: str) -> set[str]:
            return {str(row.get("ticker") or row.get("company_name")) for row in run.get("candidates", []) if row.get("comparison_outcome") == outcome}
        old_missing, new_missing = expected_set(old, "expected_missing"), expected_set(new, "expected_missing")
        def violations(run: dict[str, Any]) -> set[str]:
            return {str(row.get("ticker") or row.get("company_name")) for row in run.get("candidates", []) if row.get("expected_classification") == "must_exclude" and row.get("returned")}
        def invalid(run: dict[str, Any]) -> set[str]:
            return {str(row.get("ticker") or row.get("company_name")) for row in run.get("candidates", []) if row.get("returned") and row.get("validation_status") not in {None, "valid"}}
        old_categories = {row["category_name"]: bool(row["returned"]) for row in old.get("categories", [])}
        new_categories = {row["category_name"]: bool(row["returned"]) for row in new.get("categories", [])}
        old_ranks = {str(row.get("ticker") or row.get("company_name")): row.get("returned_rank") for row in old.get("candidates", []) if row.get("returned")}
        new_ranks = {str(row.get("ticker") or row.get("company_name")): row.get("returned_rank") for row in new.get("candidates", []) if row.get("returned")}
        comparisons.append({
            "benchmark_id": benchmark_id,
            "metric_changes": {name: new_metrics.get(name, 0) - old_metrics.get(name, 0) for name in sorted(old_metrics.keys() | new_metrics.keys())},
            "newly_recovered_expected": sorted(old_missing - new_missing),
            "newly_missed_expected": sorted(new_missing - old_missing),
            "new_must_exclude_violations": sorted(violations(new) - violations(old)),
            "category_coverage_changes": {name: [old_categories.get(name), new_categories.get(name)] for name in sorted(old_categories.keys() | new_categories.keys()) if old_categories.get(name) != new_categories.get(name)},
            "ranking_changes": {name: [old_ranks.get(name), new_ranks.get(name)] for name in sorted(old_ranks.keys() & new_ranks.keys()) if old_ranks.get(name) != new_ranks.get(name)},
            "new_invalid_candidates": sorted(invalid(new) - invalid(old)),
            "latency_change": (new.get("latency_seconds") or 0) - (old.get("latency_seconds") or 0),
            "token_change": {field: (new.get(field) or 0) - (old.get(field) or 0) for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")},
            "estimated_cost_change": (new.get("estimated_cost") or 0) - (old.get("estimated_cost") or 0),
            "overall_score_change": (new.get("overall_score") or 0) - (old.get("overall_score") or 0),
            "interpretation": "Tradeoffs require metric-level and human review; overall score alone is not an improvement label.",
        })
    return {"left_run_count": len(left), "right_run_count": len(right), "benchmarks": comparisons}


def markdown_report(results: list[dict[str, Any]], title: str = "RCE Benchmark Report") -> str:
    lines = [f"# {title}", "", "This report is deterministic benchmark instrumentation. It does not classify unexpected candidates as incorrect and does not claim improvement or regression.", ""]
    if not results:
        return "\n".join(lines + ["No benchmark runs were executed.", ""])
    first = results[0]
    lines.extend([
        f"- Execution date: {first.get('run_timestamp')}", f"- Provider: {first.get('provider')}",
        f"- Model: {first.get('model')}", f"- Prompt version: {first.get('prompt_version')}",
        f"- Benchmark corpus version(s): {', '.join(sorted({r.get('benchmark_version', 'unknown') for r in results}))}",
        f"- Runs: {len(results)} ({sum(r.get('run_status') == 'success' for r in results)} successful, {sum(r.get('run_status') != 'success' for r in results)} failed)", "",
        "## Benchmark scores", "", "| Benchmark | Status | Score | Latency (s) |", "|---|---:|---:|---:|",
    ])
    for row in results:
        score = f"{row['overall_score']:.4f}" if row.get("overall_score") is not None else "n/a"
        lines.append(f"| {row['benchmark_id']} | {row['run_status']} | {score} | {row.get('latency_seconds', 0):.3f} |")
    metric_names = sorted({name for row in results for name in row.get("evaluation", {}).get("metrics", {})})
    lines.extend(["", "## Aggregate score by metric", ""])
    for name in metric_names:
        values = [row["evaluation"]["metrics"][name] for row in results if row.get("run_status") == "success" and name in row.get("evaluation", {}).get("metrics", {})]
        lines.append(f"- {name}: {sum(values) / len(values):.4f}" if values else f"- {name}: unavailable (no successful runs)")
    headings = [
        ("Missing must-include companies", lambda c: c.get("expected_classification") == "must_include" and not c.get("returned")),
        ("Must-exclude violations", lambda c: c.get("expected_classification") == "must_exclude" and c.get("returned")),
        ("Invalid candidates", lambda c: c.get("returned") and c.get("validation_status") not in {None, "valid"}),
        ("Benchmarks requiring manual review", lambda c: c.get("comparison_outcome") == "unexpected_candidate"),
    ]
    for heading, predicate in headings:
        lines.extend(["", f"## {heading}", ""])
        found = False
        for row in results:
            for candidate in row.get("evaluation", {}).get("candidate_results", []):
                if predicate(candidate):
                    lines.append(f"- {row['benchmark_id']}: {candidate.get('ticker') or candidate.get('company_name')}")
                    found = True
        if not found:
            lines.append("- None recorded.")
    category_gaps = [(row["benchmark_id"], category["category_name"]) for row in results for category in row.get("evaluation", {}).get("category_results", []) if category["expected_status"] != "excluded" and not category["returned"]]
    lines.extend(["", "## Category gaps", ""] + ([f"- {bid}: {name}" for bid, name in category_gaps] or ["- None recorded."]))
    listing = [(row["benchmark_id"], c.get("ticker") or c.get("company_name"), c.get("listing_violation")) for row in results for c in row.get("evaluation", {}).get("candidate_results", []) if c.get("listing_violation")]
    lines.extend(["", "## Listing violations", ""] + ([f"- {bid}: {name} ({reason})" for bid, name, reason in listing] or ["- None recorded."]))
    parser = [(row["benchmark_id"], warning) for row in results for warning in row.get("parser_warnings", [])]
    provider_issues = [(row["benchmark_id"], row.get("error_message")) for row in results if row.get("run_status") != "success" or not row.get("provider_verification_valid")]
    lines.extend(["", "## Parser and provider issues", ""] + ([f"- {bid}: {issue}" for bid, issue in parser + provider_issues] or ["- None recorded."]))
    latencies = sorted(float(row.get("latency_seconds") or 0) for row in results)
    percentile = lambda p: latencies[min(len(latencies) - 1, int((len(latencies) - 1) * p))]
    total_usage = {name: sum(int(row.get("usage", {}).get(name, 0)) for row in results) for name in ("input", "cached_input", "output", "reasoning")}
    costs = [row.get("estimated_cost") for row in results]
    lines.extend([
        "", "## Latency, token usage, and cost", "",
        f"- Latency seconds: min {latencies[0]:.3f}, p50 {percentile(.5):.3f}, p95 {percentile(.95):.3f}, max {latencies[-1]:.3f}",
        f"- Token usage: input {total_usage['input']}, cached input {total_usage['cached_input']}, output {total_usage['output']}, reasoning {total_usage['reasoning']}",
        f"- Estimated API cost: {'unavailable for configured model' if any(cost is None for cost in costs) else f'${sum(costs):.6f}'}",
        "", "## Recurring failure patterns", "",
        "- Review category gaps, missing expected candidates, provider/parser issues, and unresolved unexpected candidates above. No causal claim is made automatically.",
        "", "## Known limitations", "",
        "- The corpus is reviewed reference data, not absolute truth.",
        "- Unexpected candidates remain unresolved until human review.",
        "- Structured candidate evidence is not present in the current artifact schema and is reported without failing runs.",
        "- Human-review scores remain separate from the deterministic overall score.", "",
    ])
    return "\n".join(lines)


def load_all_fixtures(path: Path | str = DEFAULT_FIXTURE_DIR) -> list[dict[str, Any]]:
    return load_fixture_directory(path)
