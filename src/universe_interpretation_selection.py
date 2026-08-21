"""Deterministic editorial selection over a Universe interpretation case file."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.universe_analysis_snapshot_comparison import Comparability
from src.universe_interpretation_input import UniverseInterpretationInputV01


SELECTION_POLICY_VERSION = "universe-interpretation-selection-policy-v0.1"
SELECTION_RESULT_SCHEMA_VERSION = "universe_interpretation_selection_result.v0.1"
SELECTION_SECTION_SCHEMA_VERSION = "universe_interpretation_selection_section.v0.1"
SELECTED_ITEM_SCHEMA_VERSION = "universe_interpretation_selected_item.v0.1"


class SelectionSectionName(StrEnum):
    CURRENT_READ = "current_read"
    DESERVES_ATTENTION = "deserves_attention"
    WHAT_CHANGED = "what_changed"
    LEADERS = "leaders"
    LAGGARDS = "laggards"
    MEMBERSHIP_CHANGES = "membership_changes"
    CAVEATS = "caveats"


class SelectionReason(StrEnum):
    HIGH_PRIORITY_CHANGE = "selected_high_priority_change"
    CURRENT_ATTENTION = "selected_current_attention_candidate"
    CURRENT_LEADER = "selected_current_leader"
    CURRENT_LAGGARD = "selected_current_laggard"
    MEMBERSHIP_ADDITION = "selected_membership_addition"
    MEMBERSHIP_REMOVAL = "selected_membership_removal"
    EXPLICIT_CAVEAT = "selected_explicit_caveat"
    COMPARISON_LIMITATION = "selected_comparison_limitation"


@dataclass(frozen=True, slots=True)
class InterpretationSelectionPolicyV01:
    policy_version: str = SELECTION_POLICY_VERSION
    current_read_limit: int = 3
    deserves_attention_limit: int = 5
    what_changed_limit: int = 8
    leaders_limit: int = 3
    laggards_limit: int = 3
    membership_changes_limit: int = 8
    caveats_limit: int = 8
    maximum_change_priority_tier: int = 8
    suppress_exact_source_reuse: bool = True
    allow_member_cross_section_reuse: bool = True


@dataclass(frozen=True, slots=True)
class InterpretationSelectedItemV01:
    schema_version: str
    selected_item_id: str
    section: SelectionSectionName
    source_type: str
    source_id: str
    source_event_id: str | None
    universe_id: str
    member_snapshot_id: str | None
    matching_key: str | None
    original_priority_tier: int | None
    source_order: int | None
    evidence_refs: tuple[str, ...]
    selection_reason: SelectionReason
    ordering_key: str


@dataclass(frozen=True, slots=True)
class InterpretationSelectionSectionV01:
    schema_version: str
    name: SelectionSectionName
    item_limit: int
    items: tuple[InterpretationSelectedItemV01, ...]


@dataclass(frozen=True, slots=True)
class InterpretationSelectionResultV01:
    schema_version: str
    policy_version: str
    universe_id: str
    current_snapshot_id: str
    comparison_status: str
    sections: tuple[InterpretationSelectionSectionV01, ...]

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))

    def section(self, name: SelectionSectionName | str) -> InterpretationSelectionSectionV01:
        target = SelectionSectionName(name)
        return next(section for section in self.sections if section.name == target)


DEFAULT_INTERPRETATION_SELECTION_POLICY_V01 = InterpretationSelectionPolicyV01()

_SECTION_ORDER = tuple(SelectionSectionName)
_ALLOWED_SOURCE_TYPES = {
    SelectionSectionName.CURRENT_READ: {"attention_candidate", "caveat", "leader", "laggard"},
    SelectionSectionName.DESERVES_ATTENTION: {"attention_candidate"},
    SelectionSectionName.WHAT_CHANGED: {"change_event"},
    SelectionSectionName.LEADERS: {"leader"},
    SelectionSectionName.LAGGARDS: {"laggard"},
    SelectionSectionName.MEMBERSHIP_CHANGES: {"membership_addition", "membership_removal"},
    SelectionSectionName.CAVEATS: {"caveat"},
}


def select_universe_interpretation_facts_v01(
    case_file: UniverseInterpretationInputV01,
    policy: InterpretationSelectionPolicyV01 = DEFAULT_INTERPRETATION_SELECTION_POLICY_V01,
) -> InterpretationSelectionResultV01:
    """Select and order existing case-file facts; never derive new analytical facts."""
    _validate_policy(policy)
    used_exact_sources: set[tuple[str, str]] = set()
    sections = []

    attention = [_attention_item(case_file, item, SelectionSectionName.DESERVES_ATTENTION, index)
                 for index, item in enumerate(case_file.attention_candidates)]
    sections.append(_section(SelectionSectionName.DESERVES_ATTENTION,
                             policy.deserves_attention_limit, attention, used_exact_sources, policy))

    changes = []
    if case_file.comparison_summary.comparability != Comparability.NOT_COMPARABLE:
        changes = [_event_item(case_file, event, index) for index, event in enumerate(case_file.priority_events)
                   if event.priority_tier <= policy.maximum_change_priority_tier]
    sections.append(_section(SelectionSectionName.WHAT_CHANGED, policy.what_changed_limit,
                             changes, used_exact_sources, policy))

    leaders = [_member_item(case_file, item, SelectionSectionName.LEADERS, "leader",
                            SelectionReason.CURRENT_LEADER, index)
               for index, item in enumerate(case_file.leaders)]
    sections.append(_section(SelectionSectionName.LEADERS, policy.leaders_limit,
                             leaders, used_exact_sources, policy))
    laggards = [_member_item(case_file, item, SelectionSectionName.LAGGARDS, "laggard",
                             SelectionReason.CURRENT_LAGGARD, index)
                for index, item in enumerate(case_file.laggards)]
    sections.append(_section(SelectionSectionName.LAGGARDS, policy.laggards_limit,
                             laggards, used_exact_sources, policy))

    membership = [
        *(_member_item(case_file, item, SelectionSectionName.MEMBERSHIP_CHANGES,
                       "membership_addition", SelectionReason.MEMBERSHIP_ADDITION, index)
          for index, item in enumerate(case_file.additions)),
        *(_member_item(case_file, item, SelectionSectionName.MEMBERSHIP_CHANGES,
                       "membership_removal", SelectionReason.MEMBERSHIP_REMOVAL,
                       len(case_file.additions) + index)
          for index, item in enumerate(case_file.removals)),
    ]
    sections.append(_section(SelectionSectionName.MEMBERSHIP_CHANGES,
                             policy.membership_changes_limit, membership, used_exact_sources, policy))

    caveats = [_caveat_item(case_file, caveat, SelectionSectionName.CAVEATS, index)
               for index, caveat in enumerate(case_file.caveats)]
    sections.append(_section(SelectionSectionName.CAVEATS, policy.caveats_limit,
                             caveats, used_exact_sources, policy))

    current_read_candidates = []
    current_read_candidates.extend(
        _attention_item(case_file, item, SelectionSectionName.CURRENT_READ, index)
        for index, item in enumerate(case_file.attention_candidates)
    )
    limitation_offset = len(current_read_candidates)
    current_read_candidates.extend(
        _caveat_item(case_file, caveat, SelectionSectionName.CURRENT_READ, limitation_offset + index)
        for index, caveat in enumerate(case_file.caveats)
        if _is_comparison_limitation(caveat)
    )
    if case_file.leaders:
        current_read_candidates.append(_member_item(
            case_file, case_file.leaders[0], SelectionSectionName.CURRENT_READ, "leader",
            SelectionReason.CURRENT_LEADER, len(current_read_candidates),
        ))
    if case_file.laggards:
        current_read_candidates.append(_member_item(
            case_file, case_file.laggards[0], SelectionSectionName.CURRENT_READ, "laggard",
            SelectionReason.CURRENT_LAGGARD, len(current_read_candidates),
        ))
    sections.append(_section(SelectionSectionName.CURRENT_READ, policy.current_read_limit,
                             current_read_candidates, used_exact_sources, policy,
                             suppress_against_prior=False))

    by_name = {section.name: section for section in sections}
    result = InterpretationSelectionResultV01(
        SELECTION_RESULT_SCHEMA_VERSION, policy.policy_version,
        case_file.metadata.universe_id, case_file.metadata.current_snapshot_id,
        case_file.comparison_summary.comparability.value,
        tuple(by_name[name] for name in _SECTION_ORDER),
    )
    _validate_result(case_file, policy, result)
    return result


def validate_interpretation_selection_result_v01(
    case_file: UniverseInterpretationInputV01,
    result: InterpretationSelectionResultV01,
    policy: InterpretationSelectionPolicyV01 = DEFAULT_INTERPRETATION_SELECTION_POLICY_V01,
) -> None:
    """Validate a selection result against its exact source case file."""
    _validate_policy(policy)
    if result.policy_version != policy.policy_version:
        raise ValueError("Selection result and policy versions disagree.")
    _validate_result(case_file, policy, result)


def _section(name, limit, candidates, used, policy, *, suppress_against_prior=True):
    ordered = sorted(candidates, key=lambda item: item.ordering_key)
    selected = []
    local = set()
    for item in ordered:
        identity = (item.source_type, item.source_id)
        if identity in local:
            continue
        if suppress_against_prior and policy.suppress_exact_source_reuse and identity in used:
            continue
        selected.append(item); local.add(identity); used.add(identity)
        if len(selected) == limit:
            break
    return InterpretationSelectionSectionV01(SELECTION_SECTION_SCHEMA_VERSION, name, limit, tuple(selected))


def _attention_item(case_file, source, section, order):
    return _item(case_file, section, "attention_candidate", source.member_snapshot_id,
                 None, source.member_snapshot_id, source.matching_key, source.priority_tier,
                 order, source.evidence_refs, SelectionReason.CURRENT_ATTENTION)


def _event_item(case_file, source, order):
    return _item(case_file, SelectionSectionName.WHAT_CHANGED, "change_event", source.event_id,
                 source.event_id, source.member_snapshot_id, source.matching_key,
                 source.priority_tier, order, source.evidence_refs, SelectionReason.HIGH_PRIORITY_CHANGE)


def _member_item(case_file, source, section, source_type, reason, order):
    return _item(case_file, section, source_type, source.member_snapshot_id, None,
                 source.member_snapshot_id, source.matching_key, None,
                 order, source.evidence_refs, reason)


def _caveat_item(case_file, source, section, order):
    reason = SelectionReason.COMPARISON_LIMITATION if _is_comparison_limitation(source) else SelectionReason.EXPLICIT_CAVEAT
    return _item(case_file, section, "caveat", source, None, None, None, None, order, (), reason)


def _item(case_file, section, source_type, source_id, event_id, member_id, matching_key,
          priority, source_order, evidence, reason):
    ordering = f"{priority if priority is not None else 99:02d}:{source_order if source_order is not None else 999:04d}:{matching_key or ''}:{source_id}"
    selected_id = str(uuid5(NAMESPACE_URL,
        f"{SELECTED_ITEM_SCHEMA_VERSION}:{case_file.metadata.current_snapshot_id}:{section.value}:{source_type}:{source_id}"))
    return InterpretationSelectedItemV01(
        SELECTED_ITEM_SCHEMA_VERSION, selected_id, section, source_type, source_id,
        event_id, case_file.metadata.universe_id, member_id, matching_key, priority,
        source_order, tuple(sorted(set(evidence))), reason, ordering,
    )


def _is_comparison_limitation(caveat):
    return caveat in {"comparison_not_fully_comparable", "universe_id_changed", "membership_changed",
                      "universe_version_changed", "analytical_behavior_version_changed"} or caveat.startswith("rank:")


def _validate_policy(policy):
    if policy.policy_version != SELECTION_POLICY_VERSION:
        raise ValueError(f"Unsupported interpretation selection policy: {policy.policy_version!r}.")
    limits = (policy.current_read_limit, policy.deserves_attention_limit, policy.what_changed_limit,
              policy.leaders_limit, policy.laggards_limit, policy.membership_changes_limit,
              policy.caveats_limit, policy.maximum_change_priority_tier)
    if any(not isinstance(value, int) or value < 0 for value in limits):
        raise ValueError("Selection policy limits and priority tier must be non-negative integers.")


def _validate_result(case_file, policy, result):
    if tuple(section.name for section in result.sections) != _SECTION_ORDER:
        raise ValueError("Selection result section order or names are invalid.")
    source_index = _source_index(case_file)
    selected_ids = []
    for section in result.sections:
        if len(section.items) > section.item_limit:
            raise ValueError(f"Selection limit exceeded for {section.name.value}.")
        if tuple(section.items) != tuple(sorted(section.items, key=lambda item: item.ordering_key)):
            raise ValueError(f"Selection ordering is invalid for {section.name.value}.")
        local_sources = set()
        for item in section.items:
            if item.source_type not in _ALLOWED_SOURCE_TYPES[section.name]:
                raise ValueError(f"Unsupported source type in {section.name.value}: {item.source_type}.")
            if (item.source_type, item.source_id) not in source_index:
                raise ValueError(f"Selected source does not exist in case file: {item.source_id}.")
            identity = item.source_type, item.source_id
            if identity in local_sources:
                raise ValueError(f"Duplicate source in {section.name.value}: {item.source_id}.")
            local_sources.add(identity); selected_ids.append(item.selected_item_id)
            expected_evidence = source_index[identity]
            if not set(item.evidence_refs) <= expected_evidence:
                raise ValueError(f"Selected evidence is not present on source: {item.source_id}.")
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Selected item identities must be globally unique.")
    if case_file.comparison_summary.comparability == Comparability.NOT_COMPARABLE:
        if result.section(SelectionSectionName.WHAT_CHANGED).items:
            raise ValueError("Not-comparable intervals cannot select change events.")


def _source_index(case_file):
    result = {}
    for item in case_file.attention_candidates:
        result[("attention_candidate", item.member_snapshot_id)] = set(item.evidence_refs)
    for item in case_file.priority_events:
        result[("change_event", item.event_id)] = set(item.evidence_refs)
    for source_type, collection in (("leader", case_file.leaders), ("laggard", case_file.laggards),
                                    ("membership_addition", case_file.additions),
                                    ("membership_removal", case_file.removals)):
        for item in collection:
            result[(source_type, item.member_snapshot_id)] = set(item.evidence_refs)
    for caveat in case_file.caveats:
        result[("caveat", caveat)] = set()
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, tuple): return [_json_safe(item) for item in value]
    if isinstance(value, list): return [_json_safe(item) for item in value]
    if isinstance(value, dict): return {str(key): _json_safe(item) for key, item in value.items()}
    return value
