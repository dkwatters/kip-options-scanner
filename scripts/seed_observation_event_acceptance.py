"""Seed manual acceptance; run as ``python -m scripts.seed_observation_event_acceptance``."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.observation_event_repository import ObservationEventRepository
from src.research_repository import REPOSITORY_BACKEND_SQLITE, ResearchRepositoryTarget
from src.scheduled_observation_engine import observe_signal_changes
from src.signal_repository import SignalRepository
from src.signals import Signal, SignalDirection, SignalFamily


def seed_acceptance_step(database: Path, step: int) -> dict[str, int]:
    if step not in (1, 2): raise ValueError("step must be 1 or 2")
    target = ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=database)
    signals = SignalRepository(target); events = ObservationEventRepository(target)
    selected = _scenario_signals(step)
    inserted = signals.save_signals(selected)
    observation = observe_signal_changes(selected, signal_repository=signals, event_repository=events)
    return {
        "signal_inserted_count": sum(inserted),
        "signal_retry_count": len(inserted) - sum(inserted),
        "event_inserted_count": observation.inserted_count,
        "event_retry_count": observation.retry_count,
    }


def _scenario_signals(step: int) -> tuple[Signal, ...]:
    as_of = f"2026-08-0{step}T16:00:00-04:00"
    volatility = Signal(
        signal_id=f"acceptance-volatility-{step}", ticker="NVDA", as_of=as_of,
        model_id="volatility-context", model_version="volatility-context-v0.1",
        signal_family=SignalFamily.VOLATILITY, direction=SignalDirection.NOT_APPLICABLE,
        conviction=0.0, reasoning="Deterministic v0.4 manual-acceptance fixture.",
        metadata={
            "regime": "normal" if step == 1 else "elevated",
            "volatility_trend": "stable" if step == 1 else "expanding",
            "source_scan_id": f"acceptance-step-{step}", "developer_test_data": True,
        },
        evidence_refs=(f"developer-test:acceptance-step-{step}:NVDA",), created_at=as_of,
    )
    directional = Signal(
        signal_id=f"acceptance-directional-{step}", ticker="HOOD", as_of=as_of,
        model_id="technical-setup-score", model_version="technical-setup-signal-v0.1.1",
        direction=SignalDirection.BULLISH if step == 1 else SignalDirection.NEUTRAL,
        conviction=.5 if step == 1 else 0.0,
        reasoning="Deterministic v0.4 manual-acceptance fixture.",
        metadata={
            "source_trend_state": "constructive" if step == 1 else "mixed",
            "source_scan_id": f"acceptance-step-{step}", "developer_test_data": True,
        },
        evidence_refs=(f"developer-test:acceptance-step-{step}:HOOD",), created_at=as_of,
    )
    return volatility, directional


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--step", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    result = seed_acceptance_step(args.database, args.step)
    print(" ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__": main()
