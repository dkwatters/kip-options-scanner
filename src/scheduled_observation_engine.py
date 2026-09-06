"""Scheduler-independent comparison service for newly persisted Signals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.observation_event_repository import ObservationEventRepository
from src.observation_events import ObservationEvent, detect_observation_events, signal_instant
from src.signal_repository import SignalRepository
from src.signals import Signal


@dataclass(frozen=True, slots=True)
class ObservationEngineResult:
    compared_signal_count: int
    event_count: int
    inserted_count: int
    retry_count: int


def observe_signal_changes(current_signals: Iterable[Signal], *, signal_repository: SignalRepository,
                           event_repository: ObservationEventRepository) -> ObservationEngineResult:
    """Compare each Signal only to its latest strictly earlier compatible Signal."""
    events: list[ObservationEvent] = []; compared = 0
    for current in current_signals:
        candidates = signal_repository.list_signals(
            ticker=current.ticker, signal_family=current.signal_family,
            model_id=current.model_id, model_version=current.model_version,
        )
        current_instant = signal_instant(current.as_of)
        earlier = tuple(signal for signal in candidates if signal_instant(signal.as_of) < current_instant)
        prior = max(earlier, key=lambda signal: (signal_instant(signal.as_of), signal.signal_id), default=None)
        if prior is None: continue
        compared += 1; events.extend(detect_observation_events(prior, current))
    inserted = event_repository.save_events(events) if events else ()
    return ObservationEngineResult(compared, len(events), sum(inserted), len(inserted) - sum(inserted))
