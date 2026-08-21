from dataclasses import replace

import pytest

from src.universe_analysis_change_detection import detect_universe_changes
from src.universe_analysis_snapshot_comparison import Comparability, assess_snapshot_comparability
from src.universe_interpretation_input import build_universe_interpretation_input_v01
from src.universe_interpretation_selection import (
    SELECTION_POLICY_VERSION,
    InterpretationSelectionPolicyV01,
    SelectionReason,
    SelectionSectionName,
    select_universe_interpretation_facts_v01,
    validate_interpretation_selection_result_v01,
)
from tests.test_universe_analysis_change_detection import _pair


def _selection(*, field=None, before=None, after=None, mutate=None, policy=None):
    baseline, current = _pair(field=field, before=before, after=after)
    if mutate:
        baseline, current = mutate(baseline, current)
    assessment = assess_snapshot_comparability(baseline, current)
    changes = detect_universe_changes(baseline, current, assessment)
    case_file = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    result = select_universe_interpretation_facts_v01(case_file, policy or InterpretationSelectionPolicyV01())
    return case_file, result


def test_fully_comparable_normal_interval_selects_current_sections_without_new_facts():
    case_file, result = _selection()
    assert result.comparison_status == Comparability.FULL.value
    assert result.section("what_changed").items == ()
    assert [item.source_id for item in result.section("leaders").items] == [
        item.member_snapshot_id for item in case_file.leaders
    ]
    assert [item.source_id for item in result.section("laggards").items] == [
        item.member_snapshot_id for item in case_file.laggards
    ]
    assert all(item.selection_reason == SelectionReason.CURRENT_LEADER
               for item in result.section("leaders").items)


def test_major_change_uses_existing_priority_and_evidence():
    case_file, result = _selection(field="technical_profile", before="Weak", after="Strong")
    selected = result.section(SelectionSectionName.WHAT_CHANGED).items
    assert selected
    assert [item.source_event_id for item in selected] == [event.event_id for event in case_file.priority_events]
    assert selected[0].original_priority_tier == case_file.priority_events[0].priority_tier
    assert selected[0].evidence_refs == tuple(sorted(set(case_file.priority_events[0].evidence_refs)))
    assert selected[0].selection_reason == SelectionReason.HIGH_PRIORITY_CHANGE


def test_limits_are_respected_without_reranking_leaders_or_laggards():
    policy = InterpretationSelectionPolicyV01(
        current_read_limit=1, deserves_attention_limit=1, what_changed_limit=1,
        leaders_limit=2, laggards_limit=1, membership_changes_limit=1, caveats_limit=1,
    )
    case_file, result = _selection(field="technical_profile", before="Weak", after="Strong", policy=policy)
    assert all(len(section.items) <= section.item_limit for section in result.sections)
    assert [item.source_id for item in result.section("leaders").items] == [
        member.member_snapshot_id for member in case_file.leaders[:2]
    ]
    assert result.section("laggards").items[0].source_id == case_file.laggards[0].member_snapshot_id


def test_limited_comparison_membership_addition_and_removal_are_selected():
    def mutate(baseline, current):
        removed = baseline.members[-1]
        added = replace(current.members[-1], matching_key="ticker:NEW", member_snapshot_id="new-member",
                        ticker_or_identifier="NEW", company_name="New Company")
        return baseline, replace(current, universe_version=4, membership_digest="changed",
                                 members=current.members[:-1] + (added,))
    case_file, result = _selection(mutate=mutate)
    assert result.comparison_status == Comparability.LIMITED.value
    membership = result.section("membership_changes").items
    assert [item.source_type for item in membership] == ["membership_addition", "membership_removal"]
    assert [item.selection_reason for item in membership] == [
        SelectionReason.MEMBERSHIP_ADDITION, SelectionReason.MEMBERSHIP_REMOVAL,
    ]
    assert "comparison_not_fully_comparable" in [item.source_id for item in result.section("caveats").items]


def test_not_comparable_suppresses_changes_but_preserves_current_and_caveats():
    def mutate(baseline, current):
        return baseline, replace(current, universe_id="other-universe")
    _, result = _selection(mutate=mutate)
    assert result.comparison_status == Comparability.NOT_COMPARABLE.value
    assert result.section("what_changed").items == ()
    assert result.section("leaders").items
    caveats = result.section("caveats").items
    assert any(item.selection_reason == SelectionReason.COMPARISON_LIMITATION for item in caveats)


def test_unavailable_members_remain_attention_candidates():
    case_file, result = _selection()
    unavailable = next(item for item in case_file.attention_candidates
                       if item.priority_tier is None)
    selected = result.section("deserves_attention").items
    assert any(item.source_id == unavailable.member_snapshot_id for item in selected)


def test_tie_breaking_duplicates_and_cross_section_reuse_are_deterministic():
    case_file, first = _selection(field="momentum", before="neutral", after="positive")
    second = select_universe_interpretation_facts_v01(case_file)
    assert first == second and first.to_dict() == second.to_dict()
    for section in first.sections:
        identities = [(item.source_type, item.source_id) for item in section.items]
        assert len(identities) == len(set(identities))
        assert list(section.items) == sorted(section.items, key=lambda item: item.ordering_key)
    attention_ids = {item.source_id for item in first.section("deserves_attention").items}
    current_ids = {item.source_id for item in first.section("current_read").items
                   if item.source_type == "attention_candidate"}
    assert attention_ids & current_ids  # explicitly allowed semantic cross-section reuse


def test_explicit_caveats_are_selected_without_invention():
    case_file, result = _selection()
    selected = tuple(item.source_id for item in result.section("caveats").items)
    assert selected == case_file.caveats[:result.section("caveats").item_limit]


def test_invalid_source_reference_is_rejected_by_diagnostic_validator():
    case_file, result = _selection()
    leaders = result.section("leaders")
    bad_item = replace(leaders.items[0], source_id="missing-source")
    bad_section = replace(leaders, items=(bad_item,) + leaders.items[1:])
    bad_result = replace(result, sections=tuple(
        bad_section if section.name == SelectionSectionName.LEADERS else section
        for section in result.sections
    ))
    with pytest.raises(ValueError, match="does not exist"):
        validate_interpretation_selection_result_v01(case_file, bad_result)


def test_unsupported_policy_version_and_negative_limits_fail_explicitly():
    case_file, _ = _selection()
    with pytest.raises(ValueError, match="Unsupported"):
        select_universe_interpretation_facts_v01(
            case_file, replace(InterpretationSelectionPolicyV01(), policy_version="future"),
        )
    with pytest.raises(ValueError, match="non-negative"):
        select_universe_interpretation_facts_v01(
            case_file, replace(InterpretationSelectionPolicyV01(), leaders_limit=-1),
        )


def test_contract_version_and_serialization_are_stable():
    _, result = _selection()
    payload = result.to_dict()
    assert result.policy_version == SELECTION_POLICY_VERSION
    assert payload["policy_version"] == SELECTION_POLICY_VERSION
    assert [section["name"] for section in payload["sections"]] == [item.value for item in SelectionSectionName]
