"""Shared ticker-only input and deterministic identity resolution."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol

from src.research_universe import IdentityStatus, UniverseSource, UniverseSourceRecord, source_record


_TICKER = re.compile(r"^[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,4})?$")


class SecurityLookup(Protocol):
    def get_quote(self, symbol: str) -> Mapping: ...


@dataclass(frozen=True, slots=True)
class TickerInput:
    original_input: str
    ticker: str


@dataclass(frozen=True, slots=True)
class TickerInputResult:
    entries: tuple[TickerInput, ...]
    invalid_values: tuple[str, ...]


def parse_ticker_input(raw: str) -> TickerInputResult:
    """Parse CSV/newline ticker input without guessing company names."""
    entries: list[TickerInput] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for value in re.split(r"[,\r\n]+", raw or ""):
        supplied = " ".join(value.split())
        if not supplied:
            continue
        ticker = supplied.upper()
        if not _TICKER.fullmatch(ticker):
            invalid.append(supplied)
            continue
        if ticker in seen:
            continue
        seen.add(ticker)
        entries.append(TickerInput(supplied, ticker))
    return TickerInputResult(tuple(entries), tuple(dict.fromkeys(invalid)))


def _record_tickers(record: UniverseSourceRecord) -> tuple[str, ...]:
    return tuple(
        token for token in re.split(r"[/,]", (record.ticker_or_identifier or "").upper())
        if token
    )


def _quote_identity(payload: Mapping, ticker: str) -> tuple[str, str] | None:
    quotes = payload.get("quotes") if isinstance(payload, Mapping) else None
    quote = quotes.get("quote") if isinstance(quotes, Mapping) else None
    if isinstance(quote, list):
        quote = next((row for row in quote if isinstance(row, Mapping)), None)
    if not isinstance(quote, Mapping):
        return None
    symbol = str(quote.get("symbol") or "").strip().upper()
    if symbol != ticker:
        return None
    name = str(quote.get("description") or quote.get("name") or ticker).strip()
    return name or ticker, symbol


class ResearchUniverseInputService:
    """Create explicit membership records through one parser/resolver pipeline."""

    def __init__(self, market_data: SecurityLookup | None = None):
        self._market_data = market_data

    def resolve(
        self,
        raw: str,
        *,
        source_reference: str,
        known_records: Iterable[UniverseSourceRecord] = (),
    ) -> tuple[TickerInputResult, tuple[UniverseSourceRecord, ...]]:
        parsed = parse_ticker_input(raw)
        known_by_ticker: dict[str, UniverseSourceRecord] = {}
        for record in known_records:
            if record.identity_status != IdentityStatus.RESOLVED:
                continue
            for ticker in _record_tickers(record):
                known_by_ticker.setdefault(ticker, record)

        records: list[UniverseSourceRecord] = []
        for entry in parsed.entries:
            known = known_by_ticker.get(entry.ticker)
            company_name = known.company_name if known else entry.ticker
            identity_status = IdentityStatus.RESOLVED if known else IdentityStatus.UNRESOLVED
            metadata = {
                "identity_resolution": "canonical_metadata" if known else "unresolved",
                "identity_diagnostic": (
                    "matched_resolved_record" if known else "ticker_not_yet_validated"
                ),
            }
            if known is None and self._market_data is not None:
                try:
                    quote = _quote_identity(self._market_data.get_quote(entry.ticker), entry.ticker)
                except Exception as error:
                    quote = None
                    metadata["identity_diagnostic"] = f"market_data_error:{type(error).__name__}"
                if quote:
                    company_name, _ = quote
                    identity_status = IdentityStatus.RESOLVED
                    metadata["identity_resolution"] = "market_data"
                    metadata["identity_diagnostic"] = "market_data_symbol_confirmed"
                elif not metadata["identity_diagnostic"].startswith("market_data_error:"):
                    metadata["identity_diagnostic"] = "market_data_symbol_not_confirmed"
            records.append(source_record(
                {
                    "company_name": company_name,
                    "ticker": entry.ticker,
                    "supplied_value": entry.original_input,
                    "identity_status": identity_status.value,
                    **metadata,
                },
                UniverseSource.USER_ENTERED,
                source_reference=source_reference,
            ))
        return parsed, tuple(records)


def configured_research_universe_input_service() -> ResearchUniverseInputService:
    """Use the existing read-only market-data resolver only when configured."""
    try:
        from src.tradier_client import TradierClient

        return ResearchUniverseInputService(TradierClient())
    except Exception:
        return ResearchUniverseInputService()
