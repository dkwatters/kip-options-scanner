"""Deterministic, developer-gated Universe Analysis demo scenarios."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Mapping

from src.research_universe import (
    IdentityStatus,
    ResearchUniverse,
    ResearchUniverseHandoff,
    ResearchUniverseMemberHandoff,
    ResearchUniverseReviewService,
    UniverseSource,
    UniverseState,
    source_record,
)
from src.research_universe_analysis import (
    AnalysisLedgerEntry,
    AnalysisMemberStatus,
    ResearchUniverseAnalysisRun,
)
from src.universe_analysis_contracts import DataFreshness, UniverseAnalysisSnapshotV1
from src.universe_analysis_presentation_service import (
    UniverseAnalysisPresentationBundleV01,
    build_universe_analysis_presentation,
)
from src.universe_analysis_snapshot_builder import build_universe_analysis_snapshot_v1
from src.universe_analysis_snapshot_repository import UniverseAnalysisSnapshotRepository


DEMO_UNIVERSE_PREFIX = "demo-"
DEVELOPER_TOOLS_ENV = "ENABLE_DEVELOPER_TOOLS"


class DemoScenarioKind(StrEnum):
    FIRST_RUN = "first_run"
    COMPARABLE_CHANGE = "comparable_change"
    NO_CHANGE = "no_change"
    MEMBERSHIP_CHANGE = "membership_change"
    LIMITED_COMPARABILITY = "limited_comparability"


@dataclass(frozen=True, slots=True)
class DemoScenarioV01:
    kind: DemoScenarioKind
    universe_id: str
    universe_name: str
    universe: ResearchUniverse
    handoff: ResearchUniverseHandoff
    current_run: ResearchUniverseAnalysisRun
    current_rows: tuple[dict, ...]
    snapshots: tuple[UniverseAnalysisSnapshotV1, ...]
    current_snapshot_id: str


@dataclass(frozen=True, slots=True)
class DemoScenarioCreationResultV01:
    scenario: DemoScenarioV01
    presentation: UniverseAnalysisPresentationBundleV01
    snapshots_created: int


def developer_tools_enabled(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return str(values.get(DEVELOPER_TOOLS_ENV, "")).strip().casefold() in {
        "1", "true", "yes", "on",
    }


def create_demo_scenario(
    kind: DemoScenarioKind | str,
    repository: UniverseAnalysisSnapshotRepository,
) -> DemoScenarioCreationResultV01:
    scenario = build_demo_scenario(DemoScenarioKind(kind))
    before = {
        item.snapshot_id
        for item in repository.list_for_universe(scenario.universe_id)
    }
    for snapshot in scenario.snapshots:
        repository.save(snapshot)
    presentation = build_universe_analysis_presentation(
        scenario.current_snapshot_id, repository,
    )
    return DemoScenarioCreationResultV01(
        scenario, presentation,
        sum(snapshot.snapshot_id not in before for snapshot in scenario.snapshots),
    )


def reset_demo_data(repository: UniverseAnalysisSnapshotRepository) -> int:
    return repository.delete_demo_snapshots(DEMO_UNIVERSE_PREFIX)


def build_demo_scenario(kind: DemoScenarioKind | str) -> DemoScenarioV01:
    kind = DemoScenarioKind(kind)
    universe_id = f"{DEMO_UNIVERSE_PREFIX}{kind.value.replace('_', '-')}"
    title = "Demo – " + kind.value.replace("_", " ").title()
    base_symbols = ("ALFA", "BETA", "GAMA", "DLTA", "EPSI", "ZETA")
    current_symbols = base_symbols
    baseline_symbols = base_symbols
    baseline_version = current_version = 1
    if kind == DemoScenarioKind.MEMBERSHIP_CHANGE:
        baseline_symbols = base_symbols
        current_symbols = base_symbols[:-1] + ("THET",)
    elif kind == DemoScenarioKind.LIMITED_COMPARABILITY:
        baseline_version, current_version = 1, 2

    baseline = None
    if kind != DemoScenarioKind.FIRST_RUN:
        baseline = _artifact(universe_id, title, baseline_version, baseline_symbols, "baseline")
    current_state = "changed" if kind == DemoScenarioKind.COMPARABLE_CHANGE else "stable"
    current = _artifact(
        universe_id, title, current_version, current_symbols, "current", current_state,
        unavailable_last=kind == DemoScenarioKind.LIMITED_COMPARABILITY,
    )
    snapshots = ((baseline[2],) if baseline else ()) + (current[2],)
    return DemoScenarioV01(
        kind, universe_id, title, current[4], current[0], current[1], current[3], snapshots,
        current[2].snapshot_id,
    )


def _artifact(universe_id, title, version, symbols, interval, state="stable", *, unavailable_last=False):
    is_current = interval == "current"
    instant = datetime(2026, 7, 21 if not is_current else 22, 14, 30, tzinfo=timezone.utc)
    run_id = f"demo-run-{universe_id.removeprefix(DEMO_UNIVERSE_PREFIX)}-{version}-{interval}"
    members = tuple(ResearchUniverseMemberHandoff(
        matching_key=f"ticker:{ticker}", company_name=f"Demo {ticker}",
        ticker_or_identifier=ticker, identity_status=IdentityStatus.RESOLVED,
        provenance_references=(f"demo-fixture:{universe_id}:{ticker}",),
    ) for ticker in symbols)
    handoff = ResearchUniverseHandoff(
        universe_id, version, title, "Deterministic developer QA scenario",
        members, tuple(symbols), len(symbols), len(symbols), (),
        (f"demo-fixture:{universe_id}",), instant,
    )
    universe = ResearchUniverseReviewService().assemble(
        universe_id=universe_id, title=title,
        research_question=handoff.research_question,
        starting_companies=tuple(source_record(
            {
                "company_name": member.company_name,
                "ticker": member.ticker_or_identifier,
                "identity_status": IdentityStatus.RESOLVED.value,
            },
            UniverseSource.IMPORTED,
            source_reference=member.provenance_references[0],
        ) for member in members),
        version=version, state=UniverseState.ANALYZED,
        provenance={"demo": True},
    )
    universe = replace(universe, created_at=instant, updated_at=instant)
    analyzed_symbols = tuple(symbols[:-1] if unavailable_last else symbols)
    ledger = tuple(AnalysisLedgerEntry(
        member.matching_key, member.company_name, member.ticker_or_identifier,
        member.identity_status,
        (AnalysisMemberStatus.NO_MARKET_DATA
         if unavailable_last and member.ticker_or_identifier == symbols[-1]
         else AnalysisMemberStatus.ANALYZED),
        ("Deterministic demo unavailability."
         if unavailable_last and member.ticker_or_identifier == symbols[-1]
         else "Deterministic demo observation."),
    ) for member in members)
    run = ResearchUniverseAnalysisRun(
        universe_id, version, title, handoff.research_question, len(symbols),
        tuple(symbols), analyzed_symbols,
        ((symbols[-1],) if unavailable_last else ()),
        instant.isoformat().replace("+00:00", "Z"),
        run_id, ledger,
    )
    rows = tuple(_technical_row(ticker, run_id, instant, index, state)
                 for index, ticker in enumerate(analyzed_symbols))
    snapshot = build_universe_analysis_snapshot_v1(
        handoff, run, rows, snapshot_id=f"demo-snapshot-{universe_id.removeprefix(DEMO_UNIVERSE_PREFIX)}-{version}-{interval}",
        built_at=instant, data_provider="deterministic-demo", data_freshness=DataFreshness.FRESH,
    )
    return handoff, run, snapshot, rows, universe


def _technical_row(ticker, run_id, instant, index, state):
    weak = index < 3 and state != "changed"
    strong = index < 3 and state == "changed"
    scale = index * .004
    p20 = .06 - scale
    p50 = .09 - scale
    p200 = .14 - scale
    rsi = 60 - index
    macd = .25
    trend, momentum = "constructive", "positive"
    if weak:
        p20, p50, p200, rsi, macd = -.05, -.09, -.15, 34, -.3
        trend, momentum = "bearish_alignment", "negative"
    elif strong:
        p20, p50, p200, rsi, macd = .08, .14, .24, 66, .4
        trend, momentum = "bullish_alignment", "positive"
    timestamp = instant.isoformat().replace("+00:00", "Z")
    return {
        "scan_id": run_id, "ticker": ticker, "technical_timestamp": timestamp,
        "price": 100.0 + index, "sma_20": 96.0, "sma_50": 92.0, "sma_200": 85.0,
        "price_vs_sma_20": p20, "price_vs_sma_50": p50, "price_vs_sma_200": p200,
        "sma_20_vs_sma_50": .04 if not weak else -.04,
        "sma_50_vs_sma_200": .08 if not weak else -.08,
        "rsi_14": rsi, "macd_line": macd + .1, "macd_signal": .1,
        "macd_histogram": macd, "realized_volatility_20d": .30,
        "trend_state": trend, "momentum_state": momentum,
        "volatility_state": "moderate", "technical_score": 50.0,
        "technical_notes": "deterministic demo evidence", "study_id": "demo-study",
        "study_name": "Developer QA", "study_version": "v0.1",
        "study_purpose": "Deterministic UI testing", "scheduled_time_label": None,
        "run_mode": "developer_demo",
    }
