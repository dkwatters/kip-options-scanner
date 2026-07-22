from datetime import datetime, timezone

from src.research_universe import (
    CandidateDisposition,
    IdentityStatus,
    ResearchUniverseReviewService,
    UniverseSource,
    source_record,
)
from src.research_universe_analysis import (
    AnalysisLedgerEntry,
    AnalysisMemberStatus,
    ResearchUniverseAnalysisRun,
)
from src.research_universe_repository import (
    SQLiteResearchUniverseRepository,
    recover_universe_from_snapshot,
)
from src.universe_analysis_snapshot_builder import build_universe_analysis_snapshot_v1
from src.universe_analysis_snapshot_repository import SQLiteUniverseAnalysisSnapshotRepository


def _universe(universe_id, title, tickers):
    records = tuple(source_record(
        {"company_name": f"Company {ticker}", "ticker": ticker,
         "identity_status": IdentityStatus.RESOLVED},
        UniverseSource.USER_ENTERED, source_reference=f"manual:{ticker}",
    ) for ticker in tickers)
    return ResearchUniverseReviewService().assemble(
        universe_id=universe_id, title=title, research_question=f"Study {title}",
        starting_companies=records,
    )


def _snapshot(universe, run_id, timestamp):
    handoff = universe.downstream_handoff()
    ledger = tuple(AnalysisLedgerEntry(
        row.matching_key, row.company_name, row.ticker_or_identifier,
        row.identity_status, AnalysisMemberStatus.ANALYZED, "Completed",
    ) for row in handoff.ordered_members)
    tickers = tuple(row.ticker_or_identifier for row in handoff.ordered_members)
    run = ResearchUniverseAnalysisRun(
        handoff.universe_id, handoff.universe_version, handoff.universe_title,
        handoff.research_question, len(tickers), tickers, tickers, (), timestamp,
        run_id, ledger,
    )
    rows = tuple({
        "scan_id": run_id, "ticker": ticker, "technical_timestamp": timestamp,
        "price": 100.0, "sma_20": 99.0, "sma_50": 98.0, "sma_200": 90.0,
        "price_vs_sma_20": .01, "price_vs_sma_50": .02, "price_vs_sma_200": .1,
        "sma_20_vs_sma_50": .01, "sma_50_vs_sma_200": .08, "rsi_14": 55.0,
        "macd_line": 1.0, "macd_signal": .5, "macd_histogram": .5,
        "realized_volatility_20d": .2, "trend_state": "bullish_alignment",
        "momentum_state": "positive", "volatility_state": "moderate",
        "technical_score": 80.0, "technical_notes": "evidence",
        "study_id": "tam", "study_name": "Technical Analysis",
        "study_version": "v0.1", "study_purpose": "Observation",
        "scheduled_time_label": None, "run_mode": "manual-ui",
    } for ticker in tickers)
    return build_universe_analysis_snapshot_v1(handoff, run, rows)


def test_multiple_universes_survive_restart_with_identity_and_manual_membership(tmp_path):
    path = tmp_path / "research.sqlite"
    first_process = SQLiteResearchUniverseRepository(path)
    technology = _universe("technology-growth-ai", "Technology Growth AI", ("NVDA",) * 0 + tuple(f"T{i}" for i in range(66)))
    cyber = _universe("cybersecurity", "Critical Infrastructure Cybersecurity", ("CRWD", "PANW"))
    cyber = ResearchUniverseReviewService().revise(
        cyber,
        additional_starting_companies=(source_record(
            {"company_name": "Zscaler", "ticker": "ZS",
             "identity_status": IdentityStatus.RESOLVED}, UniverseSource.USER_ENTERED,
            source_reference="manual:ZS",
        ),),
    )
    first_process.save(technology)
    first_process.save(cyber)

    restarted = SQLiteResearchUniverseRepository(path)
    listed = restarted.list_all()
    assert {item.universe_id for item in listed} == {"technology-growth-ai", "cybersecurity"}
    assert len(restarted.get("technology-growth-ai").approved_membership) == 66
    reopened = restarted.get("cybersecurity")
    assert reopened.universe_id == cyber.universe_id
    assert {row.ticker_or_identifier for row in reopened.approved_membership} == {"CRWD", "PANW", "ZS"}
    assert restarted.save(reopened).universe_id == cyber.universe_id
    assert len(restarted.list_all()) == 2


def test_review_dispositions_round_trip_without_provider_calls(tmp_path):
    repository = SQLiteResearchUniverseRepository(tmp_path / "research.sqlite")
    universe = _universe("u-a", "Universe A", ("AAA", "BBB"))
    rejected = universe.candidates[0].normalized_matching_key
    universe = ResearchUniverseReviewService().revise(
        universe, dispositions={rejected: CandidateDisposition.REJECTED},
    )
    repository.save(universe)
    restored = repository.get("u-a")
    assert restored.universe_id == "u-a"
    assert any(row.disposition == CandidateDisposition.REJECTED for row in restored.candidates)
    assert len(restored.approved_membership) == 1


def test_snapshot_backed_reopen_preserves_history_and_previous_candidate(tmp_path):
    path = tmp_path / "research.sqlite"
    universe_repository = SQLiteResearchUniverseRepository(path)
    snapshot_repository = SQLiteUniverseAnalysisSnapshotRepository(path)
    original = _universe("stable-universe-a", "Universe A", ("AAA", "BBB"))
    first = _snapshot(original, "run-1", "2026-07-20 12:00:00 PM EDT")
    snapshot_repository.save(first)

    orphan = universe_repository.list_orphaned_snapshots()[0]
    reopened = recover_universe_from_snapshot(orphan.snapshot)
    universe_repository.save(reopened)
    restarted = SQLiteResearchUniverseRepository(path).get("stable-universe-a")
    second = _snapshot(restarted, "run-2", "2026-07-21 12:00:00 PM EDT")
    snapshot_repository.save(second)

    history = snapshot_repository.list_for_universe("stable-universe-a")
    assert [item.snapshot_id for item in history] == [second.snapshot_id, first.snapshot_id]
    assert snapshot_repository.get_previous_candidate(
        "stable-universe-a", restarted.version, before_snapshot_id=second.snapshot_id,
    ) == first
    assert universe_repository.list_orphaned_snapshots() == ()
