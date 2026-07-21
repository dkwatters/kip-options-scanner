"""Pure Streamlit-facing view model over deterministic presentation slots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.universe_analysis_presentation_service import UniverseAnalysisPresentationBundleV01


SECTION_TITLES = {
    "current_read": "Current Read",
    "deserves_attention": "What Deserves Attention",
    "what_changed": "What Changed",
    "leaders": "Leaders",
    "laggards": "Laggards",
    "membership_changes": "Membership Changes",
    "caveats": "Caveats",
}

DISPLAY_LABELS = {
    "attention_candidate": "Attention candidate",
    "change_event_type": "Change event",
    "leader_position": "Leader position",
    "laggard_position": "Laggard position",
    "member_added": "Member added",
    "member_removed": "Member removed",
    "caveat_code": "Caveat",
}

CAVEAT_LABELS = {
    "comparison_not_fully_comparable": "Comparison is limited",
    "members_unavailable": "One or more universe members are unavailable",
    "membership_changed": "Universe membership changed",
    "universe_version_changed": "Universe definition version changed",
    "universe_id_changed": "Snapshots refer to different universes",
    "analytical_behavior_version_changed": "Analysis behavior version changed",
    "rank:comparison_not_allowed": "Rank comparison is unavailable",
    "extension_positioning:version_incompatible": "Extension comparison is unavailable",
    "data_freshness:unknown": "Observation freshness is unknown",
    "data_freshness:stale": "Observation data is stale",
    "data_freshness:mixed": "Observation freshness is mixed",
}


@dataclass(frozen=True, slots=True)
class UniverseAnalysisPresentationRowV01:
    presentation_item_id: str
    section: str
    slot_role: str
    label: str
    value: str
    company_name: str | None
    ticker: str | None
    matching_key: str | None
    event_type: str | None
    previous_value: Any
    current_value: Any
    direction: str | None
    materiality: str | None
    priority_tier: int | None
    observation_interval: tuple[str, str] | None
    evidence_refs: tuple[str, ...]
    source_identity: str


@dataclass(frozen=True, slots=True)
class UniverseAnalysisPresentationSectionV01:
    key: str
    title: str
    rows: tuple[UniverseAnalysisPresentationRowV01, ...]
    selected_item_count: int
    presented_item_count: int
    omitted_item_count: int
    omitted_source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniverseAnalysisStreamlitViewModelV01:
    sections: tuple[UniverseAnalysisPresentationSectionV01, ...]
    comparison_status: str
    current_snapshot_id: str
    baseline_snapshot_id: str | None
    current_observation_at: str | None
    baseline_observation_at: str | None
    universe_id: str
    universe_version: int
    analysis_run_id: str
    unavailable_count: int

    def section(self, key: str) -> UniverseAnalysisPresentationSectionV01:
        return next(section for section in self.sections if section.key == key)


def build_universe_analysis_streamlit_view_model(
    bundle: UniverseAnalysisPresentationBundleV01,
) -> UniverseAnalysisStreamlitViewModelV01:
    """Join presentation references to their exact deterministic source facts."""
    if not all((bundle.current_snapshot, bundle.baseline_snapshot, bundle.comparison,
                bundle.changes, bundle.interpretation_input, bundle.presentation)):
        raise ValueError("A ready deterministic presentation bundle is required.")
    current = bundle.current_snapshot
    baseline = bundle.baseline_snapshot
    events = {event.event_id: event for event in bundle.changes.atomic_events}
    members = {
        member.member_snapshot_id: member
        for snapshot in (baseline, current) for member in snapshot.members
    }
    sections = []
    for source_section in bundle.presentation.sections:
        rows = tuple(_row(slot.item, members, events) for slot in source_section.slots)
        sections.append(UniverseAnalysisPresentationSectionV01(
            source_section.name.value, SECTION_TITLES[source_section.name.value], rows,
            source_section.selected_item_count, source_section.presented_item_count,
            source_section.omitted_item_count, source_section.omitted_source_ids,
        ))
    return UniverseAnalysisStreamlitViewModelV01(
        tuple(sections), bundle.comparison.comparability.value,
        current.snapshot_id, baseline.snapshot_id,
        current.observation_as_of or current.completed_at,
        baseline.observation_as_of or baseline.completed_at,
        current.universe_id, current.universe_version, current.analysis_run_id,
        current.unavailable_count,
    )


def resolve_display_label(key: str) -> str:
    return DISPLAY_LABELS.get(key, key.replace("_", " ").strip().capitalize() or "Fact")


def resolve_caveat_label(code: str) -> str:
    return CAVEAT_LABELS.get(code, code.replace("_", " ").replace(":", ": ").strip().capitalize())


def _row(item, members, events):
    member = members.get(item.member_snapshot_id)
    event = events.get(item.event_id)
    values = {value.key: value.value for value in item.display_values}
    if item.display_label_key == "caveat_code":
        value = resolve_caveat_label(str(values.get("caveat_code") or item.source_identity))
    elif event is not None:
        value = f"{event.previous_value} → {event.current_value}"
    elif member is not None and member.derived_observation is not None:
        value = member.derived_observation.technical_profile
    else:
        value = str(next(iter(values.values()), item.source_identity))
    event_type = event.event_type if event else {
        "membership_addition": "membership_added",
        "membership_removal": "membership_removed",
    }.get(item.source_type)
    return UniverseAnalysisPresentationRowV01(
        item.presentation_item_id, item.section.value, item.slot_role.value,
        resolve_display_label(item.display_label_key), value,
        member.company_name if member else (event.company_name if event else None),
        member.ticker_or_identifier if member else (event.ticker if event else None),
        member.matching_key if member else (event.matching_key if event else None),
        event_type,
        event.previous_value if event else None, event.current_value if event else None,
        event.direction if event else None, event.materiality if event else None,
        item.source_priority, event.occurred_between if event else None,
        item.evidence_refs, item.source_identity,
    )
