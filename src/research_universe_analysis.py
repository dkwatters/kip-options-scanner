"""Exact Research Universe preflight, execution, and reconciliation contract."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from src.research_universe import IdentityStatus, ResearchUniverseHandoff
from src.study_protocol import RUN_MODE_MANUAL_UI, TAM_STUDY_PROTOCOL
from src.technical_analysis import closing_prices_from_history_payload, technical_analysis_rows_for_symbols
from src.technical_observation_service import archive_technical_observations_and_signals


EASTERN_TIME = ZoneInfo("America/New_York")
_SUPPORTED_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")


class AnalysisMemberStatus(StrEnum):
    READY = "analyzable"
    ANALYZED = "analyzed"
    UNRESOLVED = "unresolved identity"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported identifier"
    NO_MARKET_DATA = "no market data"
    PROVIDER_ERROR = "provider error"
    TECHNICAL_FAILURE = "technical calculation failure"
    NOT_ANALYZED = "intentionally not analyzed"


@dataclass(frozen=True, slots=True)
class AnalysisLedgerEntry:
    matching_key: str
    company_name: str
    ticker_or_identifier: str | None
    identity_status: IdentityStatus
    status: AnalysisMemberStatus
    reason: str


@dataclass(frozen=True, slots=True)
class ResearchUniversePreflight:
    handoff: ResearchUniverseHandoff
    ledger: tuple[AnalysisLedgerEntry, ...]

    @property
    def analyzable_tickers(self) -> tuple[str, ...]:
        return tuple(row.ticker_or_identifier for row in self.ledger if row.status == AnalysisMemberStatus.READY and row.ticker_or_identifier)

    @property
    def blocked(self) -> tuple[AnalysisLedgerEntry, ...]:
        return tuple(row for row in self.ledger if row.status != AnalysisMemberStatus.READY)


@dataclass(frozen=True, slots=True)
class ResearchUniverseAnalysisRun:
    universe_id: str
    universe_version: int
    universe_title: str
    research_question: str
    requested_constituent_count: int
    requested_tickers: tuple[str, ...]
    analyzed_tickers: tuple[str, ...]
    unavailable_tickers: tuple[str, ...]
    timestamp: str
    scan_id: str
    ledger: tuple[AnalysisLedgerEntry, ...]
    signal_persistence_error: str | None = None


def preflight_research_universe(handoff: ResearchUniverseHandoff, client: Any) -> ResearchUniversePreflight:
    """Validate every visible member deterministically and through existing market data."""
    ledger: list[AnalysisLedgerEntry] = []
    end = datetime.now(EASTERN_TIME).date()
    for member in handoff.ordered_members:
        symbol = (member.ticker_or_identifier or "").strip().upper()
        if member.identity_status == IdentityStatus.AMBIGUOUS:
            status, reason = AnalysisMemberStatus.AMBIGUOUS, "Identity is ambiguous."
        elif member.identity_status != IdentityStatus.RESOLVED or not symbol:
            status, reason = AnalysisMemberStatus.UNRESOLVED, "Identity has not been resolved to a security."
        elif not _SUPPORTED_SYMBOL.fullmatch(symbol):
            status, reason = AnalysisMemberStatus.UNSUPPORTED, "Identifier is not recognized as a supported security symbol."
        else:
            try:
                payload = client.get_price_history(symbol, start=(end - timedelta(days=365)).isoformat(), end=end.isoformat())
                if closing_prices_from_history_payload(payload):
                    status, reason = AnalysisMemberStatus.READY, "Market data is available."
                else:
                    status, reason = AnalysisMemberStatus.NO_MARKET_DATA, "No usable daily market data was returned."
            except Exception as error:
                status, reason = AnalysisMemberStatus.PROVIDER_ERROR, f"Provider lookup failed: {error}"
        ledger.append(AnalysisLedgerEntry(member.matching_key, member.company_name, member.ticker_or_identifier, member.identity_status, status, reason))
    if len(ledger) != handoff.total_member_count:
        raise ValueError("Research Universe handoff does not reconcile to total_member_count.")
    return ResearchUniversePreflight(handoff, tuple(ledger))


def execute_research_universe_analysis(preflight: ResearchUniversePreflight, *, client: Any, repository: Any, signal_repository: Any, now: datetime | None = None) -> ResearchUniverseAnalysisRun:
    """Create and archive a new TAM run for exactly the preflight-ready tickers."""
    timestamp = now or datetime.now(EASTERN_TIME)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=EASTERN_TIME)
    formatted = timestamp.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    scan_id = f"research-universe-{timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    requested = preflight.analyzable_tickers
    rows, errors = technical_analysis_rows_for_symbols(client, requested, scan_id=scan_id, technical_timestamp=formatted, end_date=timestamp.date())
    analyzed = tuple(str(row["ticker"]).upper() for row in rows)
    analyzed_set = set(analyzed)
    final: list[AnalysisLedgerEntry] = []
    for entry in preflight.ledger:
        symbol = (entry.ticker_or_identifier or "").upper()
        if entry.status != AnalysisMemberStatus.READY:
            final.append(entry)
        elif symbol in analyzed_set:
            final.append(AnalysisLedgerEntry(entry.matching_key, entry.company_name, entry.ticker_or_identifier, entry.identity_status, AnalysisMemberStatus.ANALYZED, "Technical characterization completed."))
        else:
            final.append(AnalysisLedgerEntry(entry.matching_key, entry.company_name, entry.ticker_or_identifier, entry.identity_status, AnalysisMemberStatus.TECHNICAL_FAILURE, errors.get(symbol, "Technical characterization produced no result.")))
    persistence = archive_technical_observations_and_signals(
        rows,
        archive_observations=lambda persisted_rows: repository.archive_technical_observations(
            scan_id=scan_id, technical_rows=persisted_rows,
            study_protocol=TAM_STUDY_PROTOCOL.metadata(scheduled_time_label=None, run_mode=RUN_MODE_MANUAL_UI),
        ),
        signal_repository=signal_repository,
    )
    if len(final) != preflight.handoff.total_member_count:
        raise ValueError("Analysis ledger does not reconcile to Research Universe membership.")
    return ResearchUniverseAnalysisRun(
        preflight.handoff.universe_id, preflight.handoff.universe_version,
        preflight.handoff.universe_title, preflight.handoff.research_question,
        preflight.handoff.total_member_count, requested, analyzed,
        tuple(
            entry.ticker_or_identifier or entry.company_name
            for entry in final if entry.status != AnalysisMemberStatus.ANALYZED
        ),
        formatted, scan_id, tuple(final), persistence.signal_persistence_error,
    )
