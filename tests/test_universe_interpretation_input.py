from dataclasses import replace

import pytest

from src.universe_analysis_change_detection import detect_universe_changes
from src.universe_analysis_snapshot_comparison import assess_snapshot_comparability
from src.universe_interpretation_input import (
    INTERPRETATION_INPUT_SCHEMA_VERSION,
    build_universe_interpretation_input_v01,
)
from tests.test_universe_analysis_change_detection import _pair


def _case(*, field=None, before=None, after=None):
    baseline, current = _pair(field=field, before=before, after=after)
    assessment = assess_snapshot_comparability(baseline, current)
    changes = detect_universe_changes(baseline, current, assessment)
    return baseline, current, assessment, changes


def test_normal_universe_case_file_reuses_current_facts_and_orders_rank():
    baseline, current, assessment, changes = _case()
    result = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert result.schema_version == INTERPRETATION_INPUT_SCHEMA_VERSION
    assert result.universe_summary is current.summary
    assert result.comparison_summary is assessment
    assert result.change_summary is changes.counts
    assert [member.derived_observation.rank for member in result.leaders] == [1, 2, 3]
    assert [member.derived_observation.rank for member in result.laggards] == [5, 4, 3]
    assert result.metadata.current_snapshot_id == current.snapshot_id


def test_no_changes_has_empty_priority_events_but_explicit_unavailable_attention():
    baseline, current, assessment, changes = _case()
    result = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert result.priority_events == ()
    unavailable = next(member for member in current.members if member.analysis_status != "analyzed")
    candidate = next(item for item in result.attention_candidates if item.matching_key == unavailable.matching_key)
    assert candidate.event_ids == ()
    assert candidate.reason_codes == (f"availability:{unavailable.analysis_status}",)
    assert "members_unavailable" in result.caveats


def test_major_changes_preserve_priority_event_and_evidence_order():
    baseline, current, assessment, changes = _case(
        field="technical_profile", before="Weak", after="Strong",
    )
    result = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert result.priority_events[0].materiality == "attention"
    candidate = next(item for item in result.attention_candidates
                     if item.matching_key == result.priority_events[0].matching_key)
    assert result.priority_events[0].event_id in candidate.event_ids
    assert set(result.priority_events[0].evidence_refs) <= set(result.evidence_refs)
    assert tuple(item.priority_order_key for item in result.priority_events) == tuple(sorted(
        item.priority_order_key for item in result.priority_events
    ))


def test_membership_additions_and_removals_resolve_to_correct_snapshot():
    baseline, current, _, _ = _case()
    removed = baseline.members[-1]
    new_member = replace(current.members[-1], matching_key="ticker:NEW", member_snapshot_id="new-member",
                         ticker_or_identifier="NEW", company_name="New Company")
    current = replace(current, universe_version=4, membership_digest="changed",
                      members=current.members[:-1] + (new_member,))
    assessment = assess_snapshot_comparability(baseline, current)
    changes = detect_universe_changes(baseline, current, assessment)
    result = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert [item.matching_key for item in result.additions] == [new_member.matching_key]
    assert [item.matching_key for item in result.removals] == [removed.matching_key]
    assert result.additions[0].member_snapshot_id == new_member.member_snapshot_id
    assert result.removals[0].member_snapshot_id == removed.member_snapshot_id


def test_incompatible_snapshots_are_packaged_with_explicit_caveat_and_no_events():
    baseline, current, _, _ = _case()
    current = replace(current, universe_id="different-universe")
    assessment = assess_snapshot_comparability(baseline, current)
    changes = detect_universe_changes(baseline, current, assessment)
    result = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert result.priority_events == ()
    assert "comparison_not_fully_comparable" in result.caveats
    assert "universe_id_changed" in result.caveats


def test_limits_and_repeated_builds_are_deterministic_and_json_safe():
    baseline, current, assessment, changes = _case(field="momentum", before="neutral", after="positive")
    first = build_universe_interpretation_input_v01(
        baseline, current, assessment, changes, priority_event_limit=0, leader_limit=2, laggard_limit=1,
    )
    second = build_universe_interpretation_input_v01(
        baseline, current, assessment, changes, priority_event_limit=0, leader_limit=2, laggard_limit=1,
    )
    assert first == second
    assert first.priority_events == () and len(first.leaders) == 2 and len(first.laggards) == 1
    assert first.to_dict() == second.to_dict()
    assert isinstance(first.to_dict()["leaders"], list)


def test_inputs_are_not_mutated_and_interval_mismatches_are_rejected():
    baseline, current, assessment, changes = _case()
    originals = baseline.to_dict(), current.to_dict()
    build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    assert originals == (baseline.to_dict(), current.to_dict())
    with pytest.raises(ValueError, match="Change result does not reference"):
        build_universe_interpretation_input_v01(
            baseline, current, assessment, replace(changes, current_snapshot_id="wrong"),
        )
    with pytest.raises(ValueError, match="limits cannot be negative"):
        build_universe_interpretation_input_v01(
            baseline, current, assessment, changes, priority_event_limit=-1,
        )


def test_duplicate_event_ids_are_rejected():
    baseline, current, assessment, changes = _case(field="momentum", before="neutral", after="positive")
    duplicate = replace(changes, atomic_events=changes.atomic_events + changes.atomic_events)
    with pytest.raises(ValueError, match="duplicate event"):
        build_universe_interpretation_input_v01(baseline, current, assessment, duplicate)
