"""Lifecycle integration for building and durably storing completed snapshots."""
from __future__ import annotations

from typing import Any

from src.research_universe import ResearchUniverseHandoff
from src.research_universe_analysis import ResearchUniverseAnalysisRun
from src.universe_analysis_contracts import UniverseAnalysisSnapshotV1
from src.universe_analysis_snapshot_builder import build_universe_analysis_snapshot_v1
from src.universe_analysis_snapshot_repository import UniverseAnalysisSnapshotRepository


def persist_completed_universe_analysis_snapshot(
    *,
    handoff: ResearchUniverseHandoff,
    run: ResearchUniverseAnalysisRun,
    observation_repository: Any,
    snapshot_repository: UniverseAnalysisSnapshotRepository,
) -> UniverseAnalysisSnapshotV1:
    """Persist exactly one reconciled completed run; raise on any inconsistency."""
    observations = observation_repository.technical_analysis_observations(
        tickers=list(run.analyzed_tickers), latest_scan_only=False, scan_id=run.scan_id,
    )
    snapshot = build_universe_analysis_snapshot_v1(
        handoff, run, observations["rows"]
    )
    return snapshot_repository.save(snapshot)
