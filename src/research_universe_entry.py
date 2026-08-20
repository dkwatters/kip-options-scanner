"""Typed entry-method contract for canonical Research Universe creation.

Entry method is provenance, not a behavior switch. Downstream review, identity,
analysis, scoring, and persistence must operate on the same ResearchUniverse
contract regardless of how the universe entered the system.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class ResearchUniverseEntryMethod(StrEnum):
    UNSPECIFIED = "unspecified"
    RESEARCH_LAUNCHPAD = "research_launchpad"
    CONVERSATIONAL_RESEARCH = "conversational_research"
    MANUAL_ENTRY = "manual_entry"
    ESTABLISHED_TOPIC = "established_topic"
    SAVED_UNIVERSE = "saved_universe"
    IMPORTED_LIST = "imported_list"
    BROKERAGE_PORTFOLIO = "brokerage_portfolio"
    PORTFOLIO_SERVICE_IMPORT = "portfolio_service_import"
    WATCHLIST_IMPORT = "watchlist_import"
    COMPANY_ANALYSIS_PEERS = "company_analysis_peers"


ENTRY_METHOD_PROVENANCE_KEY = "entry_method"
ORIGINAL_REQUEST_PROVENANCE_KEY = "original_request"


def entry_method_provenance(
    method: ResearchUniverseEntryMethod,
    *,
    original_request: str | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the normalized provenance envelope for one universe entry method."""
    value: dict[str, Any] = {ENTRY_METHOD_PROVENANCE_KEY: method.value}
    if original_request is not None:
        value[ORIGINAL_REQUEST_PROVENANCE_KEY] = original_request
    if source_metadata:
        value["entry_source_metadata"] = dict(source_metadata)
    return value


def research_universe_entry_method(provenance: Mapping[str, Any]) -> ResearchUniverseEntryMethod:
    """Read persisted entry method conservatively for legacy universes."""
    raw = provenance.get(ENTRY_METHOD_PROVENANCE_KEY)
    try:
        return ResearchUniverseEntryMethod(str(raw)) if raw else ResearchUniverseEntryMethod.UNSPECIFIED
    except ValueError:
        return ResearchUniverseEntryMethod.UNSPECIFIED
