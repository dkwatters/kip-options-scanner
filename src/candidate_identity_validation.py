"""Deterministic, evidence-driven validation for RCE candidate identities."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterable, Mapping, Protocol


CANDIDATE_IDENTITY_VALIDATION_SCHEMA_VERSION = "candidate-identity-validation-result-v0.1"


class CandidateIdentityValidationStatus(StrEnum):
    VALID = "valid"
    CORRECTED = "corrected"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class PublicTradingStatus(StrEnum):
    PUBLICLY_TRADABLE = "publicly_tradable"
    NOT_INDEPENDENTLY_TRADED = "not_independently_traded"
    NOT_PUBLICLY_TRADED = "not_publicly_traded"
    UNKNOWN = "unknown"


class CurrentListingStatus(StrEnum):
    CURRENT = "current"
    ACQUIRED = "acquired"
    DELISTED = "delisted"
    RENAMED = "renamed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CandidateIdentityValidationResultV01:
    candidate_id: str
    raw_company_name: str
    raw_ticker_or_identifier: str | None
    normalized_company_name: str | None
    normalized_ticker_or_identifier: str | None
    validation_status: CandidateIdentityValidationStatus
    correction_applied: bool
    correction_reason: str | None
    authoritative_source: str | None
    source_reference: str | None
    public_trading_status: PublicTradingStatus
    current_listing_status: CurrentListingStatus
    acquisition_rename_delisting_notes: str | None
    validated_at: datetime
    warnings: tuple[str, ...] = ()
    unresolved_reason: str | None = None
    resolution_source: str | None = None
    unresolved_category: str | None = None
    current_security_lookup_attempted: bool = False
    schema_version: str = CANDIDATE_IDENTITY_VALIDATION_SCHEMA_VERSION

    @property
    def promotion_eligible(self) -> bool:
        return self.validation_status in {
            CandidateIdentityValidationStatus.VALID,
            CandidateIdentityValidationStatus.CORRECTED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "raw_company_name": self.raw_company_name,
            "raw_ticker_or_identifier": self.raw_ticker_or_identifier,
            "normalized_company_name": self.normalized_company_name,
            "normalized_ticker_or_identifier": self.normalized_ticker_or_identifier,
            "validation_status": self.validation_status.value,
            "correction_applied": self.correction_applied,
            "correction_reason": self.correction_reason,
            "authoritative_source": self.authoritative_source,
            "source_reference": self.source_reference,
            "public_trading_status": self.public_trading_status.value,
            "current_listing_status": self.current_listing_status.value,
            "acquisition_rename_delisting_notes": self.acquisition_rename_delisting_notes,
            "validated_at": self.validated_at.isoformat(),
            "warnings": list(self.warnings),
            "unresolved_reason": self.unresolved_reason,
            "resolution_source": self.resolution_source,
            "unresolved_category": self.unresolved_category,
            "current_security_lookup_attempted": self.current_security_lookup_attempted,
            "promotion_eligible": self.promotion_eligible,
        }


@dataclass(frozen=True, slots=True)
class SecurityIdentityEvidenceV01:
    company_name: str
    ticker_or_identifier: str | None
    authoritative_source: str
    source_reference: str
    public_trading_status: PublicTradingStatus
    current_listing_status: CurrentListingStatus
    aliases: tuple[str, ...] = ()
    former_tickers: tuple[str, ...] = ()
    notes: str | None = None


class CandidateIdentityEvidenceLookup(Protocol):
    def by_ticker(self, ticker: str) -> tuple[SecurityIdentityEvidenceV01, ...]: ...
    def by_company_name(self, company_name: str) -> tuple[SecurityIdentityEvidenceV01, ...]: ...


_LEGAL_SUFFIXES = {
    "co", "company", "corp", "corporation", "inc", "incorporated", "limited", "ltd",
    "plc", "holdings", "group", "sa", "se", "nv", "ag",
}


def normalized_company_identity(value: str | None) -> str:
    words = re.findall(r"[a-z0-9]+", (value or "").casefold())
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return "".join(words)


def normalized_ticker_identity(value: str | None) -> str | None:
    token = re.sub(r"[^A-Z0-9.-]", "", (value or "").strip().upper())
    return token or None


class InMemoryCandidateIdentityEvidenceLookup:
    """Provider-free lookup used by fixtures and repository-backed catalogs."""

    def __init__(self, evidence: Iterable[SecurityIdentityEvidenceV01] = ()):
        self._evidence = tuple(evidence)

    def by_ticker(self, ticker: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        key = normalized_ticker_identity(ticker)
        return tuple(
            row for row in self._evidence
            if key in {
                normalized_ticker_identity(row.ticker_or_identifier),
                *(normalized_ticker_identity(value) for value in row.former_tickers),
            }
        )

    def by_company_name(self, company_name: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        key = normalized_company_identity(company_name)
        return tuple(
            row for row in self._evidence
            if key in {
                normalized_company_identity(row.company_name),
                *(normalized_company_identity(value) for value in row.aliases),
            }
        )


class CompositeCandidateIdentityEvidenceLookup:
    def __init__(self, *lookups: CandidateIdentityEvidenceLookup):
        self._lookups = lookups

    def by_ticker(self, ticker: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        return _unique_evidence(
            row for lookup in self._lookups for row in lookup.by_ticker(ticker)
        )

    def by_company_name(self, company_name: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        return _unique_evidence(
            row for lookup in self._lookups for row in lookup.by_company_name(company_name)
        )


def _unique_evidence(rows: Iterable[SecurityIdentityEvidenceV01]) -> tuple[SecurityIdentityEvidenceV01, ...]:
    unique: dict[tuple[str, str | None], SecurityIdentityEvidenceV01] = {}
    for row in rows:
        unique.setdefault(
            (normalized_company_identity(row.company_name), normalized_ticker_identity(row.ticker_or_identifier)),
            row,
        )
    return tuple(unique.values())


class MarketDataSecurityEvidenceLookup:
    """Adapt the repository's read-only quote lookup to validation evidence."""

    def __init__(self, market_data: Any):
        self._market_data = market_data

    def by_ticker(self, ticker: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        try:
            payload = self._market_data.get_quote(ticker)
        except Exception:
            return ()
        quotes = payload.get("quotes") if isinstance(payload, Mapping) else None
        quote = quotes.get("quote") if isinstance(quotes, Mapping) else None
        if isinstance(quote, list):
            quote = next((row for row in quote if isinstance(row, Mapping)), None)
        if not isinstance(quote, Mapping):
            return ()
        symbol = normalized_ticker_identity(str(quote.get("symbol") or ""))
        if symbol != normalized_ticker_identity(ticker):
            return ()
        company = str(quote.get("description") or quote.get("name") or "").strip()
        if not company:
            return ()
        return (SecurityIdentityEvidenceV01(
            company_name=company,
            ticker_or_identifier=symbol,
            authoritative_source="configured market-data security lookup",
            source_reference=f"market-data:quote:{symbol}",
            public_trading_status=PublicTradingStatus.PUBLICLY_TRADABLE,
            current_listing_status=CurrentListingStatus.CURRENT,
            notes="Current symbol and description resolved by the configured quote provider.",
        ),)

    def by_company_name(self, company_name: str) -> tuple[SecurityIdentityEvidenceV01, ...]:
        return ()


class CandidateIdentityValidatorV01:
    """Validate without fuzzy matching or unsupported inference."""

    def __init__(
        self,
        lookup: CandidateIdentityEvidenceLookup | None = None,
        *,
        current_security_lookup: CandidateIdentityEvidenceLookup | None = None,
        authoritative_lookup: CandidateIdentityEvidenceLookup | None = None,
        clock=lambda: datetime.now(timezone.utc),
    ):
        # ``lookup`` remains the deterministic authoritative-fixture argument used
        # by v0.1 callers. Production current-quote lookup is explicit so that
        # current quote evidence cannot mask acquisition/delisting evidence.
        self._has_current_security_lookup = current_security_lookup is not None
        self._current_security_lookup = (
            current_security_lookup or InMemoryCandidateIdentityEvidenceLookup()
        )
        self._authoritative_lookup = (
            authoritative_lookup or lookup or InMemoryCandidateIdentityEvidenceLookup()
        )
        self._clock = clock

    def validate(
        self,
        *,
        candidate_id: str,
        company_name: str,
        ticker_or_identifier: str | None,
    ) -> CandidateIdentityValidationResultV01:
        raw_ticker = normalized_ticker_identity(ticker_or_identifier)
        current_ticker_matches = (
            self._current_security_lookup.by_ticker(raw_ticker) if raw_ticker else ()
        )
        authoritative_ticker_matches = (
            self._authoritative_lookup.by_ticker(raw_ticker) if raw_ticker else ()
        )
        authoritative_company_matches = self._authoritative_lookup.by_company_name(company_name)
        authoritative_exact = self._matching_company(
            authoritative_ticker_matches, company_name
        )

        # Lifecycle evidence is controlling. A stale symbol returned by a quote
        # provider must not turn an acquired or delisted entity into a valid one.
        if len(authoritative_exact) == 1:
            row = authoritative_exact[0]
            if row.public_trading_status != PublicTradingStatus.PUBLICLY_TRADABLE:
                return self._result(
                    candidate_id, company_name, raw_ticker, row,
                    CandidateIdentityValidationStatus.REJECTED,
                    resolution_source="authoritative_evidence",
                )
            corrected = raw_ticker != normalized_ticker_identity(row.ticker_or_identifier)
            return self._result(
                candidate_id, company_name, raw_ticker, row,
                CandidateIdentityValidationStatus.CORRECTED if corrected else CandidateIdentityValidationStatus.VALID,
                correction_reason=(
                    "Authoritative evidence maps the former ticker to the current listing."
                    if corrected else None
                ),
                resolution_source="authoritative_evidence",
            )

        current_exact = self._matching_company(current_ticker_matches, company_name)
        if len(current_exact) == 1:
            return self._result(
                candidate_id, company_name, raw_ticker, current_exact[0],
                CandidateIdentityValidationStatus.VALID,
                resolution_source="current_security_lookup",
            )

        if len(authoritative_company_matches) == 1:
            row = authoritative_company_matches[0]
            if row.public_trading_status != PublicTradingStatus.PUBLICLY_TRADABLE:
                return self._result(
                    candidate_id, company_name, raw_ticker, row,
                    CandidateIdentityValidationStatus.REJECTED,
                    resolution_source="authoritative_evidence",
                )
            return self._result(
                candidate_id, company_name, raw_ticker, row,
                CandidateIdentityValidationStatus.CORRECTED,
                correction_reason=(
                    "A unique authoritative company-name match resolved a different current ticker."
                ),
                warnings=(
                    f"Raw ticker {raw_ticker} resolves to a materially different identity."
                    if current_ticker_matches or authoritative_ticker_matches
                    else f"Raw ticker {raw_ticker or 'was absent'} did not resolve to this company.",
                ),
                resolution_source="authoritative_evidence",
            )
        reason = (
            "Multiple authoritative company identities match the supplied name."
            if len(authoritative_company_matches) > 1
            else "Ticker and company identity could not be established from available authoritative evidence."
        )
        warnings = ()
        category = "no_authoritative_mapping"
        if (
            current_ticker_matches or authoritative_ticker_matches
        ) and not current_exact and not authoritative_exact:
            reason = "Ticker resolves, but its company identity conflicts materially with the supplied company name."
            warnings = ("No correction was applied because a unique authoritative company mapping was unavailable.",)
            category = "identity_conflict"
        return CandidateIdentityValidationResultV01(
            candidate_id=candidate_id,
            raw_company_name=company_name,
            raw_ticker_or_identifier=raw_ticker,
            normalized_company_name=None,
            normalized_ticker_or_identifier=None,
            validation_status=CandidateIdentityValidationStatus.UNRESOLVED,
            correction_applied=False,
            correction_reason=None,
            authoritative_source=None,
            source_reference=None,
            public_trading_status=PublicTradingStatus.UNKNOWN,
            current_listing_status=CurrentListingStatus.UNKNOWN,
            acquisition_rename_delisting_notes=None,
            validated_at=self._clock(),
            warnings=warnings,
            unresolved_reason=reason,
            unresolved_category=category,
            current_security_lookup_attempted=bool(
                raw_ticker and self._has_current_security_lookup
            ),
        )

    @staticmethod
    def _matching_company(
        rows: Iterable[SecurityIdentityEvidenceV01],
        company_name: str,
    ) -> tuple[SecurityIdentityEvidenceV01, ...]:
        candidate_key = normalized_company_identity(company_name)
        return tuple(
            row for row in rows
            if candidate_key in {
                normalized_company_identity(row.company_name),
                *(normalized_company_identity(value) for value in row.aliases),
            }
        )

    def _result(
        self,
        candidate_id: str,
        company_name: str,
        raw_ticker: str | None,
        evidence: SecurityIdentityEvidenceV01,
        status: CandidateIdentityValidationStatus,
        *,
        correction_reason: str | None = None,
        warnings: tuple[str, ...] = (),
        unresolved_reason: str | None = None,
        resolution_source: str | None = None,
    ) -> CandidateIdentityValidationResultV01:
        normalized_ticker = normalized_ticker_identity(evidence.ticker_or_identifier)
        correction = status == CandidateIdentityValidationStatus.CORRECTED
        return CandidateIdentityValidationResultV01(
            candidate_id=candidate_id,
            raw_company_name=company_name,
            raw_ticker_or_identifier=raw_ticker,
            normalized_company_name=evidence.company_name,
            normalized_ticker_or_identifier=normalized_ticker,
            validation_status=status,
            correction_applied=correction,
            correction_reason=correction_reason,
            authoritative_source=evidence.authoritative_source,
            source_reference=evidence.source_reference,
            public_trading_status=evidence.public_trading_status,
            current_listing_status=evidence.current_listing_status,
            acquisition_rename_delisting_notes=evidence.notes,
            validated_at=self._clock(),
            warnings=warnings,
            unresolved_reason=unresolved_reason,
            resolution_source=resolution_source,
            current_security_lookup_attempted=bool(
                raw_ticker and self._has_current_security_lookup
            ),
        )


def evidence_from_mapping(row: Mapping[str, Any]) -> SecurityIdentityEvidenceV01:
    return SecurityIdentityEvidenceV01(
        company_name=str(row["company_name"]),
        ticker_or_identifier=row.get("ticker_or_identifier"),
        authoritative_source=str(row["authoritative_source"]),
        source_reference=str(row["source_reference"]),
        public_trading_status=PublicTradingStatus(row["public_trading_status"]),
        current_listing_status=CurrentListingStatus(row["current_listing_status"]),
        aliases=tuple(row.get("aliases", ())),
        former_tickers=tuple(row.get("former_tickers", ())),
        notes=row.get("notes"),
    )
