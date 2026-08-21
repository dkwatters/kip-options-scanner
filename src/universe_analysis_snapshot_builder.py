"""Pure builder for the versioned Universe Analysis Snapshot v1 artifact.

Membership digest algorithm: SHA-256 over UTF-8 canonical JSON containing the
universe id, universe version, and ordered members.  Each ordered member contains
its normalized matching key, currently available security id (null in v1),
ticker/identifier, identity status, and the fixed included membership status.
JSON uses sorted keys and compact separators; member order is preserved.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from src.research_universe import ResearchUniverseHandoff
from src.research_universe_analysis import AnalysisMemberStatus, ResearchUniverseAnalysisRun
from src.technical_analysis import (
    TECHNICAL_ANALYSIS_VERSION,
    TECHNICAL_SCORING_VERSION,
    derived_technical_display_fields,
    technical_setup_grade,
    technical_setup_score,
)
from src.universe_analysis import (
    EXTENSION_THRESHOLDS_VERSION,
    UNIVERSE_ANALYSIS_PRESENTATION_VERSION,
    analysis_summary,
    ranked_analysis_rows,
)
from src.universe_analysis_contracts import (
    SNAPSHOT_SCHEMA_VERSION,
    DataFreshness,
    DerivedUniverseAnalysisObservationV1,
    EvidenceReferenceV1,
    RawTechnicalObservationV1,
    SnapshotStatus,
    UniverseAnalysisMemberSnapshotV1,
    UniverseAnalysisSnapshotV1,
    UniverseAnalysisSummaryV1,
    UniverseAnalysisVersionManifestV1,
    isoformat_utc,
)


class UniverseAnalysisSnapshotValidationError(ValueError):
    """Raised when source artifacts cannot form an exact completed snapshot."""


_RAW_NUMERIC_FIELDS = (
    "price", "sma_20", "sma_50", "sma_200", "price_vs_sma_20",
    "price_vs_sma_50", "price_vs_sma_200", "sma_20_vs_sma_50",
    "sma_50_vs_sma_200", "rsi_14", "macd_line", "macd_signal",
    "macd_histogram", "realized_volatility_20d", "technical_score",
)


def build_universe_analysis_snapshot_v1(
    handoff: ResearchUniverseHandoff,
    run: ResearchUniverseAnalysisRun,
    technical_rows: Iterable[dict[str, Any]],
    *,
    snapshot_id: str | None = None,
    built_at: datetime | None = None,
    data_provider: str | None = None,
    data_freshness: DataFreshness = DataFreshness.UNKNOWN,
) -> UniverseAnalysisSnapshotV1:
    """Build one strict, immutable snapshot without I/O or provider calls."""
    _validate_identity(handoff, run)
    members = tuple(handoff.ordered_members)
    ledger = tuple(run.ledger)
    if len(members) != handoff.total_member_count or len(ledger) != len(members):
        raise UniverseAnalysisSnapshotValidationError(
            "Run ledger and ordered membership must reconcile to total universe members."
        )
    member_keys = [member.matching_key for member in members]
    ledger_keys = [entry.matching_key for entry in ledger]
    if len(set(member_keys)) != len(member_keys) or len(set(ledger_keys)) != len(ledger_keys):
        raise UniverseAnalysisSnapshotValidationError("Duplicate member identity is not allowed.")
    if set(member_keys) != set(ledger_keys):
        raise UniverseAnalysisSnapshotValidationError("Run ledger identities do not match universe membership.")

    rows = [dict(row) for row in technical_rows]
    row_by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker in row_by_ticker:
            raise UniverseAnalysisSnapshotValidationError("Technical rows require unique non-empty tickers.")
        if str(row.get("scan_id") or "") != run.scan_id:
            raise UniverseAnalysisSnapshotValidationError("Technical row scan_id does not match the analysis run.")
        row_by_ticker[ticker] = row
    analyzed = tuple(str(item).strip().upper() for item in run.analyzed_tickers)
    if len(set(analyzed)) != len(analyzed) or set(row_by_ticker) != set(analyzed):
        raise UniverseAnalysisSnapshotValidationError(
            "Analyzed tickers do not reconcile exactly to technical observations."
        )

    ledger_by_key = {entry.matching_key: entry for entry in ledger}
    ledger_analyzed = {
        str(entry.ticker_or_identifier or "").strip().upper()
        for entry in ledger if entry.status == AnalysisMemberStatus.ANALYZED
    }
    if ledger_analyzed != set(analyzed):
        raise UniverseAnalysisSnapshotValidationError(
            "Analyzed ledger members do not reconcile to run results."
        )
    if run.requested_constituent_count != len(members):
        raise UniverseAnalysisSnapshotValidationError("Run member count does not match the handoff.")

    names = {
        str(member.ticker_or_identifier or "").strip().upper(): member.company_name
        for member in members if member.ticker_or_identifier
    }
    ranked = ranked_analysis_rows(rows, names)
    ranked_by_ticker = {row["ticker"]: row for row in ranked}
    summary_values = analysis_summary(ranked)
    membership_digest = build_membership_digest(handoff)
    effective_snapshot_id = snapshot_id or str(uuid5(
        NAMESPACE_URL, f"{SNAPSHOT_SCHEMA_VERSION}:{run.scan_id}:{membership_digest}"
    ))
    completed_at = _normalize_timestamp(run.timestamp)
    effective_built_at = isoformat_utc(built_at) if built_at else completed_at
    observation_times = tuple(
        value for value in (_normalize_optional_timestamp(row.get("technical_timestamp")) for row in rows)
        if value is not None
    )
    observation_as_of = max(observation_times) if observation_times else None

    member_snapshots = []
    for order, member in enumerate(members, 1):
        entry = ledger_by_key[member.matching_key]
        ticker = str(member.ticker_or_identifier or "").strip().upper()
        member_id = str(uuid5(NAMESPACE_URL, f"{effective_snapshot_id}:{order}:{member.matching_key}"))
        if entry.status == AnalysisMemberStatus.ANALYZED:
            if ticker not in ranked_by_ticker:
                raise UniverseAnalysisSnapshotValidationError(
                    f"Analyzed member {ticker or member.matching_key} has no technical observation."
                )
            ranked_row = ranked_by_ticker[ticker]
            raw, evidence = _raw_observation(ranked_row, member_id, run.scan_id)
            derived = _derived_observation(ranked_row, len(ranked), evidence)
        else:
            if ticker and ticker in row_by_ticker:
                raise UniverseAnalysisSnapshotValidationError(
                    f"Non-analyzed member {ticker} unexpectedly has a technical observation."
                )
            raw, derived, evidence = None, None, ()
        member_snapshots.append(UniverseAnalysisMemberSnapshotV1(
            member_snapshot_id=member_id,
            matching_key=member.matching_key,
            security_id=None,
            company_name=member.company_name,
            ticker_or_identifier=member.ticker_or_identifier,
            identity_status=member.identity_status.value,
            membership_status="included",
            membership_order=order,
            source_references=tuple(member.provenance_references),
            analysis_status=entry.status.value,
            analysis_status_reason=entry.reason,
            technical_observation_reference=raw.observation_reference if raw else None,
            technical_timestamp=raw.technical_timestamp if raw else None,
            raw_technical_observation=raw,
            derived_observation=derived,
            evidence_references=evidence,
        ))

    unavailable_count = len(members) - len(ranked)
    rsi_denominator = sum(row.get("rsi_14") is not None for row in ranked)
    summary = UniverseAnalysisSummaryV1(
        analyzed_count=len(ranked), unavailable_count=unavailable_count,
        profile_denominator=len(ranked), strong_count=summary_values["profiles"]["Strong"],
        constructive_count=summary_values["profiles"]["Constructive"],
        mixed_count=summary_values["profiles"]["Mixed"], weak_count=summary_values["profiles"]["Weak"],
        bullish_trend_count=summary_values["bullish_trends"], bullish_trend_denominator=len(ranked),
        above_200_day_count=summary_values["above_200_day_sma"], above_200_day_denominator=len(ranked),
        bullish_macd_count=summary_values["bullish_macd"], bullish_macd_denominator=len(ranked),
        high_volatility_count=summary_values["high_volatility"], high_volatility_denominator=len(ranked),
        average_rsi=summary_values["average_rsi"], average_rsi_denominator=rsi_denominator,
    )
    if sum((summary.strong_count, summary.constructive_count, summary.mixed_count, summary.weak_count)) != summary.analyzed_count:
        raise UniverseAnalysisSnapshotValidationError("Profile summary does not reconcile.")

    study = _common_study_metadata(rows)
    manifest = UniverseAnalysisVersionManifestV1(
        technical_analysis_version=TECHNICAL_ANALYSIS_VERSION,
        technical_scoring_version=TECHNICAL_SCORING_VERSION,
        presentation_version=UNIVERSE_ANALYSIS_PRESENTATION_VERSION,
        extension_thresholds_version=EXTENSION_THRESHOLDS_VERSION,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        data_provider=data_provider,
        **study,
    )
    if not all((manifest.technical_analysis_version, manifest.technical_scoring_version,
                manifest.presentation_version, manifest.snapshot_schema_version)):
        raise UniverseAnalysisSnapshotValidationError("Required version manifest is absent.")
    requested_at = isoformat_utc(handoff.requested_at)
    provenance = tuple(dict.fromkeys((
        *handoff.provenance_references,
        *(ref for member in members for ref in member.provenance_references),
    )))
    return UniverseAnalysisSnapshotV1(
        snapshot_id=effective_snapshot_id, schema_version=SNAPSHOT_SCHEMA_VERSION,
        universe_id=handoff.universe_id, universe_version=handoff.universe_version,
        universe_title=handoff.universe_title, research_question=handoff.research_question,
        analysis_run_id=run.scan_id, requested_at=requested_at, started_at=None,
        completed_at=completed_at, observation_as_of=observation_as_of, built_at=effective_built_at,
        status=SnapshotStatus.COMPLETED, data_freshness=data_freshness,
        total_universe_member_count=len(members), requested_analyzable_count=len(run.requested_tickers),
        analyzed_count=len(ranked), unavailable_count=unavailable_count,
        membership_digest=membership_digest, members=tuple(member_snapshots), summary=summary,
        version_manifest=manifest, provenance_references=provenance,
    )


def build_membership_digest(handoff: ResearchUniverseHandoff) -> str:
    document = {
        "universe_id": handoff.universe_id,
        "universe_version": handoff.universe_version,
        "ordered_members": [{
            "matching_key": member.matching_key,
            "security_id": None,
            "ticker_or_identifier": member.ticker_or_identifier,
            "identity_status": member.identity_status.value,
            "membership_status": "included",
        } for member in handoff.ordered_members],
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_identity(handoff: ResearchUniverseHandoff, run: ResearchUniverseAnalysisRun) -> None:
    if handoff.universe_id != run.universe_id:
        raise UniverseAnalysisSnapshotValidationError("Universe ID mismatch.")
    if handoff.universe_version != run.universe_version:
        raise UniverseAnalysisSnapshotValidationError("Universe version mismatch.")
    if handoff.universe_title != run.universe_title or handoff.research_question != run.research_question:
        raise UniverseAnalysisSnapshotValidationError("Universe metadata mismatch.")


def _raw_observation(row: dict[str, Any], member_id: str, scan_id: str):
    states = derived_technical_display_fields(row)
    observation_reference = f"technical-characterization:{scan_id}:{row['ticker']}"
    evidence_id = f"evidence:{observation_reference}"
    evidence = EvidenceReferenceV1(
        evidence_id=evidence_id, evidence_type="technical_observation",
        member_snapshot_id=member_id, observation_reference=observation_reference,
        field_paths=tuple(sorted((*_RAW_NUMERIC_FIELDS, "trend_state", "momentum_state", "volatility_state"))),
        source_reference=None,
        observed_at=_normalize_optional_timestamp(row.get("technical_timestamp")),
    )
    missing = tuple(field for field in _RAW_NUMERIC_FIELDS if row.get(field) is None)
    raw = RawTechnicalObservationV1(
        observation_reference=observation_reference, scan_id=scan_id, ticker=row["ticker"],
        technical_timestamp=row.get("technical_timestamp"),
        **{field: row.get(field) for field in _RAW_NUMERIC_FIELDS},
        trend_state=row.get("trend_state"), momentum_state=row.get("momentum_state"),
        volatility_state=row.get("volatility_state"), technical_notes=row.get("technical_notes"),
        **states, setup_score=technical_setup_score(row), setup_grade=technical_setup_grade(technical_setup_score(row)),
        missing_fields=missing, study_id=row.get("study_id"), study_name=row.get("study_name"),
        study_version=row.get("study_version"), study_purpose=row.get("study_purpose"),
        scheduled_time_label=row.get("scheduled_time_label"), run_mode=row.get("run_mode"),
    )
    return raw, (evidence,)


def _derived_observation(row: dict[str, Any], denominator: int, evidence):
    return DerivedUniverseAnalysisObservationV1(
        technical_profile=row["technical_profile"], technical_profile_score=row["technical_profile_score"],
        rank=row["rank"], rank_denominator=denominator, trend=row["trend_label"],
        momentum=row["momentum_label"], extension_positioning=row["extension_label"],
        volatility=row["volatility_label"], key_signal=row["key_signal"], rsi_regime=row["rsi_regime"],
        macd_state=row["macd_state"], price_vs_sma_20_state=row["price_vs_sma_20_state"],
        price_vs_sma_50_state=row["price_vs_sma_50_state"], price_vs_sma_200_state=row["price_vs_sma_200_state"],
        sma_20_50_state=row["sma_20_50_state"], sma_50_200_state=row["sma_50_200_state"],
        evidence_ids=tuple(item.evidence_id for item in evidence),
    )


def _common_study_metadata(rows: list[dict[str, Any]]) -> dict[str, str | None]:
    fields = ("study_id", "study_name", "study_version", "study_purpose", "run_mode")
    result = {}
    for field in fields:
        values = {row.get(field) for row in rows if row.get(field) is not None}
        result[field] = next(iter(values)) if len(values) == 1 else None
    return result


def _normalize_timestamp(value: Any) -> str:
    normalized = _normalize_optional_timestamp(value)
    if normalized is None:
        raise UniverseAnalysisSnapshotValidationError("Completed run timestamp is required and must be parseable.")
    return normalized


def _normalize_optional_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return isoformat_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return isoformat_utc(parsed)
    except ValueError:
        pass
    for zone, offset in (("EDT", "-04:00"), ("EST", "-05:00")):
        if text.endswith(" " + zone):
            candidate = text[:-(len(zone) + 1)] + offset
            for pattern in ("%Y-%m-%d %I:%M:%S %p%z", "%Y-%m-%d %H:%M:%S%z"):
                try:
                    return isoformat_utc(datetime.strptime(candidate, pattern))
                except ValueError:
                    continue
    return None
