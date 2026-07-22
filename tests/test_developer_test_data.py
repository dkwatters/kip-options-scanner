from dataclasses import replace

import pytest

from src.developer_test_data import (
    DEMO_UNIVERSE_PREFIX,
    DemoScenarioKind,
    build_demo_scenario,
    create_demo_scenario,
    developer_tools_enabled,
    reset_demo_data,
)
from src.universe_analysis_presentation_service import PresentationAssemblyStatus
from src.universe_analysis_snapshot_repository import SQLiteUniverseAnalysisSnapshotRepository


def test_developer_tools_are_disabled_by_default():
    assert developer_tools_enabled({}) is False
    assert developer_tools_enabled({"ENABLE_DEVELOPER_TOOLS": "true"}) is True


@pytest.mark.parametrize("kind", tuple(DemoScenarioKind))
def test_demo_scenarios_are_isolated_deterministic_and_reach_presentation(tmp_path, kind):
    repository = SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite")
    first = create_demo_scenario(kind, repository)
    second = create_demo_scenario(kind, repository)

    assert first.scenario.universe_id.startswith(DEMO_UNIVERSE_PREFIX)
    assert first.scenario.universe_name.startswith("Demo")
    assert first.scenario.universe.universe_id == first.scenario.handoff.universe_id
    assert all(item.snapshot_id.startswith("demo-snapshot-") for item in first.scenario.snapshots)
    assert first.scenario.snapshots == second.scenario.snapshots
    assert first.scenario.current_rows == second.scenario.current_rows
    assert tuple(
        (item.normalized_matching_key, item.company_name, item.ticker_or_identifier,
         item.identity_status, item.disposition)
        for item in first.scenario.universe.candidates
    ) == tuple(
        (item.normalized_matching_key, item.company_name, item.ticker_or_identifier,
         item.identity_status, item.disposition)
        for item in second.scenario.universe.candidates
    )
    assert first.scenario.universe.created_at == second.scenario.universe.created_at
    assert first.snapshots_created == len(first.scenario.snapshots)
    assert second.snapshots_created == 0
    assert first.presentation == second.presentation


def test_first_run_has_no_baseline(tmp_path):
    result = create_demo_scenario(
        DemoScenarioKind.FIRST_RUN,
        SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite"),
    )
    assert result.presentation.status == PresentationAssemblyStatus.FIRST_SNAPSHOT
    assert result.presentation.baseline_snapshot is None


def test_comparable_change_has_valid_changes_and_attention(tmp_path):
    result = create_demo_scenario(
        DemoScenarioKind.COMPARABLE_CHANGE,
        SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite"),
    )
    assert result.presentation.comparison.comparability.value == "fully_comparable"
    assert result.presentation.changes.atomic_events
    assert result.presentation.interpretation_input.attention_candidates


def test_no_change_has_empty_change_events(tmp_path):
    result = create_demo_scenario(
        DemoScenarioKind.NO_CHANGE,
        SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite"),
    )
    assert result.presentation.changes.atomic_events == ()
    assert result.presentation.selection.section("what_changed").items == ()


def test_membership_change_is_limited_and_not_technical(tmp_path):
    result = create_demo_scenario(
        DemoScenarioKind.MEMBERSHIP_CHANGE,
        SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite"),
    )
    events = result.presentation.changes.atomic_events
    assert result.presentation.comparison.comparability.value == "limited_comparability"
    assert {event.category for event in events} == {"membership"}
    assert {event.direction for event in events} == {"entered", "exited"}


def test_limited_comparability_includes_unavailable_member_and_caveat(tmp_path):
    result = create_demo_scenario(
        DemoScenarioKind.LIMITED_COMPARABILITY,
        SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite"),
    )
    assert result.presentation.comparison.comparability.value == "limited_comparability"
    assert result.scenario.snapshots[-1].unavailable_count == 1
    assert result.presentation.selection.section("caveats").items


def test_reset_deletes_only_demo_snapshots(tmp_path):
    repository = SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite")
    demo = create_demo_scenario(DemoScenarioKind.NO_CHANGE, repository).scenario
    non_demo = replace(
        demo.snapshots[-1], snapshot_id="real-snapshot", universe_id="real-universe",
        analysis_run_id="real-run",
    )
    repository.save(non_demo)

    assert reset_demo_data(repository) == len(demo.snapshots)
    assert repository.get("real-snapshot") == non_demo
    assert repository.list_for_universe(demo.universe_id) == ()


def test_reset_rejects_any_broader_prefix(tmp_path):
    repository = SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "demo.sqlite")
    with pytest.raises(ValueError, match="exact 'demo-'"):
        repository.delete_demo_snapshots("")


def test_demo_service_has_no_provider_ai_or_scoring_integration():
    source = open("src/developer_test_data.py", encoding="utf-8").read().casefold()
    assert "tradier" not in source
    assert "openai" not in source
    assert "technical_analysis_rows_for_symbols" not in source
    assert "scoring.py" not in source
