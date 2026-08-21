from dataclasses import replace

import pytest

from src.universe_analysis_change_detection import detect_universe_changes
from src.universe_analysis_snapshot_comparison import Comparability, assess_snapshot_comparability
from src.universe_interpretation_input import build_universe_interpretation_input_v01
from src.universe_interpretation_presentation import (
    PRESENTATION_CONTRACT_VERSION,
    InterpretationPresentationPolicyV01,
    PresentationSlotRole,
    build_interpretation_presentation_v01,
    validate_interpretation_presentation_v01,
)
from src.universe_interpretation_selection import select_universe_interpretation_facts_v01
from tests.test_universe_analysis_change_detection import _pair


def _presentation(*, field=None, before=None, after=None, mutate=None, policy=None):
    baseline, current = _pair(field=field, before=before, after=after)
    if mutate:
        baseline, current = mutate(baseline, current)
    assessment = assess_snapshot_comparability(baseline, current)
    changes = detect_universe_changes(baseline, current, assessment)
    case_file = build_universe_interpretation_input_v01(baseline, current, assessment, changes)
    selection = select_universe_interpretation_facts_v01(case_file)
    presentation = build_interpretation_presentation_v01(
        selection, policy or InterpretationPresentationPolicyV01(),
    )
    return selection, presentation


def test_normal_contract_has_stable_sections_metadata_and_serialization():
    selection, presentation = _presentation()
    assert presentation.metadata.current_snapshot_id == selection.current_snapshot_id
    assert [section.name for section in presentation.sections] == [section.name for section in selection.sections]
    assert presentation.to_dict()["metadata"]["contract_version"] == PRESENTATION_CONTRACT_VERSION
    assert build_interpretation_presentation_v01(selection) == presentation
    assert build_interpretation_presentation_v01(selection).to_dict() == presentation.to_dict()


def test_no_change_interval_has_no_change_slots_but_current_sections_remain():
    _, presentation = _presentation()
    assert presentation.section("what_changed").slots == ()
    assert presentation.section("leaders").slots
    assert presentation.section("laggards").slots
    assert presentation.section("caveats").slots


def test_current_read_attention_leader_and_laggard_roles_are_renderer_neutral():
    _, presentation = _presentation()
    slots = presentation.section("current_read").slots
    assert slots[0].role == PresentationSlotRole.PRIMARY_FACT
    assert all(slot.role in {PresentationSlotRole.PRIMARY_FACT, PresentationSlotRole.SUPPORTING_FACT,
                             PresentationSlotRole.CAVEAT} for slot in slots)
    assert all(not isinstance(value.value, dict) for slot in slots
               for value in slot.item.display_values)


def test_attention_change_leader_and_laggard_mapping():
    _, presentation = _presentation(field="technical_profile", before="Weak", after="Strong")
    assert all(slot.role == PresentationSlotRole.MEMBER_CARD
               for slot in presentation.section("deserves_attention").slots)
    changed = presentation.section("what_changed").slots
    assert changed and all(slot.role == PresentationSlotRole.CHANGE_CARD for slot in changed)
    assert all(slot.item.display_label_key == "change_event_type" for slot in changed)
    assert all(slot.role == PresentationSlotRole.LEADER_ROW for slot in presentation.section("leaders").slots)
    assert all(slot.role == PresentationSlotRole.LAGGARD_ROW for slot in presentation.section("laggards").slots)


def test_membership_additions_removals_and_limited_caveats_map_separately():
    def mutate(baseline, current):
        added = replace(current.members[-1], matching_key="ticker:NEW", member_snapshot_id="new-member",
                        ticker_or_identifier="NEW", company_name="New Company")
        return baseline, replace(current, universe_version=4, membership_digest="changed",
                                 members=current.members[:-1] + (added,))
    _, presentation = _presentation(mutate=mutate)
    assert presentation.metadata.comparison_status == Comparability.LIMITED.value
    roles = [slot.role for slot in presentation.section("membership_changes").slots]
    assert roles == [PresentationSlotRole.MEMBERSHIP_ADDITION, PresentationSlotRole.MEMBERSHIP_REMOVAL]
    assert all(slot.role == PresentationSlotRole.CAVEAT for slot in presentation.section("caveats").slots)


def test_not_comparable_never_reintroduces_interval_change_items():
    def mutate(baseline, current): return baseline, replace(current, universe_id="other")
    _, presentation = _presentation(mutate=mutate)
    assert presentation.metadata.comparison_status == Comparability.NOT_COMPARABLE.value
    assert presentation.section("what_changed").slots == ()
    assert presentation.section("leaders").slots
    assert presentation.section("caveats").slots


def test_section_limits_and_overflow_are_explicit_and_ordered():
    policy = InterpretationPresentationPolicyV01(
        current_read_limit=1, deserves_attention_limit=1, what_changed_limit=0,
        leaders_limit=1, laggards_limit=1, membership_changes_limit=0, caveats_limit=1,
    )
    selection, presentation = _presentation(
        field="technical_profile", before="Weak", after="Strong", policy=policy,
    )
    for section in presentation.sections:
        assert section.presented_item_count <= section.item_limit
        assert section.omitted_item_count == section.selected_item_count - section.presented_item_count
        assert len(section.omitted_source_ids) == section.omitted_item_count
    leaders = presentation.section("leaders")
    assert leaders.omitted_item_count == len(selection.section("leaders").items) - 1
    assert leaders.overflow_reason_code == "presentation_capacity_exceeded"
    changed = presentation.section("what_changed")
    assert changed.presented_item_count == 0 and changed.omitted_item_count > 0


def test_traceability_stable_ids_no_duplicates_and_evidence_preservation():
    selection, presentation = _presentation(field="momentum", before="neutral", after="positive")
    source = {item.selected_item_id: item for section in selection.sections for item in section.items}
    section_ids, slot_ids, item_ids = set(), set(), set()
    for section in presentation.sections:
        assert section.section_id not in section_ids; section_ids.add(section.section_id)
        seen_sources = set()
        for index, slot in enumerate(section.slots):
            assert slot.slot_index == index and slot.slot_id not in slot_ids; slot_ids.add(slot.slot_id)
            assert slot.item.presentation_item_id not in item_ids; item_ids.add(slot.item.presentation_item_id)
            selected = source[slot.item.source_selected_item_id]
            assert slot.item.source_identity == selected.source_id
            assert slot.item.evidence_refs == tuple(sorted(set(selected.evidence_refs)))
            assert selected.selected_item_id not in seen_sources; seen_sources.add(selected.selected_item_id)


def test_invalid_selected_reference_is_rejected():
    selection, presentation = _presentation()
    section = presentation.section("leaders")
    slot = section.slots[0]
    bad_item = replace(slot.item, source_selected_item_id="missing")
    bad_slot = replace(slot, item=bad_item)
    bad_section = replace(section, slots=(bad_slot,) + section.slots[1:])
    bad = replace(presentation, sections=tuple(
        bad_section if item.name == section.name else item for item in presentation.sections
    ))
    with pytest.raises(ValueError, match="unknown selected"):
        validate_interpretation_presentation_v01(selection, bad)


def test_unsupported_source_type_is_rejected():
    selection, _ = _presentation()
    source_section = selection.section("leaders")
    bad_source = replace(source_section.items[0], source_type="unsupported")
    bad_section = replace(source_section, items=(bad_source,) + source_section.items[1:])
    bad_selection = replace(selection, sections=tuple(
        bad_section if item.name == source_section.name else item for item in selection.sections
    ))
    with pytest.raises(ValueError, match="Unsupported selected source type"):
        build_interpretation_presentation_v01(bad_selection)


def test_unsupported_version_and_negative_limit_fail_explicitly():
    selection, _ = _presentation()
    with pytest.raises(ValueError, match="Unsupported presentation"):
        build_interpretation_presentation_v01(
            selection, replace(InterpretationPresentationPolicyV01(), contract_version="future"),
        )
    with pytest.raises(ValueError, match="non-negative"):
        build_interpretation_presentation_v01(
            selection, replace(InterpretationPresentationPolicyV01(), leaders_limit=-1),
        )
