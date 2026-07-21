import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.research_universe import (
    IdentityStatus, ResearchUniverseHandoff, ResearchUniverseMemberHandoff,
)
from src.research_universe_analysis import (
    AnalysisLedgerEntry, AnalysisMemberStatus, ResearchUniverseAnalysisRun,
)
from src.universe_analysis_contracts import (
    SNAPSHOT_SCHEMA_VERSION, SnapshotStatus, UniverseAnalysisSnapshotV1,
)
from src.universe_analysis_snapshot_builder import build_universe_analysis_snapshot_v1
from src.universe_analysis_snapshot_repository import (
    POSTGRES_SCHEMA_STATEMENTS, SNAPSHOT_TABLE, SQLiteUniverseAnalysisSnapshotRepository,
    SnapshotConflictError, SnapshotSchemaError,
)
from src.universe_analysis_snapshot_service import persist_completed_universe_analysis_snapshot


TICKERS = ("STR", "CON", "MIX", "WEAK", "EXT")


def _sources(run_id="run-a", timestamp="2026-07-20 12:00:00 PM EDT"):
    members = tuple(ResearchUniverseMemberHandoff(
        matching_key=f"ticker:{ticker}", company_name=f"Company {ticker}",
        ticker_or_identifier=ticker, identity_status=IdentityStatus.RESOLVED,
        provenance_references=(f"source:{ticker}",),
    ) for ticker in TICKERS) + (ResearchUniverseMemberHandoff(
        matching_key="name:private", company_name="Private Co", ticker_or_identifier=None,
        identity_status=IdentityStatus.UNRESOLVED,
        provenance_references=("source:private",),
    ),)
    handoff = ResearchUniverseHandoff(
        universe_id="durable-universe", universe_version=2, universe_title="Durable Universe",
        research_question="Which companies are positioned?", ordered_members=members,
        approved_constituents=TICKERS, expected_constituent_count=5, total_member_count=6,
        unresolved_members=("Private Co",), provenance_references=("research:durable",),
        requested_at=datetime(2026, 7, 20, 15, tzinfo=timezone.utc),
    )
    ledger = tuple(AnalysisLedgerEntry(
        member.matching_key, member.company_name, member.ticker_or_identifier,
        member.identity_status,
        AnalysisMemberStatus.ANALYZED if member.ticker_or_identifier else AnalysisMemberStatus.UNRESOLVED,
        "Completed" if member.ticker_or_identifier else "Identity unresolved",
    ) for member in members)
    run = ResearchUniverseAnalysisRun(
        handoff.universe_id, handoff.universe_version, handoff.universe_title,
        handoff.research_question, 6, TICKERS, TICKERS, ("Private Co",),
        timestamp, run_id, ledger,
    )
    profiles = (
        ("STR", .05, .10, .20, .05, .10, 60, .2, "moderate", "bullish_alignment", "positive"),
        ("CON", .02, .03, -.02, .02, -.02, 60, .2, "high", "constructive", "positive"),
        ("MIX", .02, -.02, -.02, -.02, -.02, 48, .2, "high", "mixed", "neutral"),
        ("WEAK", -.02, -.03, -.10, -.02, -.02, 35, -.2, "high", "bearish_alignment", "negative"),
        ("EXT", .10, .20, .35, .05, .10, 75, .2, "low", "bullish_alignment", "overbought_positive"),
    )
    rows = tuple(_row(run_id, timestamp, *profile) for profile in profiles)
    return handoff, run, rows


def _row(run_id, timestamp, ticker, p20, p50, p200, a20, a50, rsi, macd, volatility, trend, momentum):
    positive = macd > 0
    return {
        "scan_id": run_id, "ticker": ticker, "technical_timestamp": timestamp,
        "price": 100.123456789, "sma_20": 95.123456789, "sma_50": 90.0, "sma_200": 80.0,
        "price_vs_sma_20": p20, "price_vs_sma_50": p50, "price_vs_sma_200": p200,
        "sma_20_vs_sma_50": a20, "sma_50_vs_sma_200": a50, "rsi_14": rsi,
        "macd_line": 1.0 if positive else -.5, "macd_signal": .5 if positive else 0.0,
        "macd_histogram": macd, "realized_volatility_20d": .6 if volatility == "high" else .3,
        "trend_state": trend, "momentum_state": momentum, "volatility_state": volatility,
        "technical_score": 42.123456789, "technical_notes": "raw evidence",
        "study_id": "tam", "study_name": "Technical Analysis", "study_version": "v0.1",
        "study_purpose": "Observation", "scheduled_time_label": None, "run_mode": "manual_ui",
    }


def _snapshot(run_id="run-a", timestamp="2026-07-20 12:00:00 PM EDT"):
    handoff, run, rows = _sources(run_id, timestamp)
    return build_universe_analysis_snapshot_v1(handoff, run, rows), handoff, run, rows


@pytest.fixture
def repository(tmp_path):
    return SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "research.sqlite")


def test_save_and_typed_round_trip_preserves_complete_semantics(repository):
    snapshot, _, _, _ = _snapshot()
    assert repository.save(snapshot) is snapshot
    restored = repository.get(snapshot.snapshot_id)
    assert restored == snapshot
    assert restored.to_dict() == snapshot.to_dict()
    assert [member.matching_key for member in restored.members] == [member.matching_key for member in snapshot.members]
    assert restored.members[-1].raw_technical_observation is None
    assert restored.members[0].raw_technical_observation.price == 100.123456789
    assert restored.members[0].derived_observation.rank_denominator == 5
    assert restored.members[0].evidence_references == snapshot.members[0].evidence_references
    assert restored.summary == snapshot.summary
    assert restored.version_manifest == snapshot.version_manifest
    assert restored.membership_digest == snapshot.membership_digest
    assert restored.completed_at == snapshot.completed_at


def test_two_snapshot_history_is_deterministic_and_first_is_immutable(repository):
    first, _, _, _ = _snapshot()
    second, _, _, _ = _snapshot("run-b", "2026-07-21 12:00:00 PM EDT")
    repository.save(first)
    repository.save(second)
    assert [item.snapshot_id for item in repository.list_for_universe("durable-universe")] == [
        second.snapshot_id, first.snapshot_id,
    ]
    assert repository.get_latest_for_universe("durable-universe") == second
    assert repository.get_previous_candidate(
        "durable-universe", 2, before_snapshot_id=second.snapshot_id
    ) == first
    assert repository.get(first.snapshot_id) == first
    summary = repository.history_summary("durable-universe", 2)
    assert summary.snapshot_count == 2 and summary.latest_snapshot_id == second.snapshot_id


def test_version_filter_and_completed_filter(repository):
    snapshot, _, _, _ = _snapshot()
    repository.save(snapshot)
    version_three = replace(snapshot, snapshot_id="version-three", universe_version=3, analysis_run_id="run-v3")
    repository.save(version_three)
    invalidated = replace(snapshot, snapshot_id="invalidated", analysis_run_id="run-invalid", status=SnapshotStatus.INVALIDATED)
    repository.save(invalidated)
    assert len(repository.list_for_universe("durable-universe")) == 3
    assert repository.list_for_universe("durable-universe", 3) == (version_three,)
    assert repository.get_latest_for_universe("durable-universe", 2, completed_only=True) == snapshot


def test_duplicate_payload_is_idempotent_and_conflicting_payload_is_rejected(repository):
    snapshot, _, _, _ = _snapshot()
    repository.save(snapshot)
    assert repository.save(snapshot) == snapshot
    with pytest.raises(SnapshotConflictError):
        repository.save(replace(snapshot, research_question="different historical content"))
    assert repository.get(snapshot.snapshot_id) == snapshot


def test_invalid_and_unknown_schema_are_rejected_before_insert(repository):
    snapshot, _, _, _ = _snapshot()
    with pytest.raises(ValueError, match="do not reconcile"):
        repository.save(replace(snapshot, analyzed_count=4))
    with pytest.raises((ValueError, SnapshotSchemaError), match="schema"):
        repository.save(replace(snapshot, schema_version="future.v9"))
    assert repository.list_for_universe("durable-universe") == ()
    payload = snapshot.to_dict()
    payload["schema_version"] = "future.v9"
    with pytest.raises(ValueError, match="Unsupported"):
        UniverseAnalysisSnapshotV1.from_dict(payload)


def test_corrupt_stored_schema_is_explicit(repository):
    snapshot, _, _, _ = _snapshot()
    repository.initialize()
    payload = snapshot.to_dict()
    payload["schema_version"] = "future.v9"
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            f"INSERT INTO {SNAPSHOT_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snapshot.snapshot_id, "future.v9", snapshot.universe_id, snapshot.universe_version,
             snapshot.membership_digest, snapshot.analysis_run_id, "completed",
             snapshot.observation_as_of, snapshot.completed_at, snapshot.built_at,
             "analysis", "scoring", "presentation", json.dumps(payload)),
        )
    with pytest.raises(SnapshotSchemaError):
        repository.get(snapshot.snapshot_id)


def test_no_legacy_technical_scan_becomes_snapshot(repository):
    repository.initialize()
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("CREATE TABLE technical_characterization (scan_id TEXT, ticker TEXT)")
        connection.execute("INSERT INTO technical_characterization VALUES ('legacy', 'OLD')")
    assert repository.list_for_universe("durable-universe") == ()


class ObservationRepository:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def technical_analysis_observations(self, **kwargs):
        self.calls += 1
        return {"rows": self.rows}


class RecordingSnapshotRepository:
    def __init__(self, error=None):
        self.saved = []
        self.error = error

    def save(self, snapshot):
        if self.error:
            raise self.error
        self.saved.append(snapshot)
        return snapshot


def test_completed_lifecycle_builds_and_persists_exactly_once_without_provider_call():
    _, handoff, run, rows = _snapshot()
    observations = ObservationRepository(rows)
    snapshots = RecordingSnapshotRepository()
    result = persist_completed_universe_analysis_snapshot(
        handoff=handoff, run=run, observation_repository=observations,
        snapshot_repository=snapshots,
    )
    assert observations.calls == 1
    assert snapshots.saved == [result]
    assert result.status == SnapshotStatus.COMPLETED


def test_unreconciled_lifecycle_does_not_persist_false_snapshot():
    _, handoff, run, rows = _snapshot()
    snapshots = RecordingSnapshotRepository()
    with pytest.raises(ValueError):
        persist_completed_universe_analysis_snapshot(
            handoff=handoff, run=run, observation_repository=ObservationRepository(rows[:-1]),
            snapshot_repository=snapshots,
        )
    assert snapshots.saved == []


def test_persistence_failure_is_explicit_and_service_does_not_swallow_it():
    _, handoff, run, rows = _snapshot()
    snapshots = RecordingSnapshotRepository(RuntimeError("database unavailable"))
    with pytest.raises(RuntimeError, match="database unavailable"):
        persist_completed_universe_analysis_snapshot(
            handoff=handoff, run=run, observation_repository=ObservationRepository(rows),
            snapshot_repository=snapshots,
        )


def test_sqlite_and_postgres_schema_define_same_immutable_envelope(repository):
    repository.initialize()
    with sqlite3.connect(repository.database_path) as connection:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({SNAPSHOT_TABLE})")}
    postgres = " ".join(POSTGRES_SCHEMA_STATEMENTS)
    for column in (
        "snapshot_id", "schema_version", "universe_id", "universe_version",
        "membership_digest", "analysis_run_id", "status", "observation_as_of",
        "completed_at", "persisted_at", "analysis_version", "scoring_version",
        "presentation_version", "snapshot_json",
    ):
        assert column in columns and column in postgres
