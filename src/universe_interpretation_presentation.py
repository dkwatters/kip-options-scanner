"""Renderer-neutral deterministic presentation mapping for interpretation selections."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.universe_analysis_snapshot_comparison import Comparability
from src.universe_interpretation_selection import (
    InterpretationSelectedItemV01,
    InterpretationSelectionResultV01,
    SelectionReason,
    SelectionSectionName,
)


PRESENTATION_CONTRACT_VERSION = "universe-interpretation-presentation-v0.1"
PRESENTATION_SCHEMA_VERSION = "universe_interpretation_presentation.v0.1"
PRESENTATION_SECTION_SCHEMA_VERSION = "universe_interpretation_presentation_section.v0.1"
PRESENTATION_SLOT_SCHEMA_VERSION = "universe_interpretation_presentation_slot.v0.1"
PRESENTATION_ITEM_SCHEMA_VERSION = "universe_interpretation_presentation_item.v0.1"


class PresentationSlotRole(StrEnum):
    PRIMARY_FACT = "primary_fact"
    SUPPORTING_FACT = "supporting_fact"
    MEMBER_CARD = "member_card"
    CHANGE_CARD = "change_card"
    LEADER_ROW = "leader_row"
    LAGGARD_ROW = "laggard_row"
    MEMBERSHIP_ADDITION = "membership_addition"
    MEMBERSHIP_REMOVAL = "membership_removal"
    CAVEAT = "caveat"


@dataclass(frozen=True, slots=True)
class InterpretationPresentationPolicyV01:
    contract_version: str = PRESENTATION_CONTRACT_VERSION
    current_read_limit: int = 3
    deserves_attention_limit: int = 4
    what_changed_limit: int = 5
    leaders_limit: int = 3
    laggards_limit: int = 3
    membership_changes_limit: int = 6
    caveats_limit: int = 6
    current_read_primary_limit: int = 1
    current_read_caveat_limit: int = 1


@dataclass(frozen=True, slots=True)
class PresentationDisplayValueV01:
    key: str
    value: str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class InterpretationPresentationItemV01:
    schema_version: str
    presentation_item_id: str
    section: SelectionSectionName
    slot_role: PresentationSlotRole
    slot_index: int
    source_selected_item_id: str
    source_identity: str
    source_type: str
    member_snapshot_id: str | None
    event_id: str | None
    selection_reason_code: str
    source_priority: int | None
    display_label_key: str
    display_values: tuple[PresentationDisplayValueV01, ...]
    evidence_refs: tuple[str, ...]
    ordering_key: str


@dataclass(frozen=True, slots=True)
class InterpretationPresentationSlotV01:
    schema_version: str
    slot_id: str
    role: PresentationSlotRole
    slot_index: int
    item: InterpretationPresentationItemV01


@dataclass(frozen=True, slots=True)
class InterpretationPresentationSectionV01:
    schema_version: str
    section_id: str
    name: SelectionSectionName
    item_limit: int
    selected_item_count: int
    presented_item_count: int
    omitted_item_count: int
    omitted_source_ids: tuple[str, ...]
    overflow_reason_code: str | None
    slots: tuple[InterpretationPresentationSlotV01, ...]


@dataclass(frozen=True, slots=True)
class InterpretationPresentationMetadataV01:
    contract_version: str
    universe_id: str
    current_snapshot_id: str
    comparison_status: str
    source_policy_version: str


@dataclass(frozen=True, slots=True)
class InterpretationPresentationContractV01:
    schema_version: str
    contract_id: str
    metadata: InterpretationPresentationMetadataV01
    sections: tuple[InterpretationPresentationSectionV01, ...]

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))

    def section(self, name: SelectionSectionName | str) -> InterpretationPresentationSectionV01:
        target = SelectionSectionName(name)
        return next(section for section in self.sections if section.name == target)


DEFAULT_PRESENTATION_POLICY_V01 = InterpretationPresentationPolicyV01()
_SECTION_ORDER = tuple(SelectionSectionName)
_SECTION_LIMIT_ATTRIBUTE = {
    SelectionSectionName.CURRENT_READ: "current_read_limit",
    SelectionSectionName.DESERVES_ATTENTION: "deserves_attention_limit",
    SelectionSectionName.WHAT_CHANGED: "what_changed_limit",
    SelectionSectionName.LEADERS: "leaders_limit",
    SelectionSectionName.LAGGARDS: "laggards_limit",
    SelectionSectionName.MEMBERSHIP_CHANGES: "membership_changes_limit",
    SelectionSectionName.CAVEATS: "caveats_limit",
}
_SUPPORTED_SOURCE_TYPES = {
    "attention_candidate", "change_event", "leader", "laggard",
    "membership_addition", "membership_removal", "caveat",
}


def build_interpretation_presentation_v01(
    selection: InterpretationSelectionResultV01,
    policy: InterpretationPresentationPolicyV01 = DEFAULT_PRESENTATION_POLICY_V01,
) -> InterpretationPresentationContractV01:
    """Map selected references into bounded renderer-neutral slots."""
    _validate_policy(policy)
    source_sections = {section.name: section for section in selection.sections}
    if tuple(source_sections) != _SECTION_ORDER:
        raise ValueError("Selection result has unsupported or incorrectly ordered sections.")
    contract_id = _uuid(
        f"contract:{policy.contract_version}:{selection.current_snapshot_id}:{selection.policy_version}"
    )
    sections = tuple(
        _build_section(selection, source_sections[name], policy, contract_id)
        for name in _SECTION_ORDER
    )
    contract = InterpretationPresentationContractV01(
        PRESENTATION_SCHEMA_VERSION, contract_id,
        InterpretationPresentationMetadataV01(
            policy.contract_version, selection.universe_id, selection.current_snapshot_id,
            selection.comparison_status, selection.policy_version,
        ),
        sections,
    )
    validate_interpretation_presentation_v01(selection, contract, policy)
    return contract


def validate_interpretation_presentation_v01(
    selection: InterpretationSelectionResultV01,
    presentation: InterpretationPresentationContractV01,
    policy: InterpretationPresentationPolicyV01 = DEFAULT_PRESENTATION_POLICY_V01,
) -> None:
    """Validate exact traceability and bounded deterministic layout."""
    _validate_policy(policy)
    if presentation.schema_version != PRESENTATION_SCHEMA_VERSION:
        raise ValueError("Unsupported presentation schema version.")
    if presentation.metadata.contract_version != policy.contract_version:
        raise ValueError("Presentation and policy versions disagree.")
    if (presentation.metadata.universe_id, presentation.metadata.current_snapshot_id,
        presentation.metadata.comparison_status, presentation.metadata.source_policy_version) != (
        selection.universe_id, selection.current_snapshot_id,
        selection.comparison_status, selection.policy_version,
    ):
        raise ValueError("Presentation metadata does not match its selection source.")
    if tuple(section.name for section in presentation.sections) != _SECTION_ORDER:
        raise ValueError("Presentation sections are missing, unsupported, or incorrectly ordered.")
    selected_by_section = {
        section.name: {item.selected_item_id: item for item in section.items}
        for section in selection.sections
    }
    section_ids, slot_ids, item_ids = set(), set(), set()
    for section in presentation.sections:
        if section.section_id in section_ids: raise ValueError("Duplicate presentation section ID.")
        section_ids.add(section.section_id)
        selected = selected_by_section[section.name]
        if section.selected_item_count != len(selected): raise ValueError("Selected-item count is invalid.")
        if section.presented_item_count != len(section.slots): raise ValueError("Presented-item count is invalid.")
        if section.omitted_item_count != section.selected_item_count - section.presented_item_count:
            raise ValueError("Overflow accounting is invalid.")
        if section.presented_item_count > section.item_limit: raise ValueError("Section limit exceeded.")
        presented_sources = []
        role_counts: dict[PresentationSlotRole, int] = {}
        for expected_index, slot in enumerate(section.slots):
            if slot.slot_id in slot_ids: raise ValueError("Duplicate presentation slot ID.")
            slot_ids.add(slot.slot_id)
            if slot.slot_index != expected_index: raise ValueError("Slot ordering is invalid.")
            item = slot.item
            if item.presentation_item_id in item_ids: raise ValueError("Duplicate presentation item ID.")
            item_ids.add(item.presentation_item_id)
            if item.slot_index != slot.slot_index or item.slot_role != slot.role:
                raise ValueError("Presentation item and slot disagree.")
            source = selected.get(item.source_selected_item_id)
            if source is None: raise ValueError("Presentation item references an unknown selected item.")
            _validate_trace(item, source, section.name)
            presented_sources.append(source.source_id)
            role_counts[slot.role] = role_counts.get(slot.role, 0) + 1
        if len(presented_sources) != len(set(presented_sources)):
            raise ValueError("A selected source appears more than once in a section.")
        omitted_expected = tuple(item.source_id for item in selection.section(section.name).items
                                 if item.source_id not in set(presented_sources))
        if section.omitted_source_ids != omitted_expected:
            raise ValueError("Omitted source identities are invalid.")
        if bool(section.omitted_item_count) != bool(section.overflow_reason_code):
            raise ValueError("Overflow reason does not match overflow count.")
        if section.name == SelectionSectionName.CURRENT_READ:
            if role_counts.get(PresentationSlotRole.PRIMARY_FACT, 0) > policy.current_read_primary_limit:
                raise ValueError("Current Read primary role limit exceeded.")
            if role_counts.get(PresentationSlotRole.CAVEAT, 0) > policy.current_read_caveat_limit:
                raise ValueError("Current Read caveat role limit exceeded.")
    if selection.comparison_status == Comparability.NOT_COMPARABLE.value:
        if presentation.section(SelectionSectionName.WHAT_CHANGED).slots:
            raise ValueError("Not-comparable selection cannot present interval changes.")


def _build_section(selection, source_section, policy, contract_id):
    limit = getattr(policy, _SECTION_LIMIT_ATTRIBUTE[source_section.name])
    accepted, omitted = [], []
    role_counts: dict[PresentationSlotRole, int] = {}
    for source in source_section.items:
        role = _role(source_section.name, source, len(accepted))
        role_limit = _role_limit(source_section.name, role, policy)
        if len(accepted) >= limit or role_counts.get(role, 0) >= role_limit:
            omitted.append(source.source_id); continue
        accepted.append((source, role)); role_counts[role] = role_counts.get(role, 0) + 1
    slots = tuple(_slot(selection, source_section.name, source, role, index, contract_id)
                  for index, (source, role) in enumerate(accepted))
    section_id = _uuid(f"section:{contract_id}:{source_section.name.value}")
    return InterpretationPresentationSectionV01(
        PRESENTATION_SECTION_SCHEMA_VERSION, section_id, source_section.name, limit,
        len(source_section.items), len(slots), len(omitted), tuple(omitted),
        "presentation_capacity_exceeded" if omitted else None, slots,
    )


def _slot(selection, section, source, role, index, contract_id):
    slot_id = _uuid(f"slot:{contract_id}:{section.value}:{role.value}:{index}:{source.selected_item_id}")
    label, values = _display(source, section)
    item_id = _uuid(f"item:{slot_id}:{source.selected_item_id}")
    item = InterpretationPresentationItemV01(
        PRESENTATION_ITEM_SCHEMA_VERSION, item_id, section, role, index,
        source.selected_item_id, source.source_id, source.source_type,
        source.member_snapshot_id, source.source_event_id, source.selection_reason.value,
        source.original_priority_tier, label, values, tuple(sorted(set(source.evidence_refs))),
        f"{index:04d}:{source.ordering_key}:{source.selected_item_id}",
    )
    return InterpretationPresentationSlotV01(PRESENTATION_SLOT_SCHEMA_VERSION, slot_id, role, index, item)


def _role(section, source, accepted_count):
    if section == SelectionSectionName.CURRENT_READ:
        if source.source_type == "caveat": return PresentationSlotRole.CAVEAT
        return PresentationSlotRole.PRIMARY_FACT if accepted_count == 0 else PresentationSlotRole.SUPPORTING_FACT
    return {
        SelectionSectionName.DESERVES_ATTENTION: PresentationSlotRole.MEMBER_CARD,
        SelectionSectionName.WHAT_CHANGED: PresentationSlotRole.CHANGE_CARD,
        SelectionSectionName.LEADERS: PresentationSlotRole.LEADER_ROW,
        SelectionSectionName.LAGGARDS: PresentationSlotRole.LAGGARD_ROW,
        SelectionSectionName.CAVEATS: PresentationSlotRole.CAVEAT,
    }.get(section) or (
        PresentationSlotRole.MEMBERSHIP_ADDITION
        if source.source_type == "membership_addition" else PresentationSlotRole.MEMBERSHIP_REMOVAL
    )


def _role_limit(section, role, policy):
    if section == SelectionSectionName.CURRENT_READ and role == PresentationSlotRole.PRIMARY_FACT:
        return policy.current_read_primary_limit
    if section == SelectionSectionName.CURRENT_READ and role == PresentationSlotRole.CAVEAT:
        return policy.current_read_caveat_limit
    return getattr(policy, _SECTION_LIMIT_ATTRIBUTE[section])


def _display(source, section):
    if source.source_type == "change_event":
        return "change_event_type", _values(event_id=source.source_event_id, source_identity=source.source_id)
    if source.source_type == "leader":
        return "leader_position", _values(position=(source.source_order or 0) + 1,
                                           member_id=source.member_snapshot_id)
    if source.source_type == "laggard":
        return "laggard_position", _values(position=(source.source_order or 0) + 1,
                                            member_id=source.member_snapshot_id)
    if source.source_type == "membership_addition":
        return "member_added", _values(member_id=source.member_snapshot_id)
    if source.source_type == "membership_removal":
        return "member_removed", _values(member_id=source.member_snapshot_id)
    if source.source_type == "caveat":
        return "caveat_code", _values(caveat_code=source.source_id)
    return "attention_candidate", _values(member_id=source.member_snapshot_id,
                                           matching_key=source.matching_key,
                                           selection_reason=source.selection_reason.value)


def _values(**values):
    return tuple(PresentationDisplayValueV01(key, value) for key, value in sorted(values.items()))


def _validate_trace(item, source: InterpretationSelectedItemV01, section):
    if source.source_type not in _SUPPORTED_SOURCE_TYPES: raise ValueError("Unsupported selected source type.")
    if source.section != section or item.section != section: raise ValueError("Source section is incompatible.")
    if (item.source_identity, item.source_type, item.member_snapshot_id, item.event_id,
        item.selection_reason_code, item.source_priority) != (
        source.source_id, source.source_type, source.member_snapshot_id, source.source_event_id,
        source.selection_reason.value, source.original_priority_tier,
    ): raise ValueError("Presentation item does not preserve selected source identity.")
    if item.evidence_refs != tuple(sorted(set(source.evidence_refs))):
        raise ValueError("Presentation evidence does not preserve selected evidence.")


def _validate_policy(policy):
    if policy.contract_version != PRESENTATION_CONTRACT_VERSION:
        raise ValueError(f"Unsupported presentation contract version: {policy.contract_version!r}.")
    limits = tuple(getattr(policy, name) for name in _SECTION_LIMIT_ATTRIBUTE.values()) + (
        policy.current_read_primary_limit, policy.current_read_caveat_limit,
    )
    if any(not isinstance(value, int) or value < 0 for value in limits):
        raise ValueError("Presentation limits must be non-negative integers.")


def _uuid(value): return str(uuid5(NAMESPACE_URL, f"{PRESENTATION_SCHEMA_VERSION}:{value}"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, tuple): return [_json_safe(item) for item in value]
    if isinstance(value, list): return [_json_safe(item) for item in value]
    if isinstance(value, dict): return {str(key): _json_safe(item) for key, item in value.items()}
    return value
