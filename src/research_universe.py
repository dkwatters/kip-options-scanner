"""Canonical, presentation-neutral Research Universe review model.

Starting-company source types are provenance only.  They never select a
different matcher, disposition policy, review workflow, or downstream handoff.
"""
from __future__ import annotations

import json
from hashlib import sha256
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from src.candidate_identity_validation import (
    CANDIDATE_IDENTITY_VALIDATION_SCHEMA_VERSION,
)


class UniverseSource(StrEnum):
    CURATOR_AUTHORED = "curator_authored"
    USER_ENTERED = "user_entered"
    COMPANY_ANALYSIS_ANCHOR = "company_analysis_anchor"
    SAVED_UNIVERSE_REVISION = "saved_universe_revision"
    IMPORTED = "imported"
    RCE_GENERATED = "rce_generated"


class CandidateDisposition(StrEnum):
    INCLUDED = "included"
    REJECTED = "rejected"
    PENDING = "pending"
    DEFERRED = "deferred"
    IDENTITY_REVIEW = "identity_review"


class IdentityStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class UniverseState(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ANALYSIS_RUNNING = "analysis_running"
    ANALYZED = "analyzed"
    REVISION_DRAFT = "revision_draft"
    ARCHIVED = "archived"


class UniverseType(StrEnum):
    """Governance classification; never a membership or matching policy switch."""

    PRIVATE_USER = "private_user"
    SHARED = "shared"
    CURATED_OFFICIAL = "curated_official"
    SYSTEM_SEEDED = "system_seeded"
    IMPORTED = "imported"


@dataclass(frozen=True, slots=True, eq=False)
class UniverseSourceRecord:
    source: UniverseSource
    company_name: str
    ticker_or_identifier: str | None = None
    source_reference: str | None = None
    identity_status: IdentityStatus = IdentityStatus.UNRESOLVED
    original_input: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniverseCandidate:
    normalized_matching_key: str
    company_name: str
    ticker_or_identifier: str | None
    identity_status: IdentityStatus
    original_input: str | None
    in_starting_companies: bool
    in_rce_suggestions: bool
    source_records: tuple[UniverseSourceRecord, ...]
    disposition: CandidateDisposition
    inclusion_origin: str | None = None
    rejection_reason: str | None = None
    comment: str | None = None
    rce_rank: int | None = None
    rce_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rce_metadata", MappingProxyType(dict(self.rce_metadata)))


@dataclass(frozen=True, slots=True)
class UniverseProgress:
    total: int
    included: int
    pending: int
    rejected: int
    deferred: int
    identity_review: int
    agreements_included: int


@dataclass(frozen=True, slots=True)
class ResearchUniverseMemberHandoff:
    matching_key: str
    company_name: str
    ticker_or_identifier: str | None
    identity_status: IdentityStatus
    provenance_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchUniverseHandoff:
    universe_id: str
    universe_version: int
    universe_title: str
    research_question: str
    ordered_members: tuple[ResearchUniverseMemberHandoff, ...]
    approved_constituents: tuple[str, ...]
    expected_constituent_count: int
    total_member_count: int
    unresolved_members: tuple[str, ...]
    provenance_references: tuple[str, ...]
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchUniverse:
    universe_id: str
    title: str
    research_question: str
    state: UniverseState
    version: int
    candidates: tuple[UniverseCandidate, ...]
    created_at: datetime
    updated_at: datetime
    owner_reference: str | None = None
    visibility: str | None = None
    universe_type: UniverseType = UniverseType.PRIVATE_USER
    provenance: Mapping[str, Any] = field(default_factory=dict)
    analysis_references: tuple[str, ...] = ()
    established_topic: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))
        _validate_candidate_partition(self.candidates)

    @property
    def approved_membership(self) -> tuple[UniverseCandidate, ...]:
        return tuple(row for row in self.candidates if row.disposition == CandidateDisposition.INCLUDED)

    @property
    def progress(self) -> UniverseProgress:
        counts = {state: 0 for state in CandidateDisposition}
        for row in self.candidates:
            counts[row.disposition] += 1
        return UniverseProgress(
            total=len(self.candidates),
            included=counts[CandidateDisposition.INCLUDED],
            pending=counts[CandidateDisposition.PENDING],
            rejected=counts[CandidateDisposition.REJECTED],
            deferred=counts[CandidateDisposition.DEFERRED],
            identity_review=counts[CandidateDisposition.IDENTITY_REVIEW],
            agreements_included=sum(
                row.disposition == CandidateDisposition.INCLUDED
                and row.in_starting_companies
                and row.in_rce_suggestions
                for row in self.candidates
            ),
        )

    def with_state(self, state: UniverseState) -> "ResearchUniverse":
        return replace(self, state=state, updated_at=datetime.now(timezone.utc))

    def downstream_handoff(self) -> ResearchUniverseHandoff:
        members = tuple(
            ResearchUniverseMemberHandoff(
                matching_key=row.normalized_matching_key,
                company_name=row.company_name,
                ticker_or_identifier=row.ticker_or_identifier,
                identity_status=row.identity_status,
                provenance_references=tuple(dict.fromkeys(
                    record.source_reference for record in row.source_records
                    if record.source_reference
                )),
            )
            for row in self.approved_membership
        )
        constituents = tuple(
            row.ticker_or_identifier for row in self.approved_membership
            if row.identity_status == IdentityStatus.RESOLVED and row.ticker_or_identifier
        )
        unresolved = tuple(
            row.original_input or row.company_name for row in self.approved_membership
            if row.identity_status != IdentityStatus.RESOLVED
        )
        references = tuple(dict.fromkeys(
            record.source_reference
            for row in self.candidates
            for record in row.source_records
            if record.source_reference
        ))
        return ResearchUniverseHandoff(
            universe_id=self.universe_id,
            universe_version=self.version,
            universe_title=self.title,
            research_question=self.research_question,
            ordered_members=members,
            approved_constituents=constituents,
            expected_constituent_count=len(constituents),
            total_member_count=len(self.approved_membership),
            unresolved_members=unresolved,
            provenance_references=references,
            requested_at=datetime.now(timezone.utc),
        )


def _name_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _name_alias_key(value: str | None) -> str:
    """Conservative legal-suffix alias; no fuzzy similarity is used."""
    words = re.findall(r"[a-z0-9]+", (value or "").casefold())
    suffixes = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "holdings"}
    while words and words[-1] in suffixes:
        words.pop()
    return "".join(words)


def _ticker_keys(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    values: set[str] = set()
    for part in re.split(r"[/,]", str(value).upper()):
        token = re.sub(r"[^A-Z0-9.]", "", part.rsplit(":", 1)[-1])
        if token and token not in {"PRIVATE", "RECENT", "FILER", "LISTED", "IPO"}:
            values.add(token)
    return frozenset(values)


def normalized_matching_key(company_name: str, ticker_or_identifier: str | None) -> str:
    tickers = sorted(_ticker_keys(ticker_or_identifier))
    return f"ticker:{tickers[0]}" if tickers else f"name:{_name_key(company_name)}"


@dataclass(frozen=True, slots=True)
class _CanonicalCandidateGroup:
    canonical_key: str
    company_name: str
    ticker_or_identifier: str | None
    identity_status: IdentityStatus
    source_records: tuple[UniverseSourceRecord, ...]


_TRUSTED_PROMOTION_TYPE = "research_universe_promotion"
_TRUSTED_PROMOTION_VERSION = 1


@dataclass(frozen=True, slots=True)
class _TrustedPromotionReference:
    candidate_identity: str
    original_source_reference: str
    expected_name_key: str
    expected_raw_ticker: str | None
    expected_security_id: str | None
    promoted_security_id: str | None
    promoted_ticker: str
    validation_result: str
    validation_schema_version: str | None
    authoritative_source: str | None
    authoritative_source_reference: str | None


def _metadata_json(record: UniverseSourceRecord) -> str:
    return json.dumps(
        dict(record.metadata), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    )


def _source_fingerprint(record: UniverseSourceRecord) -> tuple[str, ...]:
    return (
        record.source.value,
        record.company_name.strip(),
        record.ticker_or_identifier or "",
        record.source_reference or "",
        record.identity_status.value,
        record.original_input or "",
        _metadata_json(record),
    )


def _source_order(record: UniverseSourceRecord) -> tuple[Any, ...]:
    return (
        record.source == UniverseSource.RCE_GENERATED,
        record.source.value,
        record.company_name.casefold(),
        record.ticker_or_identifier or "",
        record.original_input or "",
        record.source_reference or "",
        _metadata_json(record),
    )


def _logical_source_identity(record: UniverseSourceRecord) -> tuple[str, ...]:
    """Producer-scoped evidence identity; never a security merge key."""
    if record.source == UniverseSource.USER_ENTERED and record.source_reference:
        claims = sorted(_material_ticker_claim(record))
        input_identity = (
            f"ticker:{claims[0]}"
            if len(claims) == 1
            else f"name:{_name_key(record.company_name)}"
        )
        return (
            "manual",
            record.source_reference,
            input_identity,
            record.identity_status.value,
            _metadata_json(record),
        )
    return ("record", *_source_fingerprint(record))


def _deduplicate_source_records(
    records: Sequence[UniverseSourceRecord],
) -> tuple[UniverseSourceRecord, ...]:
    unique = {
        _logical_source_identity(record): record
        for record in sorted(records, key=_source_order)
    }
    return tuple(unique[key] for key in sorted(unique))


def _validation_metadata(record: UniverseSourceRecord) -> Mapping[str, Any]:
    value = record.metadata.get("candidate_identity_validation")
    return value if isinstance(value, Mapping) else {}


def _validation_status(record: UniverseSourceRecord) -> str | None:
    validation = _validation_metadata(record)
    value = validation.get("validation_status") or record.metadata.get(
        "identity_validation_status"
    )
    return str(value) if value else None


def _validated_security_id(record: UniverseSourceRecord) -> str | None:
    validation = _validation_metadata(record)
    status = _validation_status(record)
    if record.identity_status != IdentityStatus.RESOLVED and status not in {"valid", "corrected"}:
        return None
    value = (
        validation.get("normalized_security_id")
        or validation.get("security_id")
        or record.metadata.get("validated_security_id")
        or record.metadata.get("security_id")
    )
    return str(value).strip() if value else None


def _validated_display_ticker(record: UniverseSourceRecord) -> str | None:
    validation = _validation_metadata(record)
    status = _validation_status(record)
    if record.identity_status != IdentityStatus.RESOLVED and status not in {"valid", "corrected"}:
        return None
    value = (
        validation.get("normalized_ticker_or_identifier")
        or record.ticker_or_identifier
    )
    normalized = str(value).strip().upper() if value else ""
    return normalized or None


def _validated_ticker_key(record: UniverseSourceRecord) -> str | None:
    display = _validated_display_ticker(record)
    tickers = sorted(_ticker_keys(display))
    return tickers[0] if len(tickers) == 1 else None


def _material_ticker_claim(record: UniverseSourceRecord) -> frozenset[str]:
    validation = _validation_metadata(record)
    raw = (
        record.metadata.get("raw_ticker_or_identifier")
        or validation.get("raw_ticker_or_identifier")
        or record.ticker_or_identifier
    )
    return _ticker_keys(str(raw) if raw else None)


def _select_review_ticker_or_identifier(
    records: Sequence[UniverseSourceRecord],
) -> str | None:
    """Select display evidence without granting canonical identity or merge authority."""
    validated = {
        ticker for record in records
        for ticker in (_validated_display_ticker(record),)
        if ticker
    }
    if len(validated) == 1:
        return next(iter(validated))
    if validated:
        return None
    raw = {
        ticker for record in records
        for ticker in _material_ticker_claim(record)
    }
    return next(iter(raw)) if len(raw) == 1 else None


def _record_aliases(record: UniverseSourceRecord) -> frozenset[str]:
    return frozenset(
        {_name_key(record.company_name), _name_alias_key(record.company_name)} - {""}
    )


def _candidate_identity(record: UniverseSourceRecord) -> str | None:
    value = record.metadata.get("candidate_identity")
    return str(value).strip() if value else None


def _trusted_promotion_reference(
    record: UniverseSourceRecord,
) -> _TrustedPromotionReference | None:
    value = record.metadata.get("trusted_promotion_reference")
    if (
        record.source != UniverseSource.USER_ENTERED
        or not record.source_reference
        or not record.source_reference.startswith("session:")
        or not record.source_reference.endswith(":suggestion-promotion")
        or not isinstance(value, Mapping)
        or value.get("type") != _TRUSTED_PROMOTION_TYPE
        or value.get("version") != _TRUSTED_PROMOTION_VERSION
        or value.get("workflow") != "validated_manual_resolution"
    ):
        return None
    required = (
        "candidate_identity", "original_source_reference", "expected_name_key",
        "promoted_ticker", "validation_result",
    )
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required):
        return None
    validation_result = str(value["validation_result"]).strip()
    if validation_result not in {"valid", "corrected"}:
        return None
    expected_raw = value.get("expected_raw_ticker")
    expected_security = value.get("expected_security_id")
    promoted_security = value.get("promoted_security_id")
    validation_schema = value.get("validation_schema_version")
    authoritative_source = value.get("authoritative_source")
    authoritative_reference = value.get("authoritative_source_reference")
    if expected_raw is not None and not isinstance(expected_raw, str):
        return None
    if expected_security is not None and not isinstance(expected_security, str):
        return None
    if promoted_security is not None and not isinstance(promoted_security, str):
        return None
    if validation_schema is not None and not isinstance(validation_schema, str):
        return None
    if authoritative_source is not None and not isinstance(authoritative_source, str):
        return None
    if authoritative_reference is not None and not isinstance(authoritative_reference, str):
        return None
    return _TrustedPromotionReference(
        candidate_identity=str(value["candidate_identity"]).strip(),
        original_source_reference=str(value["original_source_reference"]).strip(),
        expected_name_key=str(value["expected_name_key"]).strip(),
        expected_raw_ticker=str(expected_raw).strip().upper() if expected_raw else None,
        expected_security_id=(
            str(expected_security).strip() if expected_security else None
        ),
        promoted_security_id=str(promoted_security).strip() if promoted_security else None,
        promoted_ticker=str(value["promoted_ticker"]).strip().upper(),
        validation_result=validation_result,
        validation_schema_version=(
            str(validation_schema).strip() if validation_schema else None
        ),
        authoritative_source=(
            str(authoritative_source).strip() if authoritative_source else None
        ),
        authoritative_source_reference=(
            str(authoritative_reference).strip() if authoritative_reference else None
        ),
    )


def _trusted_promotion_target(
    promoted: UniverseSourceRecord,
    possible_originals: Sequence[UniverseSourceRecord],
) -> UniverseSourceRecord | None:
    link = _trusted_promotion_reference(promoted)
    if link is None:
        return None
    matches = [
        record for record in possible_originals
        if record.source == UniverseSource.RCE_GENERATED
        and record.source_reference == link.original_source_reference
    ]
    if len(matches) != 1:
        return None
    target = matches[0]
    raw_claims = _material_ticker_claim(target)
    expected_claims = _ticker_keys(link.expected_raw_ticker)
    promoted_ticker = _validated_ticker_key(promoted)
    promoted_security = _validated_security_id(promoted)
    promoted_status = _validation_status(promoted)
    if (
        target.source != UniverseSource.RCE_GENERATED
        or _candidate_identity(target) != link.candidate_identity
        or _name_key(target.company_name) != link.expected_name_key
        or raw_claims != expected_claims
        or _validated_security_id(target) != link.expected_security_id
        or promoted_ticker != next(iter(_ticker_keys(link.promoted_ticker)), None)
        or promoted_security != link.promoted_security_id
        or promoted_status not in {"valid", "corrected"}
        or link.validation_result != promoted_status
    ):
        return None
    same_identity = [
        record for record in possible_originals
        if record.source == UniverseSource.RCE_GENERATED
        and _candidate_identity(record) == link.candidate_identity
    ]
    if len(same_identity) != 1:
        return None
    if raw_claims and link.validation_result != "corrected":
        if raw_claims != _ticker_keys(link.promoted_ticker):
            return None
    if link.validation_result == "corrected":
        target_validation = _validation_metadata(target)
        promoted_validation = _validation_metadata(promoted)
        validation_candidate_id = str(
            target_validation.get("candidate_id") or ""
        ).strip()
        validation_raw_name = str(
            target_validation.get("raw_company_name") or ""
        ).strip()
        validation_raw_claims = _ticker_keys(
            str(target_validation.get("raw_ticker_or_identifier") or "")
        )
        correction_rationale = (
            target_validation.get("correction_reason")
            or target_validation.get("resolution_source")
        )
        if (
            target_validation != promoted_validation
            or _validation_status(target) != "corrected"
            or target_validation.get("schema_version")
            != CANDIDATE_IDENTITY_VALIDATION_SCHEMA_VERSION
            or target_validation.get("correction_applied") is not True
            or _candidate_identity(promoted) != link.candidate_identity
            or validation_candidate_id != link.candidate_identity
            or _name_key(validation_raw_name) != link.expected_name_key
            or validation_raw_claims != expected_claims
            or not str(target_validation.get("raw_ticker_or_identifier") or "").strip()
            or not str(target_validation.get("normalized_ticker_or_identifier") or "").strip()
            or not str(target_validation.get("authoritative_source") or "").strip()
            or not str(target_validation.get("source_reference") or "").strip()
            or not str(correction_rationale or "").strip()
            or link.validation_schema_version
            != CANDIDATE_IDENTITY_VALIDATION_SCHEMA_VERSION
            or link.authoritative_source
            != str(target_validation.get("authoritative_source")).strip()
            or link.authoritative_source_reference
            != str(target_validation.get("source_reference")).strip()
            or _validated_ticker_key(target) != promoted_ticker
            or _validated_security_id(target) != promoted_security
        ):
            return None
    return target


def trusted_promotion_reference(
    original: UniverseSourceRecord,
    promoted: UniverseSourceRecord,
    *,
    candidate_identity: str,
    validation_result: str,
) -> dict[str, Any]:
    """Create the versioned reference used only by the validated promotion workflow."""
    validation = _validation_metadata(original)
    return {
        "type": _TRUSTED_PROMOTION_TYPE,
        "version": _TRUSTED_PROMOTION_VERSION,
        "workflow": "validated_manual_resolution",
        "candidate_identity": candidate_identity,
        "original_source_reference": original.source_reference,
        "expected_name_key": _name_key(original.company_name),
        "expected_raw_ticker": (
            next(iter(_material_ticker_claim(original)))
            if len(_material_ticker_claim(original)) == 1 else None
        ),
        "expected_security_id": _validated_security_id(original),
        "promoted_security_id": _validated_security_id(promoted),
        "promoted_ticker": _validated_display_ticker(promoted),
        "validation_result": validation_result,
        "validation_schema_version": validation.get("schema_version"),
        "authoritative_source": validation.get("authoritative_source"),
        "authoritative_source_reference": validation.get("source_reference"),
    }


def _canonical_record(records: Sequence[UniverseSourceRecord]) -> UniverseSourceRecord:
    return min(
        records,
        key=lambda row: (
            _validated_security_id(row) is None,
            _validated_display_ticker(row) is None,
            row.identity_status != IdentityStatus.RESOLVED,
            row.company_name.casefold() == (row.ticker_or_identifier or "").casefold(),
            -len(row.company_name),
            _source_order(row),
        ),
    )


def _unresolved_evidence_key(record: UniverseSourceRecord) -> str:
    digest = sha256(
        json.dumps(
            _logical_source_identity(record),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"name:{_name_key(record.company_name)}:evidence:{digest}"


def _canonical_partition(
    records: Sequence[UniverseSourceRecord],
) -> tuple[_CanonicalCandidateGroup, ...]:
    ordered = _deduplicate_source_records(records)
    security_groups: dict[str, list[UniverseSourceRecord]] = {}
    ticker_only: dict[str, list[UniverseSourceRecord]] = {}
    unresolved: list[UniverseSourceRecord] = []
    ticker_security_ids: dict[str, set[str]] = {}
    for record in ordered:
        security_id = _validated_security_id(record)
        ticker = _validated_ticker_key(record)
        if security_id:
            key = f"security:{security_id}"
            security_groups.setdefault(key, []).append(record)
            if ticker:
                ticker_security_ids.setdefault(ticker, set()).add(security_id)
        elif ticker:
            ticker_only.setdefault(ticker, []).append(record)
        else:
            unresolved.append(record)

    resolved: dict[str, list[UniverseSourceRecord]] = dict(security_groups)
    conflicted_keys: set[str] = set()
    for ticker, records_for_ticker in ticker_only.items():
        security_ids = ticker_security_ids.get(ticker, set())
        if len(security_ids) == 1:
            security_id = next(iter(security_ids))
            resolved[f"security:{security_id}"].extend(records_for_ticker)
        else:
            ticker_key = f"ticker:{ticker}"
            resolved[ticker_key] = list(records_for_ticker)
            if len(security_ids) > 1:
                conflicted_keys.add(ticker_key)
                conflicted_keys.update(f"security:{security_id}" for security_id in security_ids)
    for security_ids in ticker_security_ids.values():
        if len(security_ids) > 1:
            conflicted_keys.update(f"security:{security_id}" for security_id in security_ids)

    for key, evidence in security_groups.items():
        validated_tickers = {
            ticker for record in evidence
            for ticker in (_validated_ticker_key(record),)
            if ticker
        }
        if len(validated_tickers) > 1:
            conflicted_keys.add(key)

    resolved_aliases = {
        key: frozenset(
            alias
            for record in group
            for alias in _record_aliases(record)
        )
        for key, group in resolved.items()
    }
    explicitly_linked: set[int] = set()
    linked_targets: dict[int, str] = {}
    for key, group in resolved.items():
        for promoted in tuple(group):
            target = _trusted_promotion_target(promoted, unresolved)
            if target is None or id(target) in linked_targets:
                continue
            linked_targets[id(target)] = key
            group.append(target)
            explicitly_linked.add(id(target))
    unresolved = [
        record for record in unresolved if id(record) not in explicitly_linked
    ]
    remaining: list[UniverseSourceRecord] = []
    for record in unresolved:
        eligible: list[str] = []
        if record.source != UniverseSource.RCE_GENERATED:
            claims = _material_ticker_claim(record)
            if not claims:
                aliases = _record_aliases(record)
                eligible = [
                    key for key, group_aliases in resolved_aliases.items()
                    if aliases.intersection(group_aliases)
                ]
        if len(eligible) == 1:
            resolved[eligible[0]].append(record)
        else:
            remaining.append(record)

    unresolved_groups: dict[str, list[UniverseSourceRecord]] = {}
    for record in remaining:
        alias = _name_alias_key(record.company_name) or _name_key(record.company_name)
        claims = _material_ticker_claim(record)
        group_key = _unresolved_evidence_key(record) if claims else alias
        unresolved_groups.setdefault(group_key, []).append(record)

    resolved_name_owners: dict[str, set[str]] = {}
    for key, aliases in resolved_aliases.items():
        for alias in aliases:
            resolved_name_owners.setdefault(alias, set()).add(key)

    groups: list[_CanonicalCandidateGroup] = []
    for key, evidence in resolved.items():
        records_in_group = tuple(sorted(evidence, key=_source_order))
        selected = _canonical_record(records_in_group)
        competing_resolved = set().union(*(
            resolved_name_owners.get(alias, set())
            for alias in _record_aliases(selected)
        )) - {key}
        validated_tickers = {
            ticker for record in records_in_group
            for ticker in (_validated_display_ticker(record),)
            if ticker
        }
        status = (
            IdentityStatus.AMBIGUOUS
            if competing_resolved or key in conflicted_keys or len(validated_tickers) > 1
            else IdentityStatus.RESOLVED
        )
        groups.append(_CanonicalCandidateGroup(
            canonical_key=key,
            company_name=selected.company_name,
            ticker_or_identifier=(
                next(iter(validated_tickers)) if len(validated_tickers) == 1 else None
            ),
            identity_status=status,
            source_records=records_in_group,
        ))
    for unresolved_key, evidence in unresolved_groups.items():
        records_in_group = tuple(sorted(evidence, key=_source_order))
        selected = _canonical_record(records_in_group)
        claims = {
            ticker for record in records_in_group
            for ticker in _material_ticker_claim(record)
        }
        aliases = {
            alias for record in records_in_group for alias in _record_aliases(record)
        }
        conflicts_with_resolved = any(resolved_name_owners.get(alias) for alias in aliases)
        status = (
            IdentityStatus.AMBIGUOUS
            if len(claims) > 1 or conflicts_with_resolved
            else IdentityStatus.UNRESOLVED
        )
        groups.append(_CanonicalCandidateGroup(
            canonical_key=(
                unresolved_key
                if unresolved_key.startswith("name:")
                else f"name:{_name_key(selected.company_name)}"
            ),
            company_name=selected.company_name,
            ticker_or_identifier=_select_review_ticker_or_identifier(records_in_group),
            identity_status=status,
            source_records=records_in_group,
        ))
    groups.sort(key=lambda group: group.canonical_key)
    _validate_canonical_groups(tuple(groups), len(ordered))
    return tuple(groups)


def _validate_canonical_groups(
    groups: Sequence[_CanonicalCandidateGroup],
    expected_source_count: int,
) -> None:
    keys = tuple(group.canonical_key for group in groups)
    fingerprints = tuple(
        _source_fingerprint(record)
        for group in groups
        for record in group.source_records
    )
    if len(set(keys)) != len(keys):
        raise ValueError("Canonical candidate identities must be unique.")
    if len(fingerprints) != expected_source_count or len(set(fingerprints)) != len(fingerprints):
        raise ValueError("Every source record must belong to exactly one canonical candidate group.")


def validate_candidate_partition_integrity(
    candidates: Sequence[UniverseCandidate],
) -> None:
    """Validate a finalized partition without regrouping or repairing evidence."""
    keys = tuple(candidate.normalized_matching_key for candidate in candidates)
    owned_ids = tuple(
        id(record)
        for candidate in candidates
        for record in candidate.source_records
    )
    fingerprints = tuple(
        _source_fingerprint(record)
        for candidate in candidates
        for record in candidate.source_records
    )
    if len(set(keys)) != len(keys):
        raise ValueError("Research Universe candidates require unique canonical identities.")
    if len(set(owned_ids)) != len(owned_ids) or len(set(fingerprints)) != len(fingerprints):
        raise ValueError("Research Universe source evidence cannot belong to multiple candidates.")
    for candidate in candidates:
        if not candidate.source_records:
            raise ValueError("Research Universe candidates require source evidence.")
        key = candidate.normalized_matching_key
        security_ids = {
            security_id for record in candidate.source_records
            for security_id in (_validated_security_id(record),)
            if security_id
        }
        ticker_keys = {
            ticker for record in candidate.source_records
            for ticker in (_validated_ticker_key(record),)
            if ticker
        }
        display_keys = _ticker_keys(candidate.ticker_or_identifier)
        if key.startswith("security:"):
            expected = key.removeprefix("security:")
            if expected not in security_ids:
                raise ValueError("Security canonical identity lacks matching validated evidence.")
        elif key.startswith("ticker:"):
            expected = key.removeprefix("ticker:")
            if expected not in ticker_keys:
                raise ValueError("Ticker canonical identity lacks matching validated evidence.")
        elif key.startswith("name:"):
            base_name_key = f"name:{_name_key(candidate.company_name)}"
            ticker_bearing = tuple(
                record for record in candidate.source_records
                if _material_ticker_claim(record)
            )
            if ticker_bearing:
                if (
                    len(candidate.source_records) != 1
                    or key != _unresolved_evidence_key(candidate.source_records[0])
                ):
                    raise ValueError(
                        "Evidence-disambiguated name identity does not match owned evidence."
                    )
            elif key != base_name_key:
                raise ValueError("Name canonical identity does not match the candidate name.")
        else:
            raise ValueError("Research Universe candidate has an unsupported canonical identity.")
        if candidate.identity_status == IdentityStatus.RESOLVED and not (
            security_ids or ticker_keys
        ):
            raise ValueError("Resolved candidates require a validated canonical security identity.")
        if (
            candidate.identity_status == IdentityStatus.RESOLVED
            and key.startswith("name:")
        ):
            raise ValueError("Resolved candidates require a security or ticker canonical identity.")
        if (
            candidate.identity_status == IdentityStatus.UNRESOLVED
            and not key.startswith("name:")
        ):
            raise ValueError("Unresolved candidates require a name canonical identity.")
        if candidate.identity_status == IdentityStatus.RESOLVED:
            if len(display_keys) != 1 or not display_keys.issubset(ticker_keys):
                raise ValueError("Resolved display ticker lacks matching validated evidence.")
        elif candidate.identity_status == IdentityStatus.AMBIGUOUS:
            raw_claims = {
                claim for record in candidate.source_records
                for claim in _material_ticker_claim(record)
            }
            if key.startswith("security:"):
                expected_security = key.removeprefix("security:")
                if security_ids != {expected_security}:
                    raise ValueError("Ambiguous security identity has contradictory evidence.")
                if len(ticker_keys) > 1 and candidate.ticker_or_identifier is not None:
                    raise ValueError("Ambiguous ticker conflict cannot select a display ticker.")
                if display_keys and not display_keys.issubset(ticker_keys):
                    raise ValueError("Ambiguous display ticker lacks matching validated evidence.")
            elif key.startswith("ticker:"):
                expected_ticker = key.removeprefix("ticker:")
                if security_ids or display_keys not in (frozenset(), frozenset({expected_ticker})):
                    raise ValueError("Ambiguous ticker identity has contradictory evidence.")
            elif security_ids or ticker_keys:
                raise ValueError("Ambiguous name identity cannot contain validated security evidence.")
            elif display_keys and (
                len(raw_claims) != 1 or not display_keys.issubset(raw_claims)
            ):
                raise ValueError("Ambiguous raw display ticker contradicts owned evidence.")
        elif candidate.ticker_or_identifier and display_keys.intersection(ticker_keys):
            if key.startswith("name:"):
                raise ValueError("Unresolved display ticker cannot represent validated identity.")
        expected_starting = any(
            record.source != UniverseSource.RCE_GENERATED
            for record in candidate.source_records
        )
        expected_rce = any(
            record.source == UniverseSource.RCE_GENERATED
            for record in candidate.source_records
        )
        if candidate.in_starting_companies != expected_starting:
            raise ValueError("Starting-company flag does not match owned source evidence.")
        if candidate.in_rce_suggestions != expected_rce:
            raise ValueError("RCE flag does not match owned source evidence.")
        for record in candidate.source_records:
            if "trusted_promotion_reference" not in record.metadata:
                continue
            target = _trusted_promotion_target(record, candidate.source_records)
            if target is None:
                raise ValueError("Promotion state lacks trusted exact-source evidence.")


def _validate_candidate_partition(candidates: Sequence[UniverseCandidate]) -> None:
    validate_candidate_partition_integrity(candidates)


def source_record(
    row: Mapping[str, Any],
    source: UniverseSource,
    *,
    source_reference: str | None = None,
) -> UniverseSourceRecord:
    company_name = str(row.get("company_name") or row.get("name") or row.get("supplied_value") or "").strip()
    ticker = row.get("ticker_or_identifier") or row.get("ticker") or row.get("normalized_ticker")
    original_input = row.get("original_input") or row.get("supplied_value")
    explicit_status = row.get("identity_status")
    if explicit_status is not None:
        identity_status = IdentityStatus(explicit_status)
    elif source == UniverseSource.USER_ENTERED:
        identity_status = IdentityStatus.UNRESOLVED
    else:
        identity_status = IdentityStatus.RESOLVED if ticker else IdentityStatus.UNRESOLVED
    metadata = {
        key: value for key, value in row.items()
        if key not in {"company_name", "name", "supplied_value", "ticker", "ticker_or_identifier", "normalized_ticker"}
    }
    return UniverseSourceRecord(
        source=source,
        company_name=company_name or str(ticker or "Unknown company"),
        ticker_or_identifier=str(ticker).strip().upper() if ticker else None,
        source_reference=source_reference,
        identity_status=identity_status,
        original_input=str(original_input).strip() if original_input else None,
        metadata=metadata,
    )


class ResearchUniverseReviewService:
    """Assemble and update one canonical review model for every source origin."""

    def assemble(
        self,
        *,
        universe_id: str,
        title: str,
        research_question: str = "",
        starting_companies: Sequence[UniverseSourceRecord] = (),
        rce_suggestions: Sequence[UniverseSourceRecord] = (),
        dispositions: Mapping[str, str | CandidateDisposition] | None = None,
        comments: Mapping[str, str] | None = None,
        owner_reference: str | None = None,
        version: int = 1,
        state: UniverseState = UniverseState.UNDER_REVIEW,
        provenance: Mapping[str, Any] | None = None,
        established_topic: str | None = None,
    ) -> ResearchUniverse:
        decisions = dict(dispositions or {})
        notes = dict(comments or {})
        starting = tuple(starting_companies)
        rce = tuple(rce_suggestions)
        groups = _canonical_partition((*starting, *rce))
        candidates: list[UniverseCandidate] = []

        for group in groups:
            ordered = group.source_records
            in_starting = any(item in starting for item in ordered)
            in_rce = any(item in rce for item in ordered)
            key = group.canonical_key
            if in_starting:
                default = CandidateDisposition.INCLUDED
            elif group.identity_status == IdentityStatus.AMBIGUOUS:
                default = CandidateDisposition.IDENTITY_REVIEW
            else:
                default = CandidateDisposition.PENDING
            disposition = CandidateDisposition(decisions.get(key, default))
            rce_record = next((item for item in ordered if item.source == UniverseSource.RCE_GENERATED), None)
            validation_status = (
                rce_record.metadata.get("identity_validation_status") if rce_record else None
            )
            if (
                in_rce and not in_starting
                and validation_status in {"unresolved", "rejected"}
                and disposition == CandidateDisposition.INCLUDED
            ):
                disposition = CandidateDisposition.IDENTITY_REVIEW
            rank_value = rce_record.metadata.get("rank") if rce_record else None
            try:
                rank = int(rank_value) if rank_value is not None else None
            except (TypeError, ValueError):
                rank = None
            candidates.append(UniverseCandidate(
                normalized_matching_key=key,
                company_name=group.company_name,
                ticker_or_identifier=group.ticker_or_identifier,
                identity_status=group.identity_status,
                original_input=next((item.original_input for item in ordered if item.original_input), None),
                in_starting_companies=in_starting,
                in_rce_suggestions=in_rce,
                source_records=ordered,
                disposition=disposition,
                inclusion_origin=(
                    "Explicit user entry" if any(item.source == UniverseSource.USER_ENTERED for item in ordered)
                    else "Starting company" if in_starting and not in_rce
                    else "Starting company and RCE suggestion agreement" if default == CandidateDisposition.INCLUDED
                    else "Explicit review decision" if disposition == CandidateDisposition.INCLUDED else None
                ),
                rejection_reason=notes.get(key) if disposition == CandidateDisposition.REJECTED else None,
                comment=notes.get(key),
                rce_rank=rank,
                rce_metadata=rce_record.metadata if rce_record else {},
            ))

        now = datetime.now(timezone.utc)
        order = {
            CandidateDisposition.IDENTITY_REVIEW: 0,
            CandidateDisposition.PENDING: 1,
            CandidateDisposition.REJECTED: 2,
            CandidateDisposition.DEFERRED: 3,
            CandidateDisposition.INCLUDED: 4,
        }
        candidates.sort(key=lambda row: (order[row.disposition], row.company_name.casefold()))
        return ResearchUniverse(
            universe_id=universe_id,
            title=title,
            research_question=research_question,
            state=state,
            version=version,
            candidates=tuple(candidates),
            created_at=now,
            updated_at=now,
            owner_reference=owner_reference,
            universe_type=UniverseType((provenance or {}).get("universe_type", UniverseType.PRIVATE_USER)),
            provenance=provenance or {},
            established_topic=established_topic,
        )

    def revise(
        self,
        universe: ResearchUniverse,
        *,
        dispositions: Mapping[str, str | CandidateDisposition] | None = None,
        additional_starting_companies: Sequence[UniverseSourceRecord] = (),
    ) -> ResearchUniverse:
        """Rebuild session review state from immutable canonical source records."""
        starting = tuple(
            record for candidate in universe.candidates for record in candidate.source_records
            if record.source != UniverseSource.RCE_GENERATED
        ) + tuple(additional_starting_companies)
        suggestions = tuple(
            record for candidate in universe.candidates for record in candidate.source_records
            if record.source == UniverseSource.RCE_GENERATED
        )
        decisions = {
            candidate.normalized_matching_key: candidate.disposition
            for candidate in universe.candidates
            if candidate.disposition != CandidateDisposition.INCLUDED or not candidate.in_starting_companies
        }
        # Explicit additions reset only the finalized group that owns their evidence.
        added_fingerprints = {
            _source_fingerprint(record) for record in additional_starting_companies
        }
        for group in _canonical_partition((*starting, *suggestions)):
            if any(
                _source_fingerprint(record) in added_fingerprints
                for record in group.source_records
            ):
                decisions.pop(group.canonical_key, None)
        decisions.update(dispositions or {})
        revised = self.assemble(
            universe_id=universe.universe_id,
            title=universe.title,
            research_question=universe.research_question,
            starting_companies=starting,
            rce_suggestions=suggestions,
            dispositions=decisions,
            owner_reference=universe.owner_reference,
            version=universe.version,
            state=universe.state,
            provenance=universe.provenance,
            established_topic=universe.established_topic,
        )
        before_membership = {
            row.normalized_matching_key for row in universe.approved_membership
        }
        after_membership = {
            row.normalized_matching_key for row in revised.approved_membership
        }
        next_version = universe.version + 1 if before_membership != after_membership else universe.version
        return replace(revised, created_at=universe.created_at, version=next_version)

    def remove_members(self, universe: ResearchUniverse, matching_keys: Iterable[str]) -> ResearchUniverse:
        """Remove current members without deleting their immutable source evidence."""
        return self.revise(
            universe,
            dispositions={key: CandidateDisposition.REJECTED for key in matching_keys},
        )

    def from_curator_comparison(
        self,
        comparison: Any,
        approved_keys: Iterable[str] = (),
    ) -> ResearchUniverse:
        approved = set(approved_keys)
        starting: list[UniverseSourceRecord] = []
        rce: list[UniverseSourceRecord] = []
        decisions: dict[str, CandidateDisposition] = {}
        for row in comparison.rows:
            base = {
                "company_name": row.company_name,
                "ticker_or_identifier": row.ticker_or_identifier,
                "source_pages": row.source_pages,
            }
            if row.appears_in_authored_corpus:
                starting.append(source_record(
                    base, UniverseSource.CURATOR_AUTHORED,
                    source_reference=f"authored:{comparison.benchmark_id}:{comparison.source_corpus_version}",
                ))
            if row.appears_in_rce_corpus:
                rce.append(source_record(
                    {**base, "rank": row.rce_rank, "validation_status": row.validation_status},
                    UniverseSource.RCE_GENERATED,
                    source_reference=f"rce:{comparison.benchmark_id}",
                ))
            if row.normalized_matching_key in approved:
                decisions[normalized_matching_key(
                    row.company_name, row.ticker_or_identifier,
                )] = CandidateDisposition.INCLUDED
        return self.assemble(
            universe_id=comparison.benchmark_id,
            title=getattr(comparison, "benchmark_id", "Research Universe"),
            starting_companies=starting,
            rce_suggestions=rce,
            dispositions=decisions,
            provenance={"adapter": "existing_curator_workflow"},
        )
