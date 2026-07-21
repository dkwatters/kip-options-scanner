"""Deterministic case-file contract for future Universe interpretation consumers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.universe_analysis_change_detection import (
    ChangeDetectionCountsV01,
    UniverseChangeDetectionResultV01,
    UniverseChangeEventV01,
)
from src.universe_analysis_contracts import (
    DerivedUniverseAnalysisObservationV1,
    UniverseAnalysisMemberSnapshotV1,
    UniverseAnalysisSnapshotV1,
    UniverseAnalysisSummaryV1,
    UniverseAnalysisVersionManifestV1,
)
from src.universe_analysis_snapshot_comparison import SnapshotComparisonAssessmentV01


INTERPRETATION_INPUT_SCHEMA_VERSION = "universe_interpretation_input.v0.1"


@dataclass(frozen=True, slots=True)
class InterpretationMetadataV01:
    universe_id: str
    universe_version: int
    universe_title: str
    research_question: str
    baseline_snapshot_id: str
    current_snapshot_id: str
    baseline_completed_at: str
    current_completed_at: str
    observation_as_of: str | None
    data_freshness: str
    version_manifest: UniverseAnalysisVersionManifestV1


@dataclass(frozen=True, slots=True)
class InterpretationMemberFactV01:
    member_snapshot_id: str
    matching_key: str
    security_id: str | None
    ticker: str | None
    company_name: str
    membership_order: int
    analysis_status: str
    analysis_status_reason: str
    derived_observation: DerivedUniverseAnalysisObservationV1 | None
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InterpretationAttentionCandidateV01:
    matching_key: str
    member_snapshot_id: str
    ticker: str | None
    company_name: str
    reason_codes: tuple[str, ...]
    event_ids: tuple[str, ...]
    priority_tier: int | None
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniverseInterpretationInputV01:
    schema_version: str
    metadata: InterpretationMetadataV01
    universe_summary: UniverseAnalysisSummaryV1
    comparison_summary: SnapshotComparisonAssessmentV01
    change_summary: ChangeDetectionCountsV01
    priority_events: tuple[UniverseChangeEventV01, ...]
    leaders: tuple[InterpretationMemberFactV01, ...]
    laggards: tuple[InterpretationMemberFactV01, ...]
    additions: tuple[InterpretationMemberFactV01, ...]
    removals: tuple[InterpretationMemberFactV01, ...]
    attention_candidates: tuple[InterpretationAttentionCandidateV01, ...]
    caveats: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-safe representation without deriving new facts."""
        return _json_safe(asdict(self))


def build_universe_interpretation_input_v01(
    baseline: UniverseAnalysisSnapshotV1,
    current: UniverseAnalysisSnapshotV1,
    comparison: SnapshotComparisonAssessmentV01,
    changes: UniverseChangeDetectionResultV01,
    *,
    priority_event_limit: int = 10,
    leader_limit: int = 3,
    laggard_limit: int = 3,
) -> UniverseInterpretationInputV01:
    """Aggregate existing deterministic artifacts into a bounded case file."""
    _validate_inputs(baseline, current, comparison, changes)
    if min(priority_event_limit, leader_limit, laggard_limit) < 0:
        raise ValueError("Interpretation input limits cannot be negative.")

    baseline_by_key = {member.matching_key: member for member in baseline.members}
    current_by_key = {member.matching_key: member for member in current.members}
    ranked = sorted(
        (member for member in current.members if member.derived_observation is not None),
        key=lambda member: (member.derived_observation.rank, member.matching_key),
    )
    leaders = tuple(_member_fact(member) for member in ranked[:leader_limit])
    laggards = tuple(_member_fact(member) for member in sorted(
        ranked, key=lambda member: (-member.derived_observation.rank, member.matching_key),
    )[:laggard_limit])
    additions = tuple(_member_fact(current_by_key[key]) for key in comparison.added_matching_keys)
    removals = tuple(_member_fact(baseline_by_key[key]) for key in comparison.removed_matching_keys)
    priority_events = tuple(sorted(
        changes.atomic_events,
        key=lambda event: (event.priority_tier, event.priority_order_key, event.event_id),
    )[:priority_event_limit])
    attention = _attention_candidates(current, changes)
    caveat_values = [*comparison.reasons, *changes.suppressed_rules_categories]
    if current.data_freshness.value != "fresh":
        caveat_values.append(f"data_freshness:{current.data_freshness.value}")
    if current.unavailable_count:
        caveat_values.append("members_unavailable")
    if comparison.comparability.value != "fully_comparable":
        caveat_values.append("comparison_not_fully_comparable")
    caveats = tuple(sorted(set(caveat_values)))
    evidence = tuple(sorted(set((
        *current.provenance_references,
        *(reference.evidence_id for member in current.members for reference in member.evidence_references),
        *(reference for event in changes.atomic_events for reference in event.evidence_refs),
    ))))
    return UniverseInterpretationInputV01(
        schema_version=INTERPRETATION_INPUT_SCHEMA_VERSION,
        metadata=InterpretationMetadataV01(
            universe_id=current.universe_id,
            universe_version=current.universe_version,
            universe_title=current.universe_title,
            research_question=current.research_question,
            baseline_snapshot_id=baseline.snapshot_id,
            current_snapshot_id=current.snapshot_id,
            baseline_completed_at=baseline.completed_at,
            current_completed_at=current.completed_at,
            observation_as_of=current.observation_as_of,
            data_freshness=current.data_freshness.value,
            version_manifest=current.version_manifest,
        ),
        universe_summary=current.summary,
        comparison_summary=comparison,
        change_summary=changes.counts,
        priority_events=priority_events,
        leaders=leaders,
        laggards=laggards,
        additions=additions,
        removals=removals,
        attention_candidates=attention,
        caveats=caveats,
        evidence_refs=evidence,
    )


def _validate_inputs(baseline, current, comparison, changes) -> None:
    expected = (baseline.snapshot_id, current.snapshot_id)
    if (comparison.baseline_snapshot_id, comparison.current_snapshot_id) != expected:
        raise ValueError("Comparison assessment does not reference the supplied snapshots.")
    if (changes.baseline_snapshot_id, changes.current_snapshot_id) != expected:
        raise ValueError("Change result does not reference the supplied snapshots.")
    if changes.comparison_assessment != comparison:
        raise ValueError("Change result and comparison assessment disagree.")
    if baseline.universe_id != current.universe_id and comparison.comparability.value != "not_comparable":
        raise ValueError("Cross-universe inputs require a not-comparable assessment.")
    if len({member.matching_key for member in current.members}) != len(current.members):
        raise ValueError("Current snapshot contains duplicate stable member identities.")
    event_ids = tuple(event.event_id for event in changes.atomic_events)
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Change result contains duplicate event identifiers.")


def _member_fact(member: UniverseAnalysisMemberSnapshotV1) -> InterpretationMemberFactV01:
    evidence = tuple(sorted(set((
        *member.source_references,
        *(reference.evidence_id for reference in member.evidence_references),
    ))))
    return InterpretationMemberFactV01(
        member.member_snapshot_id, member.matching_key, member.security_id,
        member.ticker_or_identifier, member.company_name, member.membership_order,
        member.analysis_status, member.analysis_status_reason,
        member.derived_observation, evidence,
    )


def _attention_candidates(current, changes):
    member_by_key = {member.matching_key: member for member in current.members}
    event_by_id = {event.event_id: event for event in changes.atomic_events}
    rows = []
    grouped_keys = set()
    for group in sorted(changes.groups, key=lambda item: item.priority_order_key):
        member = member_by_key.get(group.matching_key)
        if member is None:
            continue
        events = tuple(event_by_id[event_id] for event_id in group.event_ids)
        reason_values = {f"event:{event.event_type}" for event in events}
        if group.highest_materiality == "attention":
            reason_values.add("attention_materiality")
        reasons = tuple(sorted(reason_values))
        evidence = tuple(sorted({ref for event in events for ref in event.evidence_refs}))
        rows.append(InterpretationAttentionCandidateV01(
            member.matching_key, member.member_snapshot_id, member.ticker_or_identifier,
            member.company_name, reasons, group.event_ids, group.priority_tier, evidence,
        ))
        grouped_keys.add(member.matching_key)
    for member in sorted(current.members, key=lambda item: (item.membership_order, item.matching_key)):
        if member.analysis_status != "analyzed" and member.matching_key not in grouped_keys:
            rows.append(InterpretationAttentionCandidateV01(
                member.matching_key, member.member_snapshot_id, member.ticker_or_identifier,
                member.company_name, (f"availability:{member.analysis_status}",), (), None,
                tuple(sorted(set(member.source_references))),
            ))
    return tuple(sorted(rows, key=lambda row: (
        row.priority_tier is None, row.priority_tier if row.priority_tier is not None else 999,
        row.matching_key,
    )))


def _json_safe(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
