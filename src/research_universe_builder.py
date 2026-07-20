"""Session-safe models and orchestration for free-form research universes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from src.research_conversation import ResearchConversationRequest, ResearchConversationResponse, utc_now
from src.research_universe import CandidateDisposition, UniverseState

GENERAL_USER_ORIGIN = "general_user"


@dataclass(frozen=True)
class AnchorCompany:
    supplied_value: str
    normalized_company_name: str | None = None
    normalized_ticker: str | None = None


@dataclass(frozen=True)
class AnchorReview:
    supplied_value: str
    normalized_company_name: str | None
    normalized_ticker: str | None
    disposition: str
    explanation: str | None = None


@dataclass
class ResearchUniverseDraft:
    research_universe_id: str
    original_question: str
    original_anchor_input: str
    anchors: tuple[AnchorCompany, ...]
    request: ResearchConversationRequest
    response: ResearchConversationResponse
    generated_at: datetime
    approved_candidate_keys: set[str] = field(default_factory=set)
    rejected_candidate_keys: set[str] = field(default_factory=set)
    inclusion_origins: dict[str, str] = field(default_factory=dict)
    universe_state: UniverseState = UniverseState.UNDER_REVIEW

    @property
    def candidates(self) -> tuple[Mapping[str, Any], ...]:
        value = self.response.structured_response.get("candidate_securities", [])
        return tuple(row for row in value if isinstance(row, Mapping))

    def approve(self, candidate: Mapping[str, Any]) -> None:
        key = candidate_key(candidate)
        self.approved_candidate_keys.add(key)
        self.rejected_candidate_keys.discard(key)
        self.inclusion_origins[key] = "User approval from RCE Candidate Universe"

    def set_disposition(self, key: str, disposition: str) -> None:
        decision = CandidateDisposition(disposition)
        if decision == CandidateDisposition.INCLUDED:
            self.approved_candidate_keys.add(key)
            self.rejected_candidate_keys.discard(key)
            self.inclusion_origins[key] = "Explicit review decision"
        elif decision == CandidateDisposition.REJECTED:
            self.rejected_candidate_keys.add(key)
            self.approved_candidate_keys.discard(key)
            self.inclusion_origins.pop(key, None)
        else:
            self.approved_candidate_keys.discard(key)
            self.rejected_candidate_keys.discard(key)
            self.inclusion_origins.pop(key, None)

    def approve_universe(self) -> None:
        self.universe_state = UniverseState.APPROVED


def parse_anchor_companies(raw: str) -> tuple[AnchorCompany, ...]:
    """Compatibility projection of the shared ticker-only parser."""
    from src.research_universe_input import parse_ticker_input

    return tuple(
        AnchorCompany(row.original_input, normalized_ticker=row.ticker)
        for row in parse_ticker_input(raw).entries
    )


def build_free_form_request(question: str, anchors: tuple[AnchorCompany, ...]) -> ResearchConversationRequest:
    return ResearchConversationRequest(
        original_question=question.strip(),
        anchor_companies=tuple(row.supplied_value for row in anchors),
        request_origin=GENERAL_USER_ORIGIN,
        context={"workflow": "research_universe_builder"},
    )


def candidate_key(candidate: Mapping[str, Any]) -> str:
    ticker = str(candidate.get("ticker") or "").strip().upper()
    name = " ".join(str(candidate.get("company_name") or "").casefold().split())
    return f"ticker:{ticker}" if ticker else f"name:{name}"


def reconcile_anchors(anchors: tuple[AnchorCompany, ...], candidates: tuple[Mapping[str, Any], ...],
                      provider_review: Any = None) -> tuple[AnchorReview, ...]:
    """Honestly reconcile anchors; malformed provider review is ignored safely."""
    reviews = provider_review if isinstance(provider_review, list) else []
    supplied_reviews = {
        str(row.get("supplied_value", "")).casefold(): row for row in reviews if isinstance(row, dict)
    }
    tickers = {str(row.get("ticker") or "").strip().upper() for row in candidates}
    names = {" ".join(str(row.get("company_name") or "").casefold().split()) for row in candidates}
    result = []
    for anchor in anchors:
        returned = ((anchor.normalized_ticker or "") in tickers or
                    (anchor.normalized_company_name or "").casefold() in names)
        supplied = supplied_reviews.get(anchor.supplied_value.casefold(), {})
        disposition = "included" if returned else "not_included"
        if supplied.get("disposition") in {"included", "not_included", "unresolved"}:
            disposition = supplied["disposition"]
        explanation = supplied.get("explanation")
        result.append(AnchorReview(
            anchor.supplied_value,
            supplied.get("normalized_company_name") or anchor.normalized_company_name,
            supplied.get("normalized_ticker") or anchor.normalized_ticker,
            disposition,
            explanation if isinstance(explanation, str) and explanation.strip() else None,
        ))
    return tuple(result)


def create_draft(question: str, original_anchor_input: str, anchors: tuple[AnchorCompany, ...],
                 request: ResearchConversationRequest, response: ResearchConversationResponse) -> ResearchUniverseDraft:
    return ResearchUniverseDraft(str(uuid4()), question, original_anchor_input, anchors, request, response, utc_now())


FUTURE_REFINEMENT_FIELDS = (
    "original_question", "current_benchmark_of_record", "accepted_candidates",
    "rejected_candidates", "deferred_candidates", "curator_comments", "previous_rce_candidate_corpus",
)
