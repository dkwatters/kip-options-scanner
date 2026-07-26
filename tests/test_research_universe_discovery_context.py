from datetime import datetime, timezone

import pytest

from src.research_universe import UniverseSource, source_record
from src.research_universe_builder_page import launch_uses_provider_backed_discovery
from src.research_universe_discovery_context import (
    DISCOVERY_CONTEXT_SCHEMA_VERSION,
    DISCOVERY_LENSES_V01,
    DISCOVERY_LENS_VOCABULARY_VERSION,
    DiscoveryLens,
    MembershipProvenanceSource,
    ResearchUniverseDiscoveryContextV01,
    build_research_universe_discovery_context_v01,
)


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def record(ticker, company, source, reference):
    return source_record(
        {"ticker": ticker, "company_name": company}, source,
        source_reference=reference,
    )


def build(*, question="What is missing?", predefined=(), manual=(), manual_input=(), topic=None):
    return build_research_universe_discovery_context_v01(
        research_question=question,
        predefined_records=predefined,
        manual_records=manual,
        manual_input=manual_input,
        predefined_universe_identity=topic,
        predefined_universe_name="AI Infrastructure" if topic else None,
        created_at=NOW,
        creation_metadata={"workflow": "test"},
    )


def test_question_only_context_has_no_seed_members():
    context = build(question="  Explore an ecosystem  ")
    assert context.research_question == "Explore an ecosystem"
    assert context.seed_universe == ()
    assert context.predefined_universe is None


def test_question_and_manual_tickers_preserve_deliberate_context():
    manual = (record("NVDA", "NVIDIA", UniverseSource.USER_ENTERED, "manual:NVDA"),)
    context = build(manual=manual, manual_input=("NVDA",))
    assert context.manual_input == ("NVDA",)
    assert [row.ticker_or_identifier for row in context.seed_universe] == ["NVDA"]
    assert context.seed_universe[0].provenance[0].source == MembershipProvenanceSource.MANUAL_ENTRY


def test_question_and_predefined_universe_context():
    predefined = (record("AMD", "Advanced Micro Devices", UniverseSource.CURATOR_AUTHORED, "topic:AMD"),)
    context = build(predefined=predefined, topic="topic:ai")
    assert context.predefined_universe.universe_identity == "topic:ai"
    assert context.predefined_universe.source_references == ("topic:AMD",)
    assert context.seed_universe[0].provenance[0].source == MembershipProvenanceSource.PREDEFINED_UNIVERSE


def test_mixed_inputs_merge_predefined_first_and_preserve_duplicate_provenance():
    predefined = (
        record("AMD", "Advanced Micro Devices", UniverseSource.CURATOR_AUTHORED, "topic:AMD"),
        record("NVDA", "NVIDIA", UniverseSource.CURATOR_AUTHORED, "topic:NVDA"),
    )
    manual = (
        record("NVDA", "NVIDIA Corporation", UniverseSource.USER_ENTERED, "manual:NVDA"),
        record("AVGO", "Broadcom", UniverseSource.USER_ENTERED, "manual:AVGO"),
    )
    first = build(predefined=predefined, manual=manual, manual_input=("NVDA", "AVGO"), topic="topic:ai")
    second = build(predefined=predefined, manual=manual, manual_input=("NVDA", "AVGO"), topic="topic:ai")
    assert [row.ticker_or_identifier for row in first.seed_universe] == ["AMD", "NVDA", "AVGO"]
    nvda = first.seed_universe[1]
    assert [row.source for row in nvda.provenance] == [
        MembershipProvenanceSource.PREDEFINED_UNIVERSE,
        MembershipProvenanceSource.MANUAL_ENTRY,
    ]
    assert first.context_identity == second.context_identity
    assert [row.member_identity for row in first.seed_universe] == [row.member_identity for row in second.seed_universe]


def test_serialization_round_trip_and_versions():
    context = build(manual=(record("NVDA", "NVIDIA", UniverseSource.USER_ENTERED, "manual:NVDA"),))
    assert ResearchUniverseDiscoveryContextV01.from_dict(context.to_dict()) == context
    payload = context.to_dict()
    payload["schema_version"] = "future-version"
    with pytest.raises(ValueError, match="Unsupported discovery context version"):
        ResearchUniverseDiscoveryContextV01.from_dict(payload)


def test_discovery_lens_vocabulary_is_complete_ordered_and_versioned():
    assert DISCOVERY_CONTEXT_SCHEMA_VERSION == "research-universe-discovery-context-v0.1"
    assert DISCOVERY_LENS_VOCABULARY_VERSION == "discovery-lens-v0.1"
    assert DISCOVERY_LENSES_V01 == (
        DiscoveryLens.DIRECT_COMPETITORS,
        DiscoveryLens.INDUSTRY_LANDSCAPE_PEERS,
        DiscoveryLens.VALUE_CHAIN_RELATIONSHIPS,
        DiscoveryLens.ADJACENT_BENEFICIARIES,
        DiscoveryLens.SUBSTITUTION_DISRUPTION_THREATS,
        DiscoveryLens.CROSS_SEED_DEPENDENCIES,
    )


def test_context_construction_has_no_provider_boundary(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("provider must not be constructed")

    monkeypatch.setattr("src.research_conversation.create_research_conversation_provider", forbidden)
    assert build().seed_universe == ()


@pytest.mark.parametrize(
    ("has_manual", "topic_id", "provider_expected"),
    ((False, None, True), (True, None, True), (False, "topic:ai", True), (True, "topic:ai", True)),
)
def test_current_abcd_provider_branch_characterization(has_manual, topic_id, provider_expected):
    assert launch_uses_provider_backed_discovery(topic_id) is provider_expected
