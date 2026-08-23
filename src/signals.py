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

    def __post_init__(self) -> None:
        for name in ("signal_id", "ticker", "as_of", "model_id", "model_version", "created_at"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        try:
            direction = SignalDirection(self.direction)
        except ValueError as error:
            raise ValueError(f"Unsupported signal direction: {self.direction}") from error
        object.__setattr__(self, "direction", direction)
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
        if self.confidence is not None and (
            not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0.0 and 1.0 when supplied")


TAM_SETUP_SIGNAL_MODEL_ID = "technical-setup-score"


def technical_setup_signal(row: Mapping[str, Any], *, created_at: str | None = None) -> Signal:
    """Translate the existing deterministic TAM score without altering its behavior."""
    ticker = str(row.get("ticker") or "").strip().upper()
    as_of = str(row.get("technical_timestamp") or "").strip()
    score = technical_setup_score(dict(row))
    source_ref = str(row.get("scan_id") or "").strip()
    identity = f"{TAM_SETUP_SIGNAL_MODEL_ID}|{TECHNICAL_SCORING_VERSION}|{ticker}|{as_of}|{source_ref}"
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
    if score is None:
        direction, conviction = SignalDirection.ABSTAIN, 0.0
        reasoning = "The existing technical setup score had insufficient inputs."
    else:
        conviction = round((score - 50.0) / 50.0, 3)
        direction = (
            SignalDirection.BULLISH if conviction > 0
            else SignalDirection.BEARISH if conviction < 0
            else SignalDirection.NEUTRAL
        )
        reasoning = f"Existing deterministic technical setup score: {score:.1f}/100."
    return Signal(
        signal_id=signal_id, ticker=ticker, as_of=as_of,
        model_id=TAM_SETUP_SIGNAL_MODEL_ID, model_version=TECHNICAL_SCORING_VERSION,
        direction=direction, conviction=conviction, confidence=None,
        reasoning=reasoning, components=components,
        metadata={"source_scan_id": source_ref, "source_score": score},
        evidence_refs=evidence_refs,
        # The source observation timestamp makes retries byte-for-byte idempotent.
        created_at=created_at or as_of,
    )
