import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.research_universe import (
    IdentityStatus,
    ResearchUniverseHandoff,
    ResearchUniverseMemberHandoff,
)
from src.research_universe_analysis import (
    AnalysisLedgerEntry,
    AnalysisMemberStatus,
    ResearchUniverseAnalysisRun,
)
from src.universe_analysis import ranked_analysis_rows
from src.universe_analysis_contracts import SNAPSHOT_SCHEMA_VERSION
from src.universe_analysis_snapshot_builder import (
    UniverseAnalysisSnapshotValidationError,
    build_membership_digest,
    build_universe_analysis_snapshot_v1,
)


TICKERS = ("STR", "CON", "MIX", "WEAK", "EXT")


def _member(ticker, order):
    return ResearchUniverseMemberHandoff(
        matching_key=f"ticker:{ticker}", company_name=f"Company {ticker}",
        ticker_or_identifier=ticker, identity_status=IdentityStatus.RESOLVED,
        provenance_references=(f"source:{order}:{ticker}",),
    )


def _fixture():
    members = tuple(_member(ticker, order) for order, ticker in enumerate(TICKERS, 1)) + (
        ResearchUniverseMemberHandoff(
            matching_key="name:privateco", company_name="Private Co", ticker_or_identifier=None,
            identity_status=IdentityStatus.UNRESOLVED,
            provenance_references=("source:6:private",),
        ),
    )
    requested_at = datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc)
    handoff = ResearchUniverseHandoff(
        universe_id="universe-fixture", universe_version=3, universe_title="Fixture Universe",
        research_question="Which fixture companies are technically positioned?",
        ordered_members=members, approved_constituents=TICKERS,
        expected_constituent_count=5, total_member_count=6,
        unresolved_members=("Private Co",),
        provenance_references=("rce:fixture",), requested_at=requested_at,
    )
    ledger = tuple(AnalysisLedgerEntry(
        member.matching_key, member.company_name, member.ticker_or_identifier,
        member.identity_status,
        AnalysisMemberStatus.ANALYZED if member.ticker_or_identifier else AnalysisMemberStatus.UNRESOLVED,
        "Technical characterization completed." if member.ticker_or_identifier else "Identity unresolved.",
    ) for member in members)
    run = ResearchUniverseAnalysisRun(
        universe_id=handoff.universe_id, universe_version=handoff.universe_version,
        universe_title=handoff.universe_title, research_question=handoff.research_question,
        requested_constituent_count=6, requested_tickers=TICKERS, analyzed_tickers=TICKERS,
        unavailable_tickers=("Private Co",), timestamp="2026-07-20 12:00:00 PM EDT",
        scan_id="fixture-run", ledger=ledger,
    )
    rows = (
        _row("STR", p20=.05, p50=.10, p200=.20, a20=.05, a50=.10, rsi=60, macd=.2, volatility="moderate", trend="bullish_alignment", momentum="positive"),
        _row("CON", p20=.02, p50=.03, p200=-.02, a20=.02, a50=-.02, rsi=60, macd=.2, volatility="high", trend="constructive", momentum="positive"),
        _row("MIX", p20=.02, p50=-.02, p200=-.02, a20=-.02, a50=-.02, rsi=48, macd=.2, volatility="high", trend="mixed", momentum="neutral"),
        _row("WEAK", p20=-.02, p50=-.03, p200=-.10, a20=-.02, a50=-.02, rsi=35, macd=-.2, volatility="high", trend="bearish_alignment", momentum="negative"),
        _row("EXT", p20=.10, p50=.20, p200=.35, a20=.05, a50=.10, rsi=75, macd=.2, volatility="low", trend="bullish_alignment", momentum="overbought_positive"),
    )
    return handoff, run, rows


def _row(ticker, *, p20, p50, p200, a20, a50, rsi, macd, volatility, trend, momentum):
    positive_macd = macd > 0
    return {
        "scan_id": "fixture-run", "ticker": ticker,
        "technical_timestamp": "2026-07-20 12:00:00 PM EDT", "price": 100.123456,
        "sma_20": 95.0, "sma_50": 90.0, "sma_200": 80.0,
        "price_vs_sma_20": p20, "price_vs_sma_50": p50, "price_vs_sma_200": p200,
        "sma_20_vs_sma_50": a20, "sma_50_vs_sma_200": a50, "rsi_14": rsi,
        "macd_line": 1.0 if positive_macd else -.5,
        "macd_signal": .5 if positive_macd else 0.0, "macd_histogram": macd,
        "realized_volatility_20d": .6 if volatility == "high" else .3,
        "trend_state": trend, "momentum_state": momentum, "volatility_state": volatility,
        "technical_score": 42.123456, "technical_notes": "exact raw evidence",
        "study_id": "tam-study", "study_name": "Technical Analysis",
        "study_version": "v0.1", "study_purpose": "Observation",
        "scheduled_time_label": None, "run_mode": "manual_ui",
    }


def _build():
    handoff, run, rows = _fixture()
    return build_universe_analysis_snapshot_v1(handoff, run, rows), handoff, run, rows


def test_completed_snapshot_preserves_contract_members_evidence_and_summary():
    snapshot, handoff, run, rows = _build()
    assert snapshot.schema_version == SNAPSHOT_SCHEMA_VERSION == "universe_analysis_snapshot.v1"
    assert (snapshot.universe_id, snapshot.universe_version) == ("universe-fixture", 3)
    assert snapshot.research_question == handoff.research_question
    assert snapshot.analysis_run_id == run.scan_id
    assert (snapshot.total_universe_member_count, snapshot.analyzed_count, snapshot.unavailable_count) == (6, 5, 1)
    assert [member.matching_key for member in snapshot.members] == [member.matching_key for member in handoff.ordered_members]
    assert [member.membership_order for member in snapshot.members] == list(range(1, 7))
    unavailable = snapshot.members[-1]
    assert unavailable.analysis_status == AnalysisMemberStatus.UNRESOLVED.value
    assert unavailable.raw_technical_observation is None and unavailable.derived_observation is None

    analyzed = snapshot.members[:-1]
    assert all(member.raw_technical_observation and member.derived_observation for member in analyzed)
    assert all(member.derived_observation.rank_denominator == 5 for member in analyzed)
    assert {member.derived_observation.technical_profile for member in analyzed} >= {"Strong", "Constructive", "Mixed", "Weak"}
    assert next(member for member in analyzed if member.ticker_or_identifier == "EXT").derived_observation.extension_positioning == "Elevated"
    assert next(member for member in analyzed if member.ticker_or_identifier == "STR").raw_technical_observation.price == rows[0]["price"]
    assert all(member.derived_observation.evidence_ids[0] == member.evidence_references[0].evidence_id for member in analyzed)
    assert all(member.evidence_references[0].observation_reference == member.technical_observation_reference for member in analyzed)

    summary = snapshot.summary
    assert summary.strong_count + summary.constructive_count + summary.mixed_count + summary.weak_count == summary.analyzed_count == 5
    assert summary.profile_denominator == summary.bullish_trend_denominator == 5
    assert summary.unavailable_count == 1
    assert snapshot.version_manifest.technical_analysis_version
    assert snapshot.version_manifest.technical_scoring_version
    assert snapshot.version_manifest.presentation_version
    assert snapshot.version_manifest.snapshot_schema_version == SNAPSHOT_SCHEMA_VERSION


def test_snapshot_derived_outputs_exactly_match_current_universe_analysis():
    snapshot, _, _, rows = _build()
    expected = {row["ticker"]: row for row in ranked_analysis_rows(rows, {ticker: f"Company {ticker}" for ticker in TICKERS})}
    for member in snapshot.members[:-1]:
        actual = member.derived_observation
        row = expected[member.ticker_or_identifier]
        assert (actual.technical_profile, actual.technical_profile_score, actual.rank) == (
            row["technical_profile"], row["technical_profile_score"], row["rank"]
        )
        assert (actual.extension_positioning, actual.key_signal) == (row["extension_label"], row["key_signal"])


def test_digest_and_serialization_are_deterministic_and_json_safe():
    first, handoff, run, rows = _build()
    second = build_universe_analysis_snapshot_v1(handoff, run, tuple(dict(row) for row in rows))
    assert first.membership_digest == second.membership_digest == build_membership_digest(handoff)
    assert first.to_dict() == second.to_dict()
    encoded = json.dumps(first.to_dict(), sort_keys=True)
    assert '"status": "completed"' in encoded
    assert first.completed_at == "2026-07-20T16:00:00Z"

    changed = replace(handoff, universe_version=4)
    assert build_membership_digest(changed) != first.membership_digest
    reordered = replace(handoff, ordered_members=tuple(reversed(handoff.ordered_members)))
    assert build_membership_digest(reordered) != first.membership_digest


@pytest.mark.parametrize("mutation, message", [
    (lambda h, r, rows: (h, replace(r, universe_id="other"), rows), "Universe ID mismatch"),
    (lambda h, r, rows: (h, replace(r, universe_version=99), rows), "Universe version mismatch"),
    (lambda h, r, rows: (h, r, rows[:-1]), "Analyzed tickers do not reconcile"),
    (lambda h, r, rows: (replace(h, ordered_members=h.ordered_members + (h.ordered_members[0],), total_member_count=7), replace(r, requested_constituent_count=7, ledger=r.ledger + (r.ledger[0],)), rows), "Duplicate member identity"),
    (lambda h, r, rows: (h, replace(r, ledger=r.ledger[:-1]), rows), "Run ledger and ordered membership"),
])
def test_inconsistent_source_artifacts_are_rejected(mutation, message):
    handoff, run, rows = _fixture()
    args = mutation(handoff, run, rows)
    with pytest.raises(UniverseAnalysisSnapshotValidationError, match=message):
        build_universe_analysis_snapshot_v1(*args)


def test_builder_has_no_provider_or_streamlit_dependency():
    source = open("src/universe_analysis_snapshot_builder.py", encoding="utf-8").read().lower()
    assert "streamlit" not in source
    assert "openai" not in source
    assert "provider." not in source
