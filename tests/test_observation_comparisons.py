"""First-observation authority, including backfills and interrupted completion."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from src.observation_comparisons import COMPARISON_DDL, comparison_identity
from src.observation_event_repository import ObservationComparisonConflict, ObservationEventRepository
from src.scheduled_observation_engine import observe_signal_changes
from src.signal_repository import SignalRepository
from src.signals import SignalDirection
from tests.test_scheduled_observation_engine import _signal, _target


def _scenario(tmp_path, state):
    signals = SignalRepository(_target(tmp_path))
    events = ObservationEventRepository(_target(tmp_path))
    a = _signal("A", "2026-08-01T16:00:00Z", trend="constructive", direction=SignalDirection.BULLISH)
    c = _signal("C", "2026-08-03T16:00:00Z", trend="mixed" if state == "events" else "constructive",
                direction=SignalDirection.NEUTRAL if state == "events" else SignalDirection.BULLISH)
    b = _signal("B", "2026-08-02T16:00:00Z", trend="bullish_alignment", direction=SignalDirection.BULLISH)
    signals.save_signals((c,) if state == "no_prior" else (a, c))
    return signals, events, a, b, c


@pytest.mark.parametrize("state,count", [("events", 2), ("unchanged", 0), ("no_prior", 0)])
def test_backfill_never_changes_completed_comparison(tmp_path, monkeypatch, state, count):
    signals, events, a, b, c = _scenario(tmp_path, state)
    first = observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    original = events.get_comparison(c.signal_id)
    original_events = events.list_events()
    assert original[1] is True and original[0].event_count == count
    assert original[0].prior_signal_id == (None if state == "no_prior" else "A")
    assert first.comparison_inserted_count == 1 and first.inserted_count == count
    signals.save_signal(b)
    # A completed retry must not even query candidate history.
    monkeypatch.setattr(signals, "list_signals", lambda **kwargs: pytest.fail("History reselected"))
    retry = observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    assert retry.comparison_retry_count == 1 and retry.comparison_inserted_count == 0
    assert retry.inserted_count == 0 and retry.retry_count == count
    assert events.get_comparison(c.signal_id) == original
    assert events.list_events() == original_events


def test_backfilled_signal_can_be_prior_for_unevaluated_signal(tmp_path):
    signals, events, a, b, c = _scenario(tmp_path, "events")
    observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    signals.save_signal(b)
    # D occurs after B, before C; C is future history for D.
    d = _signal("D", "2026-08-02T18:00:00Z", trend="mixed")
    signals.save_signal(d)
    observe_signal_changes((d,), signal_repository=signals, event_repository=events)
    assert events.get_comparison(d.signal_id)[0].prior_signal_id == "B"
    assert events.get_comparison(c.signal_id)[0].prior_signal_id == "A"


def test_identity_conflicts_and_duplicate_persistence(tmp_path):
    signals, events, a, b, c = _scenario(tmp_path, "events")
    observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    comparison, completed = events.get_comparison(c.signal_id)
    assert comparison_identity("C") == comparison.comparison_id
    assert comparison_identity("C", "future-policy") != comparison.comparison_id
    assert events.save_comparison(comparison) == (comparison, False)
    with pytest.raises(ObservationComparisonConflict):
        events.save_comparison(replace(comparison, source_scan_id="conflicting-source"))
    assert events.get_comparison(c.signal_id) == (comparison, True)
    with pytest.raises(TypeError):
        comparison.metadata["rules_version"] = "changed"


@pytest.mark.parametrize("state,count", [("events", 2), ("unchanged", 0), ("no_prior", 0)])
def test_failed_event_transaction_resumes_reserved_prior_after_backfill(tmp_path, monkeypatch, state, count):
    signals, events, a, b, c = _scenario(tmp_path, state)
    save = events._save_events
    def interrupted(cursor, rows, placeholder):
        save(cursor, rows, placeholder)
        raise RuntimeError("interrupted after event inserts")
    with monkeypatch.context() as patch:
        patch.setattr(events, "_save_events", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    comparison, completed = events.get_comparison(c.signal_id)
    assert not completed and comparison.prior_signal_id == (None if state == "no_prior" else "A")
    assert events.list_events() == ()
    signals.save_signal(b)
    recovered = observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    assert recovered.inserted_count == count
    assert events.get_comparison(c.signal_id) == (comparison, True)
    assert {e.prior_signal_id for e in events.list_events()} == ({"A"} if count else set())


def test_legacy_event_evidence_is_not_silently_reinterpreted(tmp_path):
    from src.observation_events import detect_observation_events
    signals, events, a, b, c = _scenario(tmp_path, "events")
    original = detect_observation_events(a, c)
    events.save_events(original)
    signals.save_signal(b)
    with pytest.raises(ObservationComparisonConflict, match="Legacy Observation Events"):
        observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    assert events.get_comparison(c.signal_id) is None
    assert {e.event_id for e in events.list_events()} == {e.event_id for e in original}


def test_additive_bootstrap_and_foreign_keys(tmp_path):
    target = _target(tmp_path)
    SignalRepository(target).initialize()
    events = ObservationEventRepository(target)
    events.initialize()
    events.initialize()
    with events._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"research_signals", "signal_outcomes", "observation_comparisons", "observation_comparison_completions"} <= tables
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO observation_comparison_completions VALUES ('missing')")


def test_postgres_comparison_ddl_structure():
    schema = " ".join(COMPARISON_DDL)
    assert "UNIQUE(current_signal_id, policy_version)" in schema
    assert schema.count("REFERENCES research_signals(signal_id)") == 2
    assert "REFERENCES observation_comparisons(comparison_id)" in schema
    assert "idx_observation_comparisons_model" in schema


def test_concurrent_observers_share_one_completed_comparison(tmp_path):
    signals, events, a, b, c = _scenario(tmp_path, "events")
    events.initialize()
    def observe(_):
        return observe_signal_changes((c,), signal_repository=signals, event_repository=events)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(observe, range(2)))
    assert sum(r.inserted_count for r in results) == 2
    assert sum(r.retry_count for r in results) == 2
    assert events.get_comparison(c.signal_id)[1] is True
    assert len(events.list_events()) == 2


def test_partial_batch_failure_preserves_counts_and_recovers(tmp_path, monkeypatch):
    from src.technical_observation_service import archive_technical_observations_and_signals
    from tests.test_scheduled_observation_engine import _row
    target = _target(tmp_path)
    kwargs = {"archive_observations": lambda rows: len(rows), "signal_repository": SignalRepository(target)}
    archive_technical_observations_and_signals([_row("A", "2026-08-01T10:00:00Z", "mixed")], **kwargs)
    rows = [_row("B", "2026-08-02T10:00:00Z", "constructive"),
            _row("C", "2026-08-03T10:00:00Z", "mixed")]
    complete = ObservationEventRepository.complete_comparison
    def fail_second(self, comparison, events):
        if comparison.source_scan_id == "C":
            raise RuntimeError("second comparison interrupted")
        return complete(self, comparison, events)
    with monkeypatch.context() as patch:
        patch.setattr(ObservationEventRepository, "complete_comparison", fail_second)
        failed = archive_technical_observations_and_signals(rows, **kwargs)
    assert failed.observation_event_count == 2
    assert failed.observation_comparison_inserted_count == 1
    assert "second comparison interrupted" in failed.observation_event_persistence_error
    recovered = archive_technical_observations_and_signals(rows, **kwargs)
    assert recovered.observation_event_count == 2 and recovered.observation_event_retry_count == 2
    assert recovered.observation_comparison_inserted_count == 1
    assert recovered.observation_comparison_retry_count == 1
