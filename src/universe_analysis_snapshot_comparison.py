"""Deterministic comparability assessment for Universe Analysis snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.universe_analysis_contracts import UniverseAnalysisSnapshotV1


COMPARISON_SCHEMA_VERSION = "snapshot_comparison_assessment.v0.1"


class Comparability(StrEnum):
    FULL = "fully_comparable"
    LIMITED = "limited_comparability"
    NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True, slots=True)
class SnapshotComparisonAssessmentV01:
    schema_version: str
    baseline_snapshot_id: str
    current_snapshot_id: str
    comparability: Comparability
    allowed_event_categories: tuple[str, ...]
    allowed_technical_fields: tuple[str, ...]
    rank_comparison_allowed: bool
    stable_matching_keys: tuple[str, ...]
    added_matching_keys: tuple[str, ...]
    removed_matching_keys: tuple[str, ...]
    reasons: tuple[str, ...]


TECHNICAL_FIELDS = (
    "technical_profile", "trend", "momentum", "extension_positioning", "volatility",
    "price_vs_sma_20_state", "price_vs_sma_50_state", "price_vs_sma_200_state",
    "sma_20_50_state", "sma_50_200_state", "rank",
)


def assess_snapshot_comparability(
    baseline: UniverseAnalysisSnapshotV1,
    current: UniverseAnalysisSnapshotV1,
) -> SnapshotComparisonAssessmentV01:
    """Assess once; downstream detectors must honor this decision."""
    base_keys = {member.matching_key for member in baseline.members}
    current_keys = {member.matching_key for member in current.members}
    stable = tuple(sorted(base_keys & current_keys))
    added = tuple(sorted(current_keys - base_keys))
    removed = tuple(sorted(base_keys - current_keys))
    if baseline.universe_id != current.universe_id:
        return _assessment(baseline, current, Comparability.NOT_COMPARABLE, (), (), False,
                           stable, added, removed, ("universe_id_changed",))
    bver, cver = baseline.version_manifest, current.version_manifest
    incompatible = (
        baseline.schema_version != current.schema_version
        or bver.technical_analysis_version != cver.technical_analysis_version
        or bver.technical_scoring_version != cver.technical_scoring_version
    )
    if incompatible:
        return _assessment(baseline, current, Comparability.NOT_COMPARABLE,
                           ("membership",), (), False, stable, added, removed,
                           ("analytical_behavior_version_changed",))
    presentation_compatible = (
        bver.presentation_version == cver.presentation_version
        and bver.extension_thresholds_version == cver.extension_thresholds_version
    )
    fields = tuple(field for field in TECHNICAL_FIELDS if presentation_compatible or field != "extension_positioning")
    membership_same = not added and not removed and baseline.membership_digest == current.membership_digest
    rank_allowed = membership_same and baseline.analyzed_count == current.analyzed_count
    if membership_same and baseline.universe_version == current.universe_version and presentation_compatible:
        level, reasons = Comparability.FULL, ()
    else:
        level = Comparability.LIMITED
        reasons = tuple(reason for condition, reason in (
            (not membership_same, "membership_changed"),
            (baseline.universe_version != current.universe_version, "universe_version_changed"),
            (not presentation_compatible, "presentation_version_changed"),
        ) if condition)
    return _assessment(baseline, current, level, ("technical", "availability", "membership"),
                       fields, rank_allowed, stable, added, removed, reasons)


def _assessment(baseline, current, level, categories, fields, rank, stable, added, removed, reasons):
    return SnapshotComparisonAssessmentV01(
        COMPARISON_SCHEMA_VERSION, baseline.snapshot_id, current.snapshot_id, level,
        tuple(categories), tuple(fields), rank, stable, added, removed, tuple(reasons),
    )
