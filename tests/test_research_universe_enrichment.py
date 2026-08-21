import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.rce_enrichment_benchmark import (
    ENRICHMENT_BENCHMARK_MAX_OUTPUT_TOKENS,
    evaluate_enrichment_response,
    run_enrichment_scenarios,
    run_provider_free_enrichment_scenarios,
)
from src.candidate_identity_validation import (
    CandidateIdentityValidatorV01,
    CurrentListingStatus,
    InMemoryCandidateIdentityEvidenceLookup,
    PublicTradingStatus,
    SecurityIdentityEvidenceV01,
)
from src.research_conversation import MockResearchConversationProvider
from src.research_conversation.openai_provider import OpenAIResearchConversationProvider
from src.research_conversation.openai_provider import parse_structured_response
from src.research_universe import (
    CandidateDisposition, IdentityStatus, ResearchUniverseReviewService,
    UniverseSource, source_record,
)
from src.research_universe_discovery_context import build_research_universe_discovery_context_v01
from src.research_universe_enrichment import (
    ENRICHMENT_PROMPT_VERSION,
    ResearchUniverseEnrichmentRequestV01,
    ResearchUniverseEnrichmentService,
)
from src.research_universe_review_page import promote_suggested_candidate
from src.research_universe_input import ResearchUniverseInputService
from src.research_universe_builder_page import suggestions_with_topic_fallback
from src.research_universe_builder_page import _stored_suggestions
from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
from src.research_universe_review_page import candidate_promotion_eligible


NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)


def _record(ticker, source=UniverseSource.USER_ENTERED, reference=None):
    return source_record({"ticker": ticker, "company_name": ticker}, source, source_reference=reference)


def _context(predefined=(), manual=(), topic=None, question="Find material omissions"):
    return build_research_universe_discovery_context_v01(
        research_question=question, predefined_records=predefined, manual_records=manual,
        manual_input=tuple(row.ticker_or_identifier for row in manual),
        predefined_universe_identity=topic, created_at=NOW,
    )


def test_request_serializes_full_context_not_only_flat_anchors():
    context = _context(
        predefined=(_record("AMD", UniverseSource.CURATOR_AUTHORED, "topic:AMD"),),
        manual=(_record("NVDA", reference="manual:NVDA"),), topic="topic:ai",
    )
    request = ResearchUniverseEnrichmentRequestV01(context)
    payload = request.to_dict()
    assert payload["research_question"] == "Find material omissions"
    assert payload["predefined_universe"]["universe_identity"] == "topic:ai"
    assert [row["ticker_or_identifier"] for row in payload["seed_members"]] == ["AMD", "NVDA"]
    assert len(payload["active_discovery_lenses"]) == 6
    assert request.provider_request().prompt_version == ENRICHMENT_PROMPT_VERSION


def test_mock_enrichment_is_provider_neutral_pending_evidenced_and_seed_suppressed():
    context = _context(manual=(_record("NVDA"),))
    response = ResearchUniverseEnrichmentService(MockResearchConversationProvider()).enrich(
        ResearchUniverseEnrichmentRequestV01(context)
    )
    assert all(row.ticker_or_identifier != "NVDA" for row in response.candidates)
    assert "ticker:NVDA" in response.suppressed_seed_duplicates
    assert response.candidates
    assert all(row.candidate_state == "pending" for row in response.candidates)
    assert all(row.evidence_references and row.discovery_lenses for row in response.candidates)
    assert all(row.provenance[0].source.value == "rce_discovered" for row in response.candidates)


def test_candidate_identity_is_stable_and_context_sensitive():
    service = ResearchUniverseEnrichmentService(MockResearchConversationProvider())
    first = service.enrich(ResearchUniverseEnrichmentRequestV01(_context(manual=(_record("NVDA"),))))
    same = service.enrich(ResearchUniverseEnrichmentRequestV01(_context(manual=(_record("NVDA"),))))
    changed = service.enrich(ResearchUniverseEnrichmentRequestV01(_context(manual=(_record("AMD"),))))
    assert first.candidates[0].candidate_identity == same.candidates[0].candidate_identity
    assert first.candidates[0].candidate_identity != changed.candidates[0].candidate_identity


def test_openai_payload_contains_omission_context_and_versioned_policy():
    request = ResearchUniverseEnrichmentRequestV01(_context(manual=(_record("NVDA"),))).provider_request()
    payload = json.loads(OpenAIResearchConversationProvider(api_key="test")._user_prompt(request))
    assert request.prompt_version == ENRICHMENT_PROMPT_VERSION
    assert set(payload["candidate_security_schema"]) == {
        "ticker",
        "company_name",
        "discovery_lenses",
        "related_seed_matching_keys",
        "reason_discovered",
        "evidence_references",
    }
    assert payload["enrichment_request"]["seed_members"][0]["ticker_or_identifier"] == "NVDA"
    assert payload["enrichment_request"]["active_discovery_lenses"]
    assert "known and exclude" in payload["response_policy"][0]
    assert any("Discovery Lenses" in item for item in payload["response_policy"])
    assert any("related_seed_matching_keys" in item for item in payload["response_policy"])


def test_promotion_preserves_discovery_and_adds_promoted_provenance_and_version():
    validator = CandidateIdentityValidatorV01(InMemoryCandidateIdentityEvidenceLookup((
        SecurityIdentityEvidenceV01(
            company_name="NVIDIA Corporation",
            ticker_or_identifier="NVDA",
            authoritative_source="provider-free test fixture",
            source_reference="fixture://security/NVDA",
            public_trading_status=PublicTradingStatus.PUBLICLY_TRADABLE,
            current_listing_status=CurrentListingStatus.CURRENT,
            aliases=("NVIDIA",),
        ),
    )))
    enriched = ResearchUniverseEnrichmentService(
        MockResearchConversationProvider(), validator,
    ).enrich(
        ResearchUniverseEnrichmentRequestV01(_context())
    ).candidates[0]
    suggestion = source_record(enriched.to_source_mapping(), UniverseSource.RCE_GENERATED, source_reference="rce:test")
    universe = ResearchUniverseReviewService().assemble(
        universe_id="u", title="U", rce_suggestions=(suggestion,),
    )
    promoted = promote_suggested_candidate(
        universe, universe.candidates[0].normalized_matching_key, ResearchUniverseInputService(),
    )
    member = promoted.approved_membership[0]
    provenance = [item["source"] for record in member.source_records for item in record.metadata.get("membership_provenance", [])]
    trusted_links = [
        record.metadata["trusted_promotion_reference"]
        for record in member.source_records
        if "trusted_promotion_reference" in record.metadata
    ]
    assert "rce_discovered" in provenance
    assert "promoted_candidate" in provenance
    assert len(trusted_links) == 1
    assert trusted_links[0]["type"] == "research_universe_promotion"
    assert trusted_links[0]["version"] == 1
    assert trusted_links[0]["original_source_reference"] == "rce:test"
    assert trusted_links[0]["candidate_identity"] == enriched.candidate_identity
    assert trusted_links[0]["promoted_ticker"] == "NVDA"
    assert len(promoted.candidates) == 1
    assert member.identity_status == IdentityStatus.RESOLVED
    assert promoted.version == universe.version + 1


def test_rejection_does_not_change_membership_or_version_and_reopen_is_stable():
    suggestion = _record("SUG", UniverseSource.RCE_GENERATED)
    service = ResearchUniverseReviewService()
    universe = service.assemble(universe_id="u", title="U", rce_suggestions=(suggestion,))
    rejected = service.revise(
        universe, dispositions={universe.candidates[0].normalized_matching_key: CandidateDisposition.REJECTED},
    )
    assert rejected.approved_membership == universe.approved_membership == ()
    assert rejected.version == universe.version
    reopened = service.revise(rejected)
    assert reopened.version == rejected.version


def test_manual_add_and_removal_increment_membership_version():
    service = ResearchUniverseReviewService()
    universe = service.assemble(universe_id="u", title="U")
    added = service.revise(universe, additional_starting_companies=(_record("AAA"),))
    removed = service.remove_members(added, (added.approved_membership[0].normalized_matching_key,))
    assert (universe.version, added.version, removed.version) == (1, 2, 3)


def test_provider_free_enrichment_benchmark_contract_metrics():
    fixture = json.loads(Path("tests/fixtures/rce_enrichment_scenarios_v01.json").read_text(encoding="utf-8"))
    assert len(fixture["cases"]) == 4
    response = ResearchUniverseEnrichmentService(MockResearchConversationProvider()).enrich(
        ResearchUniverseEnrichmentRequestV01(_context(manual=(_record("NVDA"),)))
    )
    metrics = evaluate_enrichment_response(response)
    assert metrics["returned_seed_duplicate_rate"] == 0.0
    assert metrics["evidence_completeness"] == 1.0
    assert metrics["lens_attribution_completeness"] == 1.0
    assert metrics["provenance_completeness"] == 1.0
    assert metrics["pending_state_completeness"] == 1.0
    assert metrics["multi_lens_candidate_count"] == metrics["candidate_count"]
    run = run_provider_free_enrichment_scenarios(fixture)
    assert run["case_count"] == 4
    assert not run["scoring_semantics_changed"]
    assert all(row["returned_seed_duplicate_rate"] == 0.0 for row in run["cases"])


def test_enrichment_report_contains_full_review_context_and_candidates():
    fixture = json.loads(Path("tests/fixtures/rce_enrichment_scenarios_v01.json").read_text(encoding="utf-8"))
    report = run_provider_free_enrichment_scenarios(fixture)
    manual_case = next(row for row in report["cases"] if row["case_id"] == "manual_anchor")
    context = manual_case["input_context"]
    candidate = manual_case["returned_candidates"][0]

    assert context["research_question"] == "Research AI infrastructure omissions"
    assert context["manual_seed_tickers"] == ["NVDA"]
    assert context["combined_seed_members"][0]["ticker_or_identifier"] == "NVDA"
    assert context["seed_provenance"]
    assert context["active_discovery_lenses"]
    assert context["context_identity"]
    assert candidate["candidate_id"]
    assert candidate["company_name"]
    assert candidate["discovery_lenses"] == [
        "industry_landscape_peers", "adjacent_beneficiaries",
    ]
    assert candidate["evidence_references"][0].startswith("mock-fixture://")
    assert candidate["discovery_reason"]
    assert candidate["provenance"]
    assert candidate["related_seeds"][0]["ticker_or_identifier"] == "NVDA"
    assert candidate["support_metadata"]["support"] == "provider_free_mock_fixture"


def test_candidate_identities_enable_overlap_and_legacy_fixture_confounding_is_explicit():
    fixture = json.loads(Path("tests/fixtures/rce_enrichment_scenarios_v01.json").read_text(encoding="utf-8"))
    report = run_provider_free_enrichment_scenarios(fixture)
    diagnostics = report["cross_case_diagnostics"]
    assert all(row["candidate_id"] for case in report["cases"] for row in case["returned_candidates"])
    assert diagnostics["candidate_ticker_overlaps"]
    assert set(diagnostics["candidates_unique_to_each_case"]) == {
        "question_only", "manual_anchor", "predefined_topic", "manual_and_topic",
    }
    assert "confounded" in diagnostics["sensitivity_comparison_limitation"]


def test_matched_sensitivity_fixture_preserves_same_base_question_and_reports_deltas():
    fixture = json.loads(
        Path("tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json").read_text(encoding="utf-8")
    )
    assert {row["question"] for row in fixture["cases"]} == {fixture["base_question"]}
    report = run_provider_free_enrichment_scenarios(fixture)
    diagnostics = report["cross_case_diagnostics"]
    assert diagnostics["fixture_family"] == "matched_context_sensitivity"
    assert diagnostics["sensitivity_comparison_limitation"] is None
    assert set(diagnostics["candidate_deltas"]) == {
        "manual_anchor_vs_question_only",
        "predefined_topic_vs_question_only",
        "manual_and_topic_vs_question_only",
    }
    assert all(row["inputs_comparable"] for row in diagnostics["candidate_deltas"].values())


def test_output_token_bound_is_opt_in_and_sent_only_by_bounded_provider():
    raw_response = SimpleNamespace(
        status="completed",
        output_text=json.dumps({"candidate_securities": []}),
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    unbounded_client = MagicMock()
    unbounded_client.responses.create.return_value = raw_response
    bounded_client = MagicMock()
    bounded_client.responses.create.return_value = raw_response
    request = ResearchUniverseEnrichmentRequestV01(_context()).provider_request()

    OpenAIResearchConversationProvider(client=unbounded_client).interpret(request)
    OpenAIResearchConversationProvider(
        client=bounded_client, max_output_tokens=ENRICHMENT_BENCHMARK_MAX_OUTPUT_TOKENS,
    ).interpret(request)

    unbounded_args = unbounded_client.responses.create.call_args.kwargs
    bounded_args = bounded_client.responses.create.call_args.kwargs
    assert unbounded_args["text"]["format"]["name"] == "rce_enrichment_response"
    assert "Context-aware Research Universe enrichment behavior" in unbounded_args["input"][0]["content"]
    assert "max_output_tokens" not in unbounded_args
    assert bounded_args["max_output_tokens"] == 8_000


def test_live_enrichment_candidate_shape_survives_provider_and_enrichment_normalization():
    """Provider-free regression for the field vocabulary returned by the live call."""
    live_shape = {
        "candidate_securities": [
            {
                "ticker": "AVGO",
                "company_name": "Broadcom Inc.",
                "discovery_lenses": [
                    "industry_landscape_peers",
                    "cross_seed_dependencies",
                ],
                "related_seed_matching_keys": ["ticker:NVDA"],
                "reason_discovered": "Adds switching silicon and custom accelerator coverage.",
                "evidence_references": [
                    "Broadcom FY2025 Form 10-K",
                    "Broadcom AI infrastructure product disclosures",
                ],
            },
            {
                "ticker": "MRVL",
                "company_name": "Marvell Technology, Inc.",
                "discovery_lenses": [],
                "related_seed_matching_keys": ["ticker:NVDA"],
                "reason_discovered": "Missing required lens attribution.",
                "evidence_references": ["Marvell FY2026 Form 10-K"],
            },
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "discovery_lenses": ["direct_competitors"],
                "related_seed_matching_keys": ["ticker:NVDA"],
                "reason_discovered": "Seed duplicate.",
                "evidence_references": ["NVIDIA FY2026 Form 10-K"],
            },
        ]
    }
    structured, warnings, errors = parse_structured_response(
        json.dumps(live_shape), "Find omissions", enrichment=True
    )
    assert not warnings
    assert not errors
    provider = MagicMock(provider_name="fixture")
    provider.interpret.return_value = SimpleNamespace(
        structured_response=structured,
        warnings=[],
    )
    response = ResearchUniverseEnrichmentService(provider).enrich(
        ResearchUniverseEnrichmentRequestV01(
            _context(manual=(_record("NVDA"),))
        )
    )
    assert [row.ticker_or_identifier for row in response.candidates] == ["AVGO"]
    candidate = response.candidates[0]
    assert [row.value for row in candidate.discovery_lenses] == [
        "industry_landscape_peers",
        "cross_seed_dependencies",
    ]
    assert candidate.reason_discovered == live_shape["candidate_securities"][0]["reason_discovered"]
    assert list(candidate.evidence_references) == live_shape["candidate_securities"][0]["evidence_references"]
    assert candidate.related_seed_member_identities
    assert candidate.provenance[0].source.value == "rce_discovered"
    assert "ticker:NVDA" in response.suppressed_seed_duplicates
    assert any("Candidate MRVL lacked" in warning for warning in response.warnings)


def test_zero_candidate_completeness_metrics_are_not_evaluable():
    provider = MagicMock(provider_name="fixture")
    provider.interpret.return_value = SimpleNamespace(
        structured_response={"candidate_securities": []},
        warnings=[],
    )
    response = ResearchUniverseEnrichmentService(provider).enrich(
        ResearchUniverseEnrichmentRequestV01(_context())
    )
    metrics = evaluate_enrichment_response(response)
    assert metrics["candidate_count"] == 0
    assert metrics["evidence_completeness"] is None
    assert metrics["lens_attribution_completeness"] is None
    assert metrics["provenance_completeness"] is None
    assert metrics["pending_state_completeness"] is None


def test_cli_exports_json_and_markdown_only_when_requested(tmp_path):
    script = Path("scripts/run_rce_enrichment_benchmarks.py")
    fixture = Path("tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json")
    json_path = tmp_path / "review.json"
    markdown_path = tmp_path / "review.md"
    result = subprocess.run(
        [
            sys.executable, str(script), "--provider", "mock", "--fixture", str(fixture),
            "--export-json", str(json_path), "--export-markdown", str(markdown_path),
        ],
        check=True, capture_output=True, text=True,
    )
    stdout_report = json.loads(result.stdout)
    assert json.loads(json_path.read_text(encoding="utf-8")) == stdout_report
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# RCE Enrichment Benchmark Review" in markdown
    assert "## Evidence limitation" in markdown
    assert "## Cross-case diagnostics" in markdown


def test_cli_writes_no_artifacts_by_default(tmp_path):
    script = Path("scripts/run_rce_enrichment_benchmarks.py").resolve()
    fixture = Path("tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json").resolve()
    subprocess.run(
        [sys.executable, str(script), "--provider", "mock", "--fixture", str(fixture)],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    assert list(tmp_path.iterdir()) == []


def test_cli_case_id_runs_exactly_one_provider_free_case():
    script = Path("scripts/run_rce_enrichment_benchmarks.py")
    fixture = Path("tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json")
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "mock",
            "--fixture",
            str(fixture),
            "--case-id",
            "sensitivity_a_question_only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["case_count"] == 1
    assert report["cases"][0]["case_id"] == "sensitivity_a_question_only"


def test_fixture_mode_diagnostics_are_deterministic_and_explicit():
    fixture = json.loads(
        Path("tests/fixtures/rce_enrichment_scenarios_v01.json").read_text(encoding="utf-8")
    )
    report = run_provider_free_enrichment_scenarios(fixture)
    assert report["identity_resolution_mode"] == "fixture"
    assert "fixture coverage" in report["identity_resolution_limitation"]
    assert all(case["live_current_security_lookup_count"] == 0 for case in report["cases"])


def test_production_cascade_resolves_current_security_without_fixture_coverage():
    fixture = {
        "identity_evidence": [],
        "cases": [{
            "id": "current",
            "question": "Find omissions",
            "manual": [],
            "mock_candidates": [{
                "ticker": "CSCO",
                "company_name": "Cisco Systems, Inc.",
                "discovery_lenses": ["direct_competitors"],
                "related_seed_matching_keys": [],
                "reason_discovered": "Current security.",
                "evidence_references": ["fixture://discovery/CSCO"],
            }],
        }],
    }
    current_lookup = InMemoryCandidateIdentityEvidenceLookup((
        SecurityIdentityEvidenceV01(
            company_name="Cisco Systems, Inc.",
            ticker_or_identifier="CSCO",
            authoritative_source="configured market-data security lookup",
            source_reference="market-data:quote:CSCO",
            public_trading_status=PublicTradingStatus.PUBLICLY_TRADABLE,
            current_listing_status=CurrentListingStatus.CURRENT,
        ),
    ))
    provider = MagicMock(provider_name="fixture", model_name="fixture", max_output_tokens=None)
    provider.interpret.return_value = SimpleNamespace(
        structured_response={"candidate_securities": fixture["cases"][0]["mock_candidates"]},
        warnings=[],
        raw_response={},
        metadata=SimpleNamespace(model_name="fixture", latency_seconds=0.0),
    )
    report = run_enrichment_scenarios(
        fixture,
        provider,
        identity_resolution_mode="production_cascade",
        current_security_lookup=current_lookup,
    )
    case = report["cases"][0]
    assert case["identity_valid_rate"] == 1.0
    assert case["fixture_evidence_match_count"] == 0
    assert case["live_current_security_lookup_count"] == 1


def test_stored_topic_candidates_are_explicit_empty_enrichment_fallback_only():
    assert suggestions_with_topic_fallback(("live",), ("stored",)) == (("live",), False)
    assert suggestions_with_topic_fallback((), ("stored",)) == (("stored",), True)


def test_legacy_stored_fallback_needs_review_remains_promotion_ineligible():
    records = _stored_suggestions(RCEBenchmarkExplorerService(), "fintech")
    record = next(
        row for row in records
        if row.metadata.get("validation_status") == "needs_review"
        and row.ticker_or_identifier
    )
    assert record.metadata["identity_validation_status"] == "unresolved"
    universe = ResearchUniverseReviewService().assemble(
        universe_id="stored-fallback", title="Stored fallback",
        rce_suggestions=(record,),
    )
    candidate = universe.candidates[0]
    assert not candidate_promotion_eligible(candidate)
    assert promote_suggested_candidate(
        universe, candidate.normalized_matching_key, ResearchUniverseInputService(),
    ) is universe
