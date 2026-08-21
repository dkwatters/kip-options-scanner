"""Pure deterministic Universe Analysis change detection v0.1."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.universe_analysis_contracts import UniverseAnalysisMemberSnapshotV1, UniverseAnalysisSnapshotV1
from src.universe_analysis_snapshot_comparison import Comparability, SnapshotComparisonAssessmentV01

CHANGE_EVENT_SCHEMA_VERSION = "universe_change_event.v0.1"
CHANGE_GROUP_SCHEMA_VERSION = "universe_change_group.v0.1"
CHANGE_RESULT_SCHEMA_VERSION = "universe_change_detection_result.v0.1"
UNIVERSE_CHANGE_RULES_VERSION = "universe-change-rules-v0.1"


class ChangeDetectionStatus(StrEnum):
    COMPLETED = "completed"
    NOT_COMPARABLE = "not_comparable"
    NO_CHANGES = "no_changes"
    CHANGES_DETECTED = "changes_detected"


@dataclass(frozen=True, slots=True)
class UniverseChangeEventV01:
    schema_version: str; event_id: str; event_type: str; category: str
    universe_id: str; baseline_universe_version: int; current_universe_version: int
    baseline_snapshot_id: str; current_snapshot_id: str
    member_snapshot_id: str | None; security_id: str | None; matching_key: str
    ticker: str | None; company_name: str; field: str
    previous_value: Any; current_value: Any; direction: str; materiality: str
    priority_tier: int; priority_order_key: str; rule_id: str; rule_version: str
    occurred_between: tuple[str, str]; detected_at: str
    previous_evidence_ref: str; current_evidence_ref: str
    evidence_refs: tuple[str, ...]; status: str = "detected"; confidence: str = "deterministic"


@dataclass(frozen=True, slots=True)
class UniverseChangeGroupV01:
    schema_version: str; group_id: str; universe_id: str
    baseline_snapshot_id: str; current_snapshot_id: str; matching_key: str
    security_id: str | None; ticker: str | None; company_name: str
    event_ids: tuple[str, ...]; highest_materiality: str
    event_categories: tuple[str, ...]; priority_tier: int; priority_order_key: str


@dataclass(frozen=True, slots=True)
class ChangeDetectionCountsV01:
    total_events: int; attention_events: int; notable_events: int; affected_members: int
    membership_events: int; availability_events: int


@dataclass(frozen=True, slots=True)
class UniverseChangeDetectionResultV01:
    schema_version: str; baseline_snapshot_id: str; current_snapshot_id: str
    comparison_assessment: SnapshotComparisonAssessmentV01; status: ChangeDetectionStatus
    atomic_events: tuple[UniverseChangeEventV01, ...]; groups: tuple[UniverseChangeGroupV01, ...]
    suppressed_rules_categories: tuple[str, ...]; rule_version: str; detected_at: str
    counts: ChangeDetectionCountsV01


PROFILE_ORDER = {"weak": 0, "mixed": 1, "constructive": 2, "strong": 3}
TREND_DIRECTION = {
    ("mixed", "bullish_alignment"): "improved", ("bullish_alignment", "mixed"): "deteriorated",
    ("deteriorating", "bearish_alignment"): "deteriorated",
}
MOMENTUM_ORDER = {"negative": 0, "neutral": 1, "positive": 2}
MOMENTUM_SPECIAL = {
    ("positive", "overbought_positive"): "changed", ("neutral", "overbought_positive"): "mixed",
    ("overbought_positive", "positive"): "changed", ("negative", "oversold_negative"): "changed",
    ("neutral", "overbought_mixed"): "mixed", ("neutral", "oversold_mixed"): "mixed",
}
EXTENSION_DIRECTION = {
    ("near_trend", "moderately_extended"): "changed",
    ("moderately_extended", "elevated"): "deteriorated",
    ("elevated", "near_trend"): "improved",
    ("below_long_term_trend", "near_trend"): "improved",
}
VOLATILITY_ORDER = {"low": 0, "moderate": 1, "high": 2}
STATE_ORDER = {"below": 0, "near": 1, "above": 2, "bearish": 0, "neutral": 1, "bullish": 2}
FIELD_RULES = {
    "technical_profile": ("technical.profile.transition", 2), "trend": ("technical.trend.transition", 3),
    "momentum": ("technical.momentum.transition", 4), "extension_positioning": ("technical.extension.transition", 5),
    "volatility": ("technical.volatility.transition", 6),
    "price_vs_sma_20_state": ("technical.price_vs_sma20.transition", 8),
    "price_vs_sma_50_state": ("technical.price_vs_sma50.transition", 3),
    "price_vs_sma_200_state": ("technical.price_vs_sma200.transition", 3),
    "sma_20_50_state": ("technical.sma20_50.transition", 8),
    "sma_50_200_state": ("technical.sma50_200.transition", 3),
}


def detect_universe_changes(baseline: UniverseAnalysisSnapshotV1, current: UniverseAnalysisSnapshotV1,
                            assessment: SnapshotComparisonAssessmentV01) -> UniverseChangeDetectionResultV01:
    """Emit auditable events using only permissions in the supplied assessment."""
    if (assessment.baseline_snapshot_id, assessment.current_snapshot_id) != (baseline.snapshot_id, current.snapshot_id):
        raise ValueError("Comparison assessment does not reference the supplied snapshots.")
    detected_at = current.built_at
    if assessment.comparability == Comparability.NOT_COMPARABLE:
        return _result(baseline, current, assessment, (), (), detected_at,
                       ("technical:not_comparable", "availability:not_comparable"), ChangeDetectionStatus.NOT_COMPARABLE)
    base = {m.matching_key: m for m in baseline.members}; now = {m.matching_key: m for m in current.members}
    events: list[UniverseChangeEventV01] = []
    if "membership" in assessment.allowed_event_categories:
        for key in assessment.added_matching_keys:
            events.append(_event(baseline, current, None, now[key], "membership_added", "membership",
                                 "membership", None, "included", "entered", "notable", 1,
                                 "membership.added", detected_at))
        for key in assessment.removed_matching_keys:
            events.append(_event(baseline, current, base[key], None, "membership_removed", "membership",
                                 "membership", "included", None, "exited", "notable", 1,
                                 "membership.removed", detected_at))
    for key in assessment.stable_matching_keys:
        previous, present = base[key], now[key]
        was_analyzed = previous.analysis_status == "analyzed"; is_analyzed = present.analysis_status == "analyzed"
        if "availability" in assessment.allowed_event_categories and was_analyzed != is_analyzed:
            lost = was_analyzed
            events.append(_event(baseline, current, previous, present,
                "availability_lost" if lost else "availability_restored", "availability", "analysis_status",
                previous.analysis_status, present.analysis_status, "unavailable" if lost else "restored",
                "attention", 1, "availability.lost" if lost else "availability.restored", detected_at))
        if "technical" not in assessment.allowed_event_categories or not (was_analyzed and is_analyzed):
            continue
        old, new = previous.derived_observation, present.derived_observation
        assert old is not None and new is not None
        for field, (rule, tier) in FIELD_RULES.items():
            if field not in assessment.allowed_technical_fields:
                continue
            before, after = getattr(old, field), getattr(new, field)
            if _norm(before) == _norm(after): continue
            direction, materiality = _transition(field, before, after)
            events.append(_event(baseline, current, previous, present, rule.rsplit(".", 1)[0], "technical",
                                 field, before, after, direction, materiality, tier, rule, detected_at))
        if assessment.rank_comparison_allowed:
            events.extend(_rank_events(baseline, current, previous, present, detected_at))
    events.sort(key=lambda e: (e.priority_tier, e.matching_key, e.rule_id, e.event_id))
    groups = _groups(baseline, current, events)
    status = ChangeDetectionStatus.CHANGES_DETECTED if events else ChangeDetectionStatus.NO_CHANGES
    suppressed = tuple(sorted(set(
        (["rank:comparison_not_allowed"] if not assessment.rank_comparison_allowed else [])
        + (["extension_positioning:version_incompatible"] if "extension_positioning" not in assessment.allowed_technical_fields else [])
    )))
    return _result(baseline, current, assessment, tuple(events), groups, detected_at, suppressed, status)


def _transition(field, before, after):
    a, b = _norm(before), _norm(after)
    if field == "technical_profile":
        delta = PROFILE_ORDER[b] - PROFILE_ORDER[a]
        return ("improved" if delta > 0 else "deteriorated", "attention" if abs(delta) >= 2 else "notable")
    if field == "trend":
        direction = TREND_DIRECTION.get((a, b), "changed")
        materiality = "attention" if "bullish_alignment" in (a, b) or "bearish_alignment" in (a, b) else "notable"
        return direction, materiality
    if field == "momentum":
        if (a, b) in MOMENTUM_SPECIAL: return MOMENTUM_SPECIAL[(a, b)], "notable"
        if a in MOMENTUM_ORDER and b in MOMENTUM_ORDER:
            return ("improved" if MOMENTUM_ORDER[b] > MOMENTUM_ORDER[a] else "deteriorated"), "notable"
        return "changed", "notable"
    if field == "extension_positioning":
        return EXTENSION_DIRECTION.get((a, b), "changed"), "attention" if "elevated" in (a, b) else "notable"
    if field == "volatility":
        delta = VOLATILITY_ORDER[b] - VOLATILITY_ORDER[a]
        return ("deteriorated" if delta > 0 else "improved"), "attention" if abs(delta) == 2 else "notable"
    delta = STATE_ORDER.get(b, 0) - STATE_ORDER.get(a, 0)
    materiality = "attention" if field in ("price_vs_sma_200_state", "sma_50_200_state") else "notable"
    return ("improved" if delta > 0 else "deteriorated" if delta < 0 else "changed"), materiality


def _rank_events(baseline, current, previous, present, detected_at):
    old, new = previous.derived_observation, present.derived_observation
    if old.rank_denominator != new.rank_denominator or old.rank_denominator != baseline.analyzed_count: return []
    threshold = max(2, math.ceil(current.analyzed_count * .20)); changes = []
    if abs(old.rank - new.rank) >= threshold:
        changes.append(("rank_material_movement", "rank", old.rank, new.rank, "rank.material_movement"))
    if current.analyzed_count >= 6:
        if old.rank > 3 >= new.rank: changes.append(("rank_entered_top_3", "top_3", False, True, "rank.entered_top3"))
        if old.rank <= 3 < new.rank: changes.append(("rank_exited_top_3", "top_3", True, False, "rank.exited_top3"))
    if current.analyzed_count >= 8:
        boundary = math.ceil(current.analyzed_count / 4)
        if old.rank > boundary >= new.rank: changes.append(("rank_entered_top_quartile", "top_quartile", False, True, "rank.entered_top_quartile"))
        if old.rank <= boundary < new.rank: changes.append(("rank_exited_top_quartile", "top_quartile", True, False, "rank.exited_top_quartile"))
    direction = "improved" if new.rank < old.rank else "deteriorated"
    return [_event(baseline, current, previous, present, kind, "technical", field, before, after,
                   direction, "attention" if "entered" in kind or "exited" in kind else "notable", 7, rule, detected_at)
            for kind, field, before, after, rule in changes]


def _event(baseline, current, previous, present, event_type, category, field, before, after,
           direction, materiality, tier, rule_id, detected_at):
    subject = present or previous; assert subject is not None
    prev_ref = _evidence_ref(baseline, previous, field); curr_ref = _evidence_ref(current, present, field)
    identity = json.dumps([baseline.snapshot_id, current.snapshot_id, rule_id, subject.matching_key, field, before, after],
                          sort_keys=True, separators=(",", ":"), default=str)
    event_id = str(uuid5(NAMESPACE_URL, f"{CHANGE_EVENT_SCHEMA_VERSION}:{identity}"))
    return UniverseChangeEventV01(
        CHANGE_EVENT_SCHEMA_VERSION, event_id, event_type, category, current.universe_id,
        baseline.universe_version, current.universe_version, baseline.snapshot_id, current.snapshot_id,
        subject.member_snapshot_id, subject.security_id, subject.matching_key, subject.ticker_or_identifier,
        subject.company_name, field, before, after, direction, materiality, tier,
        f"{tier:02d}:{subject.matching_key}:{rule_id}", rule_id, UNIVERSE_CHANGE_RULES_VERSION,
        (baseline.completed_at, current.completed_at), detected_at, prev_ref, curr_ref,
        tuple(ref for ref in (prev_ref, curr_ref) if ref),
    )


def _evidence_ref(snapshot, member, field):
    if member is None: return f"snapshot:{snapshot.snapshot_id}:membership:absent"
    if field in ("membership", "analysis_status"):
        return f"snapshot:{snapshot.snapshot_id}:member:{member.member_snapshot_id}:{field}"
    evidence = member.derived_observation.evidence_ids[0] if member.derived_observation and member.derived_observation.evidence_ids else member.technical_observation_reference
    return f"snapshot:{snapshot.snapshot_id}:member:{member.member_snapshot_id}:field:{field}:evidence:{evidence}"


def _groups(baseline, current, events):
    grouped = {}
    for event in events: grouped.setdefault(event.matching_key, []).append(event)
    result = []
    for key, items in grouped.items():
        first = items[0]; tier = min(item.priority_tier for item in items)
        reinforcing = len({item.direction for item in items if item.category == "technical"} & {"improved", "deteriorated"}) == 1 and len(items) > 1
        effective_tier = max(1, tier - 1) if reinforcing else tier
        raw = f"{baseline.snapshot_id}:{current.snapshot_id}:{key}"
        result.append(UniverseChangeGroupV01(
            CHANGE_GROUP_SCHEMA_VERSION, str(uuid5(NAMESPACE_URL, f"{CHANGE_GROUP_SCHEMA_VERSION}:{raw}")),
            current.universe_id, baseline.snapshot_id, current.snapshot_id, key, first.security_id,
            first.ticker, first.company_name, tuple(item.event_id for item in items),
            "attention" if any(item.materiality == "attention" for item in items) else "notable",
            tuple(sorted({item.category for item in items})), effective_tier,
            f"{effective_tier:02d}:{key}:{hashlib.sha256(raw.encode()).hexdigest()[:12]}",
        ))
    return tuple(sorted(result, key=lambda group: group.priority_order_key))


def _result(baseline, current, assessment, events, groups, detected_at, suppressed, status):
    counts = ChangeDetectionCountsV01(len(events), sum(e.materiality == "attention" for e in events),
        sum(e.materiality == "notable" for e in events), len({e.matching_key for e in events}),
        sum(e.category == "membership" for e in events), sum(e.category == "availability" for e in events))
    return UniverseChangeDetectionResultV01(CHANGE_RESULT_SCHEMA_VERSION, baseline.snapshot_id,
        current.snapshot_id, assessment, status, tuple(events), tuple(groups), tuple(suppressed),
        UNIVERSE_CHANGE_RULES_VERSION, detected_at, counts)


def _norm(value):
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")
