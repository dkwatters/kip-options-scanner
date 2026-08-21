"""Presentation-neutral API service for explicitly approved Research Universes."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from src.research_universe import (
    ResearchUniverse,
    ResearchUniverseReviewService,
    UniverseSource,
    UniverseState,
    UniverseType,
    source_record,
)
from src.research_universe_entry import (
    ResearchUniverseEntryMethod,
    entry_method_provenance,
    research_universe_entry_method,
)
from src.research_universe_input import configured_research_universe_input_service
from src.research_universe_repository import ResearchUniverseRepository


class ResearchUniverseAPIError(ValueError):
    """Raised when an API creation request violates the approval contract."""


@dataclass(frozen=True, slots=True)
class ApprovedMember:
    company_name: str
    ticker_or_identifier: str | None = None

    def canonical_payload(self) -> dict[str, str | None]:
        return {
            "company_name": " ".join(self.company_name.split()),
            "ticker_or_identifier": (
                self.ticker_or_identifier.strip().upper()
                if self.ticker_or_identifier else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ApprovalEnvelope:
    actor: str
    mechanism: str
    approved_at: str
    membership_digest: str
    source_reference: str
    conversation_reference: str | None = None


def membership_digest(members: Iterable[ApprovedMember]) -> str:
    """Bind approval to the exact ordered membership supplied by the caller."""
    payload = [member.canonical_payload() for member in members]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def universe_to_dict(universe: ResearchUniverse) -> dict[str, Any]:
    return {
        "universe_id": universe.universe_id,
        "title": universe.title,
        "research_question": universe.research_question,
        "entry_method": research_universe_entry_method(universe.provenance).value,
        "state": universe.state.value,
        "version": universe.version,
        "created_at": universe.created_at.isoformat(),
        "updated_at": universe.updated_at.isoformat(),
        "universe_type": universe.universe_type.value,
        "members": [
            {
                "matching_key": row.normalized_matching_key,
                "company_name": row.company_name,
                "ticker_or_identifier": row.ticker_or_identifier,
                "identity_status": row.identity_status.value,
            }
            for row in universe.approved_membership
        ],
        "provenance": dict(universe.provenance),
    }


class ResearchUniverseAPIService:
    """Read and create durable universes without exposing repository internals."""

    def __init__(self, repository: ResearchUniverseRepository):
        self.repository = repository

    def list_universes(self) -> tuple[ResearchUniverse, ...]:
        return self.repository.list_all()

    def get_universe(self, universe_id: str) -> ResearchUniverse | None:
        return self.repository.get(universe_id)

    def create_approved_universe(
        self,
        *,
        title: str,
        research_question: str,
        original_request: str,
        entry_method: ResearchUniverseEntryMethod,
        members: Iterable[ApprovedMember],
        approval: ApprovalEnvelope,
        universe_id: str | None = None,
    ) -> ResearchUniverse:
        approved_members = tuple(members)
        if not title.strip():
            raise ResearchUniverseAPIError("title is required")
        if not original_request.strip():
            raise ResearchUniverseAPIError("original_request is required")
        if not approved_members:
            raise ResearchUniverseAPIError("at least one approved member is required")
        if approval.mechanism != "explicit_conversation_confirmation":
            raise ResearchUniverseAPIError("unsupported approval mechanism")
        if not approval.actor.strip() or not approval.source_reference.strip():
            raise ResearchUniverseAPIError("approval actor and source_reference are required")
        try:
            approved_at = datetime.fromisoformat(approval.approved_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ResearchUniverseAPIError("approved_at must be ISO-8601") from error
        if approved_at.tzinfo is None:
            raise ResearchUniverseAPIError("approved_at must include a timezone")
        expected_digest = membership_digest(approved_members)
        if not hashlib.compare_digest(expected_digest, approval.membership_digest.lower()):
            raise ResearchUniverseAPIError("membership digest does not match approved membership")

        created_id = universe_id or str(uuid4())
        ticker_members = tuple(
            member for member in approved_members if member.ticker_or_identifier
        )
        raw_tickers = ",".join(
            member.ticker_or_identifier or "" for member in ticker_members
        )
        resolved_by_ticker: dict[str, Any] = {}
        if raw_tickers:
            _, resolved = configured_research_universe_input_service().resolve(
                raw_tickers,
                source_reference=f"api:{created_id}:approved-membership",
            )
            resolved_by_ticker = {
                (record.ticker_or_identifier or "").upper(): record for record in resolved
            }

        records = []
        for index, member in enumerate(approved_members):
            normalized = member.canonical_payload()
            ticker = normalized["ticker_or_identifier"]
            resolved = resolved_by_ticker.get(ticker or "")
            if resolved is not None:
                records.append(source_record(
                    {
                        "company_name": normalized["company_name"] or resolved.company_name,
                        "ticker": ticker,
                        "original_input": member.company_name,
                        "identity_status": resolved.identity_status.value,
                        **dict(resolved.metadata),
                    },
                    UniverseSource.USER_ENTERED,
                    source_reference=f"api:{created_id}:member:{index}",
                ))
            else:
                records.append(source_record(
                    {
                        "company_name": normalized["company_name"],
                        "ticker": ticker,
                        "original_input": member.company_name,
                        "identity_status": "unresolved",
                        "identity_resolution": "not_supplied_or_not_validated",
                    },
                    UniverseSource.USER_ENTERED,
                    source_reference=f"api:{created_id}:member:{index}",
                ))

        universe = ResearchUniverseReviewService().assemble(
            universe_id=created_id,
            title=title.strip(),
            research_question=research_question.strip(),
            starting_companies=tuple(records),
            state=UniverseState.APPROVED,
            provenance={
                "persistence": "research_universe_repository",
                "universe_type": UniverseType.PRIVATE_USER,
                "creation_workflow": "research_universe_api_v0.1",
                **entry_method_provenance(
                    entry_method,
                    original_request=original_request,
                    source_metadata={
                        "approval_source_reference": approval.source_reference,
                        "conversation_reference": approval.conversation_reference,
                    },
                ),
                "approval": {
                    "actor": approval.actor,
                    "mechanism": approval.mechanism,
                    "approved_at": approved_at.astimezone(timezone.utc).isoformat(),
                    "membership_digest": expected_digest,
                    "source_reference": approval.source_reference,
                    "conversation_reference": approval.conversation_reference,
                },
            },
        )
        if len(universe.approved_membership) != len(approved_members):
            raise ResearchUniverseAPIError(
                "canonicalization changed approved membership cardinality; creation refused"
            )
        return self.repository.save(universe)
