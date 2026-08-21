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
    material_change_count: int
    attention_candidate_count: int
    membership_change_count: int

    def section(self, key: str) -> UniverseAnalysisPresentationSectionV01:
        return next(section for section in self.sections if section.key == key)


@dataclass(frozen=True, slots=True)
class ConsolidatedCompanyComparisonRowV01:
    """One display-only comparison row enriched by presentation-contract facts."""

    rank: int | None
    company: str
    ticker: str
    technical_profile: str
    trend: str
    momentum: str
    positioning: str
    volatility: str
    key_signal: str
    analysis_status: str
    intelligence: tuple[str, ...]
    attention_priority: int | None
    change_status: str
    change_type: str | None
    change_summary: str | None
    membership: str
    comparison_limitation: str | None
    evidence_refs: tuple[str, ...]
    source_identities: tuple[str, ...]
    matching_key: str | None
    source_row: dict[str, Any] | None


INTELLIGENCE_FILTERS = ("Leader", "Laggard", "Attention")
MEMBERSHIP_FILTERS = ("Added", "Removed")


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
        current.unavailable_count, bundle.changes.counts.total_events,
        len(bundle.interpretation_input.attention_candidates),
        bundle.changes.counts.membership_events,
    )


def resolve_display_label(key: str) -> str:
    return DISPLAY_LABELS.get(key, key.replace("_", " ").strip().capitalize() or "Fact")


def resolve_caveat_label(code: str) -> str:
    return CAVEAT_LABELS.get(code, code.replace("_", " ").replace(":", ": ").strip().capitalize())


def build_consolidated_company_comparison_rows(
    ranked_rows: list[dict[str, Any]],
    view: UniverseAnalysisStreamlitViewModelV01 | None,
    *,
    first_observation: bool = False,
) -> tuple[ConsolidatedCompanyComparisonRowV01, ...]:
    """Project deterministic presentation facts onto ranked rows without reordering them."""
    annotations: dict[str, list[UniverseAnalysisPresentationRowV01]] = {}
    removed: list[UniverseAnalysisPresentationRowV01] = []
    if view is not None:
        for section in view.sections:
            if section.key == "current_read":
                continue  # This section deliberately repeats facts from the specific sections.
            for item in section.rows:
                identity = _identity(item.ticker, item.matching_key)
                if identity:
                    annotations.setdefault(identity, []).append(item)
                if section.key == "membership_changes" and item.event_type == "membership_removed":
                    removed.append(item)

    result = []
    present_identities = set()
    for source in ranked_rows:
        identity = _identity(source.get("ticker"), source.get("matching_key"))
        present_identities.add(identity)
        result.append(_consolidated_row(source, annotations.get(identity, ()), view, first_observation))

    # Removed members have no current rank. Keep them after the authoritative ranked population.
    for item in removed:
        identity = _identity(item.ticker, item.matching_key)
        if identity in present_identities:
            continue
        result.append(_removed_row(item, view))
    return tuple(result)


def filter_consolidated_company_rows(
    rows: tuple[ConsolidatedCompanyComparisonRowV01, ...],
    *,
    intelligence: tuple[str, ...] = (),
    changed: bool = False,
    memberships: tuple[str, ...] = (),
    profiles: tuple[str, ...] = (),
) -> tuple[ConsolidatedCompanyComparisonRowV01, ...]:
    """Subset rows only; input order and rank values are never changed."""
    return tuple(row for row in rows
                 if (not intelligence or any(label in row.intelligence for label in intelligence))
                 and (not changed or row.change_type is not None)
                 and (not memberships or row.membership in memberships)
                 and (not profiles or row.technical_profile in profiles))


def _consolidated_row(source, facts, view, first_observation):
    sections = {fact.section for fact in facts}
    intelligence = tuple(label for key, label in (
        ("leaders", "Leader"), ("laggards", "Laggard"),
        ("deserves_attention", "Attention"),
    ) if key in sections)
    membership_fact = next((fact for fact in facts if fact.event_type == "membership_added"), None)
    changes = tuple(fact for fact in facts
                    if fact.section == "what_changed" and fact.event_type not in {
                        "membership_added", "membership_removed",
                    })
    primary_change = changes[0] if changes else None
    if membership_fact:
        change_status = "No prior comparable member state"
    elif first_observation:
        change_status = "First observation"
    elif view is None:
        change_status = "No baseline"
    elif view.comparison_status == "not_comparable":
        change_status = "Not comparable"
    elif primary_change:
        change_status = _change_status(primary_change)
    else:
        change_status = "No material change"
    evidence = tuple(sorted({ref for fact in facts for ref in fact.evidence_refs}))
    return ConsolidatedCompanyComparisonRowV01(
        source.get("rank"), str(source.get("company_name") or "Unavailable"),
        str(source.get("ticker") or "Unavailable"),
        str(source.get("technical_profile") or "Unavailable"),
        str(source.get("trend_label") or "Unavailable"),
        str(source.get("momentum_label") or "Unavailable"),
        str(source.get("extension_label") or "Unavailable"),
        str(source.get("volatility_label") or "Unavailable"),
        str(source.get("key_signal") or "Unavailable"), "Analyzed", intelligence,
        min((fact.priority_tier for fact in facts if fact.section == "deserves_attention"
             and fact.priority_tier is not None), default=None),
        change_status, primary_change.event_type if primary_change else None,
        primary_change.value if primary_change else None,
        "Added" if membership_fact else "Existing",
        _comparison_limitation(view, membership_fact is not None), evidence,
        tuple(sorted({fact.source_identity for fact in facts})),
        next((fact.matching_key for fact in facts if fact.matching_key), None), source,
    )


def _removed_row(item, view):
    return ConsolidatedCompanyComparisonRowV01(
        None, item.company_name or "Unavailable", item.ticker or "Unavailable",
        "Historical member", "—", "—", "—", "—", "Removed from current universe",
        "Removed", (), None, "No current member state", None, None, "Removed",
        _comparison_limitation(view, True), item.evidence_refs, (item.source_identity,),
        item.matching_key, None,
    )


def _identity(ticker, matching_key):
    ticker_value = str(ticker or "").strip().upper()
    return f"ticker:{ticker_value}" if ticker_value else str(matching_key or "").strip().casefold()


def _change_status(fact):
    direction = str(fact.direction or "").casefold()
    if direction == "improved":
        return "Improved"
    if direction == "deteriorated":
        return "Weakened"
    event = str(fact.event_type or "").replace("_", " ").strip()
    return event.capitalize() if event else "Changed"


def _comparison_limitation(view, membership_changed):
    if view is None:
        return "No baseline"
    if membership_changed:
        return "Membership state only; no prior comparable current-member state"
    if view.comparison_status == "limited_comparability":
        return "Limited comparison"
    if view.comparison_status == "not_comparable":
        return "Not comparable"
    return None


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
