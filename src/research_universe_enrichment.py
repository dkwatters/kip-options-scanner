"""Provider-neutral, omission-oriented Research Universe enrichment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.candidate_identity_validation import (
    CandidateIdentityValidationResultV01,
    CandidateIdentityValidationStatus,
    CandidateIdentityValidatorV01,
    normalized_company_identity,
)
from src.research_conversation import ResearchConversationRequest, ResearchConversationResponse
from src.research_universe import normalized_matching_key
from src.research_universe_discovery_context import (
    DiscoveryLens,
    MembershipProvenanceSource,
    MembershipProvenanceV01,
    ResearchUniverseDiscoveryContextV01,
)


ENRICHMENT_REQUEST_SCHEMA_VERSION = "research-universe-enrichment-request-v0.1"
ENRICHMENT_RESPONSE_SCHEMA_VERSION = "research-universe-enrichment-response-v0.1"
ENRICHMENT_PROMPT_VERSION = "rce-context-aware-universe-enrichment-v0.1"
CANDIDATE_STATE_PENDING = "pending"


class EnrichmentProvider(Protocol):
    provider_name: str

    def interpret(self, request: ResearchConversationRequest) -> ResearchConversationResponse: ...


@dataclass(frozen=True, slots=True)
class ResearchUniverseEnrichmentRequestV01:
    discovery_context: ResearchUniverseDiscoveryContextV01
    workflow_marker: str = "research_universe_context_aware_enrichment"
    evidence_requirements: tuple[str, ...] = (
        "publicly_available_source_reference",
        "material_coverage_addition",
    )
    candidate_output_constraints: tuple[str, ...] = (
        "publicly_traded_preferred",
        "exclude_known_seed_members",
        "pending_suggestions_only",
        "no_automatic_promotion",
    )
    schema_version: str = ENRICHMENT_REQUEST_SCHEMA_VERSION

    @property
    def known_member_keys(self) -> tuple[str, ...]:
        return tuple(row.matching_key for row in self.discovery_context.seed_universe)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_marker": self.workflow_marker,
            "research_question": self.discovery_context.research_question,
            "discovery_context": self.discovery_context.to_dict(),
            "seed_members": [row.to_dict() for row in self.discovery_context.seed_universe],
            "predefined_universe": (
                self.discovery_context.predefined_universe.to_dict()
                if self.discovery_context.predefined_universe else None
            ),
            "active_discovery_lenses": [row.value for row in self.discovery_context.discovery_lenses],
            "known_member_keys": list(self.known_member_keys),
            "evidence_requirements": list(self.evidence_requirements),
            "candidate_output_constraints": list(self.candidate_output_constraints),
        }

    def provider_request(self) -> ResearchConversationRequest:
        return ResearchConversationRequest(
            original_question=self.discovery_context.research_question,
            prompt_version=ENRICHMENT_PROMPT_VERSION,
            request_origin="research_universe_enrichment",
            context={"enrichment_request": self.to_dict()},
            anchor_companies=tuple(
                row.ticker_or_identifier or row.company_name
                for row in self.discovery_context.seed_universe
            ),
        )


@dataclass(frozen=True, slots=True)
class RCEEnrichmentCandidateV01:
    candidate_identity: str
    company_name: str
    ticker_or_identifier: str | None
    discovery_lenses: tuple[DiscoveryLens, ...]
    related_seed_member_identities: tuple[str, ...]
    reason_discovered: str
    evidence_references: tuple[str, ...]
    provenance: tuple[MembershipProvenanceV01, ...]
    identity_validation: CandidateIdentityValidationResultV01
    duplicate_status: str = "not_in_seed_universe"
    candidate_state: str = CANDIDATE_STATE_PENDING
    support_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def validated_company_name(self) -> str | None:
        return self.identity_validation.normalized_company_name

    @property
    def validated_ticker_or_identifier(self) -> str | None:
        return self.identity_validation.normalized_ticker_or_identifier

    def to_source_mapping(self) -> dict[str, Any]:
        return {
            "company_name": self.validated_company_name or self.company_name,
            "ticker": self.validated_ticker_or_identifier,
            "raw_company_name": self.company_name,
            "raw_ticker_or_identifier": self.ticker_or_identifier,
            "candidate_identity_validation": self.identity_validation.to_dict(),
            "identity_validation_status": self.identity_validation.validation_status.value,
            "identity_status": (
                "resolved" if self.identity_validation.promotion_eligible else "unresolved"
            ),
            "inclusion_rationale": self.reason_discovered,
            "discovery_lenses": [row.value for row in self.discovery_lenses],
            "related_seed_member_identities": list(self.related_seed_member_identities),
            "evidence_references": list(self.evidence_references),
            "membership_provenance": [row.to_dict() for row in self.provenance],
            "candidate_identity": self.candidate_identity,
            "duplicate_status": self.duplicate_status,
            "candidate_state": self.candidate_state,
            **dict(self.support_metadata),
        }


@dataclass(frozen=True, slots=True)
class ResearchUniverseEnrichmentResponseV01:
    request: ResearchUniverseEnrichmentRequestV01
    candidates: tuple[RCEEnrichmentCandidateV01, ...]
    provider_response: ResearchConversationResponse
    suppressed_seed_duplicates: tuple[str, ...]
    warnings: tuple[str, ...]
    schema_version: str = ENRICHMENT_RESPONSE_SCHEMA_VERSION


class ResearchUniverseEnrichmentService:
    def __init__(
        self,
        provider: EnrichmentProvider,
        identity_validator: CandidateIdentityValidatorV01 | None = None,
    ):
        self.provider = provider
        self.identity_validator = identity_validator or CandidateIdentityValidatorV01()

    def enrich(self, request: ResearchUniverseEnrichmentRequestV01) -> ResearchUniverseEnrichmentResponseV01:
        response = self.provider.interpret(request.provider_request())
        rows = response.structured_response.get("candidate_securities", [])
        seed_keys = set(request.known_member_keys)
        seed_company_keys = {
            normalized_company_identity(row.company_name)
            for row in request.discovery_context.seed_universe
        }
        seed_ids = {row.matching_key: row.member_identity for row in request.discovery_context.seed_universe}
        candidates = []
        suppressed = []
        warnings = list(response.warnings)
        seen = set()
        for row in rows if isinstance(rows, list) else ():
            if not isinstance(row, Mapping):
                continue
            ticker = str(row.get("ticker") or "").strip().upper() or None
            company = str(row.get("company_name") or ticker or "").strip()
            if not company:
                continue
            key = normalized_matching_key(company, ticker)
            try:
                lenses = tuple(dict.fromkeys(DiscoveryLens(value) for value in row.get("discovery_lenses", ())))
            except ValueError:
                warnings.append(f"Candidate {ticker or company} used an unsupported Discovery Lens.")
                continue
            evidence = tuple(dict.fromkeys(str(value).strip() for value in row.get("evidence_references", ()) if str(value).strip()))
            reason = str(row.get("reason_discovered") or row.get("inclusion_rationale") or "").strip()
            related = tuple(dict.fromkeys(
                seed_ids[value] for value in row.get("related_seed_matching_keys", ()) if value in seed_ids
            ))
            if not lenses or not evidence or not reason:
                warnings.append(f"Candidate {ticker or company} lacked required lens, reason, or evidence support.")
                continue
            identity = str(uuid5(NAMESPACE_URL, f"{ENRICHMENT_RESPONSE_SCHEMA_VERSION}:{request.discovery_context.context_identity}:{key}"))
            validation = self.identity_validator.validate(
                candidate_id=identity,
                company_name=company,
                ticker_or_identifier=ticker,
            )
            validated_key = (
                normalized_matching_key(
                    validation.normalized_company_name or company,
                    validation.normalized_ticker_or_identifier,
                )
                if validation.validation_status in {
                    CandidateIdentityValidationStatus.VALID,
                    CandidateIdentityValidationStatus.CORRECTED,
                }
                else key
            )
            duplicate_status = "not_in_seed_universe"
            if validated_key in seed_keys:
                suppressed.append(validated_key)
                continue
            validated_name_key = normalized_company_identity(
                validation.normalized_company_name or company
            )
            if validated_name_key and validated_name_key in seed_company_keys:
                suppressed.append(validated_key)
                continue
            if validated_key in seen:
                continue
            candidates.append(RCEEnrichmentCandidateV01(
                candidate_identity=identity,
                company_name=company,
                ticker_or_identifier=ticker,
                discovery_lenses=lenses,
                related_seed_member_identities=related,
                reason_discovered=reason,
                evidence_references=evidence,
                provenance=(MembershipProvenanceV01(
                    MembershipProvenanceSource.RCE_DISCOVERED,
                    source_identity=identity,
                    source_reference=evidence[0],
                ),),
                identity_validation=validation,
                duplicate_status=duplicate_status,
                support_metadata={
                    key: row[key] for key in ("confidence", "support") if row.get(key) is not None
                },
            ))
            seen.add(validated_key)
        return ResearchUniverseEnrichmentResponseV01(
            request=request,
            candidates=tuple(candidates),
            provider_response=response,
            suppressed_seed_duplicates=tuple(dict.fromkeys(suppressed)),
            warnings=tuple(dict.fromkeys(warnings)),
        )
