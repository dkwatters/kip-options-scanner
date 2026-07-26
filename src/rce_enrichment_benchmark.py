"""Human-review diagnostics for context-aware enrichment benchmarks."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.research_conversation import MockResearchConversationProvider
from src.candidate_identity_validation import (
    CandidateIdentityValidationStatus,
    CandidateIdentityValidatorV01,
    InMemoryCandidateIdentityEvidenceLookup,
    evidence_from_mapping,
)
from src.rce_benchmark_metrics import estimate_cost, load_scoring_config
from src.research_universe import UniverseSource, source_record
from src.research_universe_discovery_context import build_research_universe_discovery_context_v01
from src.research_universe_enrichment import (
    ResearchUniverseEnrichmentRequestV01,
    ResearchUniverseEnrichmentResponseV01,
    ResearchUniverseEnrichmentService,
)


ENRICHMENT_BENCHMARK_VERSION = "rce-enrichment-benchmark-v0.1"
ENRICHMENT_BENCHMARK_MAX_OUTPUT_TOKENS = 8_000
ENRICHMENT_SCORING_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "rce_benchmark_scoring_v0.1.json"
)
EVIDENCE_LIMITATION = (
    "The enrichment provider call does not use live web/search retrieval. Evidence references are "
    "model-produced; evidence completeness does not equal evidence correctness; source truthfulness "
    "is not validated. This benchmark evaluates context-aware candidate discovery behavior, not "
    "retrieval-grounded evidence quality."
)


def _usage(raw: Any) -> dict[str, int]:
    usage = raw.get("usage", {}) if isinstance(raw, dict) else getattr(raw, "usage", {})
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    usage = usage if isinstance(usage, dict) else {}
    return {
        "input": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
    }


def _candidate(candidate: Any, seed_by_identity: Mapping[str, Any]) -> dict[str, Any]:
    related = []
    for identity in candidate.related_seed_member_identities:
        seed = seed_by_identity.get(identity)
        related.append({
            "member_identity": identity,
            "ticker_or_identifier": seed.ticker_or_identifier if seed else None,
        })
    return {
        "candidate_id": candidate.candidate_identity,
        "company_name": candidate.company_name,
        "ticker_or_identifier": candidate.ticker_or_identifier,
        "raw_identity": {
            "company_name": candidate.company_name,
            "ticker_or_identifier": candidate.ticker_or_identifier,
        },
        "validated_identity": {
            "company_name": candidate.validated_company_name,
            "ticker_or_identifier": candidate.validated_ticker_or_identifier,
        },
        "identity_validation": candidate.identity_validation.to_dict(),
        "validation_status": candidate.identity_validation.validation_status.value,
        "correction_applied": candidate.identity_validation.correction_applied,
        "correction_reason": candidate.identity_validation.correction_reason,
        "public_trading_status": candidate.identity_validation.public_trading_status.value,
        "candidate_state": candidate.candidate_state,
        "provenance": [row.to_dict() for row in candidate.provenance],
        "discovery_lenses": [row.value for row in candidate.discovery_lenses],
        "related_seeds": related,
        "discovery_reason": candidate.reason_discovered,
        "evidence_references": list(candidate.evidence_references),
        "duplicate_status": candidate.duplicate_status,
        "support_metadata": dict(candidate.support_metadata),
    }


def evaluate_enrichment_response(
    response: ResearchUniverseEnrichmentResponseV01,
    *,
    identity_resolution_mode: str = "fixture",
) -> dict[str, Any]:
    """Report contract metrics without adding qualitative or legacy scores."""
    candidates = response.candidates
    count = len(candidates)
    multi_lens = sum(len(row.discovery_lenses) > 1 for row in candidates)
    status_counts = {
        status.value: sum(row.identity_validation.validation_status == status for row in candidates)
        for status in CandidateIdentityValidationStatus
    }
    identity_valid = status_counts["valid"] + status_counts["corrected"]
    validations = [row.identity_validation for row in candidates]
    return {
        "benchmark_version": ENRICHMENT_BENCHMARK_VERSION,
        "candidate_count": count,
        "suppressed_seed_duplicates": list(response.suppressed_seed_duplicates),
        "suppressed_seed_duplicate_count": len(response.suppressed_seed_duplicates),
        "post_validation_duplicate_count": len(response.suppressed_seed_duplicates),
        "identity_valid_rate": identity_valid / count if count else None,
        "corrected_identity_count": status_counts["corrected"],
        "unresolved_count": status_counts["unresolved"],
        "rejected_count": status_counts["rejected"],
        "identity_resolution_mode": identity_resolution_mode,
        "fixture_evidence_match_count": sum(
            row.resolution_source == "authoritative_evidence" for row in validations
        ),
        "live_current_security_lookup_count": sum(
            row.current_security_lookup_attempted for row in validations
        ),
        "unresolved_due_to_missing_fixture_count": sum(
            identity_resolution_mode == "fixture"
            and row.validation_status == CandidateIdentityValidationStatus.UNRESOLVED
            and row.unresolved_category == "no_authoritative_mapping"
            for row in validations
        ),
        "unresolved_due_to_identity_conflict_count": sum(
            row.unresolved_category == "identity_conflict" for row in validations
        ),
        "unresolved_due_to_no_authoritative_mapping_count": sum(
            row.unresolved_category == "no_authoritative_mapping" for row in validations
        ),
        "returned_seed_duplicate_rate": 0.0,
        "evidence_completeness": sum(bool(row.evidence_references) for row in candidates) / count if count else None,
        "lens_attribution_completeness": sum(bool(row.discovery_lenses) for row in candidates) / count if count else None,
        "provenance_completeness": sum(bool(row.provenance) for row in candidates) / count if count else None,
        "pending_state_completeness": sum(row.candidate_state == "pending" for row in candidates) / count if count else None,
        "multi_lens_candidate_count": multi_lens,
        "warnings": list(response.warnings),
        "limitations": [
            "No relevance, recall, quality, or thematic-drift score is inferred.",
            EVIDENCE_LIMITATION,
        ],
    }


def _ticker_set(case: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("ticker_or_identifier")).upper()
        for row in case.get("returned_candidates", ())
        if row.get("ticker_or_identifier")
    }


def build_cross_case_diagnostics(
    cases: list[dict[str, Any]], fixture: Mapping[str, Any]
) -> dict[str, Any]:
    tickers = {case["case_id"]: _ticker_set(case) for case in cases}
    overlaps = []
    for index, left in enumerate(cases):
        for right in cases[index + 1:]:
            overlaps.append({
                "left_case_id": left["case_id"],
                "right_case_id": right["case_id"],
                "candidate_ticker_overlap": sorted(tickers[left["case_id"]] & tickers[right["case_id"]]),
            })
    unique = {}
    for case in cases:
        others = set().union(*(values for key, values in tickers.items() if key != case["case_id"]))
        unique[case["case_id"]] = sorted(tickers[case["case_id"]] - others)

    by_variant = {case.get("sensitivity_variant"): case for case in cases if case.get("sensitivity_variant")}
    deltas = {}
    base = by_variant.get("question_only")
    if base:
        base_tickers = _ticker_set(base)
        for variant in ("manual_anchor", "predefined_topic", "manual_and_topic"):
            compared = by_variant.get(variant)
            if compared:
                current = _ticker_set(compared)
                deltas[f"{variant}_vs_question_only"] = {
                    "added": sorted(current - base_tickers),
                    "removed": sorted(base_tickers - current),
                    "inputs_comparable": (
                        compared["input_context"]["research_question"]
                        == base["input_context"]["research_question"]
                    ),
                }
    questions = {case["input_context"]["research_question"] for case in cases}
    return {
        "candidate_ticker_overlaps": overlaps,
        "candidates_unique_to_each_case": unique,
        "candidate_deltas": deltas,
        "sensitivity_comparison_limitation": (
            None if len(questions) == 1 else
            "Fixture cases use different research questions; context-sensitivity comparisons are confounded."
        ),
        "fixture_family": fixture.get("fixture_family", "legacy_enrichment_scenarios"),
    }


def run_enrichment_scenarios(
    fixture: Mapping[str, Any],
    provider: Any,
    *,
    identity_resolution_mode: str = "fixture",
    current_security_lookup: Any = None,
) -> dict[str, Any]:
    """Run enrichment cases without persistence or scoring changes."""
    results = []
    fixture_lookup = InMemoryCandidateIdentityEvidenceLookup(
        evidence_from_mapping(row) for row in fixture.get("identity_evidence", ())
    )
    identity_validator = CandidateIdentityValidatorV01(
        authoritative_lookup=fixture_lookup,
        current_security_lookup=(
            current_security_lookup if identity_resolution_mode == "production_cascade" else None
        ),
        clock=lambda: datetime(2026, 7, 22, tzinfo=timezone.utc),
    )
    for case in fixture.get("cases", ()):
        manual = tuple(source_record(
            {"ticker": ticker, "company_name": ticker}, UniverseSource.USER_ENTERED,
            source_reference=f"benchmark:{case['id']}:manual:{ticker}",
        ) for ticker in case.get("manual", ()))
        topic = case.get("topic")
        predefined = tuple(source_record(
            {"ticker": ticker, "company_name": ticker}, UniverseSource.CURATOR_AUTHORED,
            source_reference=f"benchmark:{case['id']}:topic:{ticker}",
        ) for ticker in case.get("predefined", ()))
        context = build_research_universe_discovery_context_v01(
            research_question=case["question"], predefined_records=predefined,
            manual_records=manual, manual_input=case.get("manual", ()),
            predefined_universe_identity=topic,
            predefined_universe_name=case.get("topic_name"),
            created_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
        )
        response = ResearchUniverseEnrichmentService(provider, identity_validator).enrich(
            ResearchUniverseEnrichmentRequestV01(context)
        )
        usage = _usage(response.provider_response.raw_response)
        model = response.provider_response.metadata.model_name
        seed_by_identity = {row.member_identity: row for row in context.seed_universe}
        returned = [_candidate(row, seed_by_identity) for row in response.candidates]
        seed_tickers = {str(row.ticker_or_identifier).upper() for row in context.seed_universe if row.ticker_or_identifier}
        returned_tickers = {str(row["ticker_or_identifier"]).upper() for row in returned if row["ticker_or_identifier"]}
        results.append({
            "case_id": case["id"],
            "sensitivity_variant": case.get("sensitivity_variant"),
            "input_context": {
                "research_question": context.research_question,
                "predefined_topic": (
                    context.predefined_universe.to_dict() if context.predefined_universe else None
                ),
                "manual_seed_tickers": list(context.manual_input),
                "combined_seed_members": [row.to_dict() for row in context.seed_universe],
                "seed_provenance": {
                    row.member_identity: [item.to_dict() for item in row.provenance]
                    for row in context.seed_universe
                },
                "active_discovery_lenses": [row.value for row in context.discovery_lenses],
                "context_identity": context.context_identity,
            },
            "seed_count": len(context.seed_universe),
            "returned_candidates": returned,
            "seed_candidates_correctly_excluded": sorted(seed_tickers - returned_tickers),
            "seed_candidates_incorrectly_returned": sorted(seed_tickers & returned_tickers),
            "latency_seconds": response.provider_response.metadata.latency_seconds,
            "usage": usage,
            "estimated_cost": estimate_cost(
                model, usage, load_scoring_config(ENRICHMENT_SCORING_CONFIG_PATH)
            ),
            **evaluate_enrichment_response(
                response, identity_resolution_mode=identity_resolution_mode
            ),
        })
    return {
        "benchmark_version": ENRICHMENT_BENCHMARK_VERSION,
        "provider": str(getattr(provider, "provider_name", "unknown")),
        "model": str(getattr(provider, "model_name", "unknown")),
        "case_count": len(results),
        "max_output_tokens": getattr(provider, "max_output_tokens", None),
        "max_output_tokens_rationale": (
            "8,000 tokens conservatively bounds a structured review response containing up to "
            "the prompt's expected 25-50 candidates without changing production defaults."
        ),
        "web_search_enabled": False,
        "identity_resolution_mode": identity_resolution_mode,
        "identity_resolution_limitation": (
            "identity_valid_rate reflects frozen fixture coverage, not production resolver capability."
            if identity_resolution_mode == "fixture" else
            "Current-security lookups use the configured read-only market-data provider; "
            "frozen evidence remains authoritative for lifecycle and alias decisions."
        ),
        "evidence_limitation": EVIDENCE_LIMITATION,
        "cases": results,
        "cross_case_diagnostics": build_cross_case_diagnostics(results, fixture),
        "scoring_semantics_changed": False,
    }


def render_enrichment_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# RCE Enrichment Benchmark Review", "",
        f"- Provider: {report['provider']}",
        f"- Model: {report['model']}",
        f"- Cases: {report['case_count']}",
        f"- Max output tokens: {report.get('max_output_tokens')}", "",
        f"- Identity resolution mode: {report.get('identity_resolution_mode')}",
        f"- Identity resolution limitation: {report.get('identity_resolution_limitation')}", "",
        "## Evidence limitation", "", str(report["evidence_limitation"]), "",
    ]
    for case in report["cases"]:
        context = case["input_context"]
        lines.extend([
            f"## {case['case_id']}", "",
            f"- Question: {context['research_question']}",
            f"- Topic: {context['predefined_topic']}",
            f"- Manual seeds: {', '.join(context['manual_seed_tickers']) or 'None'}",
            f"- Combined seed members: {context['combined_seed_members']}",
            f"- Seed provenance: {context['seed_provenance']}",
            f"- Active Discovery Lenses: {', '.join(context['active_discovery_lenses'])}",
            f"- Seed count: {case['seed_count']}",
            f"- Context identity: {context['context_identity']}",
            f"- Candidate count: {case['candidate_count']}",
            f"- Suppressed seed duplicates: {case['suppressed_seed_duplicates']}",
            f"- Post-validation duplicate count: {case['post_validation_duplicate_count']}",
            f"- Identity-valid rate: {case['identity_valid_rate']}",
            f"- Corrected identity count: {case['corrected_identity_count']}",
            f"- Unresolved identity count: {case['unresolved_count']}",
            f"- Rejected identity count: {case['rejected_count']}",
            f"- Fixture evidence matches: {case['fixture_evidence_match_count']}",
            f"- Live/current-security lookups: {case['live_current_security_lookup_count']}",
            f"- Unresolved due to missing fixture: {case['unresolved_due_to_missing_fixture_count']}",
            f"- Unresolved due to identity conflict: {case['unresolved_due_to_identity_conflict_count']}",
            f"- Unresolved due to no authoritative mapping: {case['unresolved_due_to_no_authoritative_mapping_count']}",
            f"- Returned seed duplicate rate: {case['returned_seed_duplicate_rate']}",
            f"- Evidence completeness: {case['evidence_completeness']}",
            f"- Lens-attribution completeness: {case['lens_attribution_completeness']}",
            f"- Provenance completeness: {case['provenance_completeness']}",
            f"- Pending-state completeness: {case['pending_state_completeness']}",
            f"- Multi-lens candidate count: {case['multi_lens_candidate_count']}",
            f"- Latency seconds: {case['latency_seconds']}",
            f"- Tokens: input {case['usage']['input']}, output {case['usage']['output']}",
            f"- Estimated cost: {case['estimated_cost']}", "",
            "### Returned candidates", "",
        ])
        for candidate in case["returned_candidates"]:
            lines.extend([
                f"#### {candidate['ticker_or_identifier'] or candidate['company_name']}", "",
                f"- Candidate ID: {candidate['candidate_id']}",
                f"- Company: {candidate['company_name']}",
                f"- Raw identity: {candidate['raw_identity']}",
                f"- Validated identity: {candidate['validated_identity']}",
                f"- Validation status: {candidate['validation_status']}",
                f"- Correction applied / reason: {candidate['correction_applied']} / {candidate['correction_reason']}",
                f"- Public-trading status: {candidate['public_trading_status']}",
                f"- State / duplicate status: {candidate['candidate_state']} / {candidate['duplicate_status']}",
                f"- Lenses: {', '.join(candidate['discovery_lenses'])}",
                f"- Related seeds: {candidate['related_seeds']}",
                f"- Reason: {candidate['discovery_reason']}",
                f"- Evidence: {candidate['evidence_references']}",
                f"- Provenance: {candidate['provenance']}",
                f"- Support metadata: {candidate['support_metadata']}", "",
            ])
    diagnostics = report["cross_case_diagnostics"]
    lines.extend(["## Cross-case diagnostics", "", "```json",
                  __import__("json").dumps(diagnostics, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def run_provider_free_enrichment_scenarios(fixture: Mapping[str, Any]) -> dict[str, Any]:
    return run_enrichment_scenarios(fixture, MockResearchConversationProvider())
