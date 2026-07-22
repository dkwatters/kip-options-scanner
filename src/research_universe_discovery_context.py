"""Deterministic context boundary for future Research Universe discovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5

from src.research_universe import UniverseSourceRecord, normalized_matching_key


DISCOVERY_CONTEXT_SCHEMA_VERSION = "research-universe-discovery-context-v0.1"
DISCOVERY_LENS_VOCABULARY_VERSION = "discovery-lens-v0.1"
FUTURE_CANDIDATE_SCHEMA_VERSION = "research-universe-discovery-candidate-v0.1"


class MembershipProvenanceSource(StrEnum):
    PREDEFINED_UNIVERSE = "predefined_universe"
    MANUAL_ENTRY = "manual_entry"
    RCE_DISCOVERED = "rce_discovered"
    PROMOTED_CANDIDATE = "promoted_candidate"
    RECOVERED_SNAPSHOT = "recovered_snapshot"
    COMPATIBILITY_IMPORT = "compatibility_import"


class DiscoveryLens(StrEnum):
    DIRECT_COMPETITORS = "direct_competitors"
    INDUSTRY_LANDSCAPE_PEERS = "industry_landscape_peers"
    VALUE_CHAIN_RELATIONSHIPS = "value_chain_relationships"
    ADJACENT_BENEFICIARIES = "adjacent_beneficiaries"
    SUBSTITUTION_DISRUPTION_THREATS = "substitution_disruption_threats"
    CROSS_SEED_DEPENDENCIES = "cross_seed_dependencies"


DISCOVERY_LENSES_V01 = tuple(DiscoveryLens)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class MembershipProvenanceV01:
    source: MembershipProvenanceSource
    source_identity: str | None = None
    source_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "source_identity": self.source_identity,
            "source_reference": self.source_reference,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MembershipProvenanceV01":
        return cls(
            source=MembershipProvenanceSource(value["source"]),
            source_identity=value.get("source_identity"),
            source_reference=value.get("source_reference"),
        )


@dataclass(frozen=True, slots=True)
class DiscoverySeedMemberV01:
    member_identity: str
    matching_key: str
    company_name: str
    ticker_or_identifier: str | None
    identity_status: str
    provenance: tuple[MembershipProvenanceV01, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_identity": self.member_identity,
            "matching_key": self.matching_key,
            "company_name": self.company_name,
            "ticker_or_identifier": self.ticker_or_identifier,
            "identity_status": self.identity_status,
            "provenance": [row.to_dict() for row in self.provenance],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DiscoverySeedMemberV01":
        return cls(
            member_identity=str(value["member_identity"]),
            matching_key=str(value["matching_key"]),
            company_name=str(value["company_name"]),
            ticker_or_identifier=value.get("ticker_or_identifier"),
            identity_status=str(value["identity_status"]),
            provenance=tuple(MembershipProvenanceV01.from_dict(row) for row in value["provenance"]),
        )


@dataclass(frozen=True, slots=True)
class PredefinedUniverseContextV01:
    universe_identity: str
    universe_name: str | None = None
    source_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_identity": self.universe_identity,
            "universe_name": self.universe_name,
            "source_references": list(self.source_references),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PredefinedUniverseContextV01":
        return cls(str(value["universe_identity"]), value.get("universe_name"), tuple(value.get("source_references", ())))


@dataclass(frozen=True, slots=True)
class ResearchUniverseDiscoveryContextV01:
    context_identity: str
    research_question: str
    predefined_universe: PredefinedUniverseContextV01 | None
    manual_input: tuple[str, ...]
    seed_universe: tuple[DiscoverySeedMemberV01, ...]
    discovery_lenses: tuple[DiscoveryLens, ...] = DISCOVERY_LENSES_V01
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    creation_metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = DISCOVERY_CONTEXT_SCHEMA_VERSION
    lens_vocabulary_version: str = DISCOVERY_LENS_VOCABULARY_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DISCOVERY_CONTEXT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported discovery context version: {self.schema_version}")
        if self.lens_vocabulary_version != DISCOVERY_LENS_VOCABULARY_VERSION:
            raise ValueError(f"Unsupported Discovery Lens version: {self.lens_vocabulary_version}")
        if self.discovery_lenses != DISCOVERY_LENSES_V01:
            raise ValueError("Discovery Lens v0.1 must use the complete ordered vocabulary")
        object.__setattr__(self, "creation_metadata", dict(self.creation_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "context_identity": self.context_identity,
            "research_question": self.research_question,
            "predefined_universe": self.predefined_universe.to_dict() if self.predefined_universe else None,
            "manual_input": list(self.manual_input),
            "seed_universe": [row.to_dict() for row in self.seed_universe],
            "discovery_lenses": [row.value for row in self.discovery_lenses],
            "lens_vocabulary_version": self.lens_vocabulary_version,
            "created_at": _utc_iso(self.created_at),
            "creation_metadata": dict(self.creation_metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResearchUniverseDiscoveryContextV01":
        created_at = datetime.fromisoformat(str(value["created_at"]).replace("Z", "+00:00"))
        predefined = value.get("predefined_universe")
        return cls(
            schema_version=str(value["schema_version"]),
            context_identity=str(value["context_identity"]),
            research_question=str(value.get("research_question") or ""),
            predefined_universe=PredefinedUniverseContextV01.from_dict(predefined) if predefined else None,
            manual_input=tuple(value.get("manual_input", ())),
            seed_universe=tuple(DiscoverySeedMemberV01.from_dict(row) for row in value.get("seed_universe", ())),
            discovery_lenses=tuple(DiscoveryLens(row) for row in value.get("discovery_lenses", ())),
            lens_vocabulary_version=str(value["lens_vocabulary_version"]),
            created_at=created_at,
            creation_metadata=value.get("creation_metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class FutureRCECandidateV01:
    """Uninstantiated Sprint-B boundary; this sprint creates no candidate records."""
    candidate_identity: str
    company_name: str
    ticker_or_identifier: str | None
    discovery_lenses: tuple[DiscoveryLens, ...]
    related_seed_member_identities: tuple[str, ...]
    reason_discovered: str
    evidence_references: tuple[str, ...]
    provenance: tuple[MembershipProvenanceV01, ...]
    support_metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = FUTURE_CANDIDATE_SCHEMA_VERSION


def build_research_universe_discovery_context_v01(
    *,
    research_question: str,
    predefined_records: Iterable[UniverseSourceRecord] = (),
    manual_records: Iterable[UniverseSourceRecord] = (),
    manual_input: Iterable[str] = (),
    predefined_universe_identity: str | None = None,
    predefined_universe_name: str | None = None,
    created_at: datetime | None = None,
    creation_metadata: Mapping[str, Any] | None = None,
) -> ResearchUniverseDiscoveryContextV01:
    """Merge predefined then manual seeds without I/O, inference, or provider access."""
    groups: dict[str, list[tuple[UniverseSourceRecord, MembershipProvenanceV01]]] = {}
    order: list[str] = []
    predefined = tuple(predefined_records)
    manual = tuple(manual_records)
    for records, source, source_identity in (
        (predefined, MembershipProvenanceSource.PREDEFINED_UNIVERSE, predefined_universe_identity),
        (manual, MembershipProvenanceSource.MANUAL_ENTRY, None),
    ):
        for record in records:
            key = normalized_matching_key(record.company_name, record.ticker_or_identifier)
            if key not in groups:
                groups[key] = []
                order.append(key)
            provenance = MembershipProvenanceV01(source, source_identity, record.source_reference)
            if provenance not in (item[1] for item in groups[key]):
                groups[key].append((record, provenance))

    members = []
    for key in order:
        rows = groups[key]
        selected = next((row for row, _ in rows if row.ticker_or_identifier), rows[0][0])
        identity = str(uuid5(NAMESPACE_URL, f"{DISCOVERY_CONTEXT_SCHEMA_VERSION}:member:{key}"))
        members.append(DiscoverySeedMemberV01(
            member_identity=identity,
            matching_key=key,
            company_name=selected.company_name,
            ticker_or_identifier=selected.ticker_or_identifier,
            identity_status=selected.identity_status.value,
            provenance=tuple(provenance for _, provenance in rows),
        ))

    supplied_manual = tuple(dict.fromkeys(str(value).strip() for value in manual_input if str(value).strip()))
    signature = "|".join((research_question.strip(), predefined_universe_identity or "", *supplied_manual, *order))
    context_identity = str(uuid5(NAMESPACE_URL, f"{DISCOVERY_CONTEXT_SCHEMA_VERSION}:{signature}"))
    references = tuple(dict.fromkeys(row.source_reference for row in predefined if row.source_reference))
    predefined_context = (
        PredefinedUniverseContextV01(predefined_universe_identity, predefined_universe_name, references)
        if predefined_universe_identity else None
    )
    return ResearchUniverseDiscoveryContextV01(
        context_identity=context_identity,
        research_question=research_question.strip(),
        predefined_universe=predefined_context,
        manual_input=supplied_manual,
        seed_universe=tuple(members),
        created_at=created_at or datetime.now(timezone.utc),
        creation_metadata=creation_metadata or {},
    )
