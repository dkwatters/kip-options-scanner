"""Minimal authenticated HTTP API for approved Research Universe interoperability."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.research_universe_api_service import (
    ApprovalEnvelope,
    ApprovedMember,
    ResearchUniverseAPIError,
    ResearchUniverseAPIService,
    universe_to_dict,
)
from src.research_universe_entry import ResearchUniverseEntryMethod
from src.research_universe_repository import research_universe_repository_from_env


app = FastAPI(title="Kip Options Research Universe API", version="0.1.0")


class MemberRequest(BaseModel):
    company_name: str = Field(min_length=1)
    ticker_or_identifier: str | None = None


class ApprovalRequest(BaseModel):
    actor: str = Field(min_length=1)
    mechanism: str
    approved_at: str
    membership_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    source_reference: str = Field(min_length=1)
    conversation_reference: str | None = None


class CreateUniverseRequest(BaseModel):
    title: str = Field(min_length=1)
    research_question: str = ""
    original_request: str = Field(min_length=1)
    entry_method: ResearchUniverseEntryMethod = ResearchUniverseEntryMethod.CONVERSATIONAL_RESEARCH
    members: list[MemberRequest] = Field(min_length=1)
    approval: ApprovalRequest


def _authorize(authorization: Annotated[str | None, Header()] = None) -> None:
    configured = os.getenv("RESEARCH_API_KEY", "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research API authentication is not configured.",
        )
    expected = f"Bearer {configured}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _service() -> ResearchUniverseAPIService:
    return ResearchUniverseAPIService(research_universe_repository_from_env())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "api_version": "0.1.0"}


@app.get("/api/v1/universes", dependencies=[Depends(_authorize)])
def list_universes() -> dict:
    universes = _service().list_universes()
    return {"universes": [universe_to_dict(row) for row in universes]}


@app.get("/api/v1/universes/{universe_id}", dependencies=[Depends(_authorize)])
def get_universe(universe_id: str) -> dict:
    universe = _service().get_universe(universe_id)
    if universe is None:
        raise HTTPException(status_code=404, detail="Research Universe not found.")
    return universe_to_dict(universe)


@app.post(
    "/api/v1/universes",
    dependencies=[Depends(_authorize)],
    status_code=status.HTTP_201_CREATED,
)
def create_universe(request: CreateUniverseRequest) -> dict:
    try:
        universe = _service().create_approved_universe(
            title=request.title,
            research_question=request.research_question,
            original_request=request.original_request,
            entry_method=request.entry_method,
            members=tuple(
                ApprovedMember(
                    company_name=row.company_name,
                    ticker_or_identifier=row.ticker_or_identifier,
                )
                for row in request.members
            ),
            approval=ApprovalEnvelope(**request.approval.model_dump()),
        )
    except ResearchUniverseAPIError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return universe_to_dict(universe)
