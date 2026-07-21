from dataclasses import replace

import pytest

from src.universe_analysis_change_detection import (
    UNIVERSE_CHANGE_RULES_VERSION, ChangeDetectionStatus, detect_universe_changes,
)
from src.universe_analysis_snapshot_comparison import (
    Comparability, SnapshotComparisonAssessmentV01, assess_snapshot_comparability,
)
from src.universe_analysis_snapshot_repository import SQLiteUniverseAnalysisSnapshotRepository
from tests.test_universe_analysis_snapshot_contract import _build


def _pair(*, ticker="MIX", field=None, before=None, after=None):
    baseline, _, _, _ = _build()
    members = list(baseline.members)
    index = next(i for i, member in enumerate(members) if member.ticker_or_identifier == ticker)
    member = members[index]
    if field:
        old = replace(member.derived_observation, **{field: before})
        new = replace(member.derived_observation, **{field: after})
        members[index] = replace(member, derived_observation=old)
        baseline = replace(baseline, members=tuple(members))
        current_member = replace(member, member_snapshot_id="current-" + member.member_snapshot_id,
                                 derived_observation=new)
        members[index] = current_member
    current = replace(baseline, snapshot_id="snapshot-current", analysis_run_id="run-current",
                      completed_at="2026-07-21T16:00:00Z", built_at="2026-07-21T16:01:00Z",
                      members=tuple(members))
    return baseline, current


@pytest.mark.parametrize("field,before,after,direction,materiality", [
    ("technical_profile", "Constructive", "Strong", "improved", "notable"),
    ("technical_profile", "Strong", "Weak", "deteriorated", "attention"),
    ("technical_profile", "Weak", "Mixed", "improved", "notable"),
    ("trend", "mixed", "bullish alignment", "improved", "attention"),
    ("trend", "bullish_alignment", "mixed", "deteriorated", "attention"),
    ("trend", "deteriorating", "bearish_alignment", "deteriorated", "attention"),
    ("momentum", "neutral", "positive", "improved", "notable"),
    ("momentum", "positive", "negative", "deteriorated", "notable"),
    ("momentum", "positive", "overbought positive", "changed", "notable"),
    ("momentum", "negative", "neutral", "improved", "notable"),
    ("extension_positioning", "Near trend", "Moderately extended", "changed", "notable"),
    ("extension_positioning", "Moderately extended", "Elevated", "deteriorated", "attention"),
    ("extension_positioning", "Elevated", "Near trend", "improved", "attention"),
    ("extension_positioning", "Below long-term trend", "Near trend", "improved", "notable"),
    ("volatility", "moderate", "high", "deteriorated", "notable"),
    ("volatility", "high", "moderate", "improved", "notable"),
    ("price_vs_sma_20_state", "below", "above", "improved", "notable"),
    ("price_vs_sma_50_state", "above", "below", "deteriorated", "notable"),
    ("price_vs_sma_200_state", "below", "above", "improved", "attention"),
    ("sma_20_50_state", "bearish", "bullish", "improved", "notable"),
    ("sma_50_200_state", "bearish", "bullish", "improved", "attention"),
])
def test_transition_matrix(field, before, after, direction, materiality):
    baseline, current = _pair(field=field, before=before, after=after)
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    event = next(event for event in result.atomic_events if event.field == field)
    assert (event.direction, event.materiality) == (direction, materiality)
    assert event.rule_id and event.rule_version == UNIVERSE_CHANGE_RULES_VERSION
    assert len(event.evidence_refs) == 2


def test_unchanged_and_numeric_noise_emit_no_events():
    baseline, current = _pair()
    member = current.members[2]
    raw = replace(member.raw_technical_observation, rsi_14=99, macd_line=9,
                  price=999, technical_score=100, realized_volatility_20d=.59)
    current = replace(current, members=current.members[:2] + (replace(member, raw_technical_observation=raw),) + current.members[3:])
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    assert result.status == ChangeDetectionStatus.NO_CHANGES
    assert not result.atomic_events


def test_rank_threshold_boundaries_and_determinism():
    baseline, current = _pair(ticker="MIX", field="rank", before=4, after=1)
    first = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    second = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    assert first == second
    assert {e.event_type for e in first.atomic_events} >= {"rank_material_movement"}
    assert tuple(e.event_id for e in first.atomic_events) == first.groups[0].event_ids
    assert all(e.previous_value != e.current_value for e in first.atomic_events)


def test_rank_below_threshold_and_denominator_change_are_suppressed():
    baseline, current = _pair(ticker="MIX", field="rank", before=4, after=3)
    assert not detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current)).atomic_events
    current = replace(current, analyzed_count=current.analyzed_count + 1)
    assessment = replace(assess_snapshot_comparability(baseline, current), rank_comparison_allowed=False)
    assert not detect_universe_changes(baseline, current, assessment).atomic_events


def test_availability_is_not_a_technical_event():
    baseline, current = _pair()
    member = current.members[0]
    current = replace(current, members=(replace(member, analysis_status="unavailable", derived_observation=None,
        raw_technical_observation=None),) + current.members[1:])
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    event = next(e for e in result.atomic_events if e.event_type == "availability_lost")
    assert (event.category, event.direction) == ("availability", "unavailable")


def test_availability_restored_and_unavailable_in_both():
    analyzed, current = _pair()
    original = analyzed.members[0]
    unavailable = replace(original, analysis_status="unavailable", derived_observation=None,
                          raw_technical_observation=None)
    baseline = replace(analyzed, members=(unavailable,) + analyzed.members[1:])
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    assert next(e for e in result.atomic_events if e.event_type == "availability_restored").direction == "restored"
    current_unavailable = replace(current, members=(replace(unavailable, member_snapshot_id="current-unavailable"),) + current.members[1:])
    result = detect_universe_changes(baseline, current_unavailable,
                                     assess_snapshot_comparability(baseline, current_unavailable))
    assert not any(e.category == "availability" for e in result.atomic_events)


def test_membership_added_limited_comparison_preserves_intersection_and_blocks_rank():
    baseline, current = _pair(field="momentum", before="neutral", after="positive")
    new_member = replace(current.members[0], member_snapshot_id="new-member", matching_key="ticker:NEW",
                         ticker_or_identifier="NEW", company_name="New Company", membership_order=7)
    current = replace(current, universe_version=4, membership_digest="changed", members=current.members + (new_member,),
                      total_universe_member_count=7, analyzed_count=6, requested_analyzable_count=6)
    assessment = assess_snapshot_comparability(baseline, current)
    result = detect_universe_changes(baseline, current, assessment)
    assert assessment.comparability == Comparability.LIMITED and not assessment.rank_comparison_allowed
    assert any(e.event_type == "membership_added" and e.direction == "entered" for e in result.atomic_events)
    assert any(e.field == "momentum" for e in result.atomic_events)
    assert not any(e.field in ("rank", "top_3", "top_quartile") for e in result.atomic_events)


def test_membership_removed_is_separate_from_technical_direction():
    baseline, current = _pair()
    removed = current.members[-1]
    current = replace(current, universe_version=4, membership_digest="removed",
                      members=current.members[:-1], total_universe_member_count=5, unavailable_count=0)
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    event = next(e for e in result.atomic_events if e.event_type == "membership_removed")
    assert (event.matching_key, event.category, event.direction) == (removed.matching_key, "membership", "exited")


def test_eight_member_rank_leadership_boundaries():
    baseline, current = _pair(ticker="MIX", field="rank", before=4, after=1)
    extras = tuple(replace(baseline.members[i], matching_key=f"extra:{i}", member_snapshot_id=f"base-extra-{i}",
                           ticker_or_identifier=f"X{i}", membership_order=7 + i,
                           derived_observation=replace(baseline.members[i].derived_observation, rank=7 + i,
                                                       rank_denominator=8)) for i in range(2))
    def adjust(snapshot, suffix):
        members = tuple(replace(m, member_snapshot_id=f"{suffix}-{m.member_snapshot_id}",
                                derived_observation=(replace(m.derived_observation, rank_denominator=8)
                                                     if m.derived_observation else None)) for m in snapshot.members)
        return replace(snapshot, members=members + extras, analyzed_count=8, unavailable_count=0,
                       total_universe_member_count=8, requested_analyzable_count=8,
                       membership_digest="eight-member-stable")
    baseline, current = adjust(baseline, "b"), adjust(current, "c")
    result = detect_universe_changes(baseline, current, assess_snapshot_comparability(baseline, current))
    types = {e.event_type for e in result.atomic_events}
    assert {"rank_material_movement", "rank_entered_top_3", "rank_entered_top_quartile"} <= types


def test_persisted_snapshots_load_compare_detect(tmp_path):
    baseline, current = _pair(field="momentum", before="neutral", after="positive")
    repository = SQLiteUniverseAnalysisSnapshotRepository(tmp_path / "snapshots.sqlite")
    repository.save(baseline); repository.save(current)
    loaded_baseline = repository.get(baseline.snapshot_id)
    loaded_current = repository.get(current.snapshot_id)
    result = detect_universe_changes(loaded_baseline, loaded_current,
                                     assess_snapshot_comparability(loaded_baseline, loaded_current))
    assert any(event.field == "momentum" for event in result.atomic_events)


def test_not_comparable_performs_no_detection():
    baseline, current = _pair(field="technical_profile", before="Weak", after="Strong")
    current = replace(current, universe_id="other-universe")
    assessment = assess_snapshot_comparability(baseline, current)
    result = detect_universe_changes(baseline, current, assessment)
    assert assessment.comparability == Comparability.NOT_COMPARABLE
    assert result.status == ChangeDetectionStatus.NOT_COMPARABLE and not result.atomic_events


def test_assessment_identity_is_required_and_inputs_are_not_mutated():
    baseline, current = _pair(field="momentum", before="neutral", after="positive")
    before = (baseline.to_dict(), current.to_dict())
    assessment = assess_snapshot_comparability(baseline, current)
    detect_universe_changes(baseline, current, assessment)
    assert before == (baseline.to_dict(), current.to_dict())
    with pytest.raises(ValueError, match="does not reference"):
        detect_universe_changes(baseline, current, replace(assessment, current_snapshot_id="wrong"))
