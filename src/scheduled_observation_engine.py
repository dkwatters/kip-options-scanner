"""Scheduler-independent, durable first-observation comparison service."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from src.observation_comparisons import ObservationComparison, comparison_identity
from src.observation_event_repository import ObservationEventRepository, ObservationComparisonConflict
from src.observation_events import detect_observation_events, signal_instant, OBSERVATION_EVENT_RULES_VERSION
from src.signal_repository import SignalRepository
from src.signals import Signal


@dataclass(frozen=True, slots=True)
class ObservationEngineResult:
    compared_signal_count: int
    event_count: int
    inserted_count: int
    retry_count: int
    comparison_inserted_count: int = 0
    comparison_retry_count: int = 0


def observe_signal_changes(current_signals: Iterable[Signal], *, signal_repository: SignalRepository,
                           event_repository: ObservationEventRepository) -> ObservationEngineResult:
    """Resume the original selection; completed comparisons never select history again."""
    compared = event_count = inserted_count = retry_count = comparison_inserted = comparison_retry = 0
    for current in current_signals:
        try:
            stored = event_repository.get_comparison(current.signal_id)
            if stored is None:
                # Earlier development builds had events but no durable comparison receipt.
                # Their first-observation history cannot safely be inferred after backfills.
                if event_repository.list_events(current_signal_id=current.signal_id):
                    stored = event_repository.get_comparison(current.signal_id)
                    if stored is None:
                        raise ObservationComparisonConflict("Legacy Observation Events lack a comparison receipt; explicit evidence migration is required")
            if stored is None:
                candidates = signal_repository.list_signals(
                    ticker=current.ticker, signal_family=current.signal_family,
                    model_id=current.model_id, model_version=current.model_version,
                )
                current_instant = signal_instant(current.as_of)
                prior = max((s for s in candidates if signal_instant(s.as_of) < current_instant),
                            key=lambda s: (signal_instant(s.as_of), s.signal_id), default=None)
                events = detect_observation_events(prior, current) if prior else ()
                now = datetime.now(timezone.utc).isoformat()
                proposed = ObservationComparison(
                    comparison_id=comparison_identity(current.signal_id), current_signal_id=current.signal_id,
                    prior_signal_id=prior.signal_id if prior else None, ticker=current.ticker,
                    signal_family=current.signal_family, model_id=current.model_id, model_version=current.model_version,
                    current_as_of=current.as_of, prior_as_of=prior.as_of if prior else None,
                    evaluated_at=now, event_count=len(events), source_scan_id=current.metadata.get("source_scan_id"),
                    metadata={"rules_version": OBSERVATION_EVENT_RULES_VERSION,
                              "current_evidence_refs": current.evidence_refs,
                              "prior_evidence_refs": prior.evidence_refs if prior else (),
                              "prior_source_scan_id": prior.metadata.get("source_scan_id") if prior else None,
                              "event_ids": [event.event_id for event in events]}, created_at=now,
                )
                event_repository.save_comparison(proposed, accept_existing=True)
                stored = event_repository.get_comparison(current.signal_id)
            comparison, completed = stored
            compared += comparison.prior_signal_id is not None
            event_count += comparison.event_count
            if completed:
                retry_count += comparison.event_count
                comparison_retry += 1
                continue
            # A failed write or concurrent reservation resumes only its persisted prior identity.
            if comparison.prior_signal_id is None:
                events = ()
            else:
                candidates = signal_repository.list_signals(
                    ticker=comparison.ticker, signal_family=comparison.signal_family,
                    model_id=comparison.model_id, model_version=comparison.model_version,
                )
                prior = next((s for s in candidates if s.signal_id == comparison.prior_signal_id), None)
                if prior is None:
                    raise ObservationComparisonConflict("Reserved prior Signal is unavailable")
                events = detect_observation_events(prior, current)
            if tuple(event.event_id for event in events) != tuple(comparison.metadata["event_ids"]):
                raise ObservationComparisonConflict("Reserved comparison event identities changed")
            inserted, already_completed = event_repository.complete_comparison(comparison, events)
            inserted_count += sum(inserted)
            retry_count += len(inserted) - sum(inserted)
            comparison_inserted += not already_completed
            comparison_retry += already_completed
        except Exception as error:
            # Earlier items commit independently; preserve their counts for the caller.
            error.observation_result = ObservationEngineResult(
                compared, event_count, inserted_count, retry_count,
                comparison_inserted, comparison_retry,
            )
            raise
    return ObservationEngineResult(compared, event_count, inserted_count, retry_count,
                                   comparison_inserted, comparison_retry)
