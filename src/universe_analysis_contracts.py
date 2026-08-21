"""Versioned, immutable contracts for an in-memory Universe Analysis snapshot."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


SNAPSHOT_SCHEMA_VERSION = "universe_analysis_snapshot.v1"


class SnapshotStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceReferenceV1:
    evidence_id: str
    evidence_type: str
    member_snapshot_id: str | None
    observation_reference: str | None
    field_paths: tuple[str, ...]
    source_reference: str | None
    observed_at: str | None
    retrieved_at: str | None = None


@dataclass(frozen=True, slots=True)
class RawTechnicalObservationV1:
    observation_reference: str
    scan_id: str
    ticker: str
    technical_timestamp: str | None
    price: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    price_vs_sma_20: float | None
    price_vs_sma_50: float | None
    price_vs_sma_200: float | None
    sma_20_vs_sma_50: float | None
    sma_50_vs_sma_200: float | None
    rsi_14: float | None
    macd_line: float | None
    macd_signal: float | None
    macd_histogram: float | None
    realized_volatility_20d: float | None
    trend_state: str | None
    momentum_state: str | None
    volatility_state: str | None
    technical_score: float | None
    technical_notes: str | None
    price_vs_sma_20_state: str
    price_vs_sma_50_state: str
    price_vs_sma_200_state: str
    sma_20_50_state: str
    sma_50_200_state: str
    rsi_regime: str
    macd_state: str
    setup_score: float | None
    setup_grade: str
    missing_fields: tuple[str, ...]
    study_id: str | None
    study_name: str | None
    study_version: str | None
    study_purpose: str | None
    scheduled_time_label: str | None
    run_mode: str | None


@dataclass(frozen=True, slots=True)
class DerivedUniverseAnalysisObservationV1:
    technical_profile: str
    technical_profile_score: float | None
    rank: int
    rank_denominator: int
    trend: str
    momentum: str
    extension_positioning: str
    volatility: str
    key_signal: str
    rsi_regime: str
    macd_state: str
    price_vs_sma_20_state: str
    price_vs_sma_50_state: str
    price_vs_sma_200_state: str
    sma_20_50_state: str
    sma_50_200_state: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniverseAnalysisMemberSnapshotV1:
    member_snapshot_id: str
    matching_key: str
    security_id: str | None
    company_name: str
    ticker_or_identifier: str | None
    identity_status: str
    membership_status: str
    membership_order: int
    source_references: tuple[str, ...]
    analysis_status: str
    analysis_status_reason: str
    technical_observation_reference: str | None
    technical_timestamp: str | None
    raw_technical_observation: RawTechnicalObservationV1 | None
    derived_observation: DerivedUniverseAnalysisObservationV1 | None
    evidence_references: tuple[EvidenceReferenceV1, ...]


@dataclass(frozen=True, slots=True)
class UniverseAnalysisSummaryV1:
    analyzed_count: int
    unavailable_count: int
    profile_denominator: int
    strong_count: int
    constructive_count: int
    mixed_count: int
    weak_count: int
    bullish_trend_count: int
    bullish_trend_denominator: int
    above_200_day_count: int
    above_200_day_denominator: int
    bullish_macd_count: int
    bullish_macd_denominator: int
    high_volatility_count: int
    high_volatility_denominator: int
    average_rsi: float | None
    average_rsi_denominator: int


@dataclass(frozen=True, slots=True)
class UniverseAnalysisVersionManifestV1:
    technical_analysis_version: str
    technical_scoring_version: str
    presentation_version: str
    extension_thresholds_version: str
    snapshot_schema_version: str
    data_provider: str | None
    study_id: str | None
    study_name: str | None
    study_version: str | None
    study_purpose: str | None
    run_mode: str | None


@dataclass(frozen=True, slots=True)
class UniverseAnalysisSnapshotV1:
    snapshot_id: str
    schema_version: str
    universe_id: str
    universe_version: int
    universe_title: str
    research_question: str
    analysis_run_id: str
    requested_at: str | None
    started_at: str | None
    completed_at: str
    observation_as_of: str | None
    built_at: str
    status: SnapshotStatus
    data_freshness: DataFreshness
    total_universe_member_count: int
    requested_analyzable_count: int
    analyzed_count: int
    unavailable_count: int
    membership_digest: str
    members: tuple[UniverseAnalysisMemberSnapshotV1, ...]
    summary: UniverseAnalysisSummaryV1
    version_manifest: UniverseAnalysisVersionManifestV1
    provenance_references: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe structure with stable member ordering."""
        return _json_safe(asdict(self))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "UniverseAnalysisSnapshotV1":
        """Restore the typed v1 contract without deriving or changing its contents."""
        if not isinstance(value, dict):
            raise ValueError("Universe Analysis snapshot payload must be an object.")
        if value.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported Universe Analysis snapshot schema_version: "
                f"{value.get('schema_version')!r}."
            )
        try:
            members = tuple(
                UniverseAnalysisMemberSnapshotV1(
                    **{
                        **member,
                        "source_references": tuple(member["source_references"]),
                        "raw_technical_observation": (
                            RawTechnicalObservationV1(
                                **{
                                    **member["raw_technical_observation"],
                                    "missing_fields": tuple(
                                        member["raw_technical_observation"]["missing_fields"]
                                    ),
                                }
                            )
                            if member["raw_technical_observation"] is not None else None
                        ),
                        "derived_observation": (
                            DerivedUniverseAnalysisObservationV1(
                                **{
                                    **member["derived_observation"],
                                    "evidence_ids": tuple(
                                        member["derived_observation"]["evidence_ids"]
                                    ),
                                }
                            )
                            if member["derived_observation"] is not None else None
                        ),
                        "evidence_references": tuple(
                            EvidenceReferenceV1(
                                **{**reference, "field_paths": tuple(reference["field_paths"])}
                            )
                            for reference in member["evidence_references"]
                        ),
                    }
                )
                for member in value["members"]
            )
            snapshot = cls(
                **{
                    **value,
                    "status": SnapshotStatus(value["status"]),
                    "data_freshness": DataFreshness(value["data_freshness"]),
                    "members": members,
                    "summary": UniverseAnalysisSummaryV1(**value["summary"]),
                    "version_manifest": UniverseAnalysisVersionManifestV1(
                        **value["version_manifest"]
                    ),
                    "provenance_references": tuple(value["provenance_references"]),
                }
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid {SNAPSHOT_SCHEMA_VERSION} payload: {error}") from error
        validate_universe_analysis_snapshot_v1(snapshot)
        return snapshot


def validate_universe_analysis_snapshot_v1(snapshot: UniverseAnalysisSnapshotV1) -> None:
    """Validate persisted-contract invariants without recalculating analysis behavior."""
    if snapshot.schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported snapshot schema_version: {snapshot.schema_version!r}.")
    required = (
        snapshot.snapshot_id, snapshot.universe_id, snapshot.analysis_run_id,
        snapshot.membership_digest, snapshot.completed_at, snapshot.built_at,
        snapshot.version_manifest.technical_analysis_version,
        snapshot.version_manifest.technical_scoring_version,
        snapshot.version_manifest.presentation_version,
    )
    if not all(required):
        raise ValueError("Universe Analysis snapshot is missing required identity or version fields.")
    if snapshot.version_manifest.snapshot_schema_version != snapshot.schema_version:
        raise ValueError("Snapshot and version-manifest schema versions do not match.")
    if len(snapshot.members) != snapshot.total_universe_member_count:
        raise ValueError("Snapshot members do not reconcile to total universe member count.")
    if snapshot.analyzed_count + snapshot.unavailable_count != snapshot.total_universe_member_count:
        raise ValueError("Analyzed and unavailable counts do not reconcile to membership.")
    if snapshot.summary.analyzed_count != snapshot.analyzed_count:
        raise ValueError("Snapshot and summary analyzed counts do not match.")
    if snapshot.summary.unavailable_count != snapshot.unavailable_count:
        raise ValueError("Snapshot and summary unavailable counts do not match.")
    profile_total = sum((
        snapshot.summary.strong_count, snapshot.summary.constructive_count,
        snapshot.summary.mixed_count, snapshot.summary.weak_count,
    ))
    if profile_total != snapshot.analyzed_count:
        raise ValueError("Snapshot profile counts do not reconcile to analyzed count.")
    orders = tuple(member.membership_order for member in snapshot.members)
    if orders != tuple(range(1, len(snapshot.members) + 1)):
        raise ValueError("Snapshot membership order must be contiguous and one-based.")
    if len({member.member_snapshot_id for member in snapshot.members}) != len(snapshot.members):
        raise ValueError("Snapshot contains duplicate member snapshot IDs.")
    if len({member.matching_key for member in snapshot.members}) != len(snapshot.members):
        raise ValueError("Snapshot contains duplicate member identities.")
    analyzed_members = tuple(
        member for member in snapshot.members if member.analysis_status == "analyzed"
    )
    if len(analyzed_members) != snapshot.analyzed_count:
        raise ValueError("Analyzed member statuses do not reconcile to analyzed count.")
    for member in analyzed_members:
        if member.raw_technical_observation is None or member.derived_observation is None:
            raise ValueError("Analyzed members require raw and derived observations.")
        if member.derived_observation.rank_denominator != snapshot.analyzed_count:
            raise ValueError("Member rank denominator does not match analyzed count.")


def isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Snapshot datetimes must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
