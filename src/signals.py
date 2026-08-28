"""Presentation-neutral, immutable analytical signal contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from src.technical_analysis import TECHNICAL_SCORING_VERSION, technical_setup_score


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    ABSTAIN = "abstain"
    NOT_APPLICABLE = "not_applicable"


class SignalFamily(str, Enum):
    DIRECTIONAL = "directional"
    VOLATILITY = "volatility"


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    ticker: str
    as_of: str
    model_id: str
    model_version: str
    direction: SignalDirection
    conviction: float
    reasoning: str
    confidence: float | None = None
    components: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Appended after every v0.1 field to preserve positional construction compatibility.
    signal_family: SignalFamily = SignalFamily.DIRECTIONAL

    def __post_init__(self) -> None:
        for name in ("signal_id", "ticker", "as_of", "model_id", "model_version", "created_at"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        try:
            family = SignalFamily(self.signal_family)
        except ValueError as error:
            raise ValueError(f"Unsupported signal family: {self.signal_family}") from error
        object.__setattr__(self, "signal_family", family)
        try:
            direction = SignalDirection(self.direction)
        except ValueError as error:
            raise ValueError(f"Unsupported signal direction: {self.direction}") from error
        object.__setattr__(self, "direction", direction)
        if family is SignalFamily.DIRECTIONAL and direction is SignalDirection.NOT_APPLICABLE:
            raise ValueError("directional signals require directional semantics")
        if family is SignalFamily.VOLATILITY and direction is not SignalDirection.NOT_APPLICABLE:
            raise ValueError("volatility signals require direction not_applicable")
        if not isfinite(self.conviction) or not -1.0 <= self.conviction <= 1.0:
            raise ValueError("conviction must be finite and between -1.0 and 1.0")
        if direction is SignalDirection.ABSTAIN and self.conviction != 0.0:
            raise ValueError("abstain signals must use zero conviction")
        if direction is SignalDirection.NEUTRAL and self.conviction != 0.0:
            raise ValueError("neutral signals must use zero conviction")
        if direction is SignalDirection.BULLISH and self.conviction <= 0.0:
            raise ValueError("bullish signals require positive conviction")
        if direction is SignalDirection.BEARISH and self.conviction >= 0.0:
            raise ValueError("bearish signals require negative conviction")
        if direction is SignalDirection.NOT_APPLICABLE and self.conviction != 0.0:
            raise ValueError("not-applicable direction signals must use zero conviction")
        if self.confidence is not None and (
            not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0.0 and 1.0 when supplied")


TAM_SETUP_SIGNAL_MODEL_ID = "technical-setup-score"
TAM_SETUP_SIGNAL_MODEL_VERSION = "technical-setup-signal-v0.1.1"
VOLATILITY_SMOKE_MODEL_ID = "volatility-family-smoke"
VOLATILITY_SMOKE_MODEL_VERSION = "0.1"
VOLATILITY_CONTEXT_MODEL_ID = "volatility-context"
VOLATILITY_CONTEXT_MODEL_VERSION = "volatility-context-v0.1"
TREND_SIGNAL_MAPPING = {
    "bullish_alignment": (SignalDirection.BULLISH, 1.0),
    "constructive": (SignalDirection.BULLISH, 0.5),
    "mixed": (SignalDirection.NEUTRAL, 0.0),
    "deteriorating": (SignalDirection.BEARISH, -0.5),
    "bearish_alignment": (SignalDirection.BEARISH, -1.0),
}


def technical_setup_signal(row: Mapping[str, Any], *, created_at: str | None = None) -> Signal:
    """Translate the existing deterministic TAM score without altering its behavior."""
    ticker = str(row.get("ticker") or "").strip().upper()
    as_of = str(row.get("technical_timestamp") or "").strip()
    score = technical_setup_score(dict(row))
    source_ref = str(row.get("scan_id") or "").strip()
    identity = f"{TAM_SETUP_SIGNAL_MODEL_ID}|{TAM_SETUP_SIGNAL_MODEL_VERSION}|{ticker}|{as_of}|{source_ref}"
    signal_id = str(uuid5(NAMESPACE_URL, identity))
    evidence_refs = (f"technical_characterization:{source_ref}:{ticker}",) if source_ref else ()
    components = {
        key: row.get(key)
        for key in (
            "price_vs_sma_20", "price_vs_sma_50", "price_vs_sma_200",
            "sma_20_vs_sma_50", "sma_50_vs_sma_200", "rsi_14",
            "macd_line", "macd_signal", "macd_histogram", "volatility_state",
        )
    }
    trend_state = str(row.get("trend_state") or "").strip().lower()
    if score is None or trend_state not in TREND_SIGNAL_MAPPING:
        direction, conviction = SignalDirection.ABSTAIN, 0.0
        reasoning = "The existing TAM inputs did not support a directional trend conclusion."
    else:
        direction, conviction = TREND_SIGNAL_MAPPING[trend_state]
        reasoning = (
            f"Existing TAM trend state: {trend_state}; deterministic technical "
            f"setup score: {score:.1f}/100."
        )
    return Signal(
        signal_id=signal_id, ticker=ticker, as_of=as_of,
        model_id=TAM_SETUP_SIGNAL_MODEL_ID, model_version=TAM_SETUP_SIGNAL_MODEL_VERSION,
        direction=direction, conviction=conviction, confidence=None,
        reasoning=reasoning, components=components,
        metadata={
            "source_scan_id": source_ref,
            "source_score": score,
            "source_scoring_version": TECHNICAL_SCORING_VERSION,
            "source_trend_state": trend_state,
        },
        evidence_refs=evidence_refs,
        # The source observation timestamp makes retries byte-for-byte idempotent.
        created_at=created_at or as_of,
    )


def volatility_family_smoke_signal(
    row: Mapping[str, Any], *, created_at: str | None = None
) -> Signal:
    """Prove non-directional plumbing using an existing dated TAM observation.

    This experimental architecture-validation producer makes no forecast and no
    claim of predictive value. It deliberately performs no live-data lookup.
    """
    ticker = str(row.get("ticker") or "").strip().upper()
    as_of = str(row.get("technical_timestamp") or "").strip()
    source_ref = str(row.get("scan_id") or "").strip()
    volatility_state = str(row.get("volatility_state") or "").strip().lower()
    if not ticker or not as_of or not volatility_state:
        raise ValueError("ticker, technical_timestamp, and volatility_state are required")
    identity = (
        f"{VOLATILITY_SMOKE_MODEL_ID}|{VOLATILITY_SMOKE_MODEL_VERSION}|"
        f"{ticker}|{as_of}|{source_ref}"
    )
    return Signal(
        signal_id=str(uuid5(NAMESPACE_URL, identity)), ticker=ticker, as_of=as_of,
        model_id=VOLATILITY_SMOKE_MODEL_ID, model_version=VOLATILITY_SMOKE_MODEL_VERSION,
        direction=SignalDirection.NOT_APPLICABLE, conviction=0.0, confidence=None,
        reasoning=("Architecture-validation observation of the existing point-in-time "
                   f"TAM volatility state: {volatility_state}. No forecast is asserted."),
        signal_family=SignalFamily.VOLATILITY,
        components={"volatility_state": volatility_state},
        metadata={"source_scan_id": source_ref, "experimental": True},
        evidence_refs=(f"technical_characterization:{source_ref}:{ticker}",) if source_ref else (),
        created_at=created_at or as_of,
    )


def volatility_context_signal(row: Mapping[str, Any], *, created_at: str | None = None) -> Signal:
    """Create the production volatility-family Signal from dated history context."""
    ticker = str(row.get("ticker") or "").strip().upper()
    as_of = str(row.get("technical_timestamp") or "").strip()
    source_ref = str(row.get("scan_id") or "").strip()
    payload = row.get("_volatility_context")
    if not ticker or not as_of or not isinstance(payload, Mapping):
        raise ValueError("ticker, technical_timestamp, and volatility context are required")
    components = dict(payload.get("components") or {})
    metadata = dict(payload.get("metadata") or {})
    metadata["source_scan_id"] = source_ref
    identity = f"{VOLATILITY_CONTEXT_MODEL_ID}|{VOLATILITY_CONTEXT_MODEL_VERSION}|{ticker}|{as_of}|{source_ref}"
    regime = metadata.get("regime") or "unavailable"
    trend = metadata.get("volatility_trend") or "unavailable"
    return Signal(
        signal_id=str(uuid5(NAMESPACE_URL, identity)), ticker=ticker, as_of=as_of,
        model_id=VOLATILITY_CONTEXT_MODEL_ID, model_version=VOLATILITY_CONTEXT_MODEL_VERSION,
        signal_family=SignalFamily.VOLATILITY, direction=SignalDirection.NOT_APPLICABLE,
        conviction=0.0, confidence=None,
        reasoning=f"Deterministic volatility context: regime {regime}; trend {trend}.",
        components=components, metadata=metadata,
        evidence_refs=(f"technical_characterization:{source_ref}:{ticker}",) if source_ref else (),
        created_at=created_at or as_of,
    )
