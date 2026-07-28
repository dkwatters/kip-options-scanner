import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.candidate_identity_validation import (
    CandidateIdentityValidationStatus,
    CandidateIdentityValidatorV01,
    InMemoryCandidateIdentityEvidenceLookup,
    MarketDataSecurityEvidenceLookup,
    evidence_from_mapping,
)
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe import CandidateDisposition
from src.research_universe_discovery_context import build_research_universe_discovery_context_v01
from src.research_universe_enrichment import (
    ENRICHMENT_PROMPT_VERSION,
    ResearchUniverseEnrichmentRequestV01,
    ResearchUniverseEnrichmentService,
)
from src.research_universe_input import ResearchUniverseInputService
from src.research_universe_review_page import promote_suggested_candidate
from src.research_universe_repository import SQLiteResearchUniverseRepository


NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)
FIXTURE = json.loads(
    Path("tests/fixtures/candidate_identity_validation_v01.json").read_text(encoding="utf-8")
)


def _validator():
    return CandidateIdentityValidatorV01(
        InMemoryCandidateIdentityEvidenceLookup(
            evidence_from_mapping(row) for row in FIXTURE["evidence"]
        ),
        clock=lambda: NOW,
    )


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda row: row["id"])
def test_authoritative_provider_free_identity_fixtures(case):
    result = _validator().validate(
        candidate_id=case["id"],
        company_name=case["company_name"],
        ticker_or_identifier=case["ticker"],
    )
    assert result.validation_status.value == case["expected_status"]
    if case.get("expected_ticker"):
        assert result.normalized_ticker_or_identifier == case["expected_ticker"]
    assert result.validated_at == NOW


def _provider(company, ticker):
    row = {
        "company_name": company,
        "ticker": ticker,
        "discovery_lenses": ["direct_competitors"],
        "reason_discovered": "Provider-free identity gate regression.",
        "evidence_references": ["fixture://rce/discovery"],
    }
    return SimpleNamespace(
        provider_name="identity-fixture",
        interpret=lambda request: SimpleNamespace(
            structured_response={"candidate_securities": [row]},
            warnings=[],
        ),
    )


def _context(seed=()):
    records = tuple(
        source_record(
            {"company_name": company, "ticker": ticker},
            UniverseSource.CURATOR_AUTHORED,
            source_reference=f"fixture://seed/{ticker}",
        )
        for company, ticker in seed
    )
    return build_research_universe_discovery_context_v01(
        research_question="Find omissions",
        predefined_records=records,
        created_at=NOW,
    )


def _enrich(company, ticker, seed=()):
    request = ResearchUniverseEnrichmentRequestV01(_context(seed))
    return ResearchUniverseEnrichmentService(
        _provider(company, ticker), _validator(),
    ).enrich(request)


def _universe_from_candidate(candidate):
    suggestion = source_record(
        candidate.to_source_mapping(),
        UniverseSource.RCE_GENERATED,
        source_reference="fixture://rce/candidate",
    )
    return ResearchUniverseReviewService().assemble(
        universe_id="identity-gate", title="Identity gate", rce_suggestions=(suggestion,),
    )


def test_safe_correction_preserves_raw_candidate_and_can_be_promoted():
    candidate = _enrich("Jabil Inc.", "JBLU").candidates[0]
    assert candidate.company_name == "Jabil Inc."
    assert candidate.ticker_or_identifier == "JBLU"
    assert candidate.validated_ticker_or_identifier == "JBL"
    mapping = candidate.to_source_mapping()
    assert mapping["raw_ticker_or_identifier"] == "JBLU"
    assert mapping["ticker"] == "JBL"

    universe = _universe_from_candidate(candidate)
    promoted = promote_suggested_candidate(
        universe, universe.candidates[0].normalized_matching_key,
        ResearchUniverseInputService(),
    )
    member = promoted.approved_membership[0]
    links = [
        record.metadata["trusted_promotion_reference"]
        for record in member.source_records
        if "trusted_promotion_reference" in record.metadata
    ]
    assert len(promoted.candidates) == 1
    assert member.ticker_or_identifier == "JBL"
    assert len(links) == 1
    assert links[0]["original_source_reference"] == "fixture://rce/candidate"
    assert links[0]["candidate_identity"] == candidate.candidate_identity
    assert links[0]["expected_raw_ticker"] == "JBLU"
    assert links[0]["promoted_ticker"] == "JBL"
    assert links[0]["validation_result"] == "corrected"

    with tempfile.TemporaryDirectory() as directory:
        repository = SQLiteResearchUniverseRepository(Path(directory) / "jabil.sqlite")
        repository.save(promoted)
        restored = repository.get(promoted.universe_id)
    restored_link = next(
        record.metadata["trusted_promotion_reference"]
        for record in restored.candidates[0].source_records
        if "trusted_promotion_reference" in record.metadata
    )
    assert restored_link == links[0]
    revised = ResearchUniverseReviewService().revise(restored)
    assert [
        (row.normalized_matching_key, row.identity_status, row.ticker_or_identifier)
        for row in revised.candidates
    ] == [
        (row.normalized_matching_key, row.identity_status, row.ticker_or_identifier)
        for row in restored.candidates
    ]


@pytest.mark.parametrize(
    ("company", "ticker", "status"),
    [
        ("Unverified Foreign Issuer plc", "UFI.L", "unresolved"),
        ("Xilinx", "XLNX", "rejected"),
    ],
)
def test_unresolved_and_rejected_candidates_cannot_be_promoted(company, ticker, status):
    candidate = _enrich(company, ticker).candidates[0]
    assert candidate.identity_validation.validation_status.value == status
    universe = _universe_from_candidate(candidate)
    promoted = promote_suggested_candidate(
        universe, universe.candidates[0].normalized_matching_key,
        ResearchUniverseInputService(),
    )
    assert promoted is universe
    assert not promoted.approved_membership
    forced = ResearchUniverseReviewService().revise(
        universe,
        dispositions={
            universe.candidates[0].normalized_matching_key: CandidateDisposition.INCLUDED,
        },
    )
    assert not forced.approved_membership
    assert forced.candidates[0].disposition == CandidateDisposition.IDENTITY_REVIEW


def test_corrected_identity_triggers_seed_duplicate_suppression():
    response = _enrich("Jabil Inc.", "JBLU", seed=(("Jabil Inc.", "JBL"),))
    assert response.candidates == ()
    assert response.suppressed_seed_duplicates == ("ticker:JBL",)


def test_stale_ticker_and_acquired_entity_are_explicit():
    viavi = _validator().validate(
        candidate_id="viavi", company_name="Viavi Solutions", ticker_or_identifier="JDSU",
    )
    xilinx = _validator().validate(
        candidate_id="xilinx", company_name="Xilinx", ticker_or_identifier="XLNX",
    )
    assert viavi.validation_status == CandidateIdentityValidationStatus.CORRECTED
    assert viavi.current_listing_status.value == "renamed"
    assert xilinx.validation_status == CandidateIdentityValidationStatus.REJECTED
    assert xilinx.public_trading_status.value == "not_independently_traded"


def test_identity_gate_does_not_change_rce_prompt_or_discovery_lenses():
    response = _enrich("Marvell Technology, Inc.", "MRVL")
    assert response.request.provider_request().prompt_version == ENRICHMENT_PROMPT_VERSION
    assert [lens.value for lens in response.candidates[0].discovery_lenses] == [
        "direct_competitors"
    ]


class _QuoteLookup:
    def __init__(self, descriptions):
        self.descriptions = descriptions
        self.calls = []

    def get_quote(self, symbol):
        self.calls.append(symbol)
        description = self.descriptions.get(symbol)
        return {
            "quotes": {
                "quote": (
                    {"symbol": symbol, "description": description}
                    if description else None
                )
            }
        }


@pytest.mark.parametrize(
    ("company", "ticker"),
    [
        ("Cisco Systems, Inc.", "CSCO"),
        ("Lumentum Holdings Inc.", "LITE"),
    ],
)
def test_ordinary_current_security_lookup_resolves_without_fixture_coverage(company, ticker):
    quote_lookup = _QuoteLookup({ticker: company})
    validator = CandidateIdentityValidatorV01(
        current_security_lookup=MarketDataSecurityEvidenceLookup(quote_lookup)
    )
    result = validator.validate(
        candidate_id=ticker, company_name=company, ticker_or_identifier=ticker
    )
    assert result.validation_status == CandidateIdentityValidationStatus.VALID
    assert result.resolution_source == "current_security_lookup"
    assert quote_lookup.calls == [ticker]


def test_resolved_ticker_with_materially_conflicting_company_remains_unresolved():
    validator = CandidateIdentityValidatorV01(
        current_security_lookup=MarketDataSecurityEvidenceLookup(
            _QuoteLookup({"ADP": "Automatic Data Processing, Inc."})
        )
    )
    result = validator.validate(
        candidate_id="adp",
        company_name="Advance Data Processing",
        ticker_or_identifier="ADP",
    )
    assert result.validation_status == CandidateIdentityValidationStatus.UNRESOLVED
    assert result.unresolved_category == "identity_conflict"


def test_authoritative_stale_status_overrides_a_quote_provider_result():
    validator = CandidateIdentityValidatorV01(
        current_security_lookup=MarketDataSecurityEvidenceLookup(
            _QuoteLookup({"XLNX": "Xilinx, Inc."})
        ),
        authoritative_lookup=InMemoryCandidateIdentityEvidenceLookup(
            evidence_from_mapping(row) for row in FIXTURE["evidence"]
        ),
    )
    result = validator.validate(
        candidate_id="xilinx", company_name="Xilinx", ticker_or_identifier="XLNX"
    )
    assert result.validation_status == CandidateIdentityValidationStatus.REJECTED
    assert result.current_listing_status.value == "acquired"
