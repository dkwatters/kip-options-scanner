"""Canonical, presentation-neutral Research Universe review model.

Starting-company source types are provenance only.  They never select a
different matcher, disposition policy, review workflow, or downstream handoff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


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

        starting_by_name = self._by_name(starting)
        rce_by_name = self._by_name(rce)
        starting_by_ticker = self._by_ticker(starting)
        rce_by_ticker = self._by_ticker(rce)
        visited: set[int] = set()
        candidates: list[UniverseCandidate] = []

        for record in (*starting, *rce):
            if id(record) in visited:
                continue
            ticker_keys = _ticker_keys(record.ticker_or_identifier)
            name_key = _name_key(record.company_name)
            ticker_matches = {
                item for ticker in ticker_keys
                for item in (*starting_by_ticker.get(ticker, ()), *rce_by_ticker.get(ticker, ()))
            }
            alias_key = _name_alias_key(record.company_name)
            name_matches = set((*starting_by_name.get(name_key, ()), *rce_by_name.get(name_key, ())))
            if alias_key:
                name_matches.update((*starting_by_name.get(alias_key, ()), *rce_by_name.get(alias_key, ())))
            conflict = bool(ticker_keys and (name_matches - ticker_matches))
            matches = ticker_matches if ticker_keys else name_matches
            if not matches:
                matches = {record}
            visited.update(id(item) for item in matches)
            ordered = tuple(item for item in (*starting, *rce) if item in matches)
            in_starting = any(item in starting for item in ordered)
            in_rce = any(item in rce for item in ordered)
            resolved_records = tuple(item for item in ordered if item.identity_status == IdentityStatus.RESOLVED)
            selected = next((item for item in resolved_records if item.ticker_or_identifier), None)
            selected = selected or next((item for item in ordered if item.ticker_or_identifier), ordered[0])
            identity_status = (
                IdentityStatus.AMBIGUOUS if conflict
                else IdentityStatus.RESOLVED if resolved_records
                else IdentityStatus.UNRESOLVED
            )
            key = normalized_matching_key(selected.company_name, selected.ticker_or_identifier)
            if in_starting:
                default = CandidateDisposition.INCLUDED
            elif conflict or len({normalized_matching_key(item.company_name, item.ticker_or_identifier) for item in ordered}) > 1:
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
                company_name=selected.company_name,
                ticker_or_identifier=selected.ticker_or_identifier,
                identity_status=identity_status,
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
        # Explicit additions confirm membership, including a previously rejected
        # suggestion. Identity matching and membership disposition are separate.
        for record in additional_starting_companies:
            ticker_keys = _ticker_keys(record.ticker_or_identifier)
            name_keys = {_name_key(record.company_name), _name_alias_key(record.company_name)} - {""}
            for candidate in universe.candidates:
                if (
                    ticker_keys.intersection(_ticker_keys(candidate.ticker_or_identifier))
                    or _name_key(candidate.company_name) in name_keys
                    or _name_alias_key(candidate.company_name) in name_keys
                ):
                    decisions.pop(candidate.normalized_matching_key, None)
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

    @staticmethod
    def _by_name(records: Sequence[UniverseSourceRecord]) -> dict[str, tuple[UniverseSourceRecord, ...]]:
        grouped: dict[str, list[UniverseSourceRecord]] = {}
        for row in records:
            for key in {_name_key(row.company_name), _name_alias_key(row.company_name)} - {""}:
                grouped.setdefault(key, []).append(row)
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _by_ticker(records: Sequence[UniverseSourceRecord]) -> dict[str, tuple[UniverseSourceRecord, ...]]:
        grouped: dict[str, list[UniverseSourceRecord]] = {}
        for row in records:
            for ticker in _ticker_keys(row.ticker_or_identifier):
                grouped.setdefault(ticker, []).append(row)
        return {key: tuple(value) for key, value in grouped.items()}
