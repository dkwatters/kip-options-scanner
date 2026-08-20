from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.research_universe_api_service import (
    ApprovalEnvelope,
    ApprovedMember,
    ResearchUniverseAPIError,
    ResearchUniverseAPIService,
    membership_digest,
)
from src.research_universe_repository import ResearchUniverseRepository


class MemoryRepository(ResearchUniverseRepository):
    def __init__(self):
        self.rows = {}

    def initialize(self):
        return None

    def save(self, universe):
        self.rows[universe.universe_id] = universe
        return universe

    def get(self, universe_id):
        return self.rows.get(universe_id)

    def list_all(self):
        return tuple(self.rows.values())

    def list_orphaned_snapshots(self):
        return ()


def approval_for(members):
    return ApprovalEnvelope(
        actor="chat-user",
        mechanism="explicit_conversation_confirmation",
        approved_at=datetime.now(timezone.utc).isoformat(),
        membership_digest=membership_digest(members),
        source_reference="conversation:approval-message",
        conversation_reference="conversation:test",
    )


def test_membership_digest_is_order_and_content_bound():
    first = (ApprovedMember("Alpha"), ApprovedMember("Beta"))
    reversed_members = tuple(reversed(first))
    changed = (ApprovedMember("Alpha"), ApprovedMember("Gamma"))
    assert membership_digest(first) != membership_digest(reversed_members)
    assert membership_digest(first) != membership_digest(changed)


def test_create_persists_exact_approved_membership_without_network_resolution():
    repository = MemoryRepository()
    service = ResearchUniverseAPIService(repository)
    members = (ApprovedMember("Alpha Research Co"), ApprovedMember("Beta Systems"))

    universe = service.create_approved_universe(
        universe_id="api-test-universe",
        title="Approved API Universe",
        research_question="Which companies matter?",
        members=members,
        approval=approval_for(members),
    )

    assert universe.state.value == "approved"
    assert universe.universe_id == "api-test-universe"
    assert [row.company_name for row in universe.approved_membership] == [
        "Alpha Research Co", "Beta Systems"
    ]
    assert repository.get("api-test-universe") is universe
    assert universe.provenance["approval"]["membership_digest"] == membership_digest(members)


def test_create_rejects_mutated_membership_after_approval():
    repository = MemoryRepository()
    service = ResearchUniverseAPIService(repository)
    approved = (ApprovedMember("Alpha"),)
    mutated = (ApprovedMember("Alpha"), ApprovedMember("Beta"))

    with pytest.raises(ResearchUniverseAPIError, match="membership digest"):
        service.create_approved_universe(
            title="Mutated",
            research_question="",
            members=mutated,
            approval=approval_for(approved),
        )
    assert repository.list_all() == ()


def test_create_rejects_non_explicit_approval_mechanism():
    repository = MemoryRepository()
    service = ResearchUniverseAPIService(repository)
    members = (ApprovedMember("Alpha"),)
    approval = approval_for(members)
    invalid = ApprovalEnvelope(
        actor=approval.actor,
        mechanism="implicit_context",
        approved_at=approval.approved_at,
        membership_digest=approval.membership_digest,
        source_reference=approval.source_reference,
    )

    with pytest.raises(ResearchUniverseAPIError, match="approval mechanism"):
        service.create_approved_universe(
            title="No implicit approval",
            research_question="",
            members=members,
            approval=invalid,
        )
