from pathlib import Path
import sqlite3

from streamlit.testing.v1 import AppTest

from src.observation_event_repository import ObservationEventRepository, POSTGRES_SCHEMA
from src.observation_events import ObservationEventImportance, detect_observation_events
from src.research_repository import REPOSITORY_BACKEND_SQLITE, ResearchRepositoryTarget
from src.scheduled_observation_engine import observe_signal_changes
from src.signal_repository import SignalRepository
from src.signals import Signal, SignalDirection, SignalFamily
from src.technical_observation_service import archive_technical_observations_and_signals
from scripts.seed_observation_event_acceptance import seed_acceptance_step


def _target(tmp_path):
    return ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite")


def _signal(identifier, as_of, *, family=SignalFamily.DIRECTIONAL,
            model="technical-setup-score", version="technical-setup-signal-v0.1.1",
            direction=SignalDirection.NEUTRAL, trend="mixed", regime=None,
            volatility_trend=None, source_scan=None):
    metadata = {"source_scan_id": source_scan or identifier}
    if family is SignalFamily.DIRECTIONAL:
        metadata["source_trend_state"] = trend
    else:
        metadata.update({"regime": regime, "volatility_trend": volatility_trend})
    conviction = {SignalDirection.BULLISH: .5, SignalDirection.BEARISH: -.5}.get(direction, 0.0)
    return Signal(
        signal_id=identifier, ticker="NVDA", as_of=as_of, model_id=model,
        model_version=version, direction=direction, conviction=conviction,
        reasoning="deterministic test signal", signal_family=family,
        metadata=metadata, evidence_refs=(f"scan:{source_scan or identifier}",),
        created_at=as_of,
    )


def _persist_and_observe(repository, event_repository, *signals):
    repository.save_signals(signals)
    return observe_signal_changes(
        signals[-1:], signal_repository=repository, event_repository=event_repository,
    )


def test_first_signal_and_unchanged_state_emit_no_event(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    first = _signal("first", "2026-01-01T10:00:00Z")
    signals.save_signal(first)
    assert observe_signal_changes((first,), signal_repository=signals, event_repository=events).event_count == 0
    unchanged = _signal("unchanged", "2026-01-02T10:00:00Z")
    assert _persist_and_observe(signals, events, unchanged).event_count == 0
    assert events.list_events() == ()


def test_directional_transition_emits_trend_and_direction_events(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    prior = _signal("prior", "2026-01-01T10:00:00Z")
    current = _signal("current", "2026-01-02T10:00:00Z", trend="constructive", direction=SignalDirection.BULLISH)
    result = _persist_and_observe(signals, events, prior, current)
    persisted = events.list_events()
    assert result.inserted_count == 2
    assert {event.event_type for event in persisted} == {
        "directional.trend_state_changed", "directional.direction_changed",
    }
    assert all(event.signal_family is SignalFamily.DIRECTIONAL for event in persisted)


def test_volatility_regime_and_trend_transitions_are_non_directional(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    prior = _signal("vol-prior", "2026-01-01T10:00:00Z", family=SignalFamily.VOLATILITY,
                    model="volatility-context", version="volatility-context-v0.1",
                    direction=SignalDirection.NOT_APPLICABLE, regime="normal", volatility_trend="stable")
    current = _signal("vol-current", "2026-01-02T10:00:00Z", family=SignalFamily.VOLATILITY,
                      model="volatility-context", version="volatility-context-v0.1",
                      direction=SignalDirection.NOT_APPLICABLE, regime="extreme", volatility_trend="expanding")
    result = _persist_and_observe(signals, events, prior, current)
    persisted = events.list_events()
    assert result.inserted_count == 2
    assert {event.event_type for event in persisted} == {
        "volatility.regime_changed", "volatility.trend_changed",
    }
    regime = next(event for event in persisted if event.field == "regime")
    assert regime.importance is ObservationEventImportance.MAJOR
    assert all(event.metadata["directional_interpretation"] is False for event in persisted)


def test_incompatible_model_version_or_family_is_not_compared():
    directional = _signal("d", "2026-01-01T10:00:00Z")
    new_version = _signal("v", "2026-01-02T10:00:00Z", version="v2",
                          trend="constructive", direction=SignalDirection.BULLISH)
    volatility = _signal("vol", "2026-01-02T10:00:00Z", family=SignalFamily.VOLATILITY,
                         model="technical-setup-score", version="technical-setup-signal-v0.1.1",
                         direction=SignalDirection.NOT_APPLICABLE, regime="normal", volatility_trend="stable")
    assert detect_observation_events(directional, new_version) == ()
    assert detect_observation_events(directional, volatility) == ()


def test_identity_and_persistence_are_idempotent(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    prior = _signal("prior", "2026-01-01T10:00:00Z")
    current = _signal("current", "2026-01-02T10:00:00Z", trend="constructive", direction=SignalDirection.BULLISH)
    signals.save_signals((prior, current))
    first = observe_signal_changes((current,), signal_repository=signals, event_repository=events)
    second = observe_signal_changes((current,), signal_repository=signals, event_repository=events)
    assert first.inserted_count == 2 and second.retry_count == 2
    assert len(events.list_events()) == 2
    assert detect_observation_events(prior, current) == detect_observation_events(prior, current)


def test_latest_chronological_prior_is_selected_and_future_is_ignored(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    oldest = _signal("oldest", "2026-01-01T10:00:00Z", trend="mixed")
    latest_prior = _signal("latest-prior", "2026-01-02T10:00:00Z", trend="constructive", direction=SignalDirection.BULLISH)
    current = _signal("historical-current", "2026-01-03T10:00:00Z", trend="mixed")
    future = _signal("future", "2026-01-04T10:00:00Z", trend="bullish_alignment", direction=SignalDirection.BULLISH)
    signals.save_signals((oldest, latest_prior, current, future))
    observe_signal_changes((current,), signal_repository=signals, event_repository=events)
    assert {event.prior_signal_id for event in events.list_events()} == {"latest-prior"}
    assert {event.current_signal_id for event in events.list_events()} == {"historical-current"}


def test_same_timestamp_is_not_treated_as_history(tmp_path):
    signals = SignalRepository(_target(tmp_path)); events = ObservationEventRepository(_target(tmp_path))
    first = _signal("same-a", "2026-01-01T10:00:00Z")
    second = _signal("same-b", "2026-01-01T10:00:00Z", trend="constructive", direction=SignalDirection.BULLISH)
    signals.save_signals((first, second))
    assert observe_signal_changes((second,), signal_repository=signals, event_repository=events).event_count == 0


def test_legacy_database_bootstraps_additive_event_table(tmp_path):
    target = _target(tmp_path); SignalRepository(target).initialize()
    repository = ObservationEventRepository(target); repository.initialize()
    with sqlite3.connect(target.sqlite_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"research_signals", "signal_outcomes", "observation_events"} <= tables


def test_postgres_schema_has_event_table_indexes_and_signal_lineage():
    schema = " ".join(POSTGRES_SCHEMA)
    assert "observation_events" in schema
    assert "REFERENCES research_signals(signal_id)" in schema
    assert "idx_observation_events_model_observed" in schema


def _row(scan_id, timestamp, trend):
    return {
        "scan_id": scan_id, "ticker": "NVDA", "technical_timestamp": timestamp,
        "trend_state": trend, "momentum_state": "positive", "volatility_state": "moderate",
        "price": 125.0, "price_vs_sma_20": .1, "price_vs_sma_50": .1,
        "price_vs_sma_200": .1, "sma_20_vs_sma_50": .1, "sma_50_vs_sma_200": .1,
        "rsi_14": 60.0, "macd_line": 2.0, "macd_signal": 1.0, "macd_histogram": 1.0,
    }


def test_shared_boundary_generates_events_for_repeated_scheduled_or_manual_scans(tmp_path):
    target = _target(tmp_path); signals = SignalRepository(target)
    kwargs = {"archive_observations": lambda rows: len(rows), "signal_repository": signals}
    first = archive_technical_observations_and_signals(
        [_row("scheduled-1", "2026-01-01T10:00:00Z", "mixed")], **kwargs,
    )
    second = archive_technical_observations_and_signals(
        [_row("scheduled-2", "2026-01-02T10:00:00Z", "constructive")], **kwargs,
    )
    retry = archive_technical_observations_and_signals(
        [_row("scheduled-2", "2026-01-02T10:00:00Z", "constructive")], **kwargs,
    )
    assert first.observation_event_count == 0
    assert second.observation_event_count == 2
    assert retry.signal_retry_count == 1 and retry.observation_event_count == 0
    assert retry.observation_event_retry_count == 2
    assert len(ObservationEventRepository(target).list_events()) == 2


def test_model_lab_renders_observation_history_without_directional_volatility_language(monkeypatch, tmp_path):
    target = _target(tmp_path); signals = SignalRepository(target); events = ObservationEventRepository(target)
    prior = _signal("vol-prior", "2026-01-01T10:00:00Z", family=SignalFamily.VOLATILITY,
                    model="volatility-context", version="volatility-context-v0.1",
                    direction=SignalDirection.NOT_APPLICABLE, regime="normal", volatility_trend="stable")
    current = _signal("vol-current", "2026-01-02T10:00:00Z", family=SignalFamily.VOLATILITY,
                      model="volatility-context", version="volatility-context-v0.1",
                      direction=SignalDirection.NOT_APPLICABLE, regime="elevated", volatility_trend="expanding")
    _persist_and_observe(signals, events, prior, current)
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", REPOSITORY_BACKEND_SQLITE)
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(target.sqlite_path)); monkeypatch.setenv("RCE_PROVIDER", "mock")
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py", default_timeout=20).run()
    next(widget for widget in app.sidebar.radio if widget.label == "Navigation").set_value("Model Lab"); app.run()
    assert not app.exception
    frame = next(frame.value for frame in app.dataframe if "Event type" in frame.value.columns)
    assert set(frame["Prior state"]) == {"normal", "stable"}
    assert set(frame["Current state"]) == {"elevated", "expanding"}
    assert not any(word in " ".join(frame.astype(str).values.flatten()).lower() for word in ("bullish", "bearish"))


def test_manual_acceptance_seed_is_two_step_deterministic_and_idempotent(tmp_path):
    database = tmp_path / "acceptance.sqlite"
    first = seed_acceptance_step(database, 1)
    second = seed_acceptance_step(database, 2)
    retry = seed_acceptance_step(database, 2)
    assert first["event_inserted_count"] == 0
    assert second == {
        "signal_inserted_count": 2, "signal_retry_count": 0,
        "event_inserted_count": 4, "event_retry_count": 0,
    }
    assert retry == {
        "signal_inserted_count": 0, "signal_retry_count": 2,
        "event_inserted_count": 0, "event_retry_count": 4,
    }
